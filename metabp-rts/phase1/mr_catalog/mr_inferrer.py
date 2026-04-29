
import logging
from collections import defaultdict
from typing import Dict, List, Optional

from models.models import MRInstance

logger = logging.getLogger(__name__)


class MRInferrer:

    def infer_all(self, specs: Dict[str, Optional[dict]]) -> List[MRInstance]:

        instances: List[MRInstance] = []
        for service_name, spec in specs.items():
            if spec is None:
                continue
            service_instances = self.infer_service(service_name, spec)
            instances.extend(service_instances)

        logger.info(
            "MRInferrer → %d MR inférées depuis OpenAPI (%d services)",
            len(instances), sum(1 for v in specs.values() if v is not None),
        )
        return instances

    def infer_service(
        self,
        service_name: str,
        spec: dict,
    ) -> List[MRInstance]:

        instances: List[MRInstance] = []
        counters: Dict[str, int] = defaultdict(int)
        paths = spec.get("paths", {})

        for path, methods in paths.items():
            for http_method, operation in methods.items():
                http_method_upper = http_method.upper()
                # Ignorer les méthodes non REST (parameters, summary...)
                if http_method_upper not in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                    continue

                candidates = [
                    self._rule_idempotence(service_name, path, http_method_upper, operation, counters),
                    self._rule_permutation(service_name, path, http_method_upper, operation, counters),
                    self._rule_monotonie(service_name, path, http_method_upper, operation, counters),
                    self._rule_sous_ensemble(service_name, path, http_method_upper, operation, counters),
                    self._rule_ordonnancement(service_name, path, http_method_upper, operation, counters),
                    self._rule_cardinalite(service_name, path, http_method_upper, operation, counters),
                ]
                instances.extend(c for c in candidates if c is not None)

        return instances

    def _rule_idempotence(
        self, service, path, method, op, counters
    ) -> Optional[MRInstance]:
        if method != "POST":
            return None
        body = op.get("requestBody", op.get("parameters", []))
        has_id = self._body_has_id_field(body, op)
        if not has_id:
            return None
        return self._make(
            service, path, method, "Idempotence", counters,
            phi=f"Même body avec même id unique envoyé 2 fois à POST {path}",
            rho="La ressource n'est créée qu'une seule fois — pas de doublon",
        )

    def _rule_permutation(
        self, service, path, method, op, counters
    ) -> Optional[MRInstance]:
        if method != "GET":
            return None
        query_params = self._get_query_params(op)
        if len(query_params) < 2:
            return None
        return self._make(
            service, path, method, "Permutation", counters,
            phi=f"Permutation de l'ordre des paramètres {query_params[:2]}",
            rho="Résultat identique quelle que soit l'ordre des paramètres",
        )

    def _rule_monotonie(
        self, service, path, method, op, counters
    ) -> Optional[MRInstance]:
        keywords = ("stock", "inventory", "count", "quantity", "available")
        if not any(kw in path.lower() for kw in keywords):
            return None
        return self._make(
            service, path, method, "Monotonie", counters,
            phi=f"Requête {method} {path} avant et après une opération de réduction",
            rho="valeur_après <= valeur_avant",
        )

    def _rule_sous_ensemble(
        self, service, path, method, op, counters
    ) -> Optional[MRInstance]:
        if method != "GET":
            return None
        filter_params = ("filter", "query", "search", "q", "keyword")
        query_params = self._get_query_params(op)
        if not any(p.lower() in filter_params for p in query_params):
            return None
        return self._make(
            service, path, method, "Sous-ensemble", counters,
            phi=f"Ajout d'un filtre supplémentaire au GET {path}",
            rho="résultats_filtrés ⊆ résultats_sans_filtre",
        )

    def _rule_ordonnancement(
        self, service, path, method, op, counters
    ) -> Optional[MRInstance]:
        if method != "GET":
            return None
        sort_params = ("sort", "order", "orderby", "order_by", "sortby")
        query_params = self._get_query_params(op)
        if not any(p.lower() in sort_params for p in query_params):
            return None
        return self._make(
            service, path, method, "Ordonnancement", counters,
            phi=f"GET {path} avec sort=asc puis sort=desc",
            rho="Les deux listes sont inverses l'une de l'autre",
        )

    def _rule_cardinalite(
        self, service, path, method, op, counters
    ) -> Optional[MRInstance]:
        if method != "GET":
            return None
        page_params = ("limit", "page", "size", "per_page", "pagesize", "count")
        query_params = self._get_query_params(op)
        if not any(p.lower() in page_params for p in query_params):
            return None
        return self._make(
            service, path, method, "Cardinalité", counters,
            phi=f"GET {path} avec limit=N",
            rho="len(résultats) <= N",
        )


    def _make(
        self,
        service: str,
        path: str,
        method: str,
        mr_type: str,
        counters: Dict[str, int],
        phi: str,
        rho: str,
    ) -> MRInstance:
        counters[mr_type] += 1
        # Dériver un prefixe court depuis le service name
        prefix = "".join(w[0].upper() for w in service.replace("ts-", "").replace("-service", "").split("-"))
        mr_id = f"MR-{prefix}-{mr_type[:3].upper()}-{counters[mr_type]:02d}"
        return MRInstance(
            mr_id=mr_id,
            mr_type=mr_type,
            service=service,
            endpoint=path,
            http_method=method,
            phi=phi,
            rho=rho,
            source="openapi",
        )

    def _get_query_params(self, operation: dict) -> List[str]:
        #Extrait les noms des query parameters d'une opération OpenAPI
        params = operation.get("parameters", [])
        return [
            p.get("name", "")
            for p in params
            if p.get("in") == "query"
        ]

    def _body_has_id_field(self, body, operation: dict) -> bool:

        # OpenAPI v2 : requestBody → content → schema → properties
        if "requestBody" in operation:
            try:
                content = operation["requestBody"].get("content", {})
                for media in content.values():
                    props = media.get("schema", {}).get("properties", {})
                    if any("id" in k.lower() for k in props):
                        return True
            except (AttributeError, KeyError):
                pass

        for param in operation.get("parameters", []):
            if param.get("in") == "body":
                props = param.get("schema", {}).get("properties", {})
                if any("id" in k.lower() for k in props):
                    return True

        return False