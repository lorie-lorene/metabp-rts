#!/usr/bin/env python3
"""
Analyse du graphe DeathStarBench avec les modules d'analyse du pipeline MetaBP-RTS.
Démontre la PORTABILITÉ : les modules graph/ (centrality, propagation, fragility,
echo_dormant) s'appliquent SANS MODIFICATION au graphe gRPC de hotelReservation.

Reproduit les étapes 6-9 de run_phase1.py, en partant du graphe et du corpus
déjà produits par l'ingesteur gRPC (extract_dsb_full.py), sans refaire l'ingestion HTTP.

À lancer depuis phase1/scripts/ :
    python analyze_dsb.py
Pré-requis : test_suite_T.json et service_graph.json (DSB) déjà dans data/outputs/
"""
import json, sys, logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import networkx as nx
from graph.centrality import CentralityCalculator
from graph.propagation_coeff import PropagationCalculator
from graph.fragility import FragilityCalculator
from graph.echo_dormant import EchoDormantClassifier

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("analyze_dsb")

base = Path(__file__).parent.parent  # phase1/
GRAPH = base / "data/outputs/service_graph.json"
CORPUS = base / "data/outputs/test_suite_T.json"
SCORES_OUT = base / "data/outputs/service_scores.json"
WEIGHTS_OUT = base / "data/outputs/ewm_critic_weights_phase1.json"

logger.info("── Analyse DeathStarBench (portabilité) ──")

# 1) Charger le graphe DSB (format node-link NetworkX)
graph_data = json.load(open(GRAPH, encoding="utf-8"))
G = nx.node_link_graph(graph_data, directed=True, multigraph=False)
logger.info("Graphe chargé : %d nœuds, %d arcs", G.number_of_nodes(), G.number_of_edges())

# 2) Reconstruire l'edge_list depuis le corpus DSB
#    Format attendu par FragilityCalculator : List[(source, target, duration, error)]
corpus = json.load(open(CORPUS, encoding="utf-8"))
edge_list = []
for tc in corpus:
    dur = tc.get("duration_us", 0)
    for pair in tc.get("invocation_chain", []):
        # error non disponible au niveau arc dans le corpus agrégé → False
        # (cohérent avec Train-Ticket : F=0 si pas d'erreur inter-service observée)
        edge_list.append((pair[0], pair[1], dur, False))
logger.info("edge_list reconstruite : %d arcs bruts", len(edge_list))

# 3) Calculer C, P, F avec les MODULES DU PIPELINE (aucune modification)
logger.info("── Étape C : centralité")
C_scores = CentralityCalculator().compute(G)
logger.info("── Étape P : propagation")
P_scores = PropagationCalculator().compute(G)
logger.info("── Étape F : fragilité")
F_scores = FragilityCalculator().compute(edge_list)

# 4) Classification Écho-Dormant (EWM-CRITIC + seuil K-means)
logger.info("── Classification Écho-Dormant")
classifier = EchoDormantClassifier(
    weighting_method="ewm_critic", threshold_method="auto", k_clusters=3,
)
scores = classifier.classify(C_scores, P_scores, F_scores)
classifier.save(scores, str(SCORES_OUT))
classifier.save_weights(str(WEIGHTS_OUT))

# 5) Théorème de sécurité
ok, violators = classifier.verify_safety_theorem(scores)
S_dormant = classifier.get_dormant_set(scores)

# 6) Résumé
print("\n" + "="*64)
print("ANALYSE DEATHSTARBENCH — Résultats (portabilité)")
print("="*64)
print(f"Graphe G      : {G.number_of_nodes()} nœuds, {G.number_of_edges()} arcs")
print(f"Écho-Dormants : {len(S_dormant)}/{len(scores)}")
print(f"τ_dormant     : {classifier.tau_dormant:.4f}")
print(f"Poids EWM     : ω_C={classifier.omega_C:.4f} ω_P={classifier.omega_P:.4f} ω_F={classifier.omega_F:.4f}")
print(f"Théorème      : {'VÉRIFIÉ ✓' if ok else 'VIOLÉ ✗ ' + str(violators)}")
print()
print(f"{'Service':<16}{'C':>8}{'P':>8}{'F':>8}{'Θ':>9}  {'Classe'}")
print("-"*64)
for s in scores:
    cls = "ÉCHO-DORMANT" if s.is_dormant else "non-dormant"
    print(f"{s.service_name:<16}{s.C:>8.4f}{s.P:>8.4f}{s.F:>8.4f}{s.theta_dormant:>9.4f}  {cls}")
print("="*64)
print(f"\n→ {SCORES_OUT}")
print(f"→ {WEIGHTS_OUT}")
