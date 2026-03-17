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
