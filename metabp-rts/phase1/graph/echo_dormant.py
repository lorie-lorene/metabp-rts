"""
echo_dormant.py
===============
BLOC      : Phase 1 — Classification des services
ROLE      : Calcule Θ_dormant(si) et classifie chaque service comme
            Écho-Dormant ou Non-Dormant.

FORMULE :
    Θ_dormant(si) = ω_C × C(si) + ω_P × P(si) + ω_F × F(si)

PONDÉRATION (MetaBP-RTS) :
    Les poids ω_C, ω_P, ω_F sont dérivés OBJECTIVEMENT des données
    observées par la méthode combinée EWM-CRITIC :

    EWM  (Shannon, 1948)      : poids proportionnel à la dispersion
    CRITIC (Diakoulaki, 1995) : pénalise les critères corrélés

    Fusion : ω_j = ω_EWM(j) × ω_CRITIC(j) / Σ[ω_EWM(k) × ω_CRITIC(k)]

    Un critère obtient un poids élevé seulement s'il est à la fois
    très dispersé ET peu corrélé aux autres. Les poids sont recalculés
    à chaque ingestion de traces — la pondération est adaptative.

    Référence : Shannon (1948), Diakoulaki et al. (1995), Ma et al. (1999)

CLASSIFICATION :
    Θ_dormant(si) >= τ_dormant  →  Service Écho-Dormant
    Θ_dormant(si) <  τ_dormant  →  Service Non-Dormant

SÉMANTIQUE DU SERVICE ÉCHO-DORMANT (MetaBP-RTS) :
    Un Service Écho-Dormant est un service qui présente, AVANT tout
    changement ΔS, une fragilité structurelle élevée — il est au
    carrefour de nombreux chemins (C élevée), propage loin tout
    problème (P élevée), et génère déjà des erreurs en production
    (F élevée). Il est qualifié de "dormant" car cette fragilité
    est silencieuse tant qu'aucun changement n'est effectué.

PRINCIPE DE RÉSONANCE DIFFÉRÉE :
    Écho-Dormant (Phase 1) + ΔS  →  Écho-Impact (Phase 2)

ENTREES   : - Dict C : {service_name: float}
            - Dict P : {service_name: float}
            - Dict F : {service_name: float}
            - config  : {tau_dormant}
SORTIES   : - List[ServiceScore] avec theta_dormant et is_dormant
            - S_dormant : List[str]
            - weights_report : poids EWM-CRITIC calculés
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

from models.models import ServiceScore
from graph.ewm_critic import EWMCRITICWeightCalculator

logger = logging.getLogger(__name__)


class EchoDormantClassifier:
    def __init__(
        self,
        tau_dormant: float = 0.40,
        # Poids fixes gardés uniquement comme fallback
        omega_C: float = 0.357,
        omega_P: float = 0.357,
        omega_F: float = 0.286,
        weighting_method: str = "ewm_critic",
    ):
        """
        Parameters
        ----------
        tau_dormant : seuil de classification Écho-Dormant
        omega_C, omega_P, omega_F : poids fixes (fallback si weighting_method="fixed")
        weighting_method : "ewm_critic" (défaut, objectif) ou "fixed" (legacy)
        """
        self.tau_dormant      = tau_dormant
        self.omega_C_fixed    = omega_C
        self.omega_P_fixed    = omega_P
        self.omega_F_fixed    = omega_F
        self.weighting_method = weighting_method

        # Poids calculés (remplis par classify si ewm_critic)
        self.omega_C = omega_C
        self.omega_P = omega_P
        self.omega_F = omega_F
        self.weights_details = None

    def _compute_ewm_critic_weights(
        self,
        C_scores: Dict[str, float],
        P_scores: Dict[str, float],
        F_scores: Dict[str, float],
        all_services: list,
    ) -> Tuple[float, float, float, Dict]:
        """
        Calcule ω_C, ω_P, ω_F par la méthode combinée EWM-CRITIC.
        """
        matrix = np.array([
            [C_scores.get(s, 0.0), P_scores.get(s, 0.0), F_scores.get(s, 0.0)]
            for s in all_services
        ])
        criteria = ["C", "P", "F"]

        calc = EWMCRITICWeightCalculator()
        weights, details = calc.compute_combined_weights(matrix, criteria)

        return float(weights[0]), float(weights[1]), float(weights[2]), details

    def classify(
        self,
        C_scores: Dict[str, float],
        P_scores: Dict[str, float],
        F_scores: Dict[str, float],
    ) -> List[ServiceScore]:

        all_services = sorted(set(C_scores) | set(P_scores) | set(F_scores))

        # Calcul des poids selon la méthode choisie
        if self.weighting_method == "ewm_critic":
            self.omega_C, self.omega_P, self.omega_F, self.weights_details = \
                self._compute_ewm_critic_weights(C_scores, P_scores, F_scores, all_services)
            logger.info(
                "EWM-CRITIC → ω_C=%.4f  ω_P=%.4f  ω_F=%.4f",
                self.omega_C, self.omega_P, self.omega_F,
            )
        else:
            self.omega_C = self.omega_C_fixed
            self.omega_P = self.omega_P_fixed
            self.omega_F = self.omega_F_fixed
            self.weights_details = {
                "method": "fixed",
                "weights_combined": {
                    "C": self.omega_C, "P": self.omega_P, "F": self.omega_F
                },
            }
            logger.info(
                "Poids fixes → ω_C=%.4f  ω_P=%.4f  ω_F=%.4f",
                self.omega_C, self.omega_P, self.omega_F,
            )

        scores: List[ServiceScore] = []

        for service in all_services:
            c = C_scores.get(service, 0.0)
            p = P_scores.get(service, 0.0)
            f = F_scores.get(service, 0.0)

            theta = round(
                self.omega_C * c + self.omega_P * p + self.omega_F * f,
                6,
            )
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
            "EchoDormantClassifier → %d services | %d Écho-Dormants | %d Non-Dormants",
            len(scores), dormant_count, len(scores) - dormant_count,
        )
        return scores

    def get_dormant_set(self, scores: List[ServiceScore]) -> List[str]:
        """Retourne S_dormant — ensemble des services Écho-Dormants."""
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
        """Sauvegarde les poids EWM-CRITIC calculés pour documentation."""
        if self.weights_details:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            report = {
                "weighting_method": self.weighting_method,
                "tau_dormant": self.tau_dormant,
                "weights_applied": {
                    "omega_C": round(self.omega_C, 6),
                    "omega_P": round(self.omega_P, 6),
                    "omega_F": round(self.omega_F, 6),
                },
                "details": self.weights_details,
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            logger.info("Poids EWM-CRITIC Phase 1 → %s", path)

    def verify_safety_theorem(
        self, scores: List[ServiceScore]
    ) -> Tuple[bool, List[str]]:
        dormants      = [s for s in scores if s.is_dormant]
        non_dormants  = [s for s in scores if not s.is_dormant]

        if not dormants:
            logger.warning(
                "Théorème de Résonance : aucun service Écho-Dormant détecté "
                "— vérifier τ_dormant=%.2f ou enrichir le trafic Jaeger.",
                self.tau_dormant,
            )
            return True, []

        if not non_dormants:
            logger.warning(
                "Théorème de Résonance : tous les services sont Écho-Dormants "
                "— τ_dormant=%.2f peut être trop bas.",
                self.tau_dormant,
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
                "Services en zone grise : %s. "
                "Recalibrer τ_dormant ou enrichir les métriques C/P/F.",
                min_theta_dormant, max_theta_non_dormant, violators,
            )
            return False, violators
