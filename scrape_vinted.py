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
VINTED_FEEDBACK_URL = f"https://www.vinted.fr/member/{VINTED_USER_ID}/feedback"
LBC_PROFILE_URL    = "https://www.leboncoin.fr/profile/4555ce52-c61b-4f81-9fb8-c66f889a5e4e/offers"
OUTPUT_FILE        = "produits.json"
REVIEWS_FILE       = "avis.json"
USER_AGENT         = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
# ────────────────────────────────────────────────────────────────────────────

# Mots-clés pour détecter si un avis concerne un PC
PC_REVIEW_KEYWORDS = [
    "pc", "gamer", "gaming", "ordinateur", "tour",
    "ryzen", "processeur", "rx ", "rtx", "gtx", "gpu",
    "ram", "ssd", "windows", "fps", "fortnite", "warzone", "gta",
]

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

# Mots-clés pour la détection de catégorie (ordre de priorité : pc > composant > peripherique)
CATEGORY_PC_KEYWORDS = [
    "pc gamer", "pc gaming", "ordinateur gamer", "tour gamer", "setup gaming",
]
CATEGORY_COMPOSANT_KEYWORDS = [
    "processeur", "cpu", "carte graphique", "carte mere", "carte mère",
    "alimentation atx", "ventirad", "boitier pc", "boîtier pc",
    "ram ddr", "ddr4", "ddr5", "disque dur", "nvme m.2",
]
CATEGORY_PERIPHERIQUE_KEYWORDS = [
    "souris gamer", "clavier gamer", "casque gamer", "microphone", "webcam",
    "tapis de souris", "manette", "ecran gamer", "moniteur gamer",
    "souris gaming", "clavier gaming", "casque gaming",
]


def detect_gpu(text: str) -> str:
    text_lower = text.lower()
    for key, val in GPU_MAP.items():
        if key in text_lower:
            return val
    return "autre"


def detect_category(text: str) -> str:
    text_lower = text.lower()
    for kw in CATEGORY_PC_KEYWORDS:
        if kw in text_lower:
            return "pc"
    for kw in CATEGORY_COMPOSANT_KEYWORDS:
        if kw in text_lower:
            return "composant"
    for kw in CATEGORY_PERIPHERIQUE_KEYWORDS:
        if kw in text_lower:
            return "peripherique"
    return "autre"


def parse_price(price_text: str) -> int:
    cleaned = price_text.replace("\xa0", "").replace("€", "").replace(",", ".").strip()
    try:
        return int(float(cleaned))
    except ValueError:
        return 0


def is_pc_related(text: str) -> bool:
    """Retourne True si le texte contient des mots-clés liés aux PCs."""
    t = text.lower()
    return any(kw in t for kw in PC_REVIEW_KEYWORDS)


def fetch_vinted_feedback() -> list[dict]:
    """
    Récupère les avis vendeur depuis la page de feedback Vinted.
    Utilise l'interception des appels API internes de Vinted (plus fiable que le parsing HTML).
    Ne conserve que les avis dont le commentaire ou l'article concerné est lié à un PC.
    """
    print(f"[Vinted] Chargement des avis : {VINTED_FEEDBACK_URL}")
    raw_feedbacks: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=USER_AGENT)

        # Intercepter les réponses de l'API interne Vinted pour le feedback
        def on_response(resp):
            if (
                f"/api/v2/users/{VINTED_USER_ID}/feedback" in resp.url
                and resp.status == 200
            ):
                try:
                    data = resp.json()
                    batch = data.get("feedbacks", [])
                    if batch:
                        raw_feedbacks.extend(batch)
                        print(f"[API] {len(batch)} avis intercepté(s) — total : {len(raw_feedbacks)}")
                except Exception:
                    pass

        page.on("response", on_response)
        page.goto(VINTED_FEEDBACK_URL, wait_until="networkidle", timeout=30000)

        # Scroll pour déclencher d'éventuelles pages suivantes (pagination infinie)
        for _ in range(4):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1200)

        browser.close()

    if not raw_feedbacks:
        print("[Vinted] Aucun avis récupéré via l'API Vinted.")
        return []

    avis: list[dict] = []
    for fb in raw_feedbacks:
        item_info  = fb.get("item") or {}
        item_title = item_info.get("title", "")
        comment    = (fb.get("body") or "").strip()
        rating     = fb.get("rating", 5)
        date_str   = (fb.get("created_at") or "")[:10]   # "YYYY-MM-DD"
        buyer      = (fb.get("user") or {}).get("login", "Acheteur")

        # Filtrer : ne garder que ce qui concerne les PCs
        if not is_pc_related(comment) and not is_pc_related(item_title):
            continue

        avis.append({
            "id":          fb.get("id"),
            "note":        rating,          # 1 à 5
            "commentaire": comment,
            "article":     item_title,
            "acheteur":    buyer,
            "date":        date_str,
        })

    print(f"[Vinted] {len(avis)} avis PC conservé(s) sur {len(raw_feedbacks)} total")
    return avis


def fetch_vinted_items() -> list[dict]:
    print(f"[Vinted] Chargement de la page : {VINTED_PROFILE_URL}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=USER_AGENT)
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
            "categorie": detect_category(titre),
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

    # ── 1. Annonces ──────────────────────────────────────────────────────────
    produits = fetch_vinted_items()

    if not produits:
        print("\nAucun produit récupéré.")
        sys.exit(1)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(produits, f, ensure_ascii=False, indent=2)

    dispo = sum(1 for p in produits if not p["vendu"])
    vendu = sum(1 for p in produits if p["vendu"])
    print(f"\n[OK] {OUTPUT_FILE} mis à jour : {dispo} disponible(s) — {vendu} vendu(s)")

    # ── 2. Avis clients ──────────────────────────────────────────────────────
    print()
    avis = fetch_vinted_feedback()
    with open(REVIEWS_FILE, "w", encoding="utf-8") as f:
        json.dump(avis, f, ensure_ascii=False, indent=2)
    print(f"[OK] {REVIEWS_FILE} mis à jour : {len(avis)} avis")


if __name__ == "__main__":
    main()
