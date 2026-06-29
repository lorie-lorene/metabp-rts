"""
latence_verifier.py — Phase 4B (verification metamorphique, type Latence)
Verifie sur les VRAIES traces que chaque span d'un service respecte
le seuil de sa MR de latence (duration_us <= threshold_us).
Produit de vrais verdicts PASS/FAIL : P_mr nominal.
"""

import json
import logging
import yaml
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)


class LatenceVerifier:

    def __init__(self, mr_catalog_path: str):
        self.thresholds = self._load_latence_mrs(mr_catalog_path)

    def _load_latence_mrs(self, path: str) -> Dict[str, dict]:
        with open(path, encoding="utf-8") as f:
            catalog = yaml.safe_load(f) or {}
        relations = (catalog.get("mr_catalog")
                     or catalog.get("relations") or [])
        thresholds = {}
        for mr in relations:
            if mr.get("type") != "Latence":
                continue
            svc = mr.get("service")
            thr = mr.get("threshold_us")
            if svc and isinstance(thr, (int, float)):
                thresholds[svc] = {"mr_id": mr.get("id"), "threshold_us": int(thr)}
        logger.info("LatenceVerifier — %d MR de latence chargees", len(thresholds))
        return thresholds

    def _load_traces(self, traces_path: str) -> List[dict]:
        with open(traces_path, encoding="utf-8") as f:
            raw = json.load(f)
        return raw.get("data", raw) if isinstance(raw, dict) else raw

    def verify(self, traces_path: str) -> Dict:
        traces = self._load_traces(traces_path)
        n_pass, n_fail = 0, 0
        violations = []
        by_service = defaultdict(lambda: {"pass": 0, "fail": 0})

        for trace in traces:
            processes = {pid: p.get("serviceName", "unknown")
                         for pid, p in trace.get("processes", {}).items()}
            for span in trace.get("spans", []):
                svc = processes.get(span.get("processID", ""), None)
                if svc not in self.thresholds:
                    continue
                dur = span.get("duration", None)
                if not isinstance(dur, (int, float)):
                    continue
                thr = self.thresholds[svc]["threshold_us"]
                if dur <= thr:
                    n_pass += 1
                    by_service[svc]["pass"] += 1
                else:
                    n_fail += 1
                    by_service[svc]["fail"] += 1
                    violations.append({
                        "mr_id": self.thresholds[svc]["mr_id"],
                        "service": svc,
                        "duration_us": int(dur),
                        "threshold_us": thr,
                        "trace_id": trace.get("traceID", "?"),
                    })

        total = n_pass + n_fail
        p_mr = round(n_pass / total * 100, 2) if total else 0.0
        logger.info("LatenceVerifier — %d spans verifies | %d PASS | %d FAIL | P_mr=%.2f%%",
                    total, n_pass, n_fail, p_mr)

        return {
            "n_verified": total, "n_pass": n_pass, "n_fail": n_fail,
            "p_mr": p_mr, "violations": violations,
            "by_service": dict(by_service),
        }

    def save(self, result: Dict, out_path: str) -> None:
        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        logger.info("Resultats verification latence -> %s", path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--traces", required=True)
    ap.add_argument("--out", default="latence_verification.json")
    args = ap.parse_args()
    v = LatenceVerifier(args.catalog)
    res = v.verify(args.traces)
    v.save(res, args.out)
    print(f"\nP_mr (latence, nominal) = {res['p_mr']}%  "
          f"({res['n_pass']}/{res['n_verified']} spans)")
    print(f"Violations : {res['n_fail']}\n")
    for svc, st in sorted(res["by_service"].items()):
        tot = st["pass"] + st["fail"]
        print(f"  {svc:32s} {st['pass']:4d} PASS / {st['fail']:3d} FAIL  ({tot} spans)")
