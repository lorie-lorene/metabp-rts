"""
Étape 2
 Initialise le vecteur p0(si) pour la Belief Propagation.
    MetaBP-RTS — initialisation enrichie par Phase 1 :
        ψ(si) = 1.0        si si ∈ ΔS           (service modifié)
        ψ(si) = Θ(si)      si si ∈ S_dormant     (Écho-Dormant, non modifié)
        ψ(si) = 0.0        sinon


AMÉLIORATIONS v2 :
    - Validation que delta_s ⊆ nodes (avertissement si service inconnu)
    - Log explicite de chaque service et son ψ initial
    - Méthode compare() pour comparer mode MetaBP-RTS vs Chen et al.
"""

import logging
from typing import Dict, List, Set

logger = logging.getLogger(__name__)


class BPInitializer:

    def __init__(self, use_phase1_scores: bool = True):

        self.use_phase1_scores = use_phase1_scores

    def initialize(
        self,
        nodes: List[str],
        delta_s: List[str],
        scores: Dict[str, Dict],
    ) -> Dict[str, float]:
        delta_set: Set[str] = set(delta_s)
        node_set:  Set[str] = set(nodes)

        # Validation : services de delta_s présents dans le graphe 
        unknown_delta = delta_set - node_set
        if unknown_delta:
            logger.warning(
                "BPInitializer — %d service(s) de delta_s absents du graphe : %s. "
                "Ils seront ignorés dans p0.",
                len(unknown_delta), sorted(unknown_delta),
            )
            delta_set = delta_set & node_set  # restreindre aux noeuds connus

        p0: Dict[str, float] = {}
        for node in nodes:
            if node in delta_set:
                # Service directement modifié ,donc impact maximal
                p0[node] = 1.0

            elif self.use_phase1_scores:
                svc = scores.get(node, {})
                if svc.get("is_dormant", False):
                    # Écho-Dormant : potentiel local = Θ(si)
                    # Il amplifiera les messages BP entrants
                    theta = float(svc.get("theta_dormant", 0.0))
                    p0[node] = round(theta, 6)
                else:
                    p0[node] = 0.0
            else:
                
                p0[node] = 0.0
        n_mod     = sum(1 for v in p0.values() if v == 1.0)
        n_dormant = sum(
            1 for n in nodes
            if n not in delta_set
            and scores.get(n, {}).get("is_dormant", False)
            and self.use_phase1_scores
        )
        n_zero = len(nodes) - n_mod - n_dormant

        logger.info(
            "BPInitializer — %d noeuds initialisés : "
            "%d modifiés (ψ=1.0) | %d Écho-Dormants (ψ=Θ) | %d neutres (ψ=0.0)",
            len(nodes), n_mod, n_dormant, n_zero,
        )

        non_zero = {k: v for k, v in p0.items() if v > 0}
        for svc, val in sorted(non_zero.items(), key=lambda x: -x[1]):
            tag = "ΔS" if val == 1.0 else "Écho-Dormant"
            logger.debug("  ψ(%s) = %.4f  [%s]", svc, val, tag)

        return p0

    def compare_modes(
        self,
        nodes: List[str],
        delta_s: List[str],
        scores: Dict[str, Dict],
    ) -> Dict:
        """
        Compare l'initialisation MetaBP-RTS vs Chen et al. pour quantifier
        l'apport de l'enrichissement par les scores Phase 1.
        """
        p0_metabp = self.initialize(nodes, delta_s, scores)

        # Forcer mode Chen et al.
        original_mode = self.use_phase1_scores
        self.use_phase1_scores = False
        p0_chen = self.initialize(nodes, delta_s, scores)
        self.use_phase1_scores = original_mode

        # Différences
        diff = {
            node: {
                "metabp": p0_metabp[node],
                "chen":   p0_chen[node],
                "delta":  round(p0_metabp[node] - p0_chen[node], 6),
            }
            for node in nodes
            if p0_metabp[node] != p0_chen[node]
        }

        logger.info(
            "BPInitializer.compare — %d services avec ψ différent "
            "entre MetaBP-RTS et Chen et al.",
            len(diff),
        )
        return {
            "p0_metabp": p0_metabp,
            "p0_chen":   p0_chen,
            "differences": diff,
        }
