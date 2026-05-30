"""
ewm_critic.py
=============
Calcul objectif des poids et seuils par méthodes data-driven.

CONTENU :
    1. EWMCRITICWeightCalculator — poids EWM × CRITIC combinés
    2. AutoThreshold            — seuil τ dérivé par clustering K-means

PONDÉRATION EWM-CRITIC :
    EWM  (Shannon, 1948)      : poids proportionnel à la dispersion
    CRITIC (Diakoulaki, 1995) : pénalise les critères corrélés
    Fusion : ω_j = ω_EWM(j) × ω_CRITIC(j) / Σ[ω_EWM(k) × ω_CRITIC(k)]

SEUIL AUTOMATIQUE (AutoThreshold) :
    Problème : le seuil τ_dormant ne doit pas être fixé arbitrairement
    si les poids sont dérivés objectivement des données.

    Solution : partitionner les scores Θ_dormant par K-means (k=3)
    et placer τ au milieu de la frontière entre le cluster supérieur
    (services les plus vulnérables) et le cluster intermédiaire.

    τ = (min(Cluster_haut) + max(Cluster_intermédiaire)) / 2

    Le choix k=3 est justifié par :
    - L'objectif RTS : identifier un sous-ensemble RESTREINT de services
      à risque (le concept d'Écho-Dormant perd son sens si > 50% des
      services sont classés dormants)
    - Le gap analysis : le deuxième plus grand gap dans les scores
      sépare le top cluster du reste

RÉFÉRENCES :
    [1] Shannon, C.E. (1948). A Mathematical Theory of Communication.
    [2] Diakoulaki, D. et al. (1995). The CRITIC method. C&OR 22(7).
    [3] Ma, J. et al. (1999). Subjective and objective integrated
        approach. EJOR 112(2), 397-404.
"""

import json
import logging
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# 1. CALCUL DES POIDS EWM-CRITIC
# ═══════════════════════════════════════════════════════════════

