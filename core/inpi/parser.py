"""Parse une réponse API INPI RNE vers PappersCompany (adapter).

L'objectif est que le pipeline PME existant (SIG + ratios + benchmark + scoring)
puisse consommer des données INPI sans modification — on mime le format Pappers.

Mapping INPI → PappersCompany :
- identite.denomination → denomination
- formality.content.natureCreation.formeJuridique.libelle → forme_juridique
- formality.content.personneMorale.entreprise.codeActivitePrincipale → code_naf
- formality.content.natureCreation.dateCreation → date_creation
- formality.content.personneMorale.entreprise.capital.montant → capital
- formality.content.personneMorale.adresseEntreprise.adresse.commune → ville_siege
- formality.content.personneMorale.composition.pouvoirs → dirigeants

Note : INPI ne publie PAS systématiquement les comptes annuels. Ils sont
disponibles seulement si l'entreprise les a déposés publiquement et n'a pas
demandé la confidentialité. Pour les PME qui publient, on parse via
bilansSaisis / comptes associés.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

log = logging.getLogger(__name__)


def _get(obj: Any, path: str, default: Any = None) -> Any:
    """Accès sécurisé dict.nested.path."""
    cur = obj
    for key in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(key)
        elif isinstance(cur, list) and key.isdigit():
            idx = int(key)
            cur = cur[idx] if len(cur) > idx else None
        else:
            return default
        if cur is None:
            return default
    return cur if cur is not None else default


def parse_inpi_to_pappers(raw: dict) -> Optional[Any]:
    """Convertit une réponse INPI RNE en PappersCompany (même structure).

    Retourne None si données illisibles.
    """
    try:
        from core.pappers.client import PappersCompany
    except ImportError:
        log.error("[inpi.parser] PappersCompany indisponible")
        return None

    if not isinstance(raw, dict):
        return None

    formality = raw.get("formality") or {}
    content = formality.get("content") or {}
    siren = formality.get("siren") or ""
    pm = content.get("personneMorale") or {}
    entreprise = pm.get("entreprise") or {}
    identite_pm = pm.get("identite") or {}
    entite = identite_pm.get("entreprise") or {}
    adresse_ent = pm.get("adresseEntreprise") or {}
    adr = adresse_ent.get("adresse") or {}
    nature_creation = content.get("natureCreation") or {}
    forme_jur = nature_creation.get("formeJuridique") or {}
    if isinstance(forme_jur, dict):
        forme_jur_lbl = forme_jur.get("libelle") or forme_jur.get("code")
    else:
        forme_jur_lbl = str(forme_jur) if forme_jur else None

    # Dénomination
    denom = (
        entite.get("denomination")
        or entreprise.get("denomination")
        or identite_pm.get("denomination")
        or ""
    )

    # Code NAF / activité
    code_naf = (
        entreprise.get("codeApe")
        or entreprise.get("codeActivitePrincipale")
        or entite.get("codeApe")
    )
    libelle_naf = entreprise.get("activitePrincipale") or entite.get("activitePrincipale")

    # Capital
    capital_bloc = entreprise.get("capital") or entite.get("capital") or {}
    capital = None
    if isinstance(capital_bloc, dict):
        montant = capital_bloc.get("montant")
        try:
            capital = float(montant) if montant is not None else None
        except (TypeError, ValueError):
            pass

    # Date création
    date_creation = nature_creation.get("dateCreation") or entreprise.get("dateImmat")

    # Ville siège
    ville_siege = adr.get("commune") or adr.get("libelleCommune")
    departement = adr.get("codePostal", "")[:2] if adr.get("codePostal") else None

    # Dirigeants
    dirigeants: list[dict] = []
    composition = pm.get("composition") or {}
    pouvoirs = composition.get("pouvoirs") or []
    for p in pouvoirs[:15]:
        if not isinstance(p, dict):
            continue
        ind = p.get("individu") or {}
        desc = ind.get("descriptionPersonne") or {}
        role = p.get("roleEntreprise") or p.get("role")
        if isinstance(role, dict):
            role_lbl = role.get("libelle") or role.get("code") or ""
        else:
            role_lbl = str(role) if role else ""
        nom = desc.get("nom") or ""
        prenoms = desc.get("prenoms") or desc.get("prenom") or ""
        if isinstance(prenoms, list):
            prenoms = " ".join(prenoms)
        dirigeants.append({
            "nom_complet": f"{prenoms} {nom}".strip(),
            "nom": nom,
            "prenom": prenoms,
            "qualite": role_lbl,
            "date_naissance": desc.get("dateDeNaissance"),
            "nationalite": desc.get("nationalite"),
        })

    # Comptes annuels (INPI publie parfois les bilans)
    comptes: list[dict] = []
    bilans = raw.get("bilansSaisis") or raw.get("bilans") or []
    for b in bilans[:5]:
        if not isinstance(b, dict):
            continue
        year = b.get("annee") or b.get("dateClotureExercice", "")[:4]
        if year:
            try:
                year = int(str(year)[:4])
            except (TypeError, ValueError):
                continue
            # INPI fournit rarement les chiffres détaillés directement — on
            # conserve le flag "bilan déposé" pour signalement.
            comptes.append({
                "annee": year,
                "date_cloture": b.get("dateClotureExercice"),
                "confidentiel": b.get("confidentiel", False),
                "publie_rne": True,
                # Si INPI ne fournit pas les montants, il faut télécharger
                # le PDF déposé et l'OCR (hors scope v1 — Pappers XLSX reste
                # la source privilégiée pour les chiffres).
                "chiffre_affaires": None,
                "resultat_net": None,
            })

    return PappersCompany(
        siren=siren,
        denomination=denom,
        forme_juridique=forme_jur_lbl,
        code_naf=code_naf,
        libelle_naf=libelle_naf,
        date_creation=date_creation,
        capital=capital,
        ville_siege=ville_siege,
        departement=departement,
        dirigeants=dirigeants,
        comptes=comptes,
        raw=raw,
    )
