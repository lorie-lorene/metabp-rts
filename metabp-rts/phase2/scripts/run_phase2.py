"""
run_phase2.py
=============
Orchestrateur Phase 2 
Le MODE de propagation est lu depuis phase2_config.yaml :
    belief_propagation.mode: noisy_or | max_product

Si belief_propagation.compare: true, les DEUX modes sont lancés
et un rapport de comparaison est produit — utile pour la section
expérimentale du mémoire.

Etapes :
  1. Inversion G -> DG
  2. Initialisation enrichie p0 (Phase 1 + ΔS)
  3. Propagation BP selon le mode configuré (ou les deux si compare)
  4. Construction CIT + score Θ_complet + identification S_écho-impact
  5. Tiering + Scoring des tests + artefacts Phase 3

Usage :
    python run_phase2.py --config ../config/phase2_config.yaml \\
                         --delta-s ts-cancel-service
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bp.graph_inverter     import GraphInverter
from bp.bp_initializer     import BPInitializer
from bp.bp_propagator      import BPPropagator
from bp.cit_builder        import CITBuilder
from selection.test_scorer import TestScorer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_phase2")


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_scores(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return {s["service_name"]: s for s in raw}


def write_json(path_str: str, data) -> None:
    path = Path(path_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def run_bp(
    propagator: BPPropagator,
    dg: dict,
    p0: dict,
    mode: str,
    keep_history: bool = False,
) -> tuple:
    """Lance la BP dans un mode donné et retourne (p_final, n_iter, converged, history)."""
    propagator.mode = mode
    logger.info("BP mode=%s — démarrage", mode)
    p_final, n_iter, converged, history = propagator.propagate(
        dg=dg, p0=p0, keep_history=keep_history
    )
    logger.info(
        "BP mode=%s — %d itérations | convergence=%s | %d services impactés",
        mode, n_iter, converged,
        sum(1 for v in p_final.values() if v > 0),
    )
    return p_final, n_iter, converged, history


def build_comparison_report(
    p_nor: dict,
    p_mp: dict,
    n_nor: int,
    n_mp: int,
    conv_nor: bool,
    conv_mp: bool,
    scores: dict,
) -> dict:
    """
    Construit le rapport de comparaison Noisy-OR vs Max-Product.
    Utile pour la section expérimentale du mémoire.
    """
    all_services = set(p_nor.keys()) | set(p_mp.keys())

    differences = []
    for svc in sorted(all_services):
        v_nor = p_nor.get(svc, 0.0)
        v_mp  = p_mp.get(svc, 0.0)
        delta = round(v_nor - v_mp, 6)
        if abs(delta) > 1e-6:
            sc = scores.get(svc, {})
            differences.append({
                "service":       svc,
                "noisy_or":      round(v_nor, 6),
                "max_product":   round(v_mp, 6),
                "delta":         delta,
                "is_dormant":    sc.get("is_dormant", False),
                "theta_phase1":  round(sc.get("theta_dormant", 0.0), 6),
                "noisy_or_wins": delta > 0,
            })

    differences.sort(key=lambda x: abs(x["delta"]), reverse=True)

    n_nor_wins = sum(1 for d in differences if d["noisy_or_wins"])
    n_mp_wins  = len(differences) - n_nor_wins

    return {
        "summary": {
            "n_services_compared": len(all_services),
            "n_different":         len(differences),
            "noisy_or_higher":     n_nor_wins,
            "max_product_higher":  n_mp_wins,
            "n_iter_noisy_or":     n_nor,
            "n_iter_max_product":  n_mp,
            "converged_noisy_or":  conv_nor,
            "converged_max_product": conv_mp,
            "interpretation": (
                "Noisy-OR produit des scores CIT plus élevés sur "
                f"{n_nor_wins}/{len(differences)} services différents. "
                "La différence est significative pour les services avec "
                "plusieurs parents simultanément affectés."
                if n_nor_wins > n_mp_wins
                else
                "Max-Product et Noisy-OR produisent des résultats proches "
                "sur ce graphe — indiquant un faible degré entrant moyen "
                "(peu de parents par service)."
            ),
        },
        "differences": differences,
    }


def main():
    parser = argparse.ArgumentParser(description="MetaBP-RTS Phase 2")
    parser.add_argument(
        "--config", default="../config/phase2_config.yaml",
        help="Chemin vers phase2_config.yaml",
    )
    parser.add_argument(
        "--delta-s", nargs="+", required=True, metavar="SERVICE",
        help="Services modifiés ex: ts-cancel-service ts-order-service",
    )
    parser.add_argument(
        "--mode", choices=["noisy_or", "max_product"], default=None,
        help="Surcharge belief_propagation.mode dans la config",
    )
    parser.add_argument(
        "--compare", action="store_true", default=None,
        help="Surcharge belief_propagation.compare: true dans la config",
    )
    parser.add_argument(
        "--history", action="store_true",
        help="Conserver l'historique des itérations BP",
    )
    args = parser.parse_args()

    # ── Chronométrage TS (pour ET en Phase 3) ──
    _t_start = time.perf_counter()

    # ── Chargement config ──
    config   = load_config(args.config)
    base_dir = Path(args.config).resolve().parent.parent

    p1_cfg  = config["phase1_outputs"]
    out_cfg = config["outputs"]
    bp_cfg  = config["belief_propagation"]
    sel_cfg = config["selection"]
    init_cfg = config["initializer"]

    bp_mode = args.mode if args.mode else bp_cfg.get("mode", "noisy_or")
    do_compare = True if args.compare else bp_cfg.get("compare", False)

    delta_s = args.delta_s
    scores  = load_scores(str(base_dir / p1_cfg["service_scores"]))
    dormants = [s for s, v in scores.items() if v.get("is_dormant")]

    logger.info("MetaBP-RTS Phase 2 — démarrage")
    logger.info("ΔS               : %s", delta_s)
    logger.info("S_dormant Phase 1: %s", dormants)
    logger.info("Mode BP          : %s", bp_mode)
    logger.info("Comparaison      : %s", do_compare)

    logger.info("── Étape 1/5 : Inversion G → DG")
    inverter = GraphInverter()
    dg = inverter.invert(str(base_dir / p1_cfg["service_graph"]), delta_s=delta_s)
    inverter.save(dg, str(base_dir / out_cfg["dg_graph"]))
    
    logger.info("── Étape 2/5 : Initialisation p0")
    initializer = BPInitializer(
        use_phase1_scores=init_cfg.get("use_phase1_scores", True)
    )
    p0 = initializer.initialize(nodes=dg["nodes"], delta_s=delta_s, scores=scores)

    logger.info(
        "p0 — modifiés=%s | Écho-Dormants ψ>0=%s",
        [s for s, v in p0.items() if v == 1.0],
        [s for s, v in p0.items() if 0 < v < 1.0],
    )

    if do_compare and init_cfg.get("compare_init", False):
        comp_init = initializer.compare_modes(dg["nodes"], delta_s, scores)
        logger.info(
            "Init comparison — %d services avec ψ différent : %s",
            len(comp_init["differences"]),
            list(comp_init["differences"].keys()),
        )

    logger.info("── Étape 3/5 : Propagation BP")
    propagator = BPPropagator(
        max_iterations=bp_cfg.get("max_iterations", 100),
        convergence_threshold=bp_cfg.get("convergence_threshold", 1e-6),
        mode=bp_mode,
    )

    p_final, n_iter, converged, history = run_bp(
        propagator, dg, p0, bp_mode, keep_history=args.history
    )

    if do_compare:
        other_mode = "max_product" if bp_mode == "noisy_or" else "noisy_or"
        logger.info("── Comparaison avec mode=%s", other_mode)
        p_other, n_other, conv_other, _ = run_bp(propagator, dg, p0, other_mode)

        if bp_mode == "noisy_or":
            p_nor, n_nor, conv_nor = p_final, n_iter, converged
            p_mp,  n_mp,  conv_mp  = p_other, n_other, conv_other
        else:
            p_mp,  n_mp,  conv_mp  = p_final, n_iter, converged
            p_nor, n_nor, conv_nor = p_other, n_other, conv_other

        comparison = build_comparison_report(
            p_nor, p_mp, n_nor, n_mp, conv_nor, conv_mp, scores
        )

        comp_path = str(base_dir / out_cfg.get(
            "comparison_report", "data/outputs/bp_mode_comparison.json"
        ))
        write_json(comp_path, comparison)

        logger.info("Rapport comparaison sauvegardé → %s", comp_path)
        logger.info(
            "Résumé comparaison : %d services différents | "
            "Noisy-OR plus élevé sur %d | Max-Product plus élevé sur %d",
            comparison["summary"]["n_different"],
            comparison["summary"]["noisy_or_higher"],
            comparison["summary"]["max_product_higher"],
        )
        logger.info("Interprétation : %s", comparison["summary"]["interpretation"])

    if args.history and history:
        hist_path = str(base_dir / "data/outputs/bp_history.json")
        write_json(hist_path, history)
        logger.info("Historique BP → %s", hist_path)

    logger.info("── Étape 4/5 : CIT + Θ_complet + identification Écho-Impact")
    cit_builder = CITBuilder(
        tau_impact=bp_cfg.get("tau_impact", 0.30),
        omega_B=bp_cfg.get("omega_B", 0.30),
    )
    cit_result = cit_builder.build(
        p_final=p_final, delta_s=delta_s, scores=scores
    )
    cit_builder.save(
        cit_result,
        cit_path=str(base_dir / out_cfg["change_impact_table"]),
        echo_path=str(base_dir / out_cfg["echo_impact_services"]),
        theta_path=str(base_dir / out_cfg.get(
            "theta_complet", "data/outputs/theta_complet.json"
        )),
    )

    logger.info("── Étape 5/5 : Tiering + Scoring des tests")
    scorer = TestScorer(
        strategy=sel_cfg.get("strategy", "existent"),
        k=sel_cfg.get("k", 2),
        threshold_p=sel_cfg.get("threshold_p"),
    )
    sel_result = scorer.score_and_select(
        test_suite_path=str(base_dir / p1_cfg["test_suite"]),
        cit=cit_result["cit"],
        s_echo=cit_result["s_echo"],
    )
    scorer.save(
        sel_result,
        scores_path=str(base_dir / out_cfg["test_scores"]),
        selected_path=str(base_dir / out_cfg["selected_tests"]),
        tier1_path=str(base_dir / out_cfg.get(
            "tier1_tests", "data/outputs/tier1_tests.json"
        )),
        tier2_path=str(base_dir / out_cfg.get(
            "tier2_tests", "data/outputs/tier2_tests.json"
        )),
    )

    sc = cit_result["stats"]
    ss = sel_result["stats"]

    # ── Chronométrage TS ──
    _elapsed = time.perf_counter() - _t_start
    timing_path = base_dir / "data/outputs/timing_phase2.json"
    write_json(str(timing_path), {"phase": 2, "seconds": round(_elapsed, 4)})

    logger.info("=======================================================")
    logger.info("Phase 2 terminée :")
    logger.info("  ΔS                    : %s", delta_s)
    logger.info("  Mode BP utilisé       : %s", bp_mode)
    logger.info("  Itérations BP         : %d (convergé=%s)", n_iter, converged)
    logger.info("  Services Écho-Impact  : %d (τ=%.2f)",
                sc["n_echo_impact"], bp_cfg.get("tau_impact", 0.30))
    logger.info("  Résonance confirmée   : %d/%d",
                sc["n_resonant"], sc["n_echo_impact"])
    logger.info("  Tier 1 (S_echo)       : %d tests (%s)",
                ss["n_tier1"], ss["tier1_pct"])
    logger.info("  Tier 2 (candidats PSO): %d tests (%s)",
                ss["n_tier2"], ss["tier2_pct"])
    logger.info("  Sélection totale      : %d/%d (%s)",
                ss["n_selected"], ss["n_total"], ss["reduction_pct"])
    logger.info("  Temps Phase 2 (TS)    : %.2fs", _elapsed)
    logger.info("=======================================================")

    if cit_result["echo_impact_services"]:
        logger.info("Top Services Écho-Impact :")
        for svc in cit_result["echo_impact_services"][:5]:
            tag = " ← RÉSONANCE" if svc["resonance"] else ""
            logger.info(
                "  %-35s CIT=%.4f | Θ_complet=%.4f%s",
                svc["service_name"],
                svc["cit_score"],
                svc["theta_complet"],
                tag,
            )

    logger.info("")
    logger.info("Artefacts → Phase 3 :")
    logger.info("  tier1_tests.json    : Tier 1 — 100%% conservés")
    logger.info("  tier2_tests.json    : Tier 2 — candidats PSO")
    logger.info("  change_impact_table : CIT pour fitness PSO")
    if do_compare:
        logger.info("  bp_mode_comparison  : rapport comparaison modes BP")


if __name__ == "__main__":
    main()