"""
echo_dormant.py
===============
BLOC      : Phase 1 — Classification des services
ROLE      : Calcule Θ_dormant(si) et classifie chaque service comme
            Écho-Dormant ou Non-Dormant.

FORMULE :
    Θ_dormant(si) = ω_C × C(si) + ω_P × P(si) + ω_F × F(si)

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

    Après un changement ΔS, la Belief Propagation (Phase 2) calcule
    b_i(x_i=1) pour chaque service. Un service Écho-Dormant :
      - reçoit davantage de messages BP (forte centralité C)
      - amplifie ces messages (fort potentiel local ψ_i ∝ Θ(si))
    → sa probabilité d'impact est systématiquement plus élevée
      qu'un service Non-Dormant, à ΔS équivalent.
    → il "s'active" et devient un Service Écho-Impact.
    → tous les chemins de test qui le traversent deviennent urgents.

THÉORÈME DE RÉSONANCE (vérifié en Phase 1) :
    Pour tout graphe G et seuil τ_dormant calibré, les services
    Écho-Dormants ont un Θ(si) supérieur à celui de tous les
    Non-Dormants. 

NOTE : Un service Non-Dormant peut aussi être affecté par ΔS
    (notamment s'il est voisin direct du service modifié), mais
    sa probabilité d'impact sera toujours inférieure à celle d'un
    service Écho-Dormant du fait de sa faible centralité et fragilité.

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

    def verify_safety_theorem(
        self, scores: List[ServiceScore]
    ) -> Tuple[bool, List[str]]:
        """
        La séparation entre Écho-Dormants et Non-Dormants doit être nette,
        c'est-à-dire que le Θ_dormant minimal des Écho-Dormants doit être
        supérieur au Θ_dormant maximal des Non-Dormants.
        """
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