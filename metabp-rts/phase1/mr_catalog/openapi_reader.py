import logging
from typing import Dict, Optional

import requests

logger = logging.getLogger(__name__)

# Endpoints OpenAPI à essayer dans l'ordre
_OPENAPI_ENDPOINTS = ["/v2/api-docs", "/v3/api-docs", "/swagger.json"]


class OpenAPIReader:

    def __init__(self, base_host: str, services_map: Dict[str, int], timeout: int = 5):

        self.base_host = base_host.rstrip("/")
        self.services_map = services_map
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"Accept": "application/json"})

    def read_all(self) -> Dict[str, Optional[dict]]:

        results: Dict[str, Optional[dict]] = {}
        for service, port in self.services_map.items():
            results[service] = self.read_service(service, port)

        accessible = sum(1 for v in results.values() if v is not None)
        logger.info(
            "OpenAPIReader → %d/%d services avec spec OpenAPI accessible",
            accessible, len(results),
        )
        return results

    def read_service(self, service_name: str, port: int) -> Optional[dict]:
        spec = self._try_endpoints(port)
        if spec is None:
            logger.warning(
                "OpenAPI non accessible pour %s (port %d) — fallback activé",
                service_name, port,
            )
        return spec

    def _try_endpoints(self, port: int) -> Optional[dict]:

        for endpoint in _OPENAPI_ENDPOINTS:
            url = f"{self.base_host}:{port}{endpoint}"
            try:
                resp = self._session.get(url, timeout=self.timeout)
                if resp.status_code == 200:
                    spec = resp.json()
                    if "paths" in spec:
                        return spec
            except (requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout,
                    ValueError):
                # ValueError couvre le cas où la réponse n'est pas du JSON valide
                continue
        return None