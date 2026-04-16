"""
Calcule Θ_dormant(si) et classifie chaque service :
    Θ_dormant(si) = ω_C×C(si) + ω_P×P(si) + ω_F×F(si)
Classification :
    Θ_dormant >= τ_dormant (0.40) → Service Écho-Dormant
    Θ_dormant <  τ_dormant        → Service Non-Dormant
Tout service Non-Dormant ne peut PAS être un Service Écho-Impact en Phase 2.
    Preuve : Θ(si) = Θ_dormant(si) + ω3×B(si) < 0.40 + 0.30×1.0 = 0.70 = τ_echo 
    
ENTREES   : - Dict C : {service_name: float}
            - Dict P : {service_name: float}
            - Dict F : {service_name: float}
            - config  : {tau_dormant, omega_C, omega_P, omega_F}
SORTIES   : - List[ServiceScore] avec theta_dormant et is_dormant
            - S_dormant : List[str]  (noms des services Écho-Dormants)
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple
from models.models import ServiceScore

logger = logging.getLogger(__name__)


class EchoDormantClassifier:
    def __init__(
        self,
        tau_dormant: float = 0.40,
        omega_C: float = 0.357,
        omega_P: float = 0.357,
        omega_F: float = 0.286,
    ):
        assert abs(omega_C + omega_P + omega_F - 1.0) < 1e-3, (
            f"ω_C + ω_P + ω_F doit valoir 1.0, obtenu {omega_C+omega_P+omega_F:.6f}"
        )
        self.tau_dormant = tau_dormant
        self.omega_C = omega_C
        self.omega_P = omega_P
        self.omega_F = omega_F

    def classify(
        self,
        C_scores: Dict[str, float],
        P_scores: Dict[str, float],
        F_scores: Dict[str, float],
    ) -> List[ServiceScore]:
       
        # Union de tous les services connus
        all_services = set(C_scores) | set(P_scores) | set(F_scores)
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

        # Tri décroissant par Θ_dormant pour faciliter la lecture
        scores.sort(key=lambda s: s.theta_dormant, reverse=True)

        dormant_count = sum(1 for s in scores if s.is_dormant)
        logger.info(
            "EchoDormantClassifier → %d services | %d Écho-Dormants | %d Non-Dormants",
            len(scores), dormant_count, len(scores) - dormant_count,
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

    def verify_safety_theorem(self, scores: List[ServiceScore]) -> Tuple[bool, List[str]]:
        #  verification du theoreme propose ω3 × B_max = 0.30 × 1.0 = 0.30 (valeur maximale possible de la contribution BP)
        omega3_B_max = 0.30
        tau_echo = 0.70
        violators = []
        for s in scores:
            if not s.is_dormant:
                max_possible_theta = s.theta_dormant + omega3_B_max
                if max_possible_theta >= tau_echo:
                    violators.append(s.service_name)

        if violators:
            logger.error(
                "VIOLATION du Théorème de Sécurité : %d services Non-Dormants "
                "pourraient atteindre τ_echo : %s",
                len(violators), violators,
            )
        else:
            logger.info("Théorème de Sécurité d'Exclusion : ok")

        return len(violators) == 0, violators