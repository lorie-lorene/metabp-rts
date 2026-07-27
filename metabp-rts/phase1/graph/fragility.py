

import logging
from collections import defaultdict
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

RawEdge = Tuple[str, str, int, bool]  


class FragilityCalculator:
    def compute(self, edge_list: List[RawEdge]) -> Dict[str, float]:
        if not edge_list:
            logger.warning("FragilityCalculator : edge_list vide")
            return {}

        raw_scores = self._aggregate_errors(edge_list)
        normalized = self._normalize(raw_scores)

        logger.info(
            "FragilityCalculator → %d services scorés | max F=%.4f",
            len(normalized), max(normalized.values(), default=0),
        )
        return normalized



    def compute_from_spans(self, spans) -> Dict[str, float]:
       
        total: Dict[str, int] = defaultdict(int)
        errors: Dict[str, int] = defaultdict(int)
        for sp in spans:
            total[sp.service_name] += 1
            if sp.error:
                errors[sp.service_name] += 1
        raw = {svc: errors[svc] / total[svc] for svc in total}
        norm = self._normalize(raw)
        logger.info(
            "FragilityCalculator (spans) → %d services | max F=%.4f | %d spans en erreur",
            len(norm), max(norm.values(), default=0), sum(errors.values()),
        )
        return norm

    def _aggregate_errors(
        self,
        edge_list: List[RawEdge],
    ) -> Dict[str, float]:
        
        total_calls: Dict[str, int] = defaultdict(int)
        total_errors: Dict[str, int] = defaultdict(int)

        for source, _, _, error in edge_list:
            total_calls[source] += 1
            if error:
                total_errors[source] += 1

        return {
            service: total_errors[service] / total_calls[service]
            for service in total_calls
        }

    def _normalize(self, raw_scores: Dict[str, float]) -> Dict[str, float]:
        max_val = max(raw_scores.values(), default=0.0)
        if max_val == 0.0:
            return {k: 0.0 for k in raw_scores}
        return {
            k: round(v / max_val, 6)
            for k, v in raw_scores.items()
        }