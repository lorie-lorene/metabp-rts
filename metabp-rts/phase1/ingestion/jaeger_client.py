"""
jaeger_client.py
================
BLOC      : Bloc A — Ingestion
ROLE      : Communique avec l'API REST de Jaeger pour récupérer
            les traces brutes d'un service sur une fenêtre temporelle.
ENTREES   : - URL Jaeger (ex: http://localhost:16686)
            - Nom du service cible (ex: ts-gateway-service)
            - Fenêtre temporelle (lookback) et limite de traces
SORTIES   : Liste brute de traces JSON [{traceID, spans[]}]
            Persistée dans data/raw/traces_raw.json
LIBRAIRIES: requests, json
"""

# TODO: implémenter JaegerClient
# Méthodes attendues :
#   - __init__(base_url, config)
#   - get_services() -> List[str]
#   - get_traces(service, lookback, limit) -> List[dict]
#   - save_raw(traces, output_path) -> None
"""
jaeger_client.py
================
BLOC      : Bloc A — Ingestion
ROLE      : Communique avec l'API REST de Jaeger pour récupérer
            les traces brutes d'un service sur une fenêtre temporelle.
ENTREES   : - URL Jaeger (ex: http://localhost:16686)
            - Nom du service cible (ex: ts-gateway-service)
            - Fenêtre temporelle (lookback) et limite de traces
SORTIES   : Liste brute de traces JSON [{traceID, spans[]}]
            Persistée dans data/raw/traces_raw.json
LIBRAIRIES: requests, json
"""

import json
import logging
from pathlib import Path
from typing import List

import requests

logger = logging.getLogger(__name__)


class JaegerClient:
    """
    Communique avec l'API REST Jaeger.
    URL pattern : {base_url}/api/traces?service=X&lookback=Y&limit=Z
    """

    def __init__(self, base_url: str, api_version: str = "api"):
        # Supprime le slash final pour éviter les doubles slashes
        self.base_url = base_url.rstrip("/")
        self.api_version = api_version
        self._session = requests.Session()
        self._session.headers.update({"Accept": "application/json"})

    # ── Méthodes publiques ────────────────────────────────

    def get_services(self) -> List[str]:
        """
        Retourne la liste des services connus de Jaeger.
        Utile pour vérifier que Train-Ticket est bien tracé.
        """
        url = f"{self.base_url}/{self.api_version}/services"
        response = self._get(url)
        return response.get("data", [])

    def get_traces(
        self,
        service: str,
        lookback: str = "1h",
        limit: int = 5000,
    ) -> List[dict]:
        """
        Récupère les traces brutes d'un service.

        Paramètres
        ----------
        service  : nom du service Jaeger (ex: ts-gateway-service)
        lookback : fenêtre temporelle  (ex: "1h", "6h", "24h")
        limit    : nombre maximum de traces à récupérer

        Retourne
        --------
        Liste de traces brutes JSON. Chaque trace a la structure :
          {
            "traceID": "abc123",
            "spans": [...],
            "processes": {...}
          }
        """
        url = f"{self.base_url}/{self.api_version}/traces"
        params = {
            "service": service,
            "lookback": lookback,
            "limit": limit,
        }
        response = self._get(url, params=params)
        traces = response.get("data", [])
        logger.info(
            "Jaeger → service=%s | lookback=%s | traces récupérées=%d",
            service, lookback, len(traces),
        )
        return traces

    def save_raw(self, traces: List[dict], output_path: str) -> None:
        """
        Persiste les traces brutes en JSON.
        Crée les répertoires parents si nécessaire.
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(traces, f, indent=2, ensure_ascii=False)
        logger.info("Traces brutes sauvegardées → %s (%d traces)", path, len(traces))

    def load_raw(self, input_path: str) -> List[dict]:
        """
        Charge des traces brutes depuis un fichier JSON persisté.
        Utile pour éviter de ré-interroger Jaeger à chaque run.
        """
        with open(input_path, "r", encoding="utf-8") as f:
            traces = json.load(f)
        logger.info("Traces chargées depuis %s (%d traces)", input_path, len(traces))
        return traces

    # ── Méthode privée ────────────────────────────────────

    def _get(self, url: str, params: dict = None) -> dict:
        """
        Exécute un GET HTTP et lève une exception explicite en cas d'erreur.
        """
        try:
            resp = self._session.get(url, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                f"Impossible de joindre Jaeger à {self.base_url}. "
                "Vérifiez que Jaeger est démarré (docker-compose up)."
            )
        except requests.exceptions.Timeout:
            raise TimeoutError(f"Jaeger n'a pas répondu dans les 30s : {url}")
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"Erreur HTTP Jaeger {e.response.status_code} : {url}")