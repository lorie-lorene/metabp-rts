"""
Script principal d'orchestration de la Phase 1,enchaîne toutes les étapes dans l'ordre correct et produit tous les artefacts Phase 1 :
    1 : Récupération traces Jaeger       (jaeger_client)
    2 : Parsing des spans                (span_parser)
    3 : Reconstruction T et edge_list    (trace_reconstructor)
    4 : Calcul des poids w_ij            (weight_calculator)
    5 : Construction du graphe G         (graph_builder)
    6 : Calcul C(si)                     (centrality)
    7 : Calcul P(si)                     (propagation_coeff)
    8 : Calcul F(si)                     (fragility)
    9 : Classification Écho-Dormant      (echo_dormant)
    10: Lecture specs OpenAPI             (openapi_reader)
    11: Inférence MR                     (mr_inferrer)
    12: Écriture mr_catalog.yaml         (mr_catalog_writer)
ENTREES   : config/system_config.yaml
            config/services_map.yaml
SORTIES   : data/outputs/service_graph.json
            data/outputs/service_scores.json
            data/outputs/test_suite_T.json
            data/outputs/mr_catalog.yaml
USAGE     : python run_phase1.py --config ../config/system_config.yaml
"""

import argparse
import json
import logging
import sys
from pathlib import Path
import time
import yaml

