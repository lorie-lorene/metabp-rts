"""
merge_latence_mr.py
===================
Fusionne les MR de latence (latence_mr.yaml) dans le catalogue MR
principal (mr_catalog.yaml), SANS écraser les MR existantes.

Sûreté :
  - sauvegarde le catalogue principal avant toute modification (.bak)
  - ne touche QU'À l'ajout : aucune MR existante n'est modifiée
  - dédoublonne par id : si une MR de latence a un id déjà présent,
    elle est ignorée (pas de doublon, pas d'écrasement)
  - retire le champ technique _threshold_us avant écriture (optionnel)
"""

import shutil
import logging
from pathlib import Path

import yaml

logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")
logger = logging.getLogger("merge-mr")


def load_catalog(path: Path) -> list:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("mr_catalog", []) or []


def main(main_path: str, latence_path: str, keep_threshold: bool = True):
    main_p = Path(main_path)
    lat_p  = Path(latence_path)

    main_mrs = load_catalog(main_p)
    lat_mrs  = load_catalog(lat_p)

    existing_ids = {mr.get("id") for mr in main_mrs}
    logger.info("Catalogue principal : %d MR | Latence à fusionner : %d MR",
                len(main_mrs), len(lat_mrs))

    # Sauvegarde de sécurité
    bak = main_p.with_suffix(main_p.suffix + ".bak")
    shutil.copy(main_p, bak)
    logger.info("Sauvegarde → %s", bak)

    added, skipped = 0, 0
    for mr in lat_mrs:
        mr = dict(mr)
        if not keep_threshold:
            mr.pop("_threshold_us", None)

        if mr.get("id") in existing_ids:
            logger.warning("MR %s déjà présente — ignorée", mr.get("id"))
            skipped += 1
            continue

        main_mrs.append(mr)
        existing_ids.add(mr.get("id"))
        added += 1

    with open(main_p, "w", encoding="utf-8") as f:
        yaml.dump({"mr_catalog": main_mrs}, f,
                  default_flow_style=False, allow_unicode=True, sort_keys=False)

    logger.info("Fusion terminée : %d ajoutées, %d ignorées | total = %d MR",
                added, skipped, len(main_mrs))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--main",    required=True, help="mr_catalog.yaml principal")
    ap.add_argument("--latence", required=True, help="latence_mr.yaml (P99)")
    ap.add_argument("--drop-threshold", action="store_true",
                    help="retirer _threshold_us du catalogue fusionné")
    args = ap.parse_args()
    main(args.main, args.latence, keep_threshold=not args.drop_threshold)