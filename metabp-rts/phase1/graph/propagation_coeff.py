"""
Calcule P(si) = coefficient de propagation pour chaque service mesure la transmissivité logique vers les  successeurs directs :
    P(si) = (1 / |Succ(si)|) × Σ w_ij   pour sj ∈ Succ(si)
    Si |Succ(si)| = 0, alors P(si) = 0
ENTREES   : NetworkX DiGraph G (avec attribut w_ij sur chaque arc)
SORTIES   : Dict {service_name: float}  — scores P dans [0, 1]
"""


import logging
from typing import Dict, List

import networkx as nx

logger = logging.getLogger(__name__)


class PropagationCalculator:

    def compute(self, graph: nx.DiGraph) -> Dict[str, float]:
        if graph.number_of_nodes() == 0:
            return {}

        scores: Dict[str, float] = {}

        for node in graph.nodes():
            weights = self._successor_weights(graph, node)
            if not weights:
                scores[node] = 0.0
            else:
                scores[node] = round(sum(weights) / len(weights), 6)

        logger.info(
            "PropagationCalculator → %d services scorés | max P=%.4f",
            len(scores), max(scores.values(), default=0),
        )
        return scores

    # ── Méthode privée ────────────────────────────────────

    def _successor_weights(self, graph: nx.DiGraph, node: str) -> List[float]:
        return [
            data.get("w_ij", 0.0)
            for _, _, data in graph.out_edges(node, data=True)
        ]