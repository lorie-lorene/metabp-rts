"""
ewm_critic.py
=============
BLOC      : Calcul objectif des poids par méthode combinée EWM-CRITIC
CONTEXTE  : Pondération des critères pour Θ_dormant (Phase 1) et Θ_complet (Phase 2)

PROBLÈME RÉSOLU :
    Les poids fixes (ω_C=0.25, ω_P=0.25, ω_F=0.30) sont arbitraires et
    injustifiables scientifiquement. Un jury demandera "pourquoi 0.25 et pas 0.4 ?".
    
    La méthode combinée EWM-CRITIC dérive les poids DIRECTEMENT des données
    observées, sans intervention humaine ni jugement d'expert.

DEUX MÉTHODES FUSIONNÉES :

    1. EWM (Entropy Weight Method) — Shannon, 1948
       Postulat : plus un critère a une forte dispersion (variance) à travers
       les services, plus il apporte d'information discriminante.
       Limite : ignore la corrélation entre critères.

    2. CRITIC (CRiteria Importance Through Intercriteria Correlation)
       — Diakoulaki et al., 1995
       Postulat : un critère apporte d'autant plus d'information qu'il est
       à la fois dispersé (σ élevé) ET peu corrélé aux autres critères.
       Corrige le biais de l'EWM quand deux critères mesurent le même phénomène
       (ex: C et P sont mécaniquement corrélés dans un graphe de services).

    FUSION :
       ω_final(j) = ω_EWM(j) × ω_CRITIC(j) / Σ[ω_EWM(k) × ω_CRITIC(k)]
       
       Un critère n'obtient un poids élevé que s'il est À LA FOIS très dispersé
       (EWM) ET peu corrélé aux autres (CRITIC).

USAGE :
    Phase 1 — Écho-Dormants :
        matrice = [[C(s1), P(s1), F(s1)], [C(s2), P(s2), F(s2)], ...]
        ω_C, ω_P, ω_F = compute_combined_weights(matrice, ["C", "P", "F"])
        Θ_dormant(si) = ω_C·C(si) + ω_P·P(si) + ω_F·F(si)

    Phase 2 — Écho-Impact :
        matrice = [[Θ_dormant(s1), CIT(s1)], [Θ_dormant(s2), CIT(s2)], ...]
        ω_Θ, ω_B = compute_combined_weights(matrice, ["Θ_dormant", "CIT"])
        Θ_complet(si) = ω_Θ·Θ_dormant(si) + ω_B·CIT(si)

RÉFÉRENCES :
    [1] Shannon, C.E. (1948). A Mathematical Theory of Communication.
    [2] Diakoulaki, D., Mavrotas, G., Papayannakis, L. (1995).
        Determining objective weights in multiple criteria problems:
        The CRITIC method. Computers & Operations Research, 22(7), 763-770.
    [3] Ma, J., Fan, Z.P., Huang, L.H. (1999). A subjective and objective
        integrated approach to determine attribute weights.
        European Journal of Operational Research, 112(2), 397-404.
"""

