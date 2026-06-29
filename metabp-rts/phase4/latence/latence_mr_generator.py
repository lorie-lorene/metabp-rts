"""
latence_mr_generator.py — CHEMIN 2
Genere une MR de Latence par service, seuil appris des donnees (percentile).
ID unique base sur le nom de service complet (evite les collisions de prefixe).
"""

import json
import logging
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

import yaml

logger = logging.getLogger(__name__)


class LatenceMRGenerator:

    def __init__(self, percentile: float = 99.0, min_samples: int = 5):
        self.percentile = percentile
        self.min_samples = min_samples

    def _collect_durations(self, traces: List[dict]) -> Dict[str, List[int]]:
        durations: Dict[str, List[int]] = defaultdict(list)
        for trace in traces:
            processes = {
                pid: proc.get("serviceName", "unknown")
                for pid, proc in trace.get("processes", {}).items()
            }
            for span in trace.get("spans", []):
                svc = processes.get(span.get("processID", ""), None)
                dur = span.get("duration", None)
                if svc and svc != "unknown" and isinstance(dur, (int, float)):
                    durations[svc].append(int(dur))
        return dict(durations)

    def _percentile(self, values: List[int], p: float) -> int:
        if not values:
            return 0
        s = sorted(values)
        k = (len(s) - 1) * (p / 100.0)
        lo = int(k)
        hi = min(lo + 1, len(s) - 1)
        frac = k - lo
        return int(s[lo] + (s[hi] - s[lo]) * frac)

    def generate(self, traces_path: str) -> List[dict]:
        with open(traces_path, encoding="utf-8") as f:
            raw = json.load(f)
        traces = raw.get("data", raw) if isinstance(raw, dict) else raw
        durations = self._collect_durations(traces)

        mrs: List[dict] = []
        skipped = []
        for svc in sorted(durations):
            samples = durations[svc]
            if len(samples) < self.min_samples:
                skipped.append((svc, len(samples)))
                continue
            seuil_us = self._percentile(samples, self.percentile)
            seuil_ms = round(seuil_us / 1000.0, 1)
            median_ms = round(statistics.median(samples) / 1000.0, 1)
            mrs.append({
                "id": f"MR-LAT-{svc}",
                "type": "Latence",
                "service": svc,
                "endpoint": "*",
                "http_method": "*",
                "phi": (f"Appel equivalent de {svc} ; "
                        f"comportement nominal median ~ {median_ms} ms "
                        f"({len(samples)} spans observes)"),
                "rho": (f"duration_us <= {seuil_us}  "
                        f"(seuil P{int(self.percentile)} appris = {seuil_ms} ms)"),
                "source": "traces-p" + str(int(self.percentile)),
                "threshold_us": seuil_us,
            })

        logger.info("LatenceMRGenerator -> %d MR generees | %d services ignores (< %d spans)",
                    len(mrs), len(skipped), self.min_samples)
        if skipped:
            logger.info("Services ignores : %s", skipped)
        return mrs

    def save(self, mrs: List[dict], output_path: str) -> None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump({"mr_catalog": mrs}, f,
                      default_flow_style=False, allow_unicode=True, sort_keys=False)
        logger.info("MR de latence -> %s", path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--traces", required=True)
    ap.add_argument("--out", default="latence_mr.yaml")
    ap.add_argument("--percentile", type=float, default=99.0)
    ap.add_argument("--min-samples", type=int, default=5)
    args = ap.parse_args()
    gen = LatenceMRGenerator(percentile=args.percentile, min_samples=args.min_samples)
    mrs = gen.generate(args.traces)
    gen.save(mrs, args.out)
    print(f"\n{len(mrs)} MR de latence generees :\n")
    for mr in mrs:
        print(f"  {mr['id']:42s} {mr['service']:32s} {mr['rho']}")