class EWMCRITICWeightCalculator:
    """
    Calcule les poids objectifs des critères par la méthode combinée EWM-CRITIC.
    """

    def __init__(self, epsilon: float = 1e-10):
        self.epsilon = epsilon

    def _normalize(self, matrix: np.ndarray) -> np.ndarray:
        """Normalisation min-max entre 0 et 1."""
        normalized = np.zeros_like(matrix, dtype=float)
        for j in range(matrix.shape[1]):
            col = matrix[:, j]
            col_min, col_max = col.min(), col.max()
            range_j = col_max - col_min
            if range_j < self.epsilon:
                normalized[:, j] = 0.0
            else:
                normalized[:, j] = (col - col_min) / range_j
        return normalized

    def compute_ewm_weights(
        self, matrix: np.ndarray, criteria_names: Optional[List[str]] = None
    ) -> np.ndarray:
        """Méthode de l'Entropie de Shannon (EWM)."""
        m, n = matrix.shape
        normalized = self._normalize(matrix)
        k = 1.0 / math.log(max(m, 2))
        weights = np.zeros(n)

        for j in range(n):
            col = normalized[:, j]
            col_sum = col.sum()
            if col_sum < self.epsilon:
                weights[j] = 0.0
                continue
            p = col / col_sum
            p_safe = np.where(p > self.epsilon, p, self.epsilon)
            E_j = -k * np.sum(p_safe * np.log(p_safe))
            weights[j] = max(1.0 - E_j, 0.0)

        total = weights.sum()
        if total > self.epsilon:
            weights = weights / total
        else:
            weights = np.ones(n) / n

        if criteria_names:
            for name, w in zip(criteria_names, weights):
                logger.info("  EWM  ω(%s) = %.4f", name, w)
        return weights

    def compute_critic_weights(
        self, matrix: np.ndarray, criteria_names: Optional[List[str]] = None
    ) -> np.ndarray:
        """Méthode CRITIC (Diakoulaki et al., 1995)."""
        m, n = matrix.shape
        normalized = self._normalize(matrix)
        std_devs = np.std(normalized, axis=0, ddof=0)

        corr_matrix = np.zeros((n, n))
        for j in range(n):
            for k_idx in range(n):
                if j == k_idx:
                    corr_matrix[j, k_idx] = 1.0
                elif std_devs[j] < self.epsilon or std_devs[k_idx] < self.epsilon:
                    corr_matrix[j, k_idx] = 0.0
                else:
                    corr_matrix[j, k_idx] = np.corrcoef(
                        normalized[:, j], normalized[:, k_idx]
                    )[0, 1]

        C = np.zeros(n)
        for j in range(n):
            conflict = sum(1.0 - corr_matrix[j, k_idx] for k_idx in range(n))
            C[j] = std_devs[j] * conflict

        total = C.sum()
        if total > self.epsilon:
            weights = C / total
        else:
            weights = np.ones(n) / n

        if criteria_names:
            for name, w in zip(criteria_names, weights):
                logger.info("  CRITIC ω(%s) = %.4f", name, w)
        return weights

    def compute_combined_weights(
        self,
        matrix: np.ndarray,
        criteria_names: Optional[List[str]] = None,
    ) -> Tuple[np.ndarray, Dict]:
        """Fusion EWM × CRITIC."""
        names = criteria_names or [f"C{j}" for j in range(matrix.shape[1])]

        logger.info("EWM-CRITIC — matrice %d services × %d critères", *matrix.shape)

        w_ewm = self.compute_ewm_weights(matrix, names)
        w_critic = self.compute_critic_weights(matrix, names)

        w_combined = w_ewm * w_critic
        total = w_combined.sum()
        if total > self.epsilon:
            w_combined = w_combined / total
        else:
            w_combined = np.ones(len(names)) / len(names)

        logger.info("  ── Poids combinés EWM×CRITIC ──")
        for name, w in zip(names, w_combined):
            logger.info("  ω_final(%s) = %.4f", name, w)

        details = {
            "method": "EWM-CRITIC combined",
            "n_services": int(matrix.shape[0]),
            "n_criteria": int(matrix.shape[1]),
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


# ═══════════════════════════════════════════════════════════════
# 2. SEUIL AUTOMATIQUE PAR CLUSTERING
# ═══════════════════════════════════════════════════════════════

class AutoThreshold:
    """
    Dérive automatiquement le seuil τ depuis la distribution des scores
    par clustering K-means (k=3).

    Justification du k=3 :
        Le concept d'Écho-Dormant vise à identifier un sous-ensemble
        RESTREINT de services à risque. Avec k=2, la partition sépare
        typiquement les services "feuilles" des services "non-feuilles",
        ce qui classe une majorité (>50%) comme dormants — vidant le
        concept de son sens. Avec k=3, trois profils émergent :
          - Cluster HAUT   : services les plus vulnérables (Écho-Dormants)
          - Cluster MOYEN  : services intermédiaires
          - Cluster BAS    : services feuilles / périphériques

        τ = frontière entre le cluster HAUT et le cluster MOYEN.
    """

    @staticmethod
    def _kmeans_1d(data: np.ndarray, k: int, max_iter: int = 200) -> Tuple[np.ndarray, np.ndarray]:
        """
        K-means 1D simple — pas besoin de sklearn pour 1 dimension.
        """
        # Initialisation : k quantiles réguliers
        centroids = np.array([
            np.percentile(data, 100 * (i + 0.5) / k) for i in range(k)
        ])

        for _ in range(max_iter):
            # Attribution
            distances = np.abs(data[:, None] - centroids[None, :])
            labels = np.argmin(distances, axis=1)
            # Mise à jour des centroïdes
            new_centroids = np.array([
                data[labels == c].mean() if (labels == c).any() else centroids[c]
                for c in range(k)
            ])
            if np.allclose(new_centroids, centroids, atol=1e-10):
                break
            centroids = new_centroids

        return labels, centroids

    @staticmethod
    def compute(
        scores: np.ndarray,
        k: int = 3,
        min_cluster_size: int = 1,
    ) -> Tuple[float, Dict]:
        """
        Calcule τ automatiquement depuis les scores.

        Parameters
        ----------
        scores : array 1D des Θ_dormant
        k      : nombre de clusters (défaut 3)
        min_cluster_size : taille minimale d'un cluster

        Returns
        -------
        (tau, details) où tau est le seuil calculé
        """
        if len(scores) < k:
            # Pas assez de services pour k clusters
            tau = float(np.median(scores))
            logger.warning(
                "AutoThreshold — %d services < k=%d → τ = médiane = %.4f",
                len(scores), k, tau,
            )
            return tau, {"method": "median_fallback", "tau": tau}

        labels, centroids = AutoThreshold._kmeans_1d(scores, k)

        # Trier les clusters par centroïde décroissant
        sorted_indices = np.argsort(-centroids)
        cluster_high = sorted_indices[0]
        cluster_mid  = sorted_indices[1]

        members_high = scores[labels == cluster_high]
        members_mid  = scores[labels == cluster_mid]

        if len(members_high) < min_cluster_size or len(members_mid) < min_cluster_size:
            # Cluster dégénéré — fallback sur le gap max
            sorted_scores = np.sort(scores)[::-1]
            gaps = [(sorted_scores[i] - sorted_scores[i+1], i) for i in range(len(sorted_scores)-1)]
            gaps.sort(reverse=True)
            if gaps:
                best_gap_idx = gaps[0][1]
                tau = float((sorted_scores[best_gap_idx] + sorted_scores[best_gap_idx+1]) / 2)
            else:
                tau = float(np.median(scores))
            logger.warning("AutoThreshold — cluster dégénéré → fallback gap max → τ=%.4f", tau)
            return tau, {"method": "gap_fallback", "tau": tau}

        # τ = milieu de la frontière entre cluster haut et cluster moyen
        min_high = float(members_high.min())
        max_mid  = float(members_mid.max())
        tau      = round((min_high + max_mid) / 2, 6)

        # Vérification de séparation
        separation = min_high - max_mid
        if separation <= 0:
            logger.warning(
                "AutoThreshold — chevauchement entre clusters "
                "(min_haut=%.4f ≤ max_moyen=%.4f). "
                "τ = %.4f peut produire des faux positifs.",
                min_high, max_mid, tau,
            )

        # Gap analysis pour documentation
        sorted_scores = np.sort(scores)[::-1]
        all_gaps = []
        for i in range(len(sorted_scores) - 1):
            all_gaps.append({
                "rank": i + 1,
                "score_above": round(float(sorted_scores[i]), 6),
                "score_below": round(float(sorted_scores[i+1]), 6),
                "gap": round(float(sorted_scores[i] - sorted_scores[i+1]), 6),
            })
        all_gaps.sort(key=lambda x: -x["gap"])

        n_dormant = int(np.sum(scores >= tau))

        details = {
            "method": f"kmeans_k{k}_auto_threshold",
            "k": k,
            "tau": tau,
            "n_dormant": n_dormant,
            "n_total": len(scores),
            "cluster_high": {
                "centroid": round(float(centroids[cluster_high]), 6),
                "n_members": int(len(members_high)),
                "min": round(min_high, 6),
                "max": round(float(members_high.max()), 6),
            },
            "cluster_mid": {
                "centroid": round(float(centroids[cluster_mid]), 6),
                "n_members": int(len(members_mid)),
                "min": round(float(members_mid.min()), 6),
                "max": round(max_mid, 6),
            },
            "separation": round(separation, 6),
            "formula": "τ = (min(Cluster_haut) + max(Cluster_intermédiaire)) / 2",
            "top_gaps": all_gaps[:5],
            "justification": (
                f"K-means k={k} identifie {int(len(members_high))} services dans le "
                f"cluster supérieur (centroïde={float(centroids[cluster_high]):.4f}). "
                f"Le seuil τ={tau:.4f} est la frontière naturelle entre ce cluster "
                f"et le cluster intermédiaire (centroïde={float(centroids[cluster_mid]):.4f}). "
                f"Le gap de séparation est {separation:.4f}."
            ),
        }

        logger.info(
            "AutoThreshold — k=%d | τ=%.4f | %d/%d Écho-Dormants | gap=%.4f",
            k, tau, n_dormant, len(scores), separation,
        )

        return tau, details
