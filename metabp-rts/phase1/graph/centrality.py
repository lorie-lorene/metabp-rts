"""
 Construction G    
            : Calcule C(si) = centralité structurelle pour chaque service :
              C(si) = α × norm(fan_in(si)) + β × norm(fan_out(si))
            fan_in  = nombre de services qui appellent si
            fan_out = nombre de services que si appelle
            norm(x) = x / max(x sur tous les services)
ENTREES   : NetworkX DiGraph G
SORTIES   : Dict {service_name: float}  — scores C dans [0, 1]
"""

import logging
from typing import Dict
import networkx as nx

logger = logging.getLogger(__name__)


class CentralityCalculator:
    """
    Calcule C(si) = centralité structurelle pour chaque service.
    Formule :C(si) = α × norm(fan_in(si)) + β × norm(fan_out(si))
    avec les mêmes α, β que WeightCalculator (par défaut α=0.5, β=0.3,renormalisés sur α+β = 1 car on n'a pas γ ici).
    pour le moment les valeurs des constantes sont definis de maniere temporaire, elles seront ajustés après les tests sur les données réelles.
    Normalisation : norm(x) = x / max(x sur tous les services).
    Si max = 0 (graphe sans arcs), tous les scores sont 0.
    
    """

    def __init__(self, alpha: float = 0.5, beta: float = 0.3):
        total = alpha + beta
        self.alpha = alpha / total
        self.beta = beta / total

    def compute(self, graph: nx.DiGraph) -> Dict[str, float]:
        
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


    def _normalize(self, values: Dict[str, int]) -> Dict[str, float]:
        max_val = max(values.values(), default=0)
        if max_val == 0:
            return {k: 0.0 for k in values}
        return {k: v / max_val for k, v in values.items()}