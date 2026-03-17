"""
jaeger_fallback_mr.py
=====================
BLOC      : Bloc C — Catalogue MR
ROLE      : Fallback activé quand les specs OpenAPI ne sont pas
            accessibles (ex: z-Shop / Zheng de Chen et al. 2023).
            Infère des MR partiels depuis les operationName des spans
            Jaeger en appliquant des règles sur la méthode HTTP et
            le pattern d'URL.
            Règles d'inférence depuis operationName :
              "POST /.*/payment.*"  → MR Idempotence (candidat)
              "GET .*\?.*&.*"       → MR Permutation
              "GET .*\?.*filter.*"  → MR Sous-ensemble
              "GET .*\?.*sort.*"    → MR Ordonnancement
              "GET .*\?.*limit.*"   → MR Cardinalité
            Limitation : pas d'info sur les schémas de réponse.
ENTREES   : List[SpanRecord]  (champ operationName utilisé)
SORTIES   : List[MRInstance]  (partiel — source = "jaeger_fallback")
LIBRAIRIES: re, collections
"""

# TODO: implémenter JaegerFallbackMR
# Méthodes attendues :
#   - infer(spans) -> List[MRInstance]
#   - _extract_operations(spans) -> Dict[str, List[str]]
#   - _apply_rules(service, operation) -> Optional[MRInstance]
