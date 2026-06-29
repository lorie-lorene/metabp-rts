"""
mutator_full.py — Phase 4A : mutation multi-operateurs
Applique 3 operateurs sur les vraies traces et mesure le FCS par famille :
  - latency_injection  -> detectee par MR Latence
  - error_injection    -> detectee par MR Erreur
  - span_deletion      -> detectee par MR Completude
Un mutant est TUE si la MR de la famille correspondante voit l'anomalie.
"""

import json
import logging
import random
import yaml
from collections import defaultdict
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")
logger = logging.getLogger("mutator-full")


class MutatorFull:

    def __init__(self, catalog_path, injected_ms=5000, seed=42):
        self.injected_us = injected_ms * 1000
        random.seed(seed)
        self.lat, self.err, self.cmp = self._load(catalog_path)

    def _load(self, path):
        with open(path, encoding="utf-8") as f:
            cat = yaml.safe_load(f) or {}
        rel = cat.get("mr_catalog") or []
        lat, err, cmp = {}, {}, {}
        for mr in rel:
            svc, t = mr.get("service"), mr.get("type")
            if t == "Latence" and "threshold_us" in mr:
                lat[svc] = mr["threshold_us"]
            elif t == "Erreur" and "threshold_error_rate" in mr:
                err[svc] = mr["threshold_error_rate"]
            elif t == "Completude" and "threshold_min_spans" in mr:
                cmp[svc] = mr["threshold_min_spans"]
        logger.info("Charge : %d Latence, %d Erreur, %d Completude", len(lat), len(err), len(cmp))
        return lat, err, cmp

    def _load_traces(self, path):
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        return raw.get("data", raw) if isinstance(raw, dict) else raw

    def _span_error(self, span):
        return any(t.get("key") == "error" and t.get("value") is True
                   for t in span.get("tags", []))

    def run(self, traces_path):
        traces = self._load_traces(traces_path)
        res = {op: {"killed": 0, "total": 0} for op in ("latence", "erreur", "suppression")}

        for tr in traces:
            procs = {p: v.get("serviceName", "unknown")
                     for p, v in tr.get("processes", {}).items()}
            spans = tr.get("spans", [])
            if not spans:
                continue

            # comptage nominal de spans par service dans cette trace
            svc_counts = defaultdict(int)
            for s in spans:
                svc = procs.get(s.get("processID", ""), None)
                if svc and svc != "unknown":
                    svc_counts[svc] += 1

            # ---- OP1 : latency_injection ----
            s = random.choice(spans)
            svc = procs.get(s.get("processID", ""), None)
            if svc in self.lat:
                res["latence"]["total"] += 1
                if self.injected_us > self.lat[svc]:        # MR Latence detecte
                    res["latence"]["killed"] += 1

            # ---- OP2 : error_injection ----
            s = random.choice(spans)
            svc = procs.get(s.get("processID", ""), None)
            if svc in self.err and not self._span_error(s):
                res["erreur"]["total"] += 1
                # apres injection, ce service a au moins 1 erreur dans cette trace.
                # taux local = (erreurs existantes +1)/total_spans_du_svc
                base_err = sum(1 for x in spans
                               if procs.get(x.get("processID",""),None)==svc and self._span_error(x))
                tot = svc_counts[svc]
                taux_mute = (base_err + 1) / tot if tot else 1.0
                if taux_mute > self.err[svc]:               # MR Erreur detecte
                    res["erreur"]["killed"] += 1

            # ---- OP3 : span_deletion ----
            s = random.choice(spans)
            svc = procs.get(s.get("processID", ""), None)
            if svc in self.cmp:
                res["suppression"]["total"] += 1
                apres = svc_counts[svc] - 1                  # un span de svc supprime
                if apres < self.cmp[svc]:                    # MR Completude detecte
                    res["suppression"]["killed"] += 1

        # FCS par operateur + global
        report = {}
        gk = gt = 0
        for op, c in res.items():
            fcs = round(c["killed"] / c["total"] * 100, 2) if c["total"] else 0.0
            report[op] = {"killed": c["killed"], "total": c["total"], "fcs": fcs}
            gk += c["killed"]; gt += c["total"]
        report["global"] = {"killed": gk, "total": gt,
                            "fcs": round(gk / gt * 100, 2) if gt else 0.0}
        return report

    def save(self, report, out):
        p = Path(out); p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--traces", required=True)
    ap.add_argument("--injected-ms", type=int, default=5000)
    ap.add_argument("--out", default="mutation_full.json")
    args = ap.parse_args()
    m = MutatorFull(args.catalog, injected_ms=args.injected_ms)
    rep = m.run(args.traces)
    m.save(rep, args.out)
    print("\n===== FCS par operateur de mutation =====\n")
    for op in ("latence", "erreur", "suppression"):
        r = rep[op]
        print(f"  {op:14s} FCS = {r['fcs']:6.2f}%   ({r['killed']}/{r['total']} mutants tues)")
    g = rep["global"]
    print(f"\n  {'GLOBAL':14s} FCS = {g['fcs']:6.2f}%   ({g['killed']}/{g['total']})\n")
