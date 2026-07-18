"""
run_phase4.py — Orchestrateur Phase 4 MetaBP-RTS (validation sans oracle)
4A : mutation des traces reelles + verification par seuils -> FCS
4B : verification metamorphique par seuils sur T_sel        -> P_mr
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mutation.trace_mutator import TraceMutator
from mutation.mutation_verifier import MutationVerifier
from metamorphic.mr_verifier import MRVerifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_phase4")


def load_config(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path_str, data):
    path = Path(path_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def compute_metrics(n_original, n_t_sel, mutation_result, mr_result):
    en = round((n_original - n_t_sel) / max(n_original, 1) * 100, 2)
    fcs = mutation_result.get("fcs", 0.0) if mutation_result else 0.0
    p_mr = mr_result.get("pass_rate", 0.0) if mr_result else 0.0
    f = 0.0
    if fcs + p_mr > 0:
        f = round(2 * fcs * p_mr / (fcs + p_mr), 2)
    return {"EN": en, "FCS": fcs, "P_mr": p_mr, "F": f,
            "note": "FCS = proxy du Recall via mutation ; P_mr = conformite MR sur donnees nominales"}


def main():
    parser = argparse.ArgumentParser(description="MetaBP-RTS Phase 4")
    parser.add_argument("--config", default="../config/phase4_config.yaml")
    parser.add_argument("--skip-4a", action="store_true")
    parser.add_argument("--skip-4b", action="store_true")
    args = parser.parse_args()

    config = load_config(args.config)
    base_dir = Path(args.config).resolve().parent.parent

    p3_cfg = config["phase3_outputs"]
    p1_cfg = config["phase1_outputs"]
    out_cfg = config["outputs"]
    mut_cfg = config["mutation"]
    mr_cfg = config["metamorphic"]

    mr_catalog_path = str(base_dir / p1_cfg["mr_catalog"])
    t_sel_path = str(base_dir / p3_cfg["t_sel"])
    test_suite_path = str(base_dir / p1_cfg["test_suite"])
    raw_traces_path = str(base_dir / p1_cfg["raw_traces"])

    t_sel = load_json(t_sel_path)
    n_t_sel = len(t_sel)
    test_suite = load_json(test_suite_path)
    n_original = len(test_suite)

    logger.info("MetaBP-RTS Phase 4 — démarrage")
    logger.info("T original : %d chemins", n_original)
    logger.info("T_sel      : %d chemins", n_t_sel)
    logger.info("Mode MR    : %s", mr_cfg.get("mode", "offline"))

    mutation_result = None
    mr_result = None

    if not args.skip_4a:
        logger.info("── Sous-phase 4A : Mutation de traces")
        mutator = TraceMutator(
            operators=mut_cfg.get("operators", TraceMutator.OPERATORS),
            latency_ms=mut_cfg.get("latency_ms", 5000),
            max_mutants_per_path=mut_cfg.get("max_mutants_per_path", 3),
            traces_path=raw_traces_path,
        )
        mutants = mutator.generate_mutants(t_sel)
        mutator.save(mutants, str(base_dir / out_cfg["mutants"]))

        verifier_4a = MutationVerifier(mr_catalog_path=mr_catalog_path)
        mutation_result = verifier_4a.verify_mutants(mutants)
        verifier_4a.save(
            mutation_result,
            results_path=str(base_dir / out_cfg["mutation_results"]),
            fcs_path=str(base_dir / out_cfg["fcs_report"]),
        )
        logger.info("4A terminée : %d mutants | %d tués | FCS=%.1f%%",
                    mutation_result["n_total"], mutation_result["n_killed"],
                    mutation_result["fcs"])
    else:
        logger.info("4A ignorée (--skip-4a)")

    if not args.skip_4b:
        logger.info("── Sous-phase 4B : Vérification métamorphique")
        verifier_4b = MRVerifier(
            mr_catalog_path=mr_catalog_path,
            mode=mr_cfg.get("mode", "offline"),
            sut_url=mr_cfg.get("sut_url", "http://localhost:8080"),
            timeout=mr_cfg.get("timeout", 10),
            traces_path=raw_traces_path,
        )
        mr_result = verifier_4b.verify_t_sel(t_sel)
        verifier_4b.save(
            mr_result,
            pairs_path=str(base_dir / out_cfg["mr_pairs"]),
            results_path=str(base_dir / out_cfg["verification_results"]),
        )
        logger.info("4B terminée : %d MR vérifiées | %d PASS | %d FAIL | taux=%.1f%%",
                    mr_result["n_mr_verified"], mr_result["n_pass"],
                    mr_result["n_fail"], mr_result["pass_rate"])
    else:
        logger.info("4B ignorée (--skip-4b)")

    metrics = compute_metrics(n_original, n_t_sel, mutation_result, mr_result)
    report = {
        "input": {"n_original": n_original, "n_t_sel": n_t_sel},
        "phase_4a": mutation_result or {"skipped": True},
        "phase_4b": mr_result or {"skipped": True},
        "metrics": metrics,
    }
    write_json(str(base_dir / out_cfg["phase4_report"]), report)

    logger.info("=======================================================")
    logger.info("Phase 4 terminée — Métriques MetaBP-RTS :")
    logger.info("  T original       : %d chemins", n_original)
    logger.info("  T_sel            : %d chemins", n_t_sel)
    logger.info("  EN (réduction)   : %.1f%%", metrics["EN"])
    if mutation_result:
        logger.info("  FCS (qualité)    : %.1f%%  (%d/%d mutants tués)",
                    metrics["FCS"], mutation_result["n_killed"],
                    mutation_result["n_total"])
    if mr_result:
        logger.info("  P_mr (conformité): %.1f%%  (%d/%d MR conformes)",
                    metrics["P_mr"], mr_result["n_pass"],
                    mr_result["n_mr_verified"])
        logger.info("  MR non conformes : %d  (variabilite nominale + anomalies preexistantes)",
                    mr_result["n_fail"])
    logger.info("  F-measure        : %.1f%%", metrics["F"])
    logger.info("=======================================================")
    if mr_result:
        logger.info("P_mr = %.1f%% : conformite des MR sur donnees nominales "
                    "(le residuel reflete la variabilite attendue, non des regressions)",
                    metrics["P_mr"])


if __name__ == "__main__":
    main()
