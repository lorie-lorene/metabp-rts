"""
mr_inferrer.py
==============
BLOC      : Bloc C — Catalogue MR
ROLE      : Applique les 6 règles d'inférence sur les specs OpenAPI
            pour dériver automatiquement les instances MR par service.
            Règles d'inférence :
              1. Idempotence  : POST + champ id unique dans le body
              2. Permutation  : GET + 2+ query parameters
              3. Monotonie    : endpoint contenant stock/inventory/count
              4. Sous-ensemble: GET + paramètre "filter" ou "query"
              5. Ordonnancement: GET + paramètre "sort" ou "order"
              6. Cardinalité  : GET + paramètre "limit" ou "page" ou "size"
            Chaque règle produit une MRInstance avec phi et rho décrits.
ENTREES   : Dict {service_name: openapi_spec_dict}
SORTIES   : List[MRInstance]  (source = "openapi")
LIBRAIRIES: openapi-spec-validator, pyyaml, re
"""

# TODO: implémenter MRInferrer
# Méthodes attendues :
#   - infer_all(specs) -> List[MRInstance]
#   - infer_service(service_name, spec) -> List[MRInstance]
#   - _apply_rule_idempotence(service, path, method, op) -> Optional[MRInstance]
#   - _apply_rule_permutation(service, path, method, op) -> Optional[MRInstance]
#   - _apply_rule_monotonie(service, path, method, op) -> Optional[MRInstance]
#   - _apply_rule_sous_ensemble(service, path, method, op) -> Optional[MRInstance]
#   - _apply_rule_ordonnancement(service, path, method, op) -> Optional[MRInstance]
#   - _apply_rule_cardinalite(service, path, method, op) -> Optional[MRInstance]
#   - _generate_mr_id(service, rule_type, index) -> str
