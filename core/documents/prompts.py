"""Prompts Gemini Vision pour extraction structurée de documents financiers FR.

Chaque prompt vise un JSON strict — Gemini renvoie via response_schema (mode JSON).
La langue de retour est française pour cohérence avec le reste de FinSight.
"""

# Schéma JSON commun aux comptes (pour réponse structurée)
SCHEMA_COMPTE_RESULTAT = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": ["compte_resultat"]},
        "annee": {"type": "integer", "description": "Année d'exercice (ex: 2024)"},
        "devise": {"type": "string", "description": "EUR par défaut"},
        "unite": {"type": "string", "description": "1 = euros, 1000 = milliers, etc."},
        "chiffre_affaires": {"type": "number"},
        "production_vendue_biens": {"type": "number"},
        "production_vendue_services": {"type": "number"},
        "achats_marchandises": {"type": "number"},
        "achats_matieres_premieres": {"type": "number"},
        "autres_achats_charges_externes": {"type": "number"},
        "impots_taxes": {"type": "number"},
        "salaires_traitements": {"type": "number"},
        "charges_sociales": {"type": "number"},
        "dotations_amortissements": {"type": "number"},
        "ebe_estime": {"type": "number", "description": "Excédent brut d'exploitation si visible"},
        "resultat_exploitation": {"type": "number"},
        "resultat_financier": {"type": "number"},
        "resultat_courant": {"type": "number"},
        "resultat_exceptionnel": {"type": "number"},
        "impots_benefices": {"type": "number"},
        "resultat_net": {"type": "number"},
        "effectif_moyen": {"type": "integer"},
        "remarques": {"type": "string", "description": "Anomalies, valeurs partielles, doutes d'extraction"},
    },
    "required": ["type", "annee"],
}

SCHEMA_BILAN = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": ["bilan"]},
        "annee": {"type": "integer"},
        "devise": {"type": "string"},
        "unite": {"type": "string"},
        "actif_immobilise": {"type": "number"},
        "immobilisations_incorporelles": {"type": "number"},
        "immobilisations_corporelles": {"type": "number"},
        "immobilisations_financieres": {"type": "number"},
        "actif_circulant": {"type": "number"},
        "stocks": {"type": "number"},
        "creances_clients": {"type": "number"},
        "autres_creances": {"type": "number"},
        "disponibilites": {"type": "number"},
        "total_actif": {"type": "number"},
        "capitaux_propres": {"type": "number"},
        "capital_social": {"type": "number"},
        "reserves": {"type": "number"},
        "resultat_exercice": {"type": "number"},
        "provisions_risques": {"type": "number"},
        "dettes_financieres": {"type": "number"},
        "dettes_fournisseurs": {"type": "number"},
        "dettes_fiscales_sociales": {"type": "number"},
        "autres_dettes": {"type": "number"},
        "total_passif": {"type": "number"},
        "remarques": {"type": "string"},
    },
    "required": ["type", "annee"],
}

SCHEMA_CONTRAT = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": ["contrat"]},
        "nature_contrat": {"type": "string", "description": "ex: bail commercial, prestation, distribution"},
        "parties": {
            "type": "array",
            "items": {"type": "string"},
        },
        "date_signature": {"type": "string"},
        "date_effet": {"type": "string"},
        "duree": {"type": "string"},
        "montant_principal": {"type": "number"},
        "devise": {"type": "string"},
        "frequence_paiement": {"type": "string"},
        "clauses_clefs": {
            "type": "array",
            "items": {"type": "string"},
            "description": "5-10 clauses importantes (résiliation, exclusivité, garanties, indemnités…)",
        },
        "engagements_financiers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "libelle": {"type": "string"},
                    "montant": {"type": "number"},
                    "echeance": {"type": "string"},
                },
            },
        },
        "risques_identifies": {
            "type": "array",
            "items": {"type": "string"},
        },
        "resume": {"type": "string", "description": "Résumé exécutif 3-5 phrases"},
    },
    "required": ["type", "nature_contrat", "resume"],
}

SCHEMA_AUTRE = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": ["autre"]},
        "nature_document": {"type": "string"},
        "resume": {"type": "string"},
        "donnees_chiffrees": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "libelle": {"type": "string"},
                    "valeur": {"type": "number"},
                    "unite": {"type": "string"},
                    "annee": {"type": "integer"},
                },
            },
        },
        "elements_clefs": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["type", "nature_document", "resume"],
}


PROMPT_DETECTION = """Tu es un assistant d'extraction de documents financiers français.

Analyse ce document et identifie son TYPE parmi :
- "compte_resultat" : compte de résultat / income statement / P&L (CA, charges, résultat net…)
- "bilan" : bilan comptable / balance sheet (actif, passif, capitaux propres…)
- "contrat" : contrat juridique (bail, prestation, distribution, NDA, partenariat…)
- "autre" : tout autre document (rapport activité, business plan, présentation…)

Réponds STRICTEMENT en JSON : {"type": "compte_resultat" | "bilan" | "contrat" | "autre", "confiance": 0.0-1.0, "annee": <int ou null>}

Pas de texte hors du JSON."""


PROMPT_COMPTE_RESULTAT = """Tu es un expert-comptable français. Extrais TOUS les postes du compte de résultat ci-joint.

Règles strictes :
- Toutes les valeurs en EUROS (pas en milliers, convertis si nécessaire — précise l'unité d'origine dans "unite")
- Si une valeur n'est pas explicitement présente, OMETS le champ (ne mets pas 0)
- Pour les charges, utilise des valeurs POSITIVES (pas négatives)
- Si plusieurs années visibles, prends la PLUS RÉCENTE (mets l'année dans "annee")
- "remarques" : signale les ambiguïtés ou valeurs partiellement lisibles

Réponds UNIQUEMENT en JSON conforme au schéma fourni."""


PROMPT_BILAN = """Tu es un expert-comptable français. Extrais TOUS les postes du bilan ci-joint.

Règles strictes :
- Toutes les valeurs en EUROS (convertis si milliers/millions, précise dans "unite")
- Côté actif et passif, utilise des valeurs POSITIVES
- Vérifie que actif ≈ passif (tolérance 1%) — sinon signale dans "remarques"
- Si plusieurs années, prends la PLUS RÉCENTE (mets l'année dans "annee")
- Omets les champs absents du document (ne mets pas 0 par défaut)

Réponds UNIQUEMENT en JSON conforme au schéma fourni."""


PROMPT_CONTRAT = """Tu es un avocat d'affaires français. Analyse ce contrat et extrais les éléments clefs.

Règles :
- Identifie la nature exacte (bail commercial, prestation de services, distribution, NDA, etc.)
- Liste 5-10 clauses importantes (résiliation, exclusivité, indemnités, garanties, IP)
- Identifie les engagements financiers chiffrés (loyers, redevances, pénalités, paliers)
- Liste 3-5 risques juridiques ou financiers identifiables
- Résumé exécutif factuel en 3-5 phrases

Réponds UNIQUEMENT en JSON conforme au schéma fourni."""


PROMPT_AUTRE = """Tu es un analyste financier. Ce document n'est ni un compte de résultat, ni un bilan, ni un contrat.

Identifie sa nature (rapport activité, business plan, présentation commerciale, étude marché, etc.),
résume son contenu en 3-5 phrases factuelles, et extrais toutes les données chiffrées avec leur libellé,
unité et année quand applicable.

Réponds UNIQUEMENT en JSON conforme au schéma fourni."""
