"""
mr_verifier.py — Phase 4B (verification metamorphique PAR SEUIL reel)
Verifie les MR data-driven (Latence/Erreur/Completude) sur les VRAIS
spans des traces de T_sel (test_id == traceID), par seuil appris.
Produit un P_mr REEL (de vrais FAIL possibles), plus de PASS systematique.
"""

import json
import logging
import yaml
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

# Chemin par defaut relatif a ce fichier (phase4/metamorphic/ -> phase1/data/raw/)
_DEFAULT_TRACES = (Path(__file__).resolve().parent.parent.parent
                   / "phase1" / "data" / "raw" / "traces_raw.json")


class MRVerifier:

    def __init__(self, mr_catalog_path, mode="offline",
                 sut_url="http://localhost:8080", timeout=10,
                 traces_path=None):
        self.mode = mode
        self.sut_url = sut_url
        self.timeout = timeout
        self.traces_path = str(traces_path) if traces_path else str(_DEFAULT_TRACES)
        self.lat, self.err, self.cmp = self._load_thresholds(mr_catalog_path)
        self._index = None

    def _load_thresholds(self, path):
        with open(path, encoding="utf-8") as f:
            cat = yaml.safe_load(f) or {}
        rel = cat.get("mr_catalog") or cat.get("relations") or []
        lat, err, cmp = {}, {}, {}
        for mr in rel:
            svc, t = mr.get("service"), mr.get("type")
            if t == "Latence" and "threshold_us" in mr:
                lat[svc] = int(mr["threshold_us"])
            elif t == "Erreur" and "threshold_error_rate" in mr:
                err[svc] = float(mr["threshold_error_rate"])
            elif t == "Completude" and "threshold_min_spans" in mr:
                cmp[svc] = int(mr["threshold_min_spans"])
        logger.info("MRVerifier — seuils : %d Lat, %d Err, %d Cmp",
                    len(lat), len(err), len(cmp))
        return lat, err, cmp

    def _load_index(self):
        if self._index is not None:
            return self._index
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
                spans.append({"service": svc,
                              "duration": int(s.get("duration", 0)),
                              "error": is_err})
            index[tr.get("traceID")] = spans
        self._index = index
        logger.info("MRVerifier — %d traces indexees", len(index))
        return index

    def verify_t_sel(self, t_sel: List[Dict]) -> Dict:
        index = self._load_index()
        all_results = []
        violations = []
        n_pass = n_fail = 0
        by_mr_type = defaultdict(lambda: {"pass": 0, "fail": 0})
        by_service = defaultdict(lambda: {"pass": 0, "fail": 0})

        for tp in t_sel:
            tid = tp.get("test_id", tp.get("trace_id"))
            spans = index.get(tid)
            if not spans:
                continue
            svc_spans = defaultdict(list)
            for s in spans:
                svc_spans[s["service"]].append(s)

            for svc, slist in svc_spans.items():
                if svc in self.lat:
                    thr = self.lat[svc]
                    for s in slist:
                        ok = s["duration"] <= thr
                        self._record(all_results, violations, by_mr_type,
                                     by_service, tid, svc, "Latence", ok,
                                     f"duration {s['duration']} vs {thr}")
                        if ok: n_pass += 1
                        else:  n_fail += 1
                if svc in self.err:
                    thr = self.err[svc]
                    taux = sum(1 for s in slist if s["error"]) / len(slist)
                    ok = taux <= thr
                    self._record(all_results, violations, by_mr_type,
                                 by_service, tid, svc, "Erreur", ok,
                                 f"taux {round(taux,3)} vs {thr}")
                    if ok: n_pass += 1
                    else:  n_fail += 1
                if svc in self.cmp:
                    thr = self.cmp[svc]
                    ok = len(slist) >= thr
                    self._record(all_results, violations, by_mr_type,
                                 by_service, tid, svc, "Completude", ok,
                                 f"nb_spans {len(slist)} vs min {thr}")
                    if ok: n_pass += 1
                    else:  n_fail += 1

        n_mr = n_pass + n_fail
        pass_rate = round(n_pass / max(n_mr, 1) * 100, 2)
        logger.info("MRVerifier — %d tests | %d MR verifiees | %d PASS | %d FAIL | taux=%.2f%%",
                    len(t_sel), n_mr, n_pass, n_fail, pass_rate)
        if violations:
            logger.warning("%d MR non conformes (variabilite nominale + anomalies preexistantes)",
                           len(violations))
        else:
            logger.info("Aucune non-conformite MR (mode %s)", self.mode)

        return {
            "results": all_results, "n_tests": len(t_sel),
            "n_mr_verified": n_mr, "n_pass": n_pass, "n_fail": n_fail,
            "violations": violations, "pass_rate": pass_rate,
            "by_mr_type": dict(by_mr_type), "by_service": dict(by_service),
            "mode": self.mode,
        }

    def _record(self, results, violations, by_type, by_svc,
                tid, svc, mr_type, passed, reason):
        r = {"test_id": tid, "service": svc, "mr_type": mr_type,
             "passed": passed, "reason": reason}
        results.append(r)
        if passed:
            by_type[mr_type]["pass"] += 1
            by_svc[svc]["pass"] += 1
        else:
            by_type[mr_type]["fail"] += 1
            by_svc[svc]["fail"] += 1
            violations.append(r)

    def save(self, verification, pairs_path, results_path):
        p1 = Path(pairs_path); p1.parent.mkdir(parents=True, exist_ok=True)
        with open(p1, "w", encoding="utf-8") as f:
            json.dump(verification["violations"], f, indent=2, ensure_ascii=False)
        logger.info("Non-conformites MR -> %s (%d)", p1, len(verification["violations"]))
        p2 = Path(results_path)
        with open(p2, "w", encoding="utf-8") as f:
            json.dump({k: verification[k] for k in
                       ("n_tests", "n_mr_verified", "n_pass", "n_fail",
                        "pass_rate", "mode", "by_mr_type", "by_service")},
                      f, indent=2, ensure_ascii=False)
        logger.info("Resultats verification MR -> %s", p2)
