"""
run_phase1.py
=============
BLOC      : Orchestration Phase 1
ROLE      : Script principal d'orchestration de la Phase 1.
            Enchaîne toutes les étapes dans l'ordre correct et
            produit tous les artefacts Phase 1 :
              Étape 1 : Récupération traces Jaeger       (jaeger_client)
              Étape 2 : Parsing des spans                (span_parser)
              Étape 3 : Reconstruction T et edge_list    (trace_reconstructor)
              Étape 4 : Calcul des poids w_ij            (weight_calculator)
              Étape 5 : Construction du graphe G         (graph_builder)
              Étape 6 : Calcul C(si)                     (centrality)
              Étape 7 : Calcul P(si)                     (propagation_coeff)
              Étape 8 : Calcul F(si)                     (fragility)
              Étape 9 : Classification Écho-Dormant      (echo_dormant)
              Étape 10: Lecture specs OpenAPI             (openapi_reader)
              Étape 11: Inférence MR                     (mr_inferrer)
              Étape 12: Écriture mr_catalog.yaml         (mr_catalog_writer)
ENTREES   : config/system_config.yaml
            config/services_map.yaml
SORTIES   : data/outputs/service_graph.json
            data/outputs/service_scores.json
            data/outputs/test_suite_T.json
            data/outputs/mr_catalog.yaml
LIBRAIRIES: argparse, logging, pathlib, yaml
USAGE     : python run_phase1.py --config ../config/system_config.yaml
"""

# TODO: implémenter le pipeline principal
# Structure attendue :
#   - load_config(config_path) -> dict
#   - run_pipeline(config) -> None  (enchaîne les 12 étapes)
#   - log_summary(artefacts) -> None  (affiche un résumé final)
#   - main() -> None  (point d'entrée argparse)
"""
run_phase1.py
=============
BLOC      : Orchestration Phase 1
ROLE      : Script principal d'orchestration de la Phase 1.
            Enchaîne toutes les étapes dans l'ordre correct et
            produit tous les artefacts Phase 1 :
              Étape 1 : Récupération traces Jaeger       (jaeger_client)
              Étape 2 : Parsing des spans                (span_parser)
              Étape 3 : Reconstruction T et edge_list    (trace_reconstructor)
              Étape 4 : Calcul des poids w_ij            (weight_calculator)
              Étape 5 : Construction du graphe G         (graph_builder)
              Étape 6 : Calcul C(si)                     (centrality)
              Étape 7 : Calcul P(si)                     (propagation_coeff)
              Étape 8 : Calcul F(si)                     (fragility)
              Étape 9 : Classification Écho-Dormant      (echo_dormant)
              Étape 10: Lecture specs OpenAPI             (openapi_reader)
              Étape 11: Inférence MR                     (mr_inferrer)
              Étape 12: Écriture mr_catalog.yaml         (mr_catalog_writer)
ENTREES   : config/system_config.yaml
            config/services_map.yaml
SORTIES   : data/outputs/service_graph.json
            data/outputs/service_scores.json
            data/outputs/test_suite_T.json
            data/outputs/mr_catalog.yaml
LIBRAIRIES: argparse, logging, pathlib, yaml
USAGE     : python run_phase1.py --config ../config/system_config.yaml
"""

"""
run_phase1.py — Orchestrateur principal Phase 1
"""
import argparse
import json
import logging
import sys
from pathlib import Path

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

    # ── Étape 1 : Récupération traces Jaeger ─────────────
    logger.info("── Étape 1/12 : Récupération traces Jaeger")
    client = JaegerClient(j_cfg["base_url"], j_cfg.get("api_version", "api"))
    traces = client.get_traces(
        service=j_cfg["default_service"],
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
              "invocation_chain": tp.invocation_chain}
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
        tau_dormant=ed_cfg["tau_dormant"],
        omega_C=ed_cfg["omega_C"],
        omega_P=ed_cfg["omega_P"],
        omega_F=ed_cfg["omega_F"],
    )
    scores = classifier.classify(C_scores, P_scores, F_scores)
    classifier.save(scores, resolve(paths["service_scores"]))

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