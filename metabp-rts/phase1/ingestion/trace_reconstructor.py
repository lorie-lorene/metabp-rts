"""
trace_reconstructor.py
======================
BLOC      : Bloc A — Ingestion
ROLE      : Groupe les spans par traceID pour reconstruire :
            (1) La suite de tests T : chaque traceID → un TestPath
                (chaîne d'invocations représentant un cas de test)
            (2) L'edge_list : liste de (si, sj, duration, error)
                pour la construction du graphe G
ATTENTION : Deux usages distincts des spans :
            - parentSpanID → arcs du graphe G
            - traceID      → cas de test de T
ENTREES   : Liste de SpanRecord (sortie de span_parser.py)
SORTIES   : (test_suite T, edge_list)
            - T        : List[TestPath]
            - edge_list: List[Tuple[str, str, int, bool]]
LIBRAIRIES: collections.defaultdict, typing
"""

# TODO: implémenter TraceReconstructor
# Méthodes attendues :
#   - group_by_trace(spans) -> Dict[str, List[SpanRecord]]
#   - build_test_path(trace_id, spans) -> TestPath
#   - build_edge_list(spans) -> List[tuple]
#   - run(spans) -> Tuple[List[TestPath], List[tuple]]
