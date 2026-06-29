import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, List
import yaml

logger = logging.getLogger(__name__)


class MutationVerifier:

    def __init__(self, mr_catalog_path=None, mr_catalog=None):
        self.lat, self.err, self.cmp = {}, {}, {}
        path = mr_catalog_path
        if path is None and isinstance(mr_catalog, str):
            path = mr_catalog
        if path:
            self._load_thresholds(path)

    def _load_thresholds(self, path):
        with open(path, encoding="utf-8") as f:
            cat = yaml.safe_load(f) or {}
        rel = cat.get("mr_catalog") or cat.get("relations") or []
        for mr in rel:
            svc = mr.get("service")
            t = mr.get("type")
            if t == "Latence" and "threshold_us" in mr:
                self.lat[svc] = int(mr["threshold_us"])
            elif t == "Erreur" and "threshold_error_rate" in mr:
                self.err[svc] = float(mr["threshold_error_rate"])
            elif t == "Completude" and "threshold_min_spans" in mr:
                self.cmp[svc] = int(mr["threshold_min_spans"])
        logger.info("MutationVerifier — seuils charges : %d Lat, %d Err, %d Cmp",
                    len(self.lat), len(self.err), len(self.cmp))

    def verify_mutants(self, mutants):
        results = []
        n_killed = 0
        by_op = defaultdict(lambda: {"killed": 0, "total": 0})
        for m in mutants:
            op = m.get("operator")
            svc = m.get("target_service")
            killed = False
            reason = "Aucun seuil pour ce service"
            if op == "latency_injection" and svc in self.lat:
                val = m.get("mutated_duration_us", 0)
                killed = val > self.lat[svc]
                reason = f"duration {val} vs seuil {self.lat[svc]}"
            elif op == "error_injection" and svc in self.err:
                val = m.get("mutated_error_rate", 0.0)
                killed = val > self.err[svc]
                reason = f"taux {val} vs seuil {self.err[svc]}"
            elif op == "span_deletion" and svc in self.cmp:
                val = m.get("spans_after_deletion", 0)
                killed = val < self.cmp[svc]
                reason = f"spans {val} vs min {self.cmp[svc]}"
            r = dict(m)
            r["killed"] = killed
            r["reason"] = reason
            results.append(r)
            by_op[op]["total"] += 1
            if killed:
                n_killed += 1
                by_op[op]["killed"] += 1
        n_total = len(mutants)
        fcs = round(n_killed / max(n_total, 1) * 100, 2)
        by_operator = {}
        for op, s in by_op.items():
            by_operator[op] = {"n_killed": s["killed"], "n_total": s["total"],
                               "fcs": round(s["killed"] / max(s["total"], 1) * 100, 2)}
        logger.info("MutationVerifier — %d mutants | %d tues | %d survivants | FCS=%.2f%%",
                    n_total, n_killed, n_total - n_killed, fcs)
        for op, s in by_operator.items():
            logger.info("  %-25s : %d/%d tues (FCS=%.2f%%)",
                        op, s["n_killed"], s["n_total"], s["fcs"])
        return {"results": results, "fcs": fcs, "n_total": n_total,
                "n_killed": n_killed, "n_survived": n_total - n_killed,
                "by_operator": by_operator, "by_mr_type": {}}

    def save(self, verification, results_path, fcs_path):
        p1 = Path(results_path)
        p1.parent.mkdir(parents=True, exist_ok=True)
        with open(p1, "w", encoding="utf-8") as f:
            json.dump(verification["results"], f, indent=2, ensure_ascii=False)
        p2 = Path(fcs_path)
        with open(p2, "w", encoding="utf-8") as f:
            json.dump({k: verification[k] for k in
                       ("fcs", "n_total", "n_killed", "n_survived", "by_operator")},
                      f, indent=2, ensure_ascii=False)
        logger.info("Rapport FCS -> %s", p2)
