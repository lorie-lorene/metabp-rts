"""
 Étapes 4 et 5
 Construit la CIT, calcule le score Θ complet (Phase 1 + BP),
 identifie S_écho-impact, et prépare le tiering pour Phase 3

SCORE COMPLET (MetaBP-RTS) :
    En Phase 1 : Θ_dormant(si) = ω_C·C(si) + ω_P·P(si) + ω_F·F(si)
    En Phase 2 : Θ_complet(si) = ω_C·C(si) + ω_P·P(si) + ω_F·F(si) + ω_B·B(si)

    B(si) = CIT(si) = probabilité d'impact calculée par la BP après ΔS
    ω_B   = poids de la BP (configurable, défaut 0.30)


TIERING (préparation Phase 3) :
    Tier 1 = tests qui traversent au moins un service de S_écho-impact
             --> tous conservés
    Tier 2 = tests qui ne traversent aucun service de S_écho-impact
             --> optimisés par PSO en Phase 3

"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Set

logger = logging.getLogger(__name__)


class CITBuilder:

    def __init__(
        self,
        tau_impact: float = 0.30,
        omega_B: float = 0.30,
    ):
        """
        tau_impact : seuil pour identifier un Service Écho-Impact
        omega_B    : poids de B(si) dans le score Θ_complet
        """
        self.tau_impact = tau_impact
        self.omega_B    = omega_B

    def build(
        self,
        p_final: Dict[str, float],
        delta_s: List[str],
        scores: Dict[str, Dict],
    ) -> Dict:
       
        delta_set: Set[str] = set(delta_s)
        cit = dict(p_final)

        # Calcul du score Θ_complet = Θ_dormant + ω_B × B(si)
        # B(si) = CIT(si) = résultat de la BP
        theta_complet: Dict[str, float] = {}
        for service, b_si in cit.items():
            svc            = scores.get(service, {})
            theta_dormant  = float(svc.get("theta_dormant", 0.0))
            theta_c        = round(theta_dormant + self.omega_B * b_si, 6)
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
                    # résonance = service qui était Écho-Dormant ET
                    # devient Écho-Impact → validation empirique du
                    # principe de résonance différée MetaBP-RTS
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
            "omega_B":              self.omega_B,
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
            "omega_B":              self.omega_B,
            "stats":                stats,
        }

    def save(
        self,
        result: Dict,
        cit_path: str,
        echo_path: str,
        theta_path: str = None,
    ) -> None:
        """
        Sauvegarde la CIT, les services Écho-Impact, et optionnellement
        les scores Θ_complet.
        """
        # CIT
        self._write(cit_path, result["cit"])

        # Services Écho-Impact + S_echo + stats
        self._write(echo_path, {
            "delta_s":              result["delta_s"],
            "tau_impact":           result["tau_impact"],
            "omega_B":              result["omega_B"],
            "s_echo":               result["s_echo"],
            "echo_impact_services": result["echo_impact_services"],
            "stats":                result["stats"],
        })

        # Scores Θ_complet (optionnel)
        if theta_path:
            self._write(theta_path, result["theta_complet"])

    @staticmethod
    def _write(path_str: str, data) -> None:
        path = Path(path_str)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("Sauvegardé → %s", path)
