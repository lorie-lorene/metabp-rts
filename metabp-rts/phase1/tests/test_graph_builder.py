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

"""
Tests unitaires : weight_calculator, graph_builder, centrality,
                  propagation_coeff, fragility
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from graph.weight_calculator import WeightCalculator
from graph.graph_builder import GraphBuilder
from graph.centrality import CentralityCalculator
from graph.propagation_coeff import PropagationCalculator
from graph.fragility import FragilityCalculator

# ── Fixtures ──────────────────────────────────────────────
# (source, target, duration_us, error)

FIXTURE_EDGE_LIST = [
    ("gateway", "order",   1200, False),
    ("gateway", "order",   1300, False),
    ("gateway", "auth",    800,  False),
    ("order",   "payment", 4500, False),
    ("order",   "payment", 5000, True),   # 1 erreur sur payment
    ("order",   "seat",    600,  False),
    ("payment", "notify",  300,  False),
]

FIXTURE_ALL_ERRORS = [
    ("svcA", "svcB", 1000, True),
    ("svcA", "svcB", 1000, True),
    ("svcC", "svcD", 500,  False),
]

FIXTURE_NO_ERRORS = [
    ("svcX", "svcY", 1000, False),
    ("svcX", "svcZ", 2000, False),
]

# ── Tests WeightCalculator ────────────────────────────────

def test_weight_bounds():
    """Tous les w_ij doivent être dans [0, 1]."""
    wc = WeightCalculator()
    weights = wc.compute(FIXTURE_EDGE_LIST)
    for edge, ew in weights.items():
        assert 0.0 <= ew.w_ij <= 1.0, f"w_ij hors bornes pour {edge} : {ew.w_ij}"

def test_weight_alpha_beta_gamma_sum():
    """Vérification que l'invariant α+β+γ=1 est respecté."""
    wc = WeightCalculator(alpha=0.5, beta=0.3, gamma=0.2)
    assert abs(wc.alpha + wc.beta + wc.gamma - 1.0) < 1e-9

def test_weight_invalid_sum_raises():
    """Un WeightCalculator avec α+β+γ ≠ 1 doit lever une AssertionError."""
    try:
        WeightCalculator(alpha=0.5, beta=0.5, gamma=0.5)
        assert False, "Aurait dû lever AssertionError"
    except AssertionError:
        pass

def test_weight_err_ij_correct():
    """err_ij de l'arc order→payment doit refléter 1 erreur sur 2 appels."""
    wc = WeightCalculator()
    weights = wc.compute(FIXTURE_EDGE_LIST)
    ew = weights[("order", "payment")]
    assert abs(ew.err_ij - 0.5) < 1e-6, f"err_ij attendu 0.5, obtenu {ew.err_ij}"

def test_weight_empty_edge_list():
    """Un edge_list vide doit retourner un dict vide sans exception."""
    wc = WeightCalculator()
    assert wc.compute([]) == {}

# ── Tests GraphBuilder ────────────────────────────────────

def test_graph_construction():
    """Le graphe doit avoir les bons noeuds et arcs."""
    wc = WeightCalculator()
    weights = wc.compute(FIXTURE_EDGE_LIST)
    gb = GraphBuilder()
    G = gb.build(weights)
    assert "gateway" in G.nodes()
    assert "payment" in G.nodes()
    assert G.has_edge("order", "payment")

def test_graph_arc_has_w_ij():
    """Chaque arc du graphe doit avoir l'attribut w_ij."""
    wc = WeightCalculator()
    weights = wc.compute(FIXTURE_EDGE_LIST)
    gb = GraphBuilder()
    G = gb.build(weights)
    for u, v, data in G.edges(data=True):
        assert "w_ij" in data, f"Arc {u}→{v} sans w_ij"

# ── Tests CentralityCalculator ────────────────────────────

def test_centrality_scores_in_bounds():
    """Tous les scores C doivent être dans [0, 1]."""
    wc = WeightCalculator()
    G = GraphBuilder().build(wc.compute(FIXTURE_EDGE_LIST))
    scores = CentralityCalculator().compute(G)
    for svc, c in scores.items():
        assert 0.0 <= c <= 1.0, f"C hors bornes pour {svc} : {c}"

def test_centrality_most_connected_node():
    """Le noeud 'order' a le plus de connexions → C élevé."""
    wc = WeightCalculator()
    G = GraphBuilder().build(wc.compute(FIXTURE_EDGE_LIST))
    scores = CentralityCalculator().compute(G)
    # order a fan-in=1, fan-out=3 → parmi les plus hauts
    assert scores.get("order", 0) > scores.get("notify", 0)

# ── Tests PropagationCalculator ───────────────────────────

def test_propagation_leaf_is_zero():
    """Un service sans successeurs (feuille) doit avoir P=0."""
    wc = WeightCalculator()
    G = GraphBuilder().build(wc.compute(FIXTURE_EDGE_LIST))
    scores = PropagationCalculator().compute(G)
    # "notify" est une feuille dans FIXTURE_EDGE_LIST
    assert scores.get("notify", 0.0) == 0.0

def test_propagation_scores_in_bounds():
    """Tous les scores P doivent être dans [0, 1]."""
    wc = WeightCalculator()
    G = GraphBuilder().build(wc.compute(FIXTURE_EDGE_LIST))
    scores = PropagationCalculator().compute(G)
    for svc, p in scores.items():
        assert 0.0 <= p <= 1.0, f"P hors bornes pour {svc} : {p}"

# ── Tests FragilityCalculator ─────────────────────────────

def test_fragility_no_errors():
    """Sans aucune erreur, tous les scores F doivent être 0."""
    scores = FragilityCalculator().compute(FIXTURE_NO_ERRORS)
    for svc, f in scores.items():
        assert f == 0.0, f"F attendu 0.0 pour {svc}, obtenu {f}"

def test_fragility_normalization():
    """Le service avec le plus d'erreurs doit avoir F=1.0."""
    scores = FragilityCalculator().compute(FIXTURE_ALL_ERRORS)
    # svcA a 2/2 = 100% d'erreurs → F=1.0
    # svcC a 0/1 = 0% d'erreurs  → F=0.0
    assert scores.get("svcA", -1) == 1.0
    assert scores.get("svcC", -1) == 0.0

def test_fragility_partial_errors():
    """order→payment a 50% d'erreurs — doit être le max dans FIXTURE_EDGE_LIST."""
    scores = FragilityCalculator().compute(FIXTURE_EDGE_LIST)
    # "order" a 1 erreur sur 2 appels vers payment → err_out = 0.5
    # Les autres services ont 0 erreur → order est le service le plus fragile
    max_service = max(scores, key=scores.get)
    assert max_service == "order"
    assert scores["order"] == 1.0  # normalisé

def test_fragility_empty():
    """Un edge_list vide retourne un dict vide."""
    assert FragilityCalculator().compute([]) == {}