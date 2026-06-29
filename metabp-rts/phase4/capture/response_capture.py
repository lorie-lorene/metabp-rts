"""
response_capture.py
===================
Capture automatiquement chaque réponse HTTP émise par la session
requests du client train-ticket-auto-query, sans modifier ce dernier.

PRINCIPE :
    La classe Query de train-ticket-auto-query utilise UNE seule
    requests.Session() pour tous ses appels. On greffe un hook de
    réponse sur cette session : chaque réponse (status + corps JSON)
    est enregistrée dans un fichier JSONL.

USAGE :
    from response_capture import attach_capture
    q = Query(url)
    attach_capture(q.session, "data/raw/responses.jsonl")
    q.login()
    # ... scénarios : toutes les réponses sont capturées automatiquement
"""

import json
import time
import logging
from pathlib import Path
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger("response-capture")


def attach_capture(session, output_path: str):
    """
    Greffe un hook de capture sur une requests.Session existante.

    Chaque réponse HTTP traversant cette session est enregistrée :
    method, endpoint (path normalisé), query params, body de la requête,
    status, corps JSON de la réponse, durée.
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    # On ouvre en append : un run = un ensemble de lignes JSONL
    fh = out.open("a", encoding="utf-8")

    def _hook(response, *args, **kwargs):
        try:
            req = response.request
            parsed = urlparse(req.url)

            # Corps de la requête (si JSON)
            req_body = None
            if req.body:
                try:
                    req_body = json.loads(req.body)
                except (json.JSONDecodeError, TypeError):
                    req_body = str(req.body)[:500]

            # Corps de la réponse (si JSON)
            try:
                resp_body = response.json()
            except (json.JSONDecodeError, ValueError):
                resp_body = None  # réponse non-JSON (HTML, vide...)

            record = {
                "timestamp_us": int(time.time() * 1_000_000),
                "method":       req.method,
                "endpoint":     parsed.path,            # /api/v1/travelservice/trips/left
                "query":        parse_qs(parsed.query), # {param: [val]}
                "request_body": req_body,
                "status":       response.status_code,
                "elapsed_us":   int(response.elapsed.total_seconds() * 1_000_000),
                "response_body": resp_body,
            }
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            fh.flush()
        except Exception as e:
            logger.warning("capture échouée pour une réponse : %s", e)

    session.hooks.setdefault("response", [])
    session.hooks["response"].append(_hook)
    logger.info("Capture des réponses HTTP active → %s", output_path)
    return fh  # pour fermeture éventuelle en fin de run