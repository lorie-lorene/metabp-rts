"""
echo_dormant.py
===============
BLOC      : Phase 1 — Classification des services
ROLE      : Calcule Θ_dormant(si) et classifie chaque service comme
            Écho-Dormant ou Non-Dormant.

APPROCHE DATA-DRIVEN COMPLÈTE (MetaBP-RTS) :
    Aucun paramètre arbitraire. Tout est dérivé des données observées.

    1. POIDS — Méthode combinée EWM-CRITIC :
       ω_C, ω_P, ω_F calculés objectivement depuis les scores C, P, F.
       Un critère obtient un poids élevé seulement s'il est à la fois
       très dispersé (EWM) ET peu corrélé aux autres (CRITIC).

    2. SEUIL — K-means (k=3) + frontière inter-clusters :
       τ_dormant = (min(Cluster_haut) + max(Cluster_intermédiaire)) / 2
       Le choix k=3 est justifié par l'objectif RTS : identifier un
       sous-ensemble RESTREINT de services à risque, pas une majorité.

FORMULE :
    Θ_dormant(si) = ω_C × C(si) + ω_P × P(si) + ω_F × F(si)

    Θ_dormant(si) >= τ_dormant  →  Service Écho-Dormant
    Θ_dormant(si) <  τ_dormant  →  Service Non-Dormant

RÉFÉRENCES :
    [1] Shannon, C.E. (1948). A Mathematical Theory of Communication.
    [2] Diakoulaki, D. et al. (1995). The CRITIC method. C&OR 22(7).
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

from models.models import ServiceScore
from graph.ewm_critic import EWMCRITICWeightCalculator, AutoThreshold

logger = logging.getLogger(__name__)


class EchoDormantClassifier:
    def __init__(
        self,
        tau_dormant: float = None,
        omega_C: float = 0.357,
        omega_P: float = 0.357,
        omega_F: float = 0.286,
        weighting_method: str = "ewm_critic",
        threshold_method: str = "auto",
        k_clusters: int = 3,
    ):
        """
        Parameters
        ----------
        tau_dormant      : seuil fixe (utilisé si threshold_method="fixed")
                           Si None et threshold_method="auto", dérivé des données.
        omega_C/P/F      : poids fixes (fallback si weighting_method="fixed")
        weighting_method : "ewm_critic" (défaut) ou "fixed"
        threshold_method : "auto" (défaut, K-means) ou "fixed"
        k_clusters       : nombre de clusters pour AutoThreshold (défaut 3)
        """
        self.tau_dormant_fixed = tau_dormant
        self.omega_C_fixed     = omega_C
        self.omega_P_fixed     = omega_P
        self.omega_F_fixed     = omega_F
        self.weighting_method  = weighting_method
        self.threshold_method  = threshold_method
        self.k_clusters        = k_clusters

        # Valeurs calculées (remplies par classify)
        self.tau_dormant       = tau_dormant
        self.omega_C           = omega_C
        self.omega_P           = omega_P
        self.omega_F           = omega_F
        self.weights_details   = None
        self.threshold_details = None

    def _compute_weights(
        self,
        C_scores: Dict[str, float],
        P_scores: Dict[str, float],
        F_scores: Dict[str, float],
        all_services: list,
    ) -> None:
        """Calcule les poids par EWM-CRITIC ou utilise les poids fixes."""
        if self.weighting_method == "ewm_critic":
            matrix = np.array([
                [C_scores.get(s, 0.0), P_scores.get(s, 0.0), F_scores.get(s, 0.0)]
                for s in all_services
            ])
            calc = EWMCRITICWeightCalculator()
            weights, details = calc.compute_combined_weights(matrix, ["C", "P", "F"])
            self.omega_C, self.omega_P, self.omega_F = float(weights[0]), float(weights[1]), float(weights[2])
            self.weights_details = details
            logger.info(
                "Poids EWM-CRITIC → ω_C=%.4f  ω_P=%.4f  ω_F=%.4f",
                self.omega_C, self.omega_P, self.omega_F,
            )
        else:
            self.omega_C = self.omega_C_fixed
            self.omega_P = self.omega_P_fixed
            self.omega_F = self.omega_F_fixed
            self.weights_details = {
                "method": "fixed",
                "weights_combined": {"C": self.omega_C, "P": self.omega_P, "F": self.omega_F},
            }

    def _compute_threshold(self, thetas: np.ndarray) -> None:
        """Calcule τ_dormant par AutoThreshold ou utilise la valeur fixe."""
        if self.threshold_method == "auto":
            self.tau_dormant, self.threshold_details = AutoThreshold.compute(
                thetas, k=self.k_clusters,
            )
            logger.info("Seuil auto (K-means k=%d) → τ_dormant=%.4f", self.k_clusters, self.tau_dormant)
        else:
            if self.tau_dormant_fixed is None:
                self.tau_dormant = 0.35
                logger.warning("τ_dormant non spécifié → défaut 0.35")
            else:
                self.tau_dormant = self.tau_dormant_fixed
            self.threshold_details = {
                "method": "fixed",
                "tau": self.tau_dormant,
            }

    def classify(
        self,
        C_scores: Dict[str, float],
        P_scores: Dict[str, float],
        F_scores: Dict[str, float],
    ) -> List[ServiceScore]:

        all_services = sorted(set(C_scores) | set(P_scores) | set(F_scores))

        # ── Étape 1 : Calcul des poids ──
        self._compute_weights(C_scores, P_scores, F_scores, all_services)

        # ── Étape 2 : Calcul de Θ_dormant pour chaque service ──
        thetas_list = []
        for service in all_services:
            c = C_scores.get(service, 0.0)
            p = P_scores.get(service, 0.0)
            f = F_scores.get(service, 0.0)
            theta = self.omega_C * c + self.omega_P * p + self.omega_F * f
            thetas_list.append(theta)

        thetas_array = np.array(thetas_list)

        # ── Étape 3 : Calcul automatique du seuil τ ──
        self._compute_threshold(thetas_array)

        # ── Étape 4 : Classification ──
        scores: List[ServiceScore] = []
        for i, service in enumerate(all_services):
            c = C_scores.get(service, 0.0)
            p = P_scores.get(service, 0.0)
            f = F_scores.get(service, 0.0)
            theta = round(thetas_list[i], 6)
            is_dormant = theta >= self.tau_dormant

            scores.append(ServiceScore(
                service_name=service,
                C=round(c, 6),
                P=round(p, 6),
                F=round(f, 6),
                theta_dormant=theta,
                is_dormant=is_dormant,
            ))

        scores.sort(key=lambda s: s.theta_dormant, reverse=True)

        dormant_count = sum(1 for s in scores if s.is_dormant)
        logger.info(
            "EchoDormantClassifier → %d services | %d Écho-Dormants | %d Non-Dormants | τ=%.4f",
            len(scores), dormant_count, len(scores) - dormant_count, self.tau_dormant,
        )
        return scores

    def get_dormant_set(self, scores: List[ServiceScore]) -> List[str]:
        return [s.service_name for s in scores if s.is_dormant]

    def save(self, scores: List[ServiceScore], output_path: str) -> None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = [
            {
                "service_name": s.service_name,
                "C": s.C,
                "P": s.P,
                "F": s.F,
                "theta_dormant": s.theta_dormant,
                "is_dormant": s.is_dormant,
            }
            for s in scores
        ]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("Scores sauvegardés → %s (%d services)", path, len(scores))

    def save_weights(self, output_path: str) -> None:
        """Sauvegarde les poids ET le seuil calculés pour documentation."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        report = {
            "weighting": {
                "method": self.weighting_method,
                "omega_C": round(self.omega_C, 6),
                "omega_P": round(self.omega_P, 6),
                "omega_F": round(self.omega_F, 6),
                "details": self.weights_details,
            },
            "threshold": {
                "method": self.threshold_method,
                "tau_dormant": round(self.tau_dormant, 6) if self.tau_dormant else None,
                "details": self.threshold_details,
            },
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.info("Rapport EWM-CRITIC + AutoThreshold → %s", path)

    def verify_safety_theorem(
        self, scores: List[ServiceScore]
    ) -> Tuple[bool, List[str]]:
        dormants      = [s for s in scores if s.is_dormant]
        non_dormants  = [s for s in scores if not s.is_dormant]

        if not dormants:
            logger.warning(
                "Théorème de Résonance : aucun service Écho-Dormant détecté "
                "— vérifier le clustering ou enrichir le trafic Jaeger.",
            )
            return True, []

        if not non_dormants:
            logger.warning(
                "Théorème de Résonance : tous les services sont Écho-Dormants "
                "— le clustering peut être dégénéré.",
            )
            return True, []

        min_theta_dormant     = min(s.theta_dormant for s in dormants)
        max_theta_non_dormant = max(s.theta_dormant for s in non_dormants)

        separation_nette = min_theta_dormant > max_theta_non_dormant

        if separation_nette:
            logger.info(
                "Théorème de Sécurité d'Exclusion : OK   "
                "(min_dormant=%.4f > max_non_dormant=%.4f)",
                min_theta_dormant, max_theta_non_dormant,
            )
            return True, []
        else:
            violators = [
                s.service_name
                for s in non_dormants
                if s.theta_dormant >= min_theta_dormant
            ]
            logger.warning(
                "Théorème de Résonance : chevauchement Θ détecté — "
                "min_dormant=%.4f ≤ max_non_dormant=%.4f. "
                "Services en zone grise : %s.",
                min_theta_dormant, max_theta_non_dormant, violators,
            )
            return False, violators
