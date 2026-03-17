"""
fragility.py
============
BLOC      : Bloc B — Construction G
ROLE      : Calcule F(si) = fragilité opérationnelle observée pour
            chaque service — 100% automatique depuis les données Jaeger,
            sans aucune entrée manuelle (remplace l'ancien M(si)/SIL).
            Formule :
              err_out(si) = Σ erreurs(si→sj) / Σ freq(si→sj)
                            pour tous sj successeurs de si
              F(si) = norm(err_out(si))
                    = err_out(si) / max(err_out sur tous les services)
            Un service avec beaucoup d'erreurs sortantes est
            opérationnellement fragile → score F élevé.
ENTREES   : Dict {(si,sj): EdgeWeight}  (sortie de weight_calculator)
SORTIES   : Dict {service_name: float}  — scores F dans [0, 1]
LIBRAIRIES: numpy
NOTE      : Si un service n'a aucun arc sortant, F(si) = 0.0
"""

# TODO: implémenter FragilityCalculator
# Méthodes attendues :
#   - compute(edge_weights) -> Dict[str, float]
#   - _aggregate_errors(edge_weights) -> Dict[str, Tuple[int, int]]
#   - _normalize(raw_scores) -> Dict[str, float]
"""
fragility.py
============
BLOC      : Bloc B — Construction G
ROLE      : Calcule F(si) = fragilité opérationnelle observée pour
            chaque service — 100% automatique depuis les données Jaeger,
            sans aucune entrée manuelle (remplace l'ancien M(si)/SIL).
            Formule :
              err_out(si) = Σ erreurs(si→sj) / Σ freq(si→sj)
                            pour tous sj successeurs de si
              F(si) = norm(err_out(si))
                    = err_out(si) / max(err_out sur tous les services)
            Un service avec beaucoup d'erreurs sortantes est
            opérationnellement fragile → score F élevé.
ENTREES   : Dict {(si,sj): EdgeWeight}  (sortie de weight_calculator)
SORTIES   : Dict {service_name: float}  — scores F dans [0, 1]
LIBRAIRIES: numpy
NOTE      : Si un service n'a aucun arc sortant, F(si) = 0.0
"""

import logging
from collections import defaultdict
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

RawEdge = Tuple[str, str, int, bool]  # (source, target, duration_us, error)


class FragilityCalculator:
    """
    Calcule F(si) = fragilité opérationnelle observée pour chaque service.
    100% automatique depuis les données Jaeger — aucune entrée manuelle.

    Remplace l'ancien M(si)/SIL (subjectif) par une métrique observable.

    Formule :
        err_out(si) = Σ erreurs(si→sj) / Σ freq(si→sj)
                      pour tous les sj successeurs de si

        F(si) = norm(err_out(si))
              = err_out(si) / max(err_out sur tous les services)

    Cas limites :
        Aucun arc sortant    →  F(si) = 0.0
        Toutes erreurs = 0   →  F(si) = 0.0 pour tous
        max(err_out) = 0     →  F(si) = 0.0 pour tous (pas de division par 0)
    """

    def compute(self, edge_list: List[RawEdge]) -> Dict[str, float]:
        """
        Calcule F(si) pour chaque service source dans edge_list.

        Paramètre
        ---------
        edge_list : liste de (source, target, duration_us, error)

        Retourne
        --------
        Dict {service_name: F_score}  — valeurs dans [0, 1]
        """
        if not edge_list:
            logger.warning("FragilityCalculator : edge_list vide")
            return {}

        raw_scores = self._aggregate_errors(edge_list)
        normalized = self._normalize(raw_scores)

        logger.info(
            "FragilityCalculator → %d services scorés | max F=%.4f",
            len(normalized), max(normalized.values(), default=0),
        )
        return normalized

    # ── Méthodes privées ──────────────────────────────────

    def _aggregate_errors(
        self,
        edge_list: List[RawEdge],
    ) -> Dict[str, float]:
        """
        Calcule le taux d'erreur sortant brut par service source.
        Retourne {service_name: err_out_ratio}
        """
        total_calls: Dict[str, int] = defaultdict(int)
        total_errors: Dict[str, int] = defaultdict(int)

        for source, _, _, error in edge_list:
            total_calls[source] += 1
            if error:
                total_errors[source] += 1

        return {
            service: total_errors[service] / total_calls[service]
            for service in total_calls
        }

    def _normalize(self, raw_scores: Dict[str, float]) -> Dict[str, float]:
        """
        Normalise les scores bruts sur [0, 1].
        Si max = 0 (aucune erreur nulle part), tous les scores restent 0.
        """
        max_val = max(raw_scores.values(), default=0.0)
        if max_val == 0.0:
            return {k: 0.0 for k in raw_scores}
        return {
            k: round(v / max_val, 6)
            for k, v in raw_scores.items()
        }