"""
centrality.py
=============
BLOC      : Bloc B — Construction G
ROLE      : Calcule C(si) = centralité structurelle pour chaque service :
              C(si) = α × norm(fan_in(si)) + β × norm(fan_out(si))
            fan_in  = nombre de services qui appellent si
            fan_out = nombre de services que si appelle
            norm(x) = x / max(x sur tous les services)
ENTREES   : NetworkX DiGraph G
SORTIES   : Dict {service_name: float}  — scores C dans [0, 1]
LIBRAIRIES: networkx
"""

# TODO: implémenter CentralityCalculator
# Méthodes attendues :
#   - compute(graph) -> Dict[str, float]
#   - _fan_in(graph) -> Dict[str, int]
#   - _fan_out(graph) -> Dict[str, int]
#   - _normalize(scores) -> Dict[str, float]
"""
centrality.py
=============
BLOC      : Bloc B — Construction G
ROLE      : Calcule C(si) = centralité structurelle pour chaque service :
              C(si) = α × norm(fan_in(si)) + β × norm(fan_out(si))
            fan_in  = nombre de services qui appellent si
            fan_out = nombre de services que si appelle
            norm(x) = x / max(x sur tous les services)
ENTREES   : NetworkX DiGraph G
SORTIES   : Dict {service_name: float}  — scores C dans [0, 1]
LIBRAIRIES: networkx
"""

import logging
from typing import Dict

import networkx as nx

logger = logging.getLogger(__name__)


class CentralityCalculator:
    """
    Calcule C(si) = centralité structurelle pour chaque service.

    Formule :
        C(si) = α × norm(fan_in(si)) + β × norm(fan_out(si))

    avec les mêmes α, β que WeightCalculator (par défaut α=0.5, β=0.3
    renormalisés sur α+β = 1 car on n'a pas γ ici).

    Normalisation : norm(x) = x / max(x sur tous les services).
    Si max = 0 (graphe sans arcs), tous les scores sont 0.
    """

    def __init__(self, alpha: float = 0.5, beta: float = 0.3):
        total = alpha + beta
        # Renormaliser pour que la somme vaille 1
        self.alpha = alpha / total
        self.beta = beta / total

    def compute(self, graph: nx.DiGraph) -> Dict[str, float]:
        """
        Calcule C(si) pour chaque noeud du graphe.

        Retourne
        --------
        Dict {service_name: C_score}  — valeurs dans [0, 1]
        """
        if graph.number_of_nodes() == 0:
            return {}

        fan_in = dict(graph.in_degree())
        fan_out = dict(graph.out_degree())

        fan_in_norm = self._normalize(fan_in)
        fan_out_norm = self._normalize(fan_out)

        scores = {
            node: round(
                self.alpha * fan_in_norm.get(node, 0.0)
                + self.beta * fan_out_norm.get(node, 0.0),
                6,
            )
            for node in graph.nodes()
        }

        logger.info(
            "CentralityCalculator → %d services scorés | max C=%.4f",
            len(scores), max(scores.values(), default=0),
        )
        return scores

    # ── Méthode privée ────────────────────────────────────

    def _normalize(self, values: Dict[str, int]) -> Dict[str, float]:
        """
        Normalise un dict de valeurs entières sur [0, 1].
        Si toutes les valeurs sont 0, retourne un dict de 0.
        """
        max_val = max(values.values(), default=0)
        if max_val == 0:
            return {k: 0.0 for k in values}
        return {k: v / max_val for k, v in values.items()}