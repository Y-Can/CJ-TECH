"""
CJ Tech — Scraper Vinted (Playwright)
Récupère les annonces du profil Vinted via un navigateur headless et génère produits.json
"""

import json
import re
import sys
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# ── CONFIG ──────────────────────────────────────────────────────────────────
VINTED_USER_ID     = "49189698"
VINTED_PROFILE_URL = f"https://www.vinted.fr/member/{VINTED_USER_ID}"
LBC_PROFILE_URL    = "https://www.leboncoin.fr/profile/4555ce52-c61b-4f81-9fb8-c66f889a5e4e/offers"
OUTPUT_FILE        = "produits.json"
# ────────────────────────────────────────────────────────────────────────────

GPU_MAP = {
    "rx 580":     "580",
    "rx580":      "580",
    "rx 5700 xt": "5700xt",
    "rx5700xt":   "5700xt",
    "5700 xt":    "5700xt",
    "5700xt":     "5700xt",
    "rx 6500 xt": "6500xt",
    "rx6500xt":   "6500xt",
    "6500 xt":    "6500xt",
    "6500xt":     "6500xt",
    "rtx 3060":   "3060",
    "rtx 3070":   "3070",
    "rtx 3080":   "3080",
    "rtx 4060":   "4060",
    "gtx 1660":   "1660",
    "1660 ti":    "1660ti",
    "1660 super": "1660super",
}


def detect_gpu(text: str) -> str:
    text_lower = text.lower()
    for key, val in GPU_MAP.items():
        if key in text_lower:
            return val
    return "autre"


def parse_price(price_text: str) -> int:
    cleaned = price_text.replace("\xa0", "").replace("€", "").replace(",", ".").strip()
    try:
        return int(float(cleaned))
    except ValueError:
        return 0


def fetch_vinted_items() -> list[dict]:
    print(f"[Vinted] Chargement de la page : {VINTED_PROFILE_URL}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page.goto(VINTED_PROFILE_URL, wait_until="networkidle", timeout=30000)

        try:
            page.wait_for_selector('[data-testid^="product-item-id-"]', timeout=15000)
        except PlaywrightTimeout:
            print("[Vinted] Timeout : aucun produit apparu dans la page.")
            browser.close()
            return []

        html = page.content()
        browser.close()

    soup = BeautifulSoup(html, "html.parser")
    containers = soup.find_all(
        "div",
        attrs={"data-testid": re.compile(r"^product-item-id-\d+$")}
    )
    print(f"[Vinted] {len(containers)} annonce(s) trouvée(s)")

    produits = []
    for container in containers:
        item_id = container["data-testid"].replace("product-item-id-", "")

        img_tag   = container.find("img", attrs={"data-testid": f"product-item-id-{item_id}--image--img"})
        image_url = img_tag["src"] if img_tag else ""
        alt_text  = img_tag.get("alt", "") if img_tag else ""
        titre     = alt_text.split(",")[0].strip() if alt_text else f"PC Gaming #{item_id}"

        price_tag = container.find("p", attrs={"data-testid": f"product-item-id-{item_id}--price-text"})
        prix      = parse_price(price_tag.get_text()) if price_tag else 0

        status_tag = container.find("p", attrs={"data-testid": f"product-item-id-{item_id}--status-text"})
        vendu      = status_tag is not None and "vendu" in status_tag.get_text().lower()

        link_tag    = container.find("a", attrs={"data-testid": f"product-item-id-{item_id}--overlay-link"})
        url_annonce = (
            f"https://www.vinted.fr{link_tag['href']}"
            if link_tag
            else f"https://www.vinted.fr/items/{item_id}"
        )

        produits.append({
            "id":        int(item_id),
            "nom":       titre,
            "gpu":       detect_gpu(titre),
            "prix":      prix,
            "image":     image_url,
            "specs":     [],
            "note":      "",
            "vinted":    url_annonce,
            "leboncoin": LBC_PROFILE_URL,
            "vendu":     vendu,
            "source":    "vinted-html",
        })

    return produits


def main():
    print("=" * 50)
    print("  CJ Tech — Scraper Vinted")
    print("=" * 50)

    produits = fetch_vinted_items()

    if not produits:
        print("\nAucun produit récupéré.")
        sys.exit(1)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(produits, f, ensure_ascii=False, indent=2)

    dispo = sum(1 for p in produits if not p["vendu"])
    vendu = sum(1 for p in produits if p["vendu"])
    print(f"\n[OK] {OUTPUT_FILE} mis à jour :")
    print(f"     {dispo} disponible(s) — {vendu} vendu(s)")


if __name__ == "__main__":
    main()