import json
import logging
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class EWMCRITICWeightCalculator:
    """
    Calcule les poids objectifs des critères par la méthode combinée EWM-CRITIC.
    """

    def __init__(self, epsilon: float = 1e-10):
        """
        Parameters
        ----------
        epsilon : petite valeur pour éviter log(0) et division par 0
        """
        self.epsilon = epsilon

    def _normalize(self, matrix: np.ndarray) -> np.ndarray:
        """
        Normalisation min-max : ramène chaque critère entre 0 et 1.
        
        x'_ij = (x_ij - min(x_j)) / (max(x_j) - min(x_j))
        
        Si un critère a une variance nulle (tous les services ont la même
        valeur), toutes les valeurs normalisées sont mises à 0 — ce critère
        ne discrimine rien et recevra un poids nul.
        """
        normalized = np.zeros_like(matrix, dtype=float)
        n_criteria = matrix.shape[1]

        for j in range(n_criteria):
            col = matrix[:, j]
            col_min = col.min()
            col_max = col.max()
            range_j = col_max - col_min

            if range_j < self.epsilon:
                # Variance nulle — critère non discriminant
                normalized[:, j] = 0.0
                logger.debug(
                    "Critère %d : variance nulle (min=max=%.4f) → poids=0",
                    j, col_min,
                )
            else:
                normalized[:, j] = (col - col_min) / range_j

        return normalized

    def compute_ewm_weights(
        self, matrix: np.ndarray, criteria_names: Optional[List[str]] = None
    ) -> np.ndarray:
        """
        Méthode de l'Entropie de Shannon (EWM).

        Pour chaque critère j :
          1. Normaliser → x'_ij
          2. Calculer la proportion → p_ij = x'_ij / Σ x'_ij
          3. Calculer l'entropie → E_j = -k Σ p_ij·ln(p_ij), k = 1/ln(m)
          4. Poids → ω_j = (1 - E_j) / Σ(1 - E_k)

        Returns
        -------
        np.ndarray de poids, un par critère
        """
        m, n = matrix.shape  # m services, n critères
        normalized = self._normalize(matrix)

        k = 1.0 / math.log(max(m, 2))  # constante de normalisation
        weights = np.zeros(n)

        for j in range(n):
            col = normalized[:, j]
            col_sum = col.sum()

            if col_sum < self.epsilon:
                # Critère entièrement nul → entropie maximale → poids 0
                weights[j] = 0.0
                continue

            # Proportions
            p = col / col_sum
            # Éviter log(0)
            p_safe = np.where(p > self.epsilon, p, self.epsilon)

            # Entropie
            E_j = -k * np.sum(p_safe * np.log(p_safe))

            # Degré de divergence
            weights[j] = max(1.0 - E_j, 0.0)

        # Normalisation finale
        total = weights.sum()
        if total > self.epsilon:
            weights = weights / total
        else:
            # Tous les critères ont variance nulle → poids égaux
            weights = np.ones(n) / n
            logger.warning("EWM — tous les critères ont variance nulle → poids égaux")

        if criteria_names:
            for name, w in zip(criteria_names, weights):
                logger.info("  EWM  ω(%s) = %.4f", name, w)

        return weights

    def compute_critic_weights(
        self, matrix: np.ndarray, criteria_names: Optional[List[str]] = None
    ) -> np.ndarray:
        """
        Méthode CRITIC (Diakoulaki et al., 1995).

        Pour chaque critère j :
          1. Calculer l'écart-type σ_j (contraste)
          2. Calculer la corrélation de Pearson r_jk entre chaque paire
          3. Information → C_j = σ_j × Σ(1 - r_jk)
          4. Poids → ω_j = C_j / Σ C_k

        Returns
        -------
        np.ndarray de poids, un par critère
        """
        m, n = matrix.shape
        normalized = self._normalize(matrix)

        # Écarts-types
        std_devs = np.std(normalized, axis=0, ddof=0)

        # Matrice de corrélation de Pearson
        # Gérer le cas où un critère a σ=0 (corrélation indéfinie)
        corr_matrix = np.zeros((n, n))
        for j in range(n):
            for k in range(n):
                if j == k:
                    corr_matrix[j, k] = 1.0
                elif std_devs[j] < self.epsilon or std_devs[k] < self.epsilon:
                    corr_matrix[j, k] = 0.0  # pas de corrélation si variance nulle
                else:
                    corr_matrix[j, k] = np.corrcoef(
                        normalized[:, j], normalized[:, k]
                    )[0, 1]

        # Information par critère
        C = np.zeros(n)
        for j in range(n):
            conflict = sum(1.0 - corr_matrix[j, k] for k in range(n))
            C[j] = std_devs[j] * conflict

        # Normalisation finale
        total = C.sum()
        if total > self.epsilon:
            weights = C / total
        else:
            weights = np.ones(n) / n
            logger.warning("CRITIC — tous les critères ont σ=0 → poids égaux")

        if criteria_names:
            for name, w in zip(criteria_names, weights):
                logger.info("  CRITIC ω(%s) = %.4f", name, w)

        return weights

    def compute_combined_weights(
        self,
        matrix: np.ndarray,
        criteria_names: Optional[List[str]] = None,
    ) -> Tuple[np.ndarray, Dict]:
        """
        Fusion EWM × CRITIC.

        ω_final(j) = ω_EWM(j) × ω_CRITIC(j) / Σ[ω_EWM(k) × ω_CRITIC(k)]

        Un critère obtient un poids élevé seulement s'il est À LA FOIS
        très dispersé (EWM) ET peu corrélé aux autres (CRITIC).

        Returns
        -------
        (weights, details) où details contient les poids intermédiaires
        """
        names = criteria_names or [f"C{j}" for j in range(matrix.shape[1])]

        logger.info("EWM-CRITIC — matrice %d services × %d critères", *matrix.shape)

        # Étape 1 : EWM
        w_ewm = self.compute_ewm_weights(matrix, names)

        # Étape 2 : CRITIC
        w_critic = self.compute_critic_weights(matrix, names)

        # Étape 3 : Fusion multiplicative normalisée
        w_combined = w_ewm * w_critic
        total = w_combined.sum()

        if total > self.epsilon:
            w_combined = w_combined / total
        else:
            w_combined = np.ones(len(names)) / len(names)
            logger.warning("EWM-CRITIC — fusion nulle → poids égaux")

        logger.info("  ── Poids combinés EWM×CRITIC ──")
        for name, w in zip(names, w_combined):
            logger.info("  ω_final(%s) = %.4f", name, w)

        details = {
            "method": "EWM-CRITIC combined",
            "n_services": matrix.shape[0],
            "n_criteria": matrix.shape[1],
            "criteria": names,
            "weights_ewm": {n: round(float(w), 6) for n, w in zip(names, w_ewm)},
            "weights_critic": {n: round(float(w), 6) for n, w in zip(names, w_critic)},
            "weights_combined": {n: round(float(w), 6) for n, w in zip(names, w_combined)},
            "references": [
                "Shannon, C.E. (1948). A Mathematical Theory of Communication.",
                "Diakoulaki, D. et al. (1995). The CRITIC method. C&OR 22(7), 763-770.",
            ],
        }

        return w_combined, details

    def save(self, details: Dict, output_path: str) -> None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(details, f, indent=2, ensure_ascii=False)
        logger.info("Poids EWM-CRITIC → %s", path)
