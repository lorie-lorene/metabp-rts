"""
Étape 5
Score chaque chemin tp ∈ T selon la CIT, applique le TIERING,
 et prépare les artefacts pour la Phase 3.

"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class TestScorer:

    def __init__(
        self,
        strategy: str = "existent",
        k: int = 2,
        threshold_p: Optional[float] = None,
    ):
        assert strategy in ("existent", "complete", "k_existent"), \
            f"Stratégie inconnue : {strategy}"
        self.strategy    = strategy
        self.k           = k
        self.threshold_p = threshold_p

    def _extract_services(self, tp: Dict) -> List[str]:
        """
        Extrait la liste ordonnée des services depuis un chemin.
        Supporte le format MetaBP-RTS (invocation_chain) et les formats alternatifs.
        """
        # Format MetaBP-RTS : invocation_chain = [[si, sj], [sj, sk], ...]
        chain = tp.get("invocation_chain", [])
        if chain:
            seen = []
            for pair in chain:
                for svc in pair:
                    if svc not in seen:
                        seen.append(svc)
            return seen
        # Formats alternatifs
        return tp.get("services", tp.get("path", []))

    def score_and_select(
        self,
        test_suite_path: str,
        cit: Dict[str, float],
        s_echo: Optional[List[str]] = None,
    ) -> Dict:
        """
        Charge T, score chaque chemin, applique le tiering, et retourne T_sel.
        """
        with open(test_suite_path, encoding="utf-8") as f:
            test_suite = json.load(f)

        s_echo_set: Set[str] = set(s_echo) if s_echo else set()

        # Seuil p = min non-zero de la CIT (recommandation Chen et al.)
        non_zero = [v for v in cit.values() if v > 0]
        p = self.threshold_p if self.threshold_p is not None \
            else (min(non_zero) if non_zero else 0.0)

        logger.info(
            "TestScorer — stratégie=%s | p=%.4f | k=%d | |S_echo|=%d",
            self.strategy, p, self.k, len(s_echo_set),
        )

        # Scorer chaque chemin
        test_scores = []
        for tp in test_suite:
            services = self._extract_services(tp)

            impacts    = [cit.get(s, 0.0) for s in services]
            score_max  = max(impacts) if impacts else 0.0
            score_avg  = round(
                sum(impacts) / max(len(impacts), 1), 6
            )
            n_above_p  = sum(1 for sc in impacts if sc >= p)

            # Tiering : Tier 1 si au moins un service ∈ S_echo
            in_s_echo  = any(s in s_echo_set for s in services)
            tier       = 1 if in_s_echo else 2

            test_scores.append({
                "test_id":    tp.get("test_id", tp.get("trace_id", tp.get("path_id", "?"))),
                "services":   services,
                "score":      round(score_max, 6),
                "score_avg":  score_avg,
                "n_above_p":  n_above_p,
                "n_services": len(services),
                "tier":       tier,
                "in_s_echo":  in_s_echo,
            })

        # Tri stable : score desc, score_avg desc, test_id asc
        test_scores.sort(
            key=lambda x: (-x["score"], -x["score_avg"], x["test_id"])
        )

        # Séparation Tier 1 / Tier 2
        tier1 = [tp for tp in test_scores if tp["tier"] == 1]
        tier2 = [tp for tp in test_scores if tp["tier"] == 2]

        # Sélection selon stratégie (sur l'ensemble complet)
        selected = self._select(test_scores, p)

        # Statistiques
        n_total    = len(test_scores)
        n_selected = len(selected)
        n_tier1    = len(tier1)
        n_tier2    = len(tier2)
        reduction  = round(1 - n_selected / max(n_total, 1), 4)

        logger.info(
            "TestScorer — %d tests : Tier1=%d | Tier2=%d | "
            "sélectionnés=%d (réduction=%.1f%%)",
            n_total, n_tier1, n_tier2, n_selected, reduction * 100,
        )

        return {
            "strategy":       self.strategy,
            "threshold_p":    round(p, 6),
            "k":              self.k,
            "test_scores":    test_scores,
            "tier1":          tier1,
            "tier2":          tier2,
            "selected_tests": selected,
            "stats": {
                "n_total":        n_total,
                "n_tier1":        n_tier1,
                "n_tier2":        n_tier2,
                "n_selected":     n_selected,
                "reduction_rate": reduction,
                "reduction_pct":  f"{reduction*100:.1f}%",
                "tier1_pct":      f"{n_tier1/max(n_total,1)*100:.1f}%",
                "tier2_pct":      f"{n_tier2/max(n_total,1)*100:.1f}%",
            },
        }

    def _select(self, test_scores: List[Dict], p: float) -> List[Dict]:
        """Applique la stratégie de sélection."""
        if self.strategy == "existent":
            # ∃s ∈ S_tp : CIT(s) >= p
            return [tp for tp in test_scores if tp["n_above_p"] >= 1]
        elif self.strategy == "complete":
            # ∀s ∈ S_tp : CIT(s) >= p
            return [
                tp for tp in test_scores
                if tp["n_above_p"] == tp["n_services"]
            ]
        elif self.strategy == "k_existent":
            # |{s : CIT(s)>=p}| >= k
            return [tp for tp in test_scores if tp["n_above_p"] >= self.k]
        return []

    def save(
        self,
        result: Dict,
        scores_path: str,
        selected_path: str,
        tier1_path: str = None,
        tier2_path: str = None,
    ) -> None:
        """
        Sauvegarde les artefacts Phase 2 → Phase 3.

        tier1_path et tier2_path sont les artefacts consommés par Phase 3.
        """
        self._write(scores_path, result["test_scores"])
        self._write(selected_path, result["selected_tests"])

        if tier1_path:
            self._write(tier1_path, {
                "tier": 1,
                "description": "Tests traversant au moins un Service Echo-Impact",
                "n_tests": result["stats"]["n_tier1"],
                "tests": result["tier1"],
            })

        if tier2_path:
            self._write(tier2_path, {
                "tier": 2,
                "description": "Tests ne traversant aucun Service Echo-Impact — candidats PSO Phase 3",
                "n_tests": result["stats"]["n_tier2"],
                "tests": result["tier2"],
            })

    @staticmethod
    def _write(path_str: str, data) -> None:
        path = Path(path_str)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("%s → %s", type(data).__name__, path)