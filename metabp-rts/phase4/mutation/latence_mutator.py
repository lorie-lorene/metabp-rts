"""
latence_mutator.py — Phase 4A (mutation de traces, FCS)
Injecte des anomalies de latence dans les vraies traces et mesure
combien sont detectees par les MR de latence (mutants tues).
FCS = mutants_tues / mutants_total.
"""

import json
import logging
import random
import yaml
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)


class LatenceMutator:

    def __init__(self, mr_catalog_path: str, injected_us: int = 5_000_000,
                 sample_rate: float = 1.0, seed: int = 42):
        """
        injected_us : latence anormale injectee (defaut 5000 ms).
        sample_rate : fraction de spans mutables a muter (1.0 = tous).
        """
        self.thresholds = self._load(mr_catalog_path)
        self.injected_us = injected_us
        self.sample_rate = sample_rate
        random.seed(seed)

    def _load(self, path: str) -> Dict[str, int]:
        with open(path, encoding="utf-8") as f:
            catalog = yaml.safe_load(f) or {}
        relations = catalog.get("mr_catalog") or catalog.get("relations") or []
        thr = {}
        for mr in relations:
            if mr.get("type") == "Latence" and isinstance(mr.get("threshold_us"), (int, float)):
                thr[mr["service"]] = int(mr["threshold_us"])
        logger.info("LatenceMutator — %d seuils de latence charges", len(thr))
        return thr

    def _load_traces(self, p: str) -> List[dict]:
        with open(p, encoding="utf-8") as f:
            raw = json.load(f)
        return raw.get("data", raw) if isinstance(raw, dict) else raw

    def run(self, traces_path: str) -> Dict:
        traces = self._load_traces(traces_path)
        total, killed = 0, 0
        by_service = defaultdict(lambda: {"killed": 0, "survived": 0})

        for trace in traces:
            processes = {pid: p.get("serviceName", "unknown")
                         for pid, p in trace.get("processes", {}).items()}
            for span in trace.get("spans", []):
                svc = processes.get(span.get("processID", ""), None)
                if svc not in self.thresholds:
                    continue
                if random.random() > self.sample_rate:
                    continue
                # MUTATION : on injecte une latence anormale
                mutated_dur = self.injected_us
                total += 1
                # VERIFICATION : la MR detecte-t-elle l'anomalie ?
                if mutated_dur > self.thresholds[svc]:
                    killed += 1
                    by_service[svc]["killed"] += 1
                else:
                    by_service[svc]["survived"] += 1

        fcs = round(killed / total * 100, 2) if total else 0.0
        logger.info("LatenceMutator — %d mutants | %d tues | FCS=%.2f%%",
                    total, killed, fcs)
        return {
            "n_mutants": total, "n_killed": killed,
            "n_survived": total - killed, "fcs": fcs,
            "injected_us": self.injected_us,
            "by_service": dict(by_service),
        }

    def save(self, result: Dict, out_path: str) -> None:
        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        logger.info("Resultats mutation -> %s", path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--traces", required=True)
    ap.add_argument("--injected-ms", type=int, default=5000)
    ap.add_argument("--out", default="latence_mutation.json")
    args = ap.parse_args()
    m = LatenceMutator(args.catalog, injected_us=args.injected_ms * 1000)
    res = m.run(args.traces)
    m.save(res, args.out)
    print(f"\nFCS (latence) = {res['fcs']}%  ({res['n_killed']}/{res['n_mutants']} mutants tues)")
    print(f"Latence injectee : {args.injected_ms} ms\n")
