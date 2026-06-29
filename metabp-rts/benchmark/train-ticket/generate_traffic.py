"""
generate_traffic.py
===================
Génère le trafic sur Train-Ticket ET capture les réponses HTTP.
À lancer depuis le dossier train-ticket-auto-query cloné, avec
response_capture.py accessible dans le PYTHONPATH.

Produit deux artefacts complémentaires :
  - les traces Jaeger (collectées côté Jaeger, comme avant)
  - data/raw/responses.jsonl (les réponses HTTP, pour la Phase 4)
"""

import sys
import logging
import time
from pathlib import Path

# Ajuster ce chemin vers le dossier contenant response_capture.py
sys.path.insert(0, str(Path.home() / "Bureau/MEMOIRE-2026/metabp-rts/metabp-rts/phase4/capture"))

from queries import Query
from scenarios import *
from response_capture import attach_capture

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("generate-traffic")

URL = "http://localhost:8080"
RESPONSES_OUT = str(Path.home() / "Bureau/MEMOIRE-2026/metabp-rts/metabp-rts/phase1/data/raw/responses.jsonl")
N_ITER = 50


def main():
    q = Query(URL)

    # Brancher la capture AVANT le login (capture aussi le login)
    fh = attach_capture(q.session, RESPONSES_OUT)

    if not q.login():
        logger.fatal("Login failed")
        sys.exit(1)

    logger.info("Login OK — génération du trafic + capture des réponses...")

    for i in range(N_ITER):
        try:
            query_and_preserve(q)
            query_and_cancel(q)
            query_order_and_pay(q)
            query_and_rebook(q)
            query_and_collect_ticket(q)
            query_and_enter_station(q)
            query_and_put_consign(q)
            query_food(q)
        except Exception as e:
            logger.warning(f"Itération {i}: {e}")

        if i % 10 == 0:
            logger.info(f"  Itération {i}/{N_ITER}")

    fh.close()
    logger.info(f"Terminé — réponses capturées dans {RESPONSES_OUT}")
    logger.info("Vérifier aussi les traces dans Jaeger")


if __name__ == "__main__":
    main()