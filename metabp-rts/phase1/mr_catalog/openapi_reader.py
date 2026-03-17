"""
openapi_reader.py
=================
BLOC      : Bloc C — Catalogue MR
ROLE      : Interroge l'endpoint /v2/api-docs ou /v3/api-docs de chaque
            service Train-Ticket déployé pour récupérer les specs OpenAPI.
            Disponibilité confirmée pour :
              - Train-Ticket  (springfox-swagger2 v2.4.0) → /v2/api-docs
              - SpringBlade   (m-Ticket, Chen et al. 2023) → /v2 ou /v3
            Fallback automatique vers jaeger_fallback_mr.py si
            l'endpoint n'est pas accessible.
ENTREES   : - Dict {service_name: port}  (depuis services_map.yaml)
            - URL de base du déploiement (depuis system_config.yaml)
SORTIES   : Dict {service_name: openapi_spec_dict}
            Les services sans spec retournent None (déclenche le fallback)
LIBRAIRIES: requests, json
"""

# TODO: implémenter OpenAPIReader
# Méthodes attendues :
#   - __init__(base_url, services_map)
#   - read_all() -> Dict[str, Optional[dict]]
#   - read_service(service_name, port) -> Optional[dict]
#   - _try_endpoints(port) -> Optional[dict]
#     (essaie /v2/api-docs puis /v3/api-docs)
"""
openapi_reader.py
=================
BLOC      : Bloc C — Catalogue MR
ROLE      : Interroge l'endpoint /v2/api-docs ou /v3/api-docs de chaque
            service Train-Ticket déployé pour récupérer les specs OpenAPI.
            Disponibilité confirmée pour :
              - Train-Ticket  (springfox-swagger2 v2.4.0) → /v2/api-docs
              - SpringBlade   (m-Ticket, Chen et al. 2023) → /v2 ou /v3
            Fallback automatique vers jaeger_fallback_mr.py si
            l'endpoint n'est pas accessible.
ENTREES   : - Dict {service_name: port}  (depuis services_map.yaml)
            - URL de base du déploiement (depuis system_config.yaml)
SORTIES   : Dict {service_name: openapi_spec_dict}
            Les services sans spec retournent None (déclenche le fallback)
LIBRAIRIES: requests, json
"""

import logging
from typing import Dict, Optional

import requests

logger = logging.getLogger(__name__)

# Endpoints OpenAPI à essayer dans l'ordre
_OPENAPI_ENDPOINTS = ["/v2/api-docs", "/v3/api-docs", "/swagger.json"]


class OpenAPIReader:
    """
    Récupère les specs OpenAPI de chaque service Train-Ticket déployé.

    Disponibilité confirmée :
        - Train-Ticket  (springfox-swagger2 v2.4.0)  → /v2/api-docs
        - SpringBlade   (m-Ticket, Chen et al. 2023)  → /v2 ou /v3/api-docs

    Si aucun endpoint n'est accessible, retourne None pour ce service.
    Le fallback vers jaeger_fallback_mr.py est déclenché en amont
    par mr_inferrer.py lorsqu'une spec est None.
    """

    def __init__(self, base_host: str, services_map: Dict[str, int], timeout: int = 5):
        """
        Paramètres
        ----------
        base_host    : hôte de déploiement (ex: "http://localhost")
        services_map : {service_name: port}
        timeout      : timeout HTTP en secondes (court car local)
        """
        self.base_host = base_host.rstrip("/")
        self.services_map = services_map
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"Accept": "application/json"})

    def read_all(self) -> Dict[str, Optional[dict]]:
        """
        Récupère les specs OpenAPI pour tous les services.
        Les services inaccessibles ont la valeur None.

        Retourne
        --------
        Dict {service_name: spec_dict | None}
        """
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
        """
        Essaie les endpoints OpenAPI connus pour un service donné.
        Retourne la spec JSON du premier endpoint qui répond, ou None.
        """
        spec = self._try_endpoints(port)
        if spec is None:
            logger.warning(
                "OpenAPI non accessible pour %s (port %d) — fallback activé",
                service_name, port,
            )
        return spec

    # ── Méthode privée ────────────────────────────────────

    def _try_endpoints(self, port: int) -> Optional[dict]:
        """
        Essaie chaque endpoint OpenAPI connu jusqu'à en trouver un accessible.
        """
        for endpoint in _OPENAPI_ENDPOINTS:
            url = f"{self.base_host}:{port}{endpoint}"
            try:
                resp = self._session.get(url, timeout=self.timeout)
                if resp.status_code == 200:
                    spec = resp.json()
                    # Vérification minimale : une spec OpenAPI a toujours "paths"
                    if "paths" in spec:
                        return spec
            except (requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout,
                    ValueError):
                # ValueError couvre le cas où la réponse n'est pas du JSON valide
                continue
        return None