"""
Génère les contextes de test métamorphique à partir des request_body réels
capturés dans responses.jsonl (on n'utilise QUE les requêtes, pas les réponses
capturées — les réponses viendront du système live en S3).
"""
import json
from pathlib import Path


SEARCH_ENDPOINTS = {
    "/api/v1/travelservice/trips/left",
    "/api/v1/travel2service/trips/left",
}


def load_search_contexts(responses_path, limit=None):
    contexts, seen = [], set()
    for line in Path(responses_path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("endpoint") not in SEARCH_ENDPOINTS:
            continue
        body = r.get("request_body") or {}
        start, end = body.get("startingPlace"), body.get("endPlace")
        date = body.get("departureTime")
        if not (start and end and date):
            continue
        key = (start, end, date)
        if key in seen:                    # dédupliquer les paires identiques
            continue
        seen.add(key)
        contexts.append({
            "src_method": "POST",
            "src_endpoint": r["endpoint"],
            "src_payload": {"departureTime": date,
                            "startingPlace": start, "endPlace": end},
            "date": date, "start": start, "end": end,
        })
        if limit and len(contexts) >= limit:
            break
    return contexts


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else \
        "../../../phase1/data/raw/responses.jsonl"
    ctxs = load_search_contexts(path)
    print(f"{len(ctxs)} contextes de recherche distincts extraits")
    for c in ctxs[:5]:
        print("  ", c["start"], "->", c["end"], "@", c["date"])
