# phase4/metamorphic/online/mr_runner.py
"""
Exécute les paires (source, follow-up) contre le SUT vivant via queries.Query
et applique la relation-oracle. Produit un rapport P_mr online.
Train-Ticket doit être UP pour ce module (utilisé en S3/S4, pas maintenant).
"""
import json, logging
from pathlib import Path

logger = logging.getLogger("mr-online")


class MRRunner:
    def __init__(self, query_client, capture_path=None):
        self.q = query_client          # instance de queries.Query (déjà loggée)
        self.capture_path = capture_path

    def _exec(self, method, endpoint, payload, headers_override):
        url = f"{self.q.address}{endpoint}"
        headers = dict(self.q.session.headers)
        headers.update(headers_override or {})
        if method == "POST":
            r = self.q.session.post(url, json=payload, headers=headers)
        else:
            r = self.q.session.get(url, headers=headers)
        try:
            body = r.json()
        except Exception:
            body = None
        return {"status": r.status_code, "json": body}

    def run_pair(self, mr, source_call, ctx):
        # 1) exécuter la source
        rs = self._exec(*source_call)
        # 2) construire + exécuter le follow-up via T
        method, endpoint, payload, hdr = mr.transform(ctx)
        rf = self._exec(method, endpoint, payload, hdr)
        # 3) appliquer l'oracle R
        ok, detail = mr.relation(rs, rf)
        return {"mr": mr.name, "passed": ok, "detail": detail,
                "src_status": rs["status"], "follow_status": rf["status"]}

    def run_suite(self, mr_list, contexts):
        results, n_pass = [], 0
        for ctx in contexts:
            source_call = (ctx["src_method"], ctx["src_endpoint"],
                           ctx["src_payload"], {})
            for mr in mr_list:
                if mr.has_side_effect:      # MR5 isolée : run dédié
                    continue
                res = self.run_pair(mr, source_call, ctx)
                results.append(res)
                n_pass += int(res["passed"])
        p_mr = round(100 * n_pass / max(len(results), 1), 2)
        logger.info("MR online — %d paires | %d PASS | P_mr=%.2f%%",
                    len(results), n_pass, p_mr)
        return {"results": results, "n": len(results),
                "n_pass": n_pass, "p_mr": p_mr}