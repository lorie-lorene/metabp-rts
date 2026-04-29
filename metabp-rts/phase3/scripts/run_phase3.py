"""
run_phase3.py
=============
Orchestrateur Phase 3 MetaBP-RTS.

Étapes :
  1. MRPS — déduplication de Tier 2 par signature enrichie
  2. Binary PSO — sélection optimale sur Tier2_dédupliqué
  3. Assemblage T_sel = Tier1 ∪ Tier2_sel
  4. Rapport de réduction global

Usage :
    python run_phase3.py --config ../config/phase3_config.yaml
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mrps.mrps     import MRPS
from pso.binary_pso import BinaryPSO

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_phase3")


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_json(path: str) -> object:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path_str: str, data) -> None:
    path = Path(path_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def extract_tier2_paths(tier2_data) -> list:
    """Extrait la liste des chemins depuis tier2_tests.json."""
    if isinstance(tier2_data, dict):
        return tier2_data.get("tests", [])
    if isinstance(tier2_data, list):
        return tier2_data
    return []


def extract_tier1_paths(tier1_data) -> list:
    """Extrait la liste des chemins depuis tier1_tests.json."""
    if isinstance(tier1_data, dict):
        return tier1_data.get("tests", [])
    if isinstance(tier1_data, list):
        return tier1_data
    return []


def collect_all_services(tier2_paths: list, cit: dict) -> list:
    """
    Collecte tous les services présents dans Tier 2 + services de la CIT.
    Ce sont les services que le PSO doit couvrir.
    """
    services = set(cit.keys())
    for tp in tier2_paths:
        chain = tp.get("invocation_chain", [])
        if chain:
            for pair in chain:
                services.update(pair)
        else:
            services.update(tp.get("services", []))
    return sorted(services)


def main():
    parser = argparse.ArgumentParser(description="MetaBP-RTS Phase 3")
    parser.add_argument(
        "--config", default="../config/phase3_config.yaml",
        help="Chemin vers phase3_config.yaml",
    )
    args = parser.parse_args()

    config   = load_config(args.config)
    base_dir = Path(args.config).resolve().parent.parent

    p2_cfg   = config["phase2_outputs"]
    p1_cfg   = config["phase1_outputs"]
    out_cfg  = config["outputs"]
    mrps_cfg = config["mrps"]
    pso_cfg  = config["pso"]

    logger.info("MetaBP-RTS Phase 3 — démarrage")

    # ── Chargement des entrées ───────────────────────────────────────────────
    tier1_data  = load_json(str(base_dir / p2_cfg["tier1_tests"]))
    tier2_data  = load_json(str(base_dir / p2_cfg["tier2_tests"]))
    cit         = load_json(str(base_dir / p2_cfg["change_impact_table"]))
    echo_data   = load_json(str(base_dir / p2_cfg["echo_impact_services"]))

    mr_catalog_path = str(base_dir / p1_cfg["mr_catalog"])

    tier1_paths = extract_tier1_paths(tier1_data)
    tier2_paths = extract_tier2_paths(tier2_data)

    s_echo = echo_data.get("s_echo", []) if isinstance(echo_data, dict) else []

    logger.info(
        "Entrées — Tier1=%d | Tier2=%d | S_echo=%d | CIT=%d services",
        len(tier1_paths), len(tier2_paths), len(s_echo), len(cit),
    )

    # Services à couvrir par le PSO
    all_services = collect_all_services(tier2_paths, cit)
    logger.info("Services à couvrir par PSO : %d", len(all_services))

    logger.info("── Étape 1/3 : MRPS — déduplication Tier 2")

    mrps = MRPS(
        mode=mrps_cfg.get("mode", "enriched"),
        representative=mrps_cfg.get("representative", "cit"),
    )
    mrps_result = mrps.deduplicate(
        tier2_tests=tier2_paths,
        mr_catalog_path=mr_catalog_path,
        cit=cit,
    )
    mrps.save(
        mrps_result,
        groups_path=str(base_dir / out_cfg["mrps_groups"]),
        dedup_path=str(base_dir / out_cfg["tier2_deduplicated"]),
    )

    tier2_dedup = mrps_result["representatives"]
    s = mrps_result["stats"]
    logger.info(
        "MRPS terminé : %d → %d chemins uniques | réduction=%s | singletons=%s",
        s["n_input"], s["n_groups"], s["dedup_pct"], s["singleton_pct"],
    )

    logger.info("── Étape 2/3 : Binary PSO — sélection optimale Tier 2")

    pso = BinaryPSO(
        n_particles=pso_cfg.get("n_particles", 30),
        max_iterations=pso_cfg.get("max_iterations", 100),
        patience=pso_cfg.get("patience", 20),
        w=pso_cfg.get("w", 0.7),
        c1=pso_cfg.get("c1", 1.5),
        c2=pso_cfg.get("c2", 1.5),
        w_coverage=pso_cfg.get("w_coverage", 0.6),
        w_size=pso_cfg.get("w_size", 0.3),
        w_cit=pso_cfg.get("w_cit", 0.1),
        threshold=pso_cfg.get("threshold", 0.5),
        init_strategy=pso_cfg.get("init_strategy", "greedy"),
    )
    pso_result = pso.optimize(
        paths=tier2_dedup,
        cit=cit,
        all_services=all_services,
    )
    pso.save(
        pso_result,
        selected_path=str(base_dir / out_cfg["tier2_selected"]),
        history_path=str(base_dir / out_cfg["pso_history"]),
    )

    tier2_sel = pso_result["selected_paths"]
    ps = pso_result["stats"]
    logger.info(
        "PSO terminé : %d/%d chemins sélectionnés | couverture=%s | "
        "réduction=%s | iter=%d | convergé=%s",
        ps["n_selected"], ps["n_input"],
        ps["coverage_pct"], ps["reduction_pct"],
        ps["n_iterations"], ps["converged"],
    )

    logger.info("── Étape 3/3 : Assemblage T_sel = Tier1 ∪ Tier2_sel")

    t_sel = tier1_paths + tier2_sel

    write_json(str(base_dir / out_cfg["t_sel"]), t_sel)
    logger.info("T_sel sauvegardé : %d chemins", len(t_sel))

    n_original = len(tier1_paths) + len(tier2_paths)
    n_t_sel    = len(t_sel)
    reduction_globale = round(1 - n_t_sel / max(n_original, 1), 4)

    report = {
        "input": {
            "n_tier1":         len(tier1_paths),
            "n_tier2":         len(tier2_paths),
            "n_total":         n_original,
            "n_s_echo":        len(s_echo),
            "n_services_cit":  len(cit),
        },
        "mrps": mrps_result["stats"],
        "pso":  pso_result["stats"],
        "output": {
            "n_tier1_conserved": len(tier1_paths),
            "n_tier2_selected":  len(tier2_sel),
            "n_t_sel":           n_t_sel,
            "reduction_globale": reduction_globale,
            "reduction_pct":     f"{reduction_globale*100:.1f}%",
        },
    }

    write_json(str(base_dir / out_cfg["report"]), report)

    # ── Résumé 
    logger.info("=======================================================")
    logger.info("Phase 3 terminée :")
    logger.info("  T original     : %d chemins", n_original)
    logger.info("  ── MRPS        : %d → %d (réduction %s)",
                len(tier2_paths), len(tier2_dedup),
                mrps_result["stats"]["dedup_pct"])
    logger.info("  ── PSO         : %d → %d (réduction %s)",
                len(tier2_dedup), len(tier2_sel),
                pso_result["stats"]["reduction_pct"])
    logger.info("  Tier 1         : %d (100%% conservés)", len(tier1_paths))
    logger.info("  Tier 2_sel     : %d (optimisé MRPS+PSO)", len(tier2_sel))
    logger.info("  T_sel final    : %d chemins", n_t_sel)
    logger.info("  Réduction glob : %s", report["output"]["reduction_pct"])
    logger.info("  Couverture     : %s services", pso_result["stats"]["coverage_pct"])
    logger.info("=======================================================")
    logger.info("Artefacts → Phase 4 :")
    logger.info("  T_sel.json      : suite de test optimisée")
    logger.info("  phase3_report   : métriques complètes")


if __name__ == "__main__":
    main()
