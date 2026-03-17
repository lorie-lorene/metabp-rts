"""
propagation_coeff.py
====================
BLOC      : Bloc B — Construction G
ROLE      : Calcule P(si) = coefficient de propagation pour chaque
            service — mesure la transmissivité logique vers les
            successeurs directs :
              P(si) = (1 / |Succ(si)|) × Σ w_ij   pour sj ∈ Succ(si)
            Si |Succ(si)| = 0, alors P(si) = 0.
ENTREES   : NetworkX DiGraph G (avec attribut w_ij sur chaque arc)
SORTIES   : Dict {service_name: float}  — scores P dans [0, 1]
LIBRAIRIES: networkx, numpy
"""

# TODO: implémenter PropagationCalculator
# Méthodes attendues :
#   - compute(graph) -> Dict[str, float]
#   - _successors_weights(graph, node) -> List[float]
"""
propagation_coeff.py
====================
BLOC      : Bloc B — Construction G
ROLE      : Calcule P(si) = coefficient de propagation pour chaque
            service — mesure la transmissivité logique vers les
            successeurs directs :
              P(si) = (1 / |Succ(si)|) × Σ w_ij   pour sj ∈ Succ(si)
            Si |Succ(si)| = 0, alors P(si) = 0.
ENTREES   : NetworkX DiGraph G (avec attribut w_ij sur chaque arc)
SORTIES   : Dict {service_name: float}  — scores P dans [0, 1]
LIBRAIRIES: networkx, numpy
"""

import logging
from typing import Dict, List

import networkx as nx

logger = logging.getLogger(__name__)


class PropagationCalculator:
    """
    Calcule P(si) = coefficient de propagation pour chaque service.

    Formule :
        P(si) = (1 / |Succ(si)|) × Σ w_ij   pour sj ∈ Succ(si)

    Interprétation : probabilité moyenne qu'un impact se propage
    depuis si vers l'un de ses successeurs directs.

    Cas limites :
        |Succ(si)| = 0  →  P(si) = 0.0  (service feuille, pas de propagation)
        w_ij manquant   →  w_ij = 0.0   (arc sans poids traité comme neutre)
    """

    def compute(self, graph: nx.DiGraph) -> Dict[str, float]:
        """
        Calcule P(si) pour chaque noeud du graphe.

        Retourne
        --------
        Dict {service_name: P_score}  — valeurs dans [0, 1]
        """
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
        """
        Retourne la liste des poids w_ij des arcs sortants de node.
        Si l'attribut w_ij est absent sur un arc, utilise 0.0.
        """
        return [
            data.get("w_ij", 0.0)
            for _, _, data in graph.out_edges(node, data=True)
        ]