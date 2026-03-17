"""
test_graph_builder.py
=====================
BLOC      : Tests Phase 1
ROLE      : Tests unitaires du graphe G et de ses métriques :
            poids w_ij, centralité C, propagation P, fragilité F.
            Cas testés :
              - Construction G avec edge_list synthétique (5 services)
              - Vérification que w_ij ∈ [0, 1]
              - Vérification que α+β+γ = 1 (conservation des poids)
              - C(si) croissant avec le fan-in
              - P(si) = 0 pour un service sans successeurs
              - F(si) = 0 pour un service sans erreurs sortantes
              - F(si) = 1 pour le service avec le plus d'erreurs
ENTREES   : edge_list synthétique définie dans les fixtures
SORTIES   : Rapport pytest (pass/fail)
LIBRAIRIES: pytest, networkx
"""

# TODO: écrire les fixtures et les fonctions de test
# Structure attendue :
#   - FIXTURE_EDGE_LIST      : List[tuple]  (5 services, 7 arcs)
#   - FIXTURE_EDGE_WITH_ERRORS: List[tuple] (avec erreurs simulées)
#   - test_graph_construction()
#   - test_weight_bounds()
#   - test_centrality_ordering()
#   - test_propagation_leaf_node()
#   - test_fragility_no_errors()
#   - test_fragility_normalization()
