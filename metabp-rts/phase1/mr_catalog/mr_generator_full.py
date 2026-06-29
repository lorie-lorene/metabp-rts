"""
mr_generator_full.py — composant Phase 1 (Chemin 2)
Genere TROIS familles de MR data-driven depuis les traces Jaeger :
  - Latence    : duration_us <= seuil P99 appris par service
  - Erreur     : taux_erreur <= taux_nominal + marge (appris par service)
  - Completude : nb_spans(service par trace) >= seuil nominal appris
Deux entrees :
  - generate(traces_path)      : depuis un fichier JSON brut (standalone)
  - generate_from_spans(spans) : depuis une liste de SpanRecord (pipeline)
Champs techniques (threshold_*) preserves pour la Phase 4.
"""

import json
import logging
import statistics
from collections import defaultdict
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


class MRGeneratorFull:

    def __init__(self, percentile=99.0, min_samples=5, error_margin=0.10):
        self.percentile = percentile
        self.min_samples = min_samples
        self.error_margin = error_margin

    # ---------- ENTREE 1 : fichier de traces brut ----------
    def _load_traces(self, path):
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        return raw.get("data", raw) if isinstance(raw, dict) else raw

    def _span_error_raw(self, span):
        for t in span.get("tags", []):
            if t.get("key") == "error" and t.get("value") is True:
                return True
        return False

    def generate(self, traces_path):
        traces = self._load_traces(traces_path)
        durations = defaultdict(list)
        err_count = defaultdict(lambda: {"err": 0, "tot": 0})
        per_trace_svc = defaultdict(list)
        for tr in traces:
            procs = {p: v.get("serviceName", "unknown")
                     for p, v in tr.get("processes", {}).items()}
            here = defaultdict(int)
            for s in tr.get("spans", []):
                svc = procs.get(s.get("processID", ""), None)
                if not svc or svc == "unknown":
                    continue
                d = s.get("duration", None)
                if isinstance(d, (int, float)):
                    durations[svc].append(int(d))
                err_count[svc]["tot"] += 1
                if self._span_error_raw(s):
                    err_count[svc]["err"] += 1
                here[svc] += 1
            for svc, n in here.items():
                per_trace_svc[svc].append(n)
        return self._build_mrs(durations, err_count, per_trace_svc)

    # ---------- ENTREE 2 : liste de SpanRecord en memoire ----------
    def generate_from_spans(self, spans):
        durations = defaultdict(list)
        err_count = defaultdict(lambda: {"err": 0, "tot": 0})
        by_trace = defaultdict(lambda: defaultdict(int))
        for sp in spans:
            svc = getattr(sp, "service_name", None)
            if not svc or svc == "unknown":
                continue
            d = getattr(sp, "duration_us", None)
            if isinstance(d, (int, float)):
                durations[svc].append(int(d))
            err_count[svc]["tot"] += 1
            if getattr(sp, "error", False):
                err_count[svc]["err"] += 1
            by_trace[getattr(sp, "trace_id", "?")][svc] += 1
        per_trace_svc = defaultdict(list)
        for _tid, counts in by_trace.items():
            for svc, n in counts.items():
                per_trace_svc[svc].append(n)
        return self._build_mrs(durations, err_count, per_trace_svc)

    # ---------- noyau commun ----------
    def _percentile(self, values, p):
        if not values:
            return 0
        s = sorted(values)
        k = (len(s) - 1) * (p / 100.0)
        lo = int(k); hi = min(lo + 1, len(s) - 1)
        return int(s[lo] + (s[hi] - s[lo]) * (k - lo))

    def _build_mrs(self, durations, err_count, per_trace_svc):
        mrs = []
        for svc in sorted(durations):
            samples = durations[svc]
            if len(samples) < self.min_samples:
                continue
            # LATENCE
            seuil_us = self._percentile(samples, self.percentile)
            mrs.append({
                "id": f"MR-LAT-{svc}", "type": "Latence", "service": svc,
                "endpoint": "*", "http_method": "*",
                "phi": f"Appel equivalent de {svc} ; mediane ~ {round(statistics.median(samples)/1000,1)} ms",
                "rho": f"duration_us <= {seuil_us} (P{int(self.percentile)})",
                "source": f"traces-p{int(self.percentile)}",
                "threshold_us": seuil_us,
            })
            # ERREUR
            ec = err_count[svc]
            taux = ec["err"] / ec["tot"] if ec["tot"] else 0.0
            seuil_err = round(min(1.0, taux + self.error_margin), 4)
            mrs.append({
                "id": f"MR-ERR-{svc}", "type": "Erreur", "service": svc,
                "endpoint": "*", "http_method": "*",
                "phi": f"Taux d'erreur nominal de {svc} = {round(taux*100,1)}%",
                "rho": f"taux_erreur <= {seuil_err} (nominal {round(taux,4)} + marge {self.error_margin})",
                "source": "traces-error",
                "threshold_error_rate": seuil_err,
                "nominal_error_rate": round(taux, 4),
            })
            # COMPLETUDE
            counts = per_trace_svc.get(svc, [])
            if counts:
                seuil_span = max(1, self._percentile(counts, 5.0))
                mrs.append({
                    "id": f"MR-CMP-{svc}", "type": "Completude", "service": svc,
                    "endpoint": "*", "http_method": "*",
                    "phi": f"{svc} produit typiquement >= {seuil_span} span(s) par trace",
                    "rho": f"nb_spans({svc}) >= {seuil_span}",
                    "source": "traces-completude",
                    "threshold_min_spans": seuil_span,
                })
        n_lat = sum(1 for m in mrs if m["type"] == "Latence")
        n_err = sum(1 for m in mrs if m["type"] == "Erreur")
        n_cmp = sum(1 for m in mrs if m["type"] == "Completude")
        logger.info("MRGeneratorFull -> %d MR (%d Lat, %d Err, %d Cmp)",
                    len(mrs), n_lat, n_err, n_cmp)
        return mrs

    def save(self, mrs, out_path):
        p = Path(out_path); p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            yaml.dump({"mr_catalog": mrs}, f, default_flow_style=False,
                      allow_unicode=True, sort_keys=False)
        logger.info("MR -> %s", p)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--traces", required=True)
    ap.add_argument("--out", default="mr_full.yaml")
    ap.add_argument("--percentile", type=float, default=99.0)
    ap.add_argument("--error-margin", type=float, default=0.10)
    args = ap.parse_args()
    gen = MRGeneratorFull(percentile=args.percentile, error_margin=args.error_margin)
    mrs = gen.generate(args.traces)
    gen.save(mrs, args.out)
    print(f"{len(mrs)} MR generees")
