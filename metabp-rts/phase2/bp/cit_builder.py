"""
cit_builder.py
==============
BLOC      : Phase 2 — Étapes 4 et 5
ROLE      : Construit la CIT, calcule le score Θ_complet (Phase 1 + BP),
            identifie S_écho-impact, et prépare le tiering pour Phase 3.

SCORE COMPLET (MetaBP-RTS) :
    Θ_complet(si) = ω_Θ × Θ_dormant(si) + ω_B × CIT(si)

PONDÉRATION (MetaBP-RTS) :
    Les poids ω_Θ et ω_B sont dérivés OBJECTIVEMENT des données
    observées par la méthode combinée EWM-CRITIC :

    EWM  (Shannon, 1948)      : poids proportionnel à la dispersion
    CRITIC (Diakoulaki, 1995) : pénalise les critères corrélés

    En Phase 2, CIT apporte l'information NOUVELLE (impact dynamique
    de ΔS), tandis que Θ_dormant est un score structurel pré-existant.
    EWM-CRITIC attribue automatiquement un poids plus élevé au critère
    le plus discriminant — typiquement CIT, car sa dispersion est plus
    forte (de 0 à 1.0) que celle de Θ_dormant.

TIERING (préparation Phase 3) :
    Tier 1 = tests qui traversent au moins un service de S_écho-impact
             --> tous conservés (100% Recall garanti)
    Tier 2 = tests qui ne traversent aucun service de S_écho-impact
             --> optimisés par PSO en Phase 3
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Set

import numpy as np

logger = logging.getLogger(__name__)


class CITBuilder:

    def __init__(
        self,
        tau_impact: float = 0.30,
        omega_B: float = 0.30,
        weighting_method: str = "ewm_critic",
    ):
        """
        Parameters
        ----------
        tau_impact : seuil pour identifier un Service Écho-Impact
        omega_B    : poids fixe de B(si) (fallback si weighting_method="fixed")
        weighting_method : "ewm_critic" (défaut, objectif) ou "fixed" (legacy)
        """
        self.tau_impact       = tau_impact
        self.omega_B_fixed    = omega_B
        self.weighting_method = weighting_method

        # Poids calculés (remplis par build si ewm_critic)
        self.omega_theta = None
        self.omega_B     = omega_B
        self.weights_details = None

    def _compute_ewm_critic_weights(
        self,
        theta_dormants: Dict[str, float],
        cit_values: Dict[str, float],
        all_services: list,
    ) -> tuple:
        """
        Calcule ω_Θ et ω_B par la méthode combinée EWM-CRITIC.
        """
        from bp.ewm_critic import EWMCRITICWeightCalculator

        matrix = np.array([
            [theta_dormants.get(s, 0.0), cit_values.get(s, 0.0)]
            for s in all_services
        ])
        criteria = ["Θ_dormant", "CIT"]

        calc = EWMCRITICWeightCalculator()
        weights, details = calc.compute_combined_weights(matrix, criteria)

        return float(weights[0]), float(weights[1]), details

    def build(
        self,
        p_final: Dict[str, float],
        delta_s: List[str],
        scores: Dict[str, Dict],
    ) -> Dict:

        delta_set: Set[str] = set(delta_s)
        cit = dict(p_final)

        # Préparer les données pour EWM-CRITIC
        all_services = sorted(cit.keys())

        theta_dormants = {
            s: float(scores.get(s, {}).get("theta_dormant", 0.0))
            for s in all_services
        }

        # Calcul des poids selon la méthode choisie
        if self.weighting_method == "ewm_critic":
            self.omega_theta, self.omega_B, self.weights_details = \
                self._compute_ewm_critic_weights(theta_dormants, cit, all_services)
            logger.info(
                "EWM-CRITIC Phase 2 → ω_Θ=%.4f  ω_B=%.4f",
                self.omega_theta, self.omega_B,
            )
        else:
            # Mode legacy : Θ_complet = Θ_dormant + ω_B × CIT
            # Équivalent à ω_Θ=1.0, ω_B=config
            self.omega_theta = 1.0
            self.omega_B     = self.omega_B_fixed
            self.weights_details = {
                "method": "fixed",
                "weights_combined": {
                    "Θ_dormant": 1.0, "CIT": self.omega_B
                },
            }
            logger.info(
                "Poids fixes Phase 2 → ω_Θ=1.0  ω_B=%.4f", self.omega_B,
            )

        # Calcul du score Θ_complet = ω_Θ × Θ_dormant + ω_B × CIT
        theta_complet: Dict[str, float] = {}
        for service in all_services:
            td  = theta_dormants.get(service, 0.0)
            b   = cit.get(service, 0.0)
            theta_c = round(self.omega_theta * td + self.omega_B * b, 6)
            theta_complet[service] = theta_c

        # Identification S_écho-impact
        # S_écho-impact = { si | CIT(si) > τ_impact ET si ∉ ΔS }
        echo_impact = []
        for service, impact in cit.items():
            if service in delta_set:
                continue
            if impact > self.tau_impact:
                svc         = scores.get(service, {})
                was_dormant = svc.get("is_dormant", False)
                theta_p1    = float(svc.get("theta_dormant", 0.0))
                theta_c     = theta_complet.get(service, 0.0)

                echo_impact.append({
                    "service_name":   service,
                    "cit_score":      round(impact, 6),
                    "theta_phase1":   round(theta_p1, 6),
                    "theta_complet":  round(theta_c, 6),
                    "was_dormant":    was_dormant,
                    "resonance":      was_dormant,
                })

        echo_impact.sort(key=lambda x: x["cit_score"], reverse=True)

        # S_echo : set des noms de services Écho-Impact (pour tiering)
        s_echo: List[str] = [s["service_name"] for s in echo_impact]

        n_resonant = sum(1 for s in echo_impact if s["resonance"])

        # Statistiques
        all_cit_values = list(cit.values())
        echo_cit_values = [s["cit_score"] for s in echo_impact]

        stats = {
            "n_services_total":     len(cit),
            "n_modified":           len(delta_set),
            "n_echo_impact":        len(echo_impact),
            "n_resonant":           n_resonant,
            "resonance_rate":       round(n_resonant / max(len(echo_impact), 1), 4),
            "max_cit":              max(all_cit_values, default=0.0),
            "avg_cit_all":          round(
                sum(all_cit_values) / max(len(all_cit_values), 1), 4
            ),
            "avg_cit_echo_impact":  round(
                sum(echo_cit_values) / max(len(echo_cit_values), 1), 4
            ),
            "avg_theta_complet":    round(
                sum(theta_complet.values()) / max(len(theta_complet), 1), 4
            ),
            "weighting_method":     self.weighting_method,
            "omega_theta":          round(self.omega_theta, 6) if self.omega_theta else None,
            "omega_B":              round(self.omega_B, 6),
        }

        # Logs
        logger.info(
            "CITBuilder — %d Services Écho-Impact (τ=%.2f) | "
            "%d en résonance (étaient Écho-Dormants Phase 1)",
            len(echo_impact), self.tau_impact, n_resonant,
        )
        if n_resonant > 0:
            logger.info(
                "RÉSONANCE CONFIRMÉE : %d/%d — principe de résonance "
                "différée MetaBP-RTS validé empiriquement.",
                n_resonant, len(echo_impact),
            )
        if n_resonant == 0 and echo_impact:
            logger.warning(
                "CITBuilder — aucun Écho-Dormant Phase 1 n'est devenu "
                "Écho-Impact. Vérifier τ_dormant, τ_impact, ou ΔS."
            )

        return {
            "cit":                  cit,
            "theta_complet":        theta_complet,
            "echo_impact_services": echo_impact,
            "s_echo":               s_echo,
            "delta_s":              list(delta_s),
            "tau_impact":           self.tau_impact,
            "omega_theta":          self.omega_theta,
            "omega_B":              self.omega_B,
            "weighting_method":     self.weighting_method,
            "weights_details":      self.weights_details,
            "stats":                stats,
        }

    def save_weights(self, output_path: str) -> None:
        """Sauvegarde les poids EWM-CRITIC calculés pour documentation."""
        if self.weights_details:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            report = {
                "weighting_method": self.weighting_method,
                "tau_impact": self.tau_impact,
                "weights_applied": {
                    "omega_theta": round(self.omega_theta, 6) if self.omega_theta else None,
                    "omega_B": round(self.omega_B, 6),
                },
                "details": self.weights_details,
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            logger.info("Poids EWM-CRITIC Phase 2 → %s", path)

    def save(
        self,
        result: Dict,
        cit_path: str,
        echo_path: str,
        theta_path: str = None,
    ) -> None:
        self._write(cit_path, result["cit"])

        self._write(echo_path, {
            "delta_s":              result["delta_s"],
            "tau_impact":           result["tau_impact"],
            "weighting_method":     result["weighting_method"],
            "omega_theta":          result.get("omega_theta"),
            "omega_B":              result["omega_B"],
            "s_echo":               result["s_echo"],
            "echo_impact_services": result["echo_impact_services"],
            "stats":                result["stats"],
        })

        if theta_path:
            self._write(theta_path, result["theta_complet"])

    @staticmethod
    def _write(path_str: str, data) -> None:
        path = Path(path_str)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("Sauvegardé → %s", path)
