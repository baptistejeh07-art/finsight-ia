"""
Module `pappers` : analyse des sociétés françaises non cotées.

Architecture :
- `client.py`         : client HTTP Pappers API v2 (identité + dirigeants + BODACC via Pappers)
- `inpi_client.py`    : client INPI XBRL open data (gratuit, comptes peers)
- `bodacc_client.py`  : client BODACC open data (gratuit, procédures)
- `sector_registry.py`: 50 profils sectoriels (seuils, multiples, vocabulaire)
- `analytics.py`      : moteur SIG + ratios + scoring (100% Python déterministe)
- `benchmark.py`      : comparaison peers (quartiles, médianes)
- `pipeline.py`       : orchestration LangGraph style (fetch → calculs → narratif → outputs)

Règle fondamentale : **aucun calcul financier par LLM**. Le LLM n'intervient que
pour les commentaires narratifs (3-6 phrases par section), jamais pour inventer
ou transformer des chiffres.
"""