# Ajout du répertoire parent au path pour les imports relatifs
sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.jaeger_client import JaegerClient
from ingestion.span_parser import SpanParser
from ingestion.trace_reconstructor import TraceReconstructor
from graph.weight_calculator import WeightCalculator
from graph.graph_builder import GraphBuilder
from graph.centrality import CentralityCalculator
from graph.propagation_coeff import PropagationCalculator
from graph.fragility import FragilityCalculator
from graph.echo_dormant import EchoDormantClassifier
from mr_catalog.openapi_reader import OpenAPIReader
from mr_catalog.jaeger_fallback_mr import JaegerFallbackMR
from mr_catalog.mr_inferrer import MRInferrer
from mr_catalog.mr_catalog_writer import MRCatalogWriter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_phase1")


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_services_map(services_map_path: str) -> dict:
    with open(services_map_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("services", {})


def run_pipeline(config: dict, services_map: dict, base_dir: Path) -> None:

    j_cfg  = config["jaeger"]
    w_cfg  = config["weights"]
    ed_cfg = config["echo_dormant"]
    paths  = config["paths"]

    # Résoudre les chemins relatifs depuis base_dir
    def resolve(p): return base_dir / p
    _t_start = time.perf_counter()

    # ── Étape 1 : Récupération traces Jaeger ─────────────
    logger.info("── Étape 1/12 : Récupération traces Jaeger")
    client = JaegerClient(j_cfg["base_url"], j_cfg.get("api_version", "api"))
    traces = client.get_all_traces(
        lookback=j_cfg.get("lookback", "1h"),
        limit=j_cfg.get("limit", 5000),
    )
    client.save_raw(traces, resolve(paths["raw_traces"]))

    # ── Étape 2 : Parsing des spans ───────────────────────
    logger.info("── Étape 2/12 : Parsing des spans")
    parser = SpanParser()
    spans = parser.parse_all(traces)

    # ── Étape 3 : Reconstruction T et edge_list ──────────
    logger.info("── Étape 3/12 : Reconstruction T et edge_list")
    reconstructor = TraceReconstructor()
    test_suite, edge_list = reconstructor.run(spans)

    # Sauvegarder T
    t_path = resolve(paths["test_suite"])
    t_path.parent.mkdir(parents=True, exist_ok=True)
    with open(t_path, "w", encoding="utf-8") as f:
        json.dump(
           [{"trace_id": tp.trace_id,
              "invocation_chain": tp.invocation_chain,
              "duration_us": tp.duration_us}
             for tp in test_suite],
            f, indent=2,
        )
    logger.info("Test suite T sauvegardée → %s (%d cas)", t_path, len(test_suite))

    # ── Étape 4 : Calcul des poids w_ij ──────────────────
    logger.info("── Étape 4/12 : Calcul des poids w_ij")
    wc = WeightCalculator(w_cfg["alpha"], w_cfg["beta"], w_cfg["gamma"])
    edge_weights = wc.compute(edge_list)

    # ── Étape 5 : Construction du graphe G ───────────────
    logger.info("── Étape 5/12 : Construction du graphe G")
    gb = GraphBuilder()
    graph = gb.build(edge_weights)
    gb.save(graph, resolve(paths["service_graph"]))
    summary = gb.summary(graph)
    logger.info("Résumé G : %s", summary)

    # ── Étape 6 : Calcul C(si) ────────────────────────────
    logger.info("── Étape 6/12 : Calcul centralité C(si)")
    C_scores = CentralityCalculator().compute(graph)

    # ── Étape 7 : Calcul P(si) ────────────────────────────
    logger.info("── Étape 7/12 : Calcul propagation P(si)")
    P_scores = PropagationCalculator().compute(graph)

    # ── Étape 8 : Calcul F(si) ────────────────────────────
    logger.info("── Étape 8/12 : Calcul fragilité F(si)")
    F_scores = FragilityCalculator().compute(edge_list)

    # ── Étape 9 : Classification Écho-Dormant ─────────────
    logger.info("── Étape 9/12 : Classification Écho-Dormant")
    classifier = EchoDormantClassifier(
        weighting_method="ewm_critic",
        threshold_method="auto",
        k_clusters=3,
    )
    scores = classifier.classify(C_scores, P_scores, F_scores)
    classifier.save(scores, resolve(paths["service_scores"]))
    # Sauvegarder les poids EWM-CRITIC calculés
    classifier.save_weights(resolve("data/outputs/ewm_critic_weights_phase1.json"))

    # Vérification du théorème de sécurité
    ok, violators = classifier.verify_safety_theorem(scores)
    if not ok:
        logger.error("ARRÊT : Théorème de Sécurité violé pour %s", violators)
        sys.exit(1)

    S_dormant = classifier.get_dormant_set(scores)
    logger.info("S_dormant (%d services) : %s", len(S_dormant), S_dormant)

    # ── Étape 10 : Lecture specs OpenAPI ──────────────────
    logger.info("── Étape 10/12 : Lecture specs OpenAPI")
    reader = OpenAPIReader(
        base_host="http://localhost",
        services_map=services_map,
    )
    specs = reader.read_all()

    # ── Étape 11 : Inférence MR ───────────────────────────
    logger.info("── Étape 11/12 : Inférence MR")
    # Inférence depuis OpenAPI
    inferrer = MRInferrer()
    mr_openapi = inferrer.infer_all(specs)

    # Fallback Jaeger pour les services sans spec
    services_without_spec = [s for s, spec in specs.items() if spec is None]
    mr_fallback = []
    if services_without_spec:
        logger.info(
            "Fallback Jaeger activé pour %d services sans spec OpenAPI",
            len(services_without_spec),
        )
        fallback_spans = [sp for sp in spans if sp.service_name in services_without_spec]
        mr_fallback = JaegerFallbackMR().infer(fallback_spans)

    all_mr = mr_openapi + mr_fallback

    # ── Étape 12 : Écriture mr_catalog.yaml ───────────────
    logger.info("── Étape 12/12 : Écriture mr_catalog.yaml")
    writer = MRCatalogWriter()
    writer.write(all_mr, resolve(paths["mr_catalog"]))

    # ── Résumé final ──────────────────────────────────────
    logger.info("=" * 55)
    logger.info("Phase 1 terminée — Artefacts produits :")
    logger.info("  G        : %s noeuds, %s arcs", summary["nodes"], summary["edges"])
    logger.info("  T        : %d cas de test", len(test_suite))
    logger.info("  Scores   : %d services (%d Écho-Dormants)", len(scores), len(S_dormant))
    logger.info("  MR       : %d relations (%d OpenAPI + %d fallback)",
                len(all_mr), len(mr_openapi), len(mr_fallback))
    logger.info("=" * 55)

    # ── Visualisation automatique du graphe G ─────────────
    # ── Chronométrage TS (pour ET en Phase 3) ─────────────
    _elapsed = time.perf_counter() - _t_start
    timing_path = resolve("data/outputs/timing_phase1.json")
    with open(timing_path, "w", encoding="utf-8") as f:
        json.dump({"phase": 1, "seconds": round(_elapsed, 4)}, f, indent=2)
    logger.info("Temps Phase 1 : %.2fs → %s", _elapsed, timing_path)
    try:
        from visualize_graph import generate as generate_viz
        viz_path = generate_viz(base_dir)
        logger.info("Visualisation → %s", viz_path)
        logger.info("Ouvrir : file://%s", viz_path)
    except Exception as e:
        logger.warning("Visualisation non générée : %s", e)


def main():
    parser = argparse.ArgumentParser(description="MetaBP-RTS — Phase 1")
    parser.add_argument(
        "--config",
        default="../config/system_config.yaml",
        help="Chemin vers system_config.yaml",
    )
    parser.add_argument(
        "--services-map",
        default="../config/services_map.yaml",
        help="Chemin vers services_map.yaml",
    )
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    services_map_path = Path(args.services_map).resolve()
    base_dir = config_path.parent.parent  # répertoire phase1/

    config = load_config(config_path)
    services_map = load_services_map(services_map_path)

    logger.info("MetaBP-RTS Phase 1 — démarrage")
    logger.info("Config     : %s", config_path)
    logger.info("Services   : %d services chargés", len(services_map))

    run_pipeline(config, services_map, base_dir)


if __name__ == "__main__":
    main()