"""One-shot : crée les 3 Products + 6 Prices FinSight sur Stripe via API.

Usage (après avoir créé le compte Stripe et mis la clé sk_test_... en env) :

    export STRIPE_SECRET_KEY="sk_test_..."
    python tools/stripe_setup.py

Sortie : imprime les JSON STRIPE_PRICE_IDS + STRIPE_PRICE_MAP à coller dans
Railway env vars. Webhook endpoint à configurer manuellement dans le dashboard.

Plans :
  - Plan Découverte : 34,99€ mensuel | 336€ annuel (-20%)
  - Plan Pro        : 44,99€ mensuel | 432€ annuel (-20%)
  - Plan Enterprise : 299€ mensuel | 2870€ annuel (custom negotiable 499€/mois)
"""
from __future__ import annotations

import io
import json
import os
import sys

# Force UTF-8 output sur Windows cp1252
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

try:
    import stripe
except ImportError:
    print("pip install stripe")
    sys.exit(1)

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
if not stripe.api_key:
    print("STRIPE_SECRET_KEY manquante en env")
    sys.exit(1)

# (plan_slug, name, monthly_eur, annual_eur, description)
PLANS = [
    ("decouverte", "FinSight Plan Découverte",
     34.99, 336.00,
     "Analyse société + secteur + indice, livrables PDF/PPTX/XLSX, jusqu'à X analyses/mois"),
    ("pro", "FinSight Plan Pro",
     44.99, 432.00,
     "Tout Découverte + PME non cotées, portraits, comparatifs, i18n 6 langues"),
    ("enterprise", "FinSight Plan Enterprise",
     299.00, 2870.00,
     "API access, white-label, team seats, dedicated support, custom integrations"),
]


def upsert_product_price(plan_slug: str, name: str, amount_eur: float,
                          interval: str, description: str) -> dict:
    # Idempotent via lookup_key
    lookup_key = f"finsight_{plan_slug}_{interval}"

    # Chercher price existant par lookup_key
    existing = stripe.Price.list(lookup_keys=[lookup_key], limit=1)
    if existing.data:
        p = existing.data[0]
        print(f"  ✓ {lookup_key} déjà existe ({p.id})")
        return {"price_id": p.id, "product_id": p.product}

    # Créer product (ou récup)
    products = stripe.Product.list(limit=100)
    prod = next((pr for pr in products.data if pr.name == name), None)
    if not prod:
        prod = stripe.Product.create(
            name=name,
            description=description,
            metadata={"plan": plan_slug},
        )
        print(f"  + Product créé : {prod.id} ({name})")
    else:
        print(f"  = Product existant : {prod.id} ({name})")

    # Créer price
    price = stripe.Price.create(
        product=prod.id,
        unit_amount=int(amount_eur * 100),
        currency="eur",
        recurring={"interval": interval},
        lookup_key=lookup_key,
        nickname=f"{plan_slug.capitalize()} — {interval}",
        metadata={"plan": plan_slug, "interval": interval},
    )
    print(f"  + Price créé : {price.id} ({amount_eur}€/{interval})")
    return {"price_id": price.id, "product_id": prod.id}


def main() -> int:
    print("=== FinSight Stripe setup ===")
    print(f"Account: {stripe.api_key[:12]}...\n")

    STRIPE_PRICE_IDS: dict[str, str] = {}
    STRIPE_PRICE_MAP: dict[str, str] = {}

    for slug, name, monthly, annual, desc in PLANS:
        print(f"\n→ {slug}")
        # Monthly
        m = upsert_product_price(slug, name, monthly, "month", desc)
        STRIPE_PRICE_IDS[f"{slug}_month"] = m["price_id"]
        STRIPE_PRICE_MAP[m["price_id"]] = slug
        # Annual (-20%)
        a = upsert_product_price(slug, name, annual, "year", desc)
        STRIPE_PRICE_IDS[f"{slug}_year"] = a["price_id"]
        STRIPE_PRICE_MAP[a["price_id"]] = slug

    print("\n" + "=" * 60)
    print("À copier dans Railway → Variables :")
    print("=" * 60)
    print(f"\nSTRIPE_PRICE_IDS={json.dumps(STRIPE_PRICE_IDS)}")
    print(f"\nSTRIPE_PRICE_MAP={json.dumps(STRIPE_PRICE_MAP)}")
    print("\n(N'oublie pas STRIPE_SECRET_KEY + STRIPE_WEBHOOK_SECRET)\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
