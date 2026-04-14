"""
CJ Tech — Scraper Vinted
Récupère les annonces du profil Vinted et génère produits.json

Usage :
    pip install requests
    python scrape_vinted.py

Le fichier produits.json est mis à jour automatiquement.
"""

import json
import sys
import time
import requests

# ── CONFIG ──────────────────────────────────────────────────────────────────
VINTED_USER_ID  = "49189698"          # ton ID Vinted (visible dans l'URL du profil)
LBC_PROFILE_URL = "https://www.leboncoin.fr/profile/4555ce52-c61b-4f81-9fb8-c66f889a5e4e/offers"
OUTPUT_FILE     = "produits.json"
PER_PAGE        = 20                  # annonces à récupérer
# ────────────────────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Referer": f"https://www.vinted.fr/member/{VINTED_USER_ID}",
    "Origin": "https://www.vinted.fr",
}

# Catégories GPU reconnues (pour le filtre du site)
GPU_MAP = {
    "rx 580":    "580",
    "rx580":     "580",
    "rx 5700 xt":"5700xt",
    "rx5700xt":  "5700xt",
    "rx 6500 xt":"6500xt",
    "rx6500xt":  "6500xt",
    "rtx 3060":  "3060",
    "rtx 3070":  "3070",
    "rtx 3080":  "3080",
    "rtx 4060":  "4060",
    "gtx 1660":  "1660",
    "1660 ti":   "1660ti",
    "1660 super":"1660super",
}

def detect_gpu(text: str) -> str:
    text_lower = text.lower()
    for key, val in GPU_MAP.items():
        if key in text_lower:
            return val
    return "autre"


def fetch_vinted_items() -> list[dict]:
    url = (
        f"https://www.vinted.fr/api/v2/users/{VINTED_USER_ID}/items"
        f"?page=1&per_page={PER_PAGE}&order=relevance"
    )
    print(f"[Vinted] Requête : {url}")

    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
    except requests.HTTPError as e:
        print(f"[Vinted] Erreur HTTP {r.status_code} : {e}")
        if r.status_code == 401:
            print("  → L'API demande une authentification.")
            print("  → Lance le script avec cookies (voir README) ou utilise le mode manuel.")
        return []
    except requests.RequestException as e:
        print(f"[Vinted] Erreur réseau : {e}")
        return []

    data = r.json()
    raw_items = data.get("items", [])
    print(f"[Vinted] {len(raw_items)} annonce(s) trouvée(s)")

    produits = []
    for item in raw_items:
        # Prix
        price_obj = item.get("price", {})
        prix = float(price_obj.get("amount", 0))

        # Photos
        photos = item.get("photos", [])
        image_url = ""
        if photos:
            image_url = photos[0].get("url", photos[0].get("full_size_url", ""))

        # Titre + description
        titre      = item.get("title", "")
        description = item.get("description", "")
        texte_complet = f"{titre} {description}"

        # Statut vendu
        status = item.get("status", "")
        vendu  = status in ("sold_out", "hidden", "reserved")

        # URL annonce
        url_annonce = item.get("url", f"https://www.vinted.fr/items/{item.get('id', '')}")

        produit = {
            "id":          item.get("id"),
            "nom":         titre,
            "gpu":         detect_gpu(texte_complet),
            "prix":        int(prix),
            "image":       image_url,
            "specs":       [],          # à remplir manuellement ou via description
            "note":        "",          # ex : "Silencieux & stable"
            "vinted":      url_annonce,
            "leboncoin":   LBC_PROFILE_URL,
            "vendu":       vendu,
            "source":      "vinted",
        }

        # Extraire des specs basiques depuis la description
        specs = []
        desc_lower = description.lower()
        if "ssd" in desc_lower:
            specs.append("SSD inclus")
        if "windows 11" in desc_lower or "win 11" in desc_lower:
            specs.append("Windows 11 prêt à l'emploi")
        if "nvme" in desc_lower:
            specs.append("SSD NVMe")
        if "16 go" in desc_lower or "16go" in desc_lower:
            specs.append("16 Go RAM")
        if specs:
            produit["specs"] = specs

        produits.append(produit)
        time.sleep(0.3)   # petit délai poli

    return produits


def main():
    print("=" * 50)
    print("  CJ Tech — Scraper Vinted")
    print("=" * 50)

    produits = fetch_vinted_items()

    if not produits:
        print("\nAucun produit récupéré. Vérifie ta connexion ou les cookies.")
        sys.exit(1)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(produits, f, ensure_ascii=False, indent=2)

    dispo = sum(1 for p in produits if not p["vendu"])
    vendu = sum(1 for p in produits if p["vendu"])
    print(f"\n[OK] {OUTPUT_FILE} mis à jour :")
    print(f"     {dispo} disponible(s) — {vendu} vendu(s)")
    print("\nProchaine étape : déploie ton site pour mettre les annonces à jour.")


if __name__ == "__main__":
    main()
