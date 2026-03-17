"""
span_parser.py
==============
BLOC      : Bloc A — Ingestion
ROLE      : Parse chaque span Jaeger brut et extrait les champs
            utiles pour la construction de G et de T.
ENTREES   : Liste brute de traces JSON (sortie de jaeger_client.py)
SORTIES   : Liste de SpanRecord :
            {traceID, spanID, parentSpanID, serviceName,
             operationName, duration_us, error, startTime_us}
LIBRAIRIES: dataclasses, typing
"""

# TODO: implémenter SpanParser
# Méthodes attendues :
#   - parse_trace(trace_dict) -> List[SpanRecord]
#   - parse_all(traces) -> List[SpanRecord]
#   - extract_service_name(process) -> str
#   - extract_error(tags) -> bool
