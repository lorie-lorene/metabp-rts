"""
cit_builder.py
==============
BLOC      : Phase 2 — Étapes 4 et 5
ROLE      : Construit la CIT, calcule le score Θ_complet (Phase 1 + BP),
            identifie S_écho-impact, et prépare le tiering pour Phase 3.

APPROCHE DATA-DRIVEN COMPLÈTE (MetaBP-RTS) :
    Aucun paramètre arbitraire. Tout est dérivé des données observées.

    1. POIDS — Méthode combinée EWM-CRITIC :
       ω_Θ, ω_B calculés objectivement depuis Θ_dormant et CIT.
       CIT reçoit typiquement un poids plus élevé car il apporte
       l'information NOUVELLE (impact dynamique de ΔS).

    2. SEUIL — K-means (k=3) + frontière inter-clusters :
       τ_impact = (min(Cluster_haut) + max(Cluster_intermédiaire)) / 2
       Appliqué sur les valeurs CIT des services non-ΔS.

SCORE COMPLET :
    Θ_complet(si) = ω_Θ × Θ_dormant(si) + ω_B × CIT(si)

TIERING :
    Tier 1 = tests traversant au moins un service de S_écho-impact
             → tous conservés (100% Recall garanti)
    Tier 2 = tests ne traversant aucun service de S_écho-impact
             → optimisés par PSO en Phase 3
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Set

import numpy as np

from bp.ewm_critic import EWMCRITICWeightCalculator, AutoThreshold

logger = logging.getLogger(__name__)


class CITBuilder:

    def __init__(
        self,
        tau_impact: float = None,
        omega_B: float = 0.30,
        weighting_method: str = "ewm_critic",
        threshold_method: str = "auto",
        k_clusters: int = 3,
    ):
        """
        Parameters
        ----------
        tau_impact        : seuil fixe (utilisé si threshold_method="fixed")
                            Si None et threshold_method="auto", dérivé des données.
        omega_B           : poids fixe de CIT (fallback si weighting_method="fixed")
        weighting_method  : "ewm_critic" (défaut) ou "fixed"
        threshold_method  : "auto" (défaut, K-means) ou "fixed"
        k_clusters        : nombre de clusters pour AutoThreshold (défaut 3)
        """
        self.tau_impact_fixed  = tau_impact
        self.omega_B_fixed     = omega_B
        self.weighting_method  = weighting_method
        self.threshold_method  = threshold_method
        self.k_clusters        = k_clusters

        # Valeurs calculées (remplies par build)
        self.tau_impact        = tau_impact
        self.omega_theta       = None
        self.omega_B           = omega_B
        self.weights_details   = None
        self.threshold_details = None

    def _compute_weights(
        self,
        theta_dormants: Dict[str, float],
        cit_values: Dict[str, float],
        all_services: list,
    ) -> None:
        """Calcule ω_Θ et ω_B par EWM-CRITIC ou utilise les poids fixes."""
        if self.weighting_method == "ewm_critic":
            matrix = np.array([
                [theta_dormants.get(s, 0.0), cit_values.get(s, 0.0)]
                for s in all_services
            ])
            criteria = ["Θ_dormant", "CIT"]
            calc = EWMCRITICWeightCalculator()
            weights, details = calc.compute_combined_weights(matrix, criteria)
            self.omega_theta = float(weights[0])
            self.omega_B     = float(weights[1])
            self.weights_details = details
            logger.info(
                "EWM-CRITIC Phase 2 → ω_Θ=%.4f  ω_B=%.4f",
                self.omega_theta, self.omega_B,
            )
        else:
            self.omega_theta = 1.0
            self.omega_B     = self.omega_B_fixed
            self.weights_details = {
                "method": "fixed",
                "weights_combined": {"Θ_dormant": 1.0, "CIT": self.omega_B},
            }

    def _compute_threshold(
        self,
        cit_values: Dict[str, float],
        delta_set: set,
    ) -> None:
        """Calcule τ_impact par AutoThreshold sur les CIT (hors ΔS) ou utilise la valeur fixe."""
        if self.threshold_method == "auto":
            # Exclure ΔS du clustering (CIT(ΔS)=1.0 par définition)
            cit_non_delta = np.array([
                v for s, v in cit_values.items() if s not in delta_set
            ])

            if len(cit_non_delta) < self.k_clusters:
                # Pas assez de services → fallback
                self.tau_impact = 0.25
                self.threshold_details = {"method": "fallback", "tau": 0.25}
                logger.warning("AutoThreshold — pas assez de services non-ΔS → τ_impact=0.25")
                return

            self.tau_impact, self.threshold_details = AutoThreshold.compute(
                cit_non_delta, k=self.k_clusters,
            )
            logger.info(
                "AutoThreshold Phase 2 (k=%d) → τ_impact=%.4f",
                self.k_clusters, self.tau_impact,
            )
        else:
            if self.tau_impact_fixed is None:
                self.tau_impact = 0.25
            else:
                self.tau_impact = self.tau_impact_fixed
            self.threshold_details = {"method": "fixed", "tau": self.tau_impact}

    def build(
        self,
        p_final: Dict[str, float],
        delta_s: List[str],
        scores: Dict[str, Dict],
    ) -> Dict:

        delta_set: Set[str] = set(delta_s)
        cit = dict(p_final)
        all_services = sorted(cit.keys())

        # Préparer Θ_dormant
        theta_dormants = {
            s: float(scores.get(s, {}).get("theta_dormant", 0.0))
            for s in all_services
        }

        # ── Étape 1 : Calcul des poids EWM-CRITIC ──
        self._compute_weights(theta_dormants, cit, all_services)

        # ── Étape 2 : Calcul du seuil τ_impact automatique ──
        self._compute_threshold(cit, delta_set)

        # ── Étape 3 : Calcul Θ_complet ──
        theta_complet: Dict[str, float] = {}
        for service in all_services:
            td = theta_dormants.get(service, 0.0)
            b  = cit.get(service, 0.0)
            theta_c = round(self.omega_theta * td + self.omega_B * b, 6)
            theta_complet[service] = theta_c

        # ── Étape 4 : Identification S_écho-impact ──
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
            "avg_cit_all":          round(sum(all_cit_values) / max(len(all_cit_values), 1), 4),
            "avg_cit_echo_impact":  round(sum(echo_cit_values) / max(len(echo_cit_values), 1), 4),
            "avg_theta_complet":    round(sum(theta_complet.values()) / max(len(theta_complet), 1), 4),
            "weighting_method":     self.weighting_method,
            "threshold_method":     self.threshold_method,
            "omega_theta":          round(self.omega_theta, 6) if self.omega_theta else None,
            "omega_B":              round(self.omega_B, 6),
            "tau_impact":           round(self.tau_impact, 6),
        }

        # Logs
        logger.info(
            "CITBuilder — %d Services Écho-Impact (τ=%.4f) | "
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
                "Écho-Impact. Vérifier les seuils ou ΔS."
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
            "threshold_method":     self.threshold_method,
            "weights_details":      self.weights_details,
            "threshold_details":    self.threshold_details,
            "stats":                stats,
        }

    def save_weights(self, output_path: str) -> None:
        """Sauvegarde les poids ET le seuil calculés pour documentation."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        report = {
            "weighting": {
                "method": self.weighting_method,
                "omega_theta": round(self.omega_theta, 6) if self.omega_theta else None,
                "omega_B": round(self.omega_B, 6),
                "details": self.weights_details,
            },
            "threshold": {
                "method": self.threshold_method,
                "tau_impact": round(self.tau_impact, 6) if self.tau_impact else None,
                "details": self.threshold_details,
            },
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.info("Rapport EWM-CRITIC + AutoThreshold Phase 2 → %s", path)

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
            "threshold_method":     result["threshold_method"],
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
