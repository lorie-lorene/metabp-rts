# MetaBP-RTS — Phase 1

Méthodologie MetaBP-RTS — Phase 1 : Modélisation Architecturale & Extraction.

## Prérequis
1. Déployer Train-Ticket : `docker-compose up -d`
2. Générer du trafic : `python phase1/scripts/generate_traffic.py`

## Lancement Phase 1
```bash
pip install -r requirements.txt
python phase1/scripts/run_phase1.py --config phase1/config/system_config.yaml
```

## Artefacts produits
- `phase1/data/outputs/service_graph.json`   — Graphe G = (V, E)
- `phase1/data/outputs/service_scores.json`  — Scores C, P, F, Θ_dormant
- `phase1/data/outputs/test_suite_T.json`    — Suite de tests T
- `phase1/data/outputs/mr_catalog.yaml`      — Catalogue MR

## Auteur
NIKOUM Modeste Lorene — Master II SIGL — Université de Yaoundé I
