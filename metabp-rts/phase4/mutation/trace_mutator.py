"""
trace_mutator.py — Phase 4A (Option A : mutation des VRAIES traces)
Pour chaque chemin t de T_sel, on retrouve la trace Jaeger reelle
(via test_id == traceID) et on mute ses spans reels :
  - latency_injection : duration <- latency_ms*1000 (us)
  - error_injection   : error <- True sur un span sain
  - span_deletion     : retrait d'un span d'un service donne
Chaque mutant porte le service cible, la valeur mutee et le nb de spans
du service apres mutation, pour une verification PAR SEUIL (pas par type).
"""

import json
import logging
import copy
import random
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class TraceMutator:

    OPERATORS = ["span_deletion", "error_injection", "latency_injection"]

    def __init__(self, operators: Optional[List[str]] = None,
                 latency_ms: int = 5000, max_mutants_per_path: int = 3,
                 traces_path: str = None, seed: int = 42):
        self.operators = operators or self.OPERATORS
        self.latency_us = latency_ms * 1000
        self.max_mutants_per_path = max_mutants_per_path
        self.traces_path = traces_path
        random.seed(seed)
        self._trace_index = None

    def _load_trace_index(self) -> Dict[str, dict]:
        """Indexe les traces brutes par traceID, avec service_name par span."""
        if self._trace_index is not None:
            return self._trace_index
        if not self.traces_path:
            raise ValueError("traces_path non defini pour TraceMutator")
        with open(self.traces_path, encoding="utf-8") as f:
            raw = json.load(f)
        traces = raw.get("data", raw) if isinstance(raw, dict) else raw
        index = {}
        for tr in traces:
            procs = {p: v.get("serviceName", "unknown")
                     for p, v in tr.get("processes", {}).items()}
            spans = []
            for s in tr.get("spans", []):
                svc = procs.get(s.get("processID", ""), "unknown")
                is_err = any(t.get("key") == "error" and t.get("value") is True
                             for t in s.get("tags", []))
                spans.append({
                    "span_id": s.get("spanID", ""),
                    "service": svc,
                    "duration": int(s.get("duration", 0)),
                    "error": is_err,
                })
            index[tr.get("traceID")] = spans
        self._trace_index = index
        logger.info("TraceMutator — %d traces indexees", len(index))
        return index

    def _svc_span_count(self, spans, svc):
        return sum(1 for s in spans if s["service"] == svc)

    def generate_mutants(self, t_sel: List[Dict]) -> List[Dict]:
        index = self._load_trace_index()
        mutants = []
        skipped = 0

        for tp in t_sel:
            tid = tp.get("test_id", tp.get("trace_id"))
            spans = index.get(tid)
            if not spans or len(spans) < 1:
                skipped += 1
                continue

            count = 0
            for operator in self.operators:
                if count >= self.max_mutants_per_path:
                    break

                if operator == "latency_injection":
                    # cible : un span au hasard
                    s = random.choice(spans)
                    svc = s["service"]
                    mutants.append({
                        "mutant_id": f"{tid}__lat__{svc}",
                        "test_id": tid, "operator": operator,
                        "target_service": svc,
                        "mutated_duration_us": self.latency_us,
                        "killed": False,
                    })
                    count += 1

                elif operator == "error_injection":
                    # cible : un span SAIN (sinon l'injection ne change rien)
                    sains = [s for s in spans if not s["error"]]
                    if not sains:
                        continue
                    s = random.choice(sains)
                    svc = s["service"]
                    tot = self._svc_span_count(spans, svc)
                    err = sum(1 for x in spans if x["service"] == svc and x["error"])
                    taux_mute = (err + 1) / tot if tot else 1.0
                    mutants.append({
                        "mutant_id": f"{tid}__err__{svc}",
                        "test_id": tid, "operator": operator,
                        "target_service": svc,
                        "mutated_error_rate": round(taux_mute, 4),
                        "killed": False,
                    })
                    count += 1

                elif operator == "span_deletion":
                    s = random.choice(spans)
                    svc = s["service"]
                    apres = self._svc_span_count(spans, svc) - 1
                    mutants.append({
                        "mutant_id": f"{tid}__del__{svc}",
                        "test_id": tid, "operator": operator,
                        "target_service": svc,
                        "spans_after_deletion": apres,
                        "killed": False,
                    })
                    count += 1

        logger.info("TraceMutator — %d chemins T_sel → %d mutants reels "
                    "(%d chemins sans trace, ignores)",
                    len(t_sel), len(mutants), skipped)
        return mutants

    def save(self, mutants: List[Dict], output_path: str) -> None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(mutants, f, indent=2, ensure_ascii=False)
        logger.info("Mutants sauvegardes → %s (%d)", path, len(mutants))
