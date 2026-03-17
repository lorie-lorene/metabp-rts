"""
weight_calculator.py
====================
BLOC      : Bloc B — Construction G
ROLE      : Calcule les trois composantes du poids w_ij pour chaque
            arc (si → sj) depuis l'edge_list :
              - rate_ij  = freq_ij / total_spans(si)
              - lat_norm = mean(duration si→sj) / max(duration global)
              - err_ij   = erreurs(si→sj) / freq_ij
              - w_ij     = α×rate + β×lat_norm + γ×err
ENTREES   : edge_list : List[Tuple[str, str, int, bool]]
            config    : {alpha, beta, gamma}
SORTIES   : Dict {(si,sj): EdgeWeight}
LIBRAIRIES: numpy, collections
"""

# TODO: implémenter WeightCalculator
# Méthodes attendues :
#   - __init__(alpha, beta, gamma)
#   - compute(edge_list) -> Dict[Tuple, EdgeWeight]
#   - _compute_rates(edge_list) -> Dict
#   - _compute_latencies(edge_list) -> Dict
#   - _compute_errors(edge_list) -> Dict
#   - _normalize(values) -> Dict
"""
weight_calculator.py
====================
BLOC      : Bloc B — Construction G
ROLE      : Calcule les trois composantes du poids w_ij pour chaque
            arc (si → sj) depuis l'edge_list :
              - rate_ij  = freq_ij / total_spans(si)
              - lat_norm = mean(duration si→sj) / max(duration global)
              - err_ij   = erreurs(si→sj) / freq_ij
              - w_ij     = α×rate + β×lat_norm + γ×err
ENTREES   : edge_list : List[Tuple[str, str, int, bool]]
            config    : {alpha, beta, gamma}
SORTIES   : Dict {(si,sj): EdgeWeight}
LIBRAIRIES: numpy, collections
"""

import logging
from collections import defaultdict
from typing import Dict, List, Tuple

import numpy as np

from models.models import EdgeWeight

logger = logging.getLogger(__name__)

# Type alias pour la clarté
Edge = Tuple[str, str]
RawEdge = Tuple[str, str, int, bool]  # (source, target, duration_us, error)


class WeightCalculator:
    """
    Calcule les poids w_ij pour chaque arc (si → sj) du graphe G.

    Formule :
        w_ij = α × rate_ij + β × lat_norm + γ × err_ij

    avec :
        rate_ij  = freq(si→sj) / Σ freq(si→*)   fréquence relative
        lat_norm = mean(duration si→sj) / max(mean duration global)
        err_ij   = erreurs(si→sj) / freq(si→sj)

    Invariant vérifié : α + β + γ = 1.0
    """

    def __init__(self, alpha: float = 0.5, beta: float = 0.3, gamma: float = 0.2):
        assert abs(alpha + beta + gamma - 1.0) < 1e-9, (
            f"α+β+γ doit valoir 1.0, obtenu {alpha+beta+gamma}"
        )
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma

    def compute(self, edge_list: List[RawEdge]) -> Dict[Edge, EdgeWeight]:
        """
        Calcule EdgeWeight pour chaque arc unique (si, sj).

        Paramètre
        ---------
        edge_list : liste brute de (source, target, duration_us, error)
                    — peut contenir des doublons (même arc, occurrences multiples)

        Retourne
        --------
        Dict {(si, sj): EdgeWeight}
        """
        if not edge_list:
            logger.warning("WeightCalculator : edge_list vide — aucun poids calculé")
            return {}

        # Agrégation par arc
        freq: Dict[Edge, int] = defaultdict(int)
        total_duration: Dict[Edge, int] = defaultdict(int)
        error_count: Dict[Edge, int] = defaultdict(int)

        for source, target, duration, error in edge_list:
            edge = (source, target)
            freq[edge] += 1
            total_duration[edge] += duration
            if error:
                error_count[edge] += 1

        # Fréquence totale sortante par service source
        total_out: Dict[str, int] = defaultdict(int)
        for (source, _), count in freq.items():
            total_out[source] += count

        # Latence moyenne par arc
        mean_lat: Dict[Edge, float] = {
            edge: total_duration[edge] / freq[edge]
            for edge in freq
        }

        # Normalisation de la latence sur [0, 1]
        max_lat = max(mean_lat.values()) if mean_lat else 1.0
        # Éviter la division par zéro si tous les arcs ont latence 0
        if max_lat == 0:
            max_lat = 1.0

        # Construction des EdgeWeight
        results: Dict[Edge, EdgeWeight] = {}
        for edge, count in freq.items():
            source, target = edge
            rate = count / total_out[source] if total_out[source] > 0 else 0.0
            lat_n = mean_lat[edge] / max_lat
            err = error_count[edge] / count

            w = self.alpha * rate + self.beta * lat_n + self.gamma * err

            results[edge] = EdgeWeight(
                source=source,
                target=target,
                freq=count,
                rate_ij=round(rate, 6),
                lat_norm=round(lat_n, 6),
                err_ij=round(err, 6),
                w_ij=round(w, 6),
            )

        logger.info(
            "WeightCalculator → %d arcs uniques calculés (α=%.1f β=%.1f γ=%.1f)",
            len(results), self.alpha, self.beta, self.gamma,
        )
        return results