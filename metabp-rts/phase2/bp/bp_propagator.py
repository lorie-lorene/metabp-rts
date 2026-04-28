"""
Étape 3
Propagation itérative des messages BP sur DG jusqu'à convergence.

DEUX MODES DE PROPAGATION( on fera les deux modes afin d'avoir des moyens de comparaions) :

    Mode 1 — Chen et al. (max-product) :
        m_ij = p_t(si) * w(eij)
        p_{t+1}(si) = max(p_t(si), max_j m_ji)

    Mode 2 — Noisy-OR (MetaBP-RTS, recommandé) :
        P(si = sain | parents) = ∏_{sk ∈ parents(si)} (1 - w_ki * p_t(sk))
        P(si = affecté)        = 1 - P(si = sain)
        p_{t+1}(si)            = max(p_t(si), P(si = affecté))

"""

import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


class BPPropagator:

    def __init__(
        self,
        max_iterations: int = 100,
        convergence_threshold: float = 1e-6,
        mode: str = "noisy_or",
    ):
        
        assert mode in ("noisy_or", "max_product"), \
            f"Mode inconnu : {mode}. Valeurs : noisy_or | max_product"
        self.max_iterations = max_iterations
        self.epsilon        = convergence_threshold
        self.mode           = mode

    def propagate(
        self,
        dg: Dict,
        p0: Dict[str, float],
        keep_history: bool = False,
    ) -> Tuple[Dict[str, float], int, bool, List]:
        """
        Exécution de la BP et retourne (p_final, n_iter, converged, history)

        Parameters ( en fonction des resultats on erra comment les modifier)
        ----------
        dg           : graphe DG avec "adjacency" : { service: [{neighbor, w_ij}] }
        p0           : vecteur initial des degrés d'impact (BPInitializer)
        keep_history : si True, conserve p à chaque itération (pour visualisation)

        Returns
        -------
        p_final   : { service_name: float }
        n_iter    : int
        converged : bool
        history   : List[Dict]  (vide si keep_history=False)
        """
        adjacency = dg.get("adjacency", {})
        p_current = dict(p0)
        converged = False
        n_iter    = 0
        max_delta = 0.0
        history: List = []

        logger.info(
            "BPPropagator — démarrage mode=%s | max_iter=%d | epsilon=%.1e",
            self.mode, self.max_iterations, self.epsilon,
        )

        for t in range(self.max_iterations):
            n_iter = t + 1

            if self.mode == "noisy_or":
                p_new, max_delta = self._step_noisy_or(adjacency, p_current)
            else:
                p_new, max_delta = self._step_max_product(adjacency, p_current)

            if keep_history:
                history.append({
                    "iteration": n_iter,
                    "max_delta": round(max_delta, 8),
                    "p":         {k: round(v, 6) for k, v in p_new.items()},
                })

            p_current = p_new

            if max_delta < self.epsilon:
                converged = True
                logger.info(
                    "BPPropagator — convergence à t=%d | Δmax=%.2e",
                    n_iter, max_delta,
                )
                break

        if not converged:
            logger.warning(
                "BPPropagator — max_iterations=%d atteint sans convergence "
                "(Δmax=%.2e). Résultats approximatifs.",
                self.max_iterations, max_delta,
            )

        p_final    = {k: round(v, 6) for k, v in p_current.items()}
        n_impacted = sum(1 for v in p_final.values() if v > 0)

        logger.info(
            "BPPropagator — %d itérations | %d services impactés (p>0) | mode=%s",
            n_iter, n_impacted, self.mode,
        )

        return p_final, n_iter, converged, history

    def _step_noisy_or(
        self,
        adjacency: Dict,
        p_current: Dict[str, float],
    ) -> Tuple[Dict[str, float], float]:
        """
        Une itération Noisy-OR.

        Pour chaque service si, calcule la probabilité d'être sain
        comme le produit des compléments pondérés de ses parents :

            P(si = sain) = ∏_{sk ∈ parents(si)} (1 - w_ki × p_t(sk))
            p_{t+1}(si)  = max(p_t(si), 1 - P(si = sain))
        """
        # Accumuler la probabilité d'être SAIN pour chaque noeud
        # Initialiser à 1.0 (pas d'impact reçu)
        p_sain: Dict[str, float] = {node: 1.0 for node in p_current}

        for src, neighbors in adjacency.items():
            p_src = p_current.get(src, 0.0)
            if p_src == 0.0:
                continue  # ce noeud n'est pas affecté, aucun message
            for nbr in neighbors:
                dst  = nbr["neighbor"]
                w_ij = nbr["w_ij"]
                # Facteur de survie : (1 - w_ij × p_src)
                # Si p_src=1.0 et w_ij=1.0 → facteur=0.0 → impact certain
                if dst in p_sain:
                    p_sain[dst] *= max(0.0, 1.0 - w_ij * p_src)

        # Mise à jour : p_{t+1} = max(p_t, P(affecté) = 1 - P(sain))
        p_new    = {}
        max_delta = 0.0
        for node in p_current:
            p_old    = p_current[node]
            p_affect = 1.0 - p_sain.get(node, 1.0)
            p_upd    = max(p_old, p_affect)
            p_new[node] = p_upd
            max_delta = max(max_delta, abs(p_upd - p_old))

        return p_new, max_delta

    def _step_max_product(
        self,
        adjacency: Dict,
        p_current: Dict[str, float],
    ) -> Tuple[Dict[str, float], float]:
        """
        Une itération Max-Product (

            m_ij = p_t(si) × w(eij)
            p_{t+1}(si) = max(p_t(si), max_j m_ji)
        """
        messages: Dict[str, float] = {node: 0.0 for node in p_current}

        for src, neighbors in adjacency.items():
            p_src = p_current.get(src, 0.0)
            if p_src == 0.0:
                continue
            for nbr in neighbors:
                dst = nbr["neighbor"]
                m   = p_src * nbr["w_ij"]
                if dst in messages:
                    messages[dst] = max(messages[dst], m)

        p_new    = {}
        max_delta = 0.0
        for node in p_current:
            p_old = p_current[node]
            p_upd = max(p_old, messages.get(node, 0.0))
            p_new[node] = p_upd
            max_delta = max(max_delta, abs(p_upd - p_old))

        return p_new, max_delta

    def compare_modes(
        self,
        dg: Dict,
        p0: Dict[str, float],
    ) -> Dict:
        """
        Compare les résultats Noisy-OR vs Max-Product sur le même DG et p0.
        Utile pour la section expérimentale du mémoire.
        """
        # Noisy-OR
        self.mode = "noisy_or"
        p_nor, n_nor, conv_nor, _ = self.propagate(dg, p0)

        # Max-Product (Chen et al.)
        self.mode = "max_product"
        p_mp, n_mp, conv_mp, _ = self.propagate(dg, p0)

        # Restaurer le mode par défaut
        self.mode = "noisy_or"

        # Différences
        diff = {
            node: {
                "noisy_or":   p_nor.get(node, 0.0),
                "max_product": p_mp.get(node, 0.0),
                "delta":       round(p_nor.get(node, 0.0) - p_mp.get(node, 0.0), 6),
            }
            for node in set(list(p_nor.keys()) + list(p_mp.keys()))
            if abs(p_nor.get(node, 0.0) - p_mp.get(node, 0.0)) > 1e-6
        }

        logger.info(
            "BPPropagator.compare — %d services avec CIT différente "
            "entre Noisy-OR et Max-Product",
            len(diff),
        )
        return {
            "noisy_or":   {"p_final": p_nor, "n_iter": n_nor, "converged": conv_nor},
            "max_product": {"p_final": p_mp,  "n_iter": n_mp,  "converged": conv_mp},
            "differences": diff,
        }
