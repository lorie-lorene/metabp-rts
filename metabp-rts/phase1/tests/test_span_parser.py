"""
test_span_parser.py
===================
BLOC      : Tests Phase 1
ROLE      : Tests unitaires du span_parser et trace_reconstructor
            avec des traces Jaeger synthétiques (fixtures JSON).
            Cas testés :
              - Parse d'un span simple (sans parent)
              - Parse d'un span enfant (avec parentSpanID)
              - Détection correcte du flag error
              - Reconstruction d'un test path depuis 3 spans
              - Gestion d'une trace avec un seul span (chemin trivial)
              - Déduplication des arcs dans edge_list
ENTREES   : Fixtures JSON de traces synthétiques (définies inline)
SORTIES   : Rapport pytest (pass/fail)
LIBRAIRIES: pytest, json
"""

# TODO: écrire les fixtures et les fonctions de test
# Structure attendue :
#   - FIXTURE_SIMPLE_TRACE  : dict  (trace avec 3 spans)
#   - FIXTURE_ERROR_TRACE   : dict  (trace avec un span en erreur)
#   - test_parse_span_fields()
#   - test_parent_child_relationship()
#   - test_error_detection()
#   - test_reconstruct_test_path()
#   - test_edge_list_deduplication()
