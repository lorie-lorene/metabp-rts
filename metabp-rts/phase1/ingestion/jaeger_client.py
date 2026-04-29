"""
Communique avec l'API REST de Jaeger pour récupérer les traces brutes de TOUS les services sur une fenêtre temporelle, afin de construire le graphe global du système.

Stratégie d'ingestion :
    1. get_services()     → liste tous les services connus de Jaeger
    2. get_all_traces()   → pour chaque service, récupère ses traces
    3. merge_traces()     → déduplique par traceID (une trace peut apparaître dans plusieurs services)
    4. save_raw()         → persiste le résultat consolidé

Le graphe G est ensuite construit depuis les relations parentSpanID → spanID inter-services observées dans les traces.

ENTREES   : - URL Jaeger (ex: http://localhost:16686)
SORTIES   : Liste consolidée de traces JSON [{traceID, spans[]}]
"""

import json
import logging
from pathlib import Path
from typing import List, Dict

import requests

logger = logging.getLogger(__name__)

# Services internes Jaeger à exclure
_JAEGER_INTERNAL = {"jaeger-all-in-one", "jaeger-query", "jaeger-collector"}


class JaegerClient:
    def __init__(self, base_url: str, api_version: str = "api"):
        self.base_url    = base_url.rstrip("/")
        self.api_version = api_version
        self._session    = requests.Session()
        self._session.headers.update({"Accept": "application/json"})

    def get_services(self) -> List[str]:
        url      = f"{self.base_url}/{self.api_version}/services"
        response = self._get(url)
        all_svcs = response.get("data", [])
        return [s for s in all_svcs if s not in _JAEGER_INTERNAL]

    def get_traces(
        self,
        service: str,
        lookback: str = "1h",
        limit: int    = 5000,
    ) -> List[dict]:
        url    = f"{self.base_url}/{self.api_version}/traces"
        params = {"service": service, "lookback": lookback, "limit": limit}
        response = self._get(url, params=params)
        traces   = response.get("data", [])
        logger.info(
            "Jaeger → service=%s | lookback=%s | traces récupérées=%d",
            service, lookback, len(traces),
        )
        return traces

    def get_all_traces(
        self,
        lookback: str = "1h",
        limit: int    = 5000,
    ) -> List[dict]:
        services = self.get_services()
        logger.info(
            "Ingestion globale → %d services détectés : %s",
            len(services), services,
        )

        # Index global : traceID → trace consolidée
        trace_index: Dict[str, dict] = {}
        # Index des spans déjà vus : traceID → set(spanID)
        span_index:  Dict[str, set]  = {}

        for svc in services:
            try:
                traces = self.get_traces(svc, lookback=lookback, limit=limit)
            except Exception as e:
                logger.warning("Impossible de récupérer les traces de %s : %s", svc, e)
                continue

            for trace in traces:
                tid = trace.get("traceID")
                if not tid:
                    continue

                if tid not in trace_index:
                    trace_index[tid] = trace
                    span_index[tid]  = {s["spanID"] for s in trace.get("spans", [])}
                else:
                    existing    = trace_index[tid]
                    known_spans = span_index[tid]

                    for span in trace.get("spans", []):
                        if span["spanID"] not in known_spans:
                            existing["spans"].append(span)
                            known_spans.add(span["spanID"])

                    # Fusionner les processus (processes map)
                    existing_procs = existing.get("processes", {})
                    for pid, proc in trace.get("processes", {}).items():
                        if pid not in existing_procs:
                            existing_procs[pid] = proc
                    existing["processes"] = existing_procs

        consolidated = list(trace_index.values())
        total_spans  = sum(len(t.get("spans", [])) for t in consolidated)

        logger.info(
            "Ingestion globale terminée → %d traces consolidées | %d spans totaux",
            len(consolidated), total_spans,
        )
        return consolidated

    def save_raw(self, traces: List[dict], output_path: str) -> None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(traces, f, indent=2, ensure_ascii=False)
        logger.info(
            "Traces brutes sauvegardées → %s (%d traces)", path, len(traces)
        )

    def load_raw(self, input_path: str) -> List[dict]:

        with open(input_path, "r", encoding="utf-8") as f:
            traces = json.load(f)
        logger.info(
            "Traces chargées depuis %s (%d traces)", input_path, len(traces)
        )
        return traces

    def _get(self, url: str, params: dict = None) -> dict:
      
       # Exécute un GET HTTP et lève une exception explicite en cas d'erreur.

        try:
            resp = self._session.get(url, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                f"Impossible de joindre Jaeger à {self.base_url}. "
            )
        except requests.exceptions.Timeout:
            raise TimeoutError(
                f"Jaeger n'a pas répondu dans les 30s : {url}"
            )
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(
                f"Erreur HTTP Jaeger {e.response.status_code} : {url}"
            )