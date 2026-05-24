"""
et_calculator.py — Métrique ET (Testing time cost saving rate)
Calcul de ET selon Chen et al. (2023), Formule 9 :
    ET = (TO - TR - TS) / TO × 100%
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ETCalculator:

    @staticmethod
    def _extract_duration_us(tp: Dict) -> int:
        return int(tp.get("duration_us", 0))

    def compute(
        self,
        t_original: List[Dict],
        t_sel: List[Dict],
        ts_seconds: float,
        ts_breakdown: Optional[Dict[str, float]] = None,
    ) -> Dict:
        to_us = sum(self._extract_duration_us(tp) for tp in t_original)
        tr_us = sum(self._extract_duration_us(tp) for tp in t_sel)
        ts_us = int(ts_seconds * 1_000_000)

        n_with_duration = sum(
            1 for tp in t_original if self._extract_duration_us(tp) > 0
        )
        coverage_duration = n_with_duration > 0

        if to_us > 0:
            et = round((to_us - tr_us - ts_us) / to_us * 100, 2)
        else:
            et = 0.0

        n_original = len(t_original)
        n_sel      = len(t_sel)
        en = round((n_original - n_sel) / max(n_original, 1) * 100, 2)

        if not coverage_duration:
            logger.warning(
                "ETCalculator — AUCUNE durée trouvée dans T. "
                "Re-tourner Phase 1 pour enrichir test_suite_T.json "
                "avec duration_us. ET non fiable."
            )

        logger.info(
            "ETCalculator — TO=%.3fs | TR=%.3fs | TS=%.3fs | ET=%.1f%% | EN=%.1f%%",
            to_us / 1e6, tr_us / 1e6, ts_us / 1e6, et, en,
        )

        result = {
            "TO_us": to_us, "TR_us": tr_us, "TS_us": ts_us,
            "TO_s":  round(to_us / 1e6, 4),
            "TR_s":  round(tr_us / 1e6, 4),
            "TS_s":  round(ts_us / 1e6, 4),
            "ET":    et,
            "EN":    en,
            "n_original":        n_original,
            "n_sel":             n_sel,
            "n_with_duration":   n_with_duration,
            "coverage_duration": coverage_duration,
            "note": (
                "TS mesuré directement (Phase 1+2+3) ; TO/TR estimés via "
                "latences Jaeger (duration_us du span racine). "
                "Mode online = raffinement futur."
            ),
        }

        if ts_breakdown:
            result["TS_breakdown_s"] = {
                k: round(v, 4) for k, v in ts_breakdown.items()
            }
            result["note_breakdown"] = (
                "Phase 1 est un coût amortissable (indépendant de ΔS, "
                "calculé une fois et réutilisé). Phase 2+3 se relancent à "
                "chaque cycle de régression."
            )

        return result

    def save(self, et_result: Dict, output_path: str) -> None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(et_result, f, indent=2, ensure_ascii=False)
        logger.info("Rapport ET → %s", path)