
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.span_parser import SpanParser
from ingestion.trace_reconstructor import TraceReconstructor
from models.models import SpanRecord, TestPath

FIXTURE_SIMPLE_TRACE = {
    "traceID": "trace001",
    "spans": [
        {
            "traceID": "trace001",
            "spanID": "span001",
            "references": [],
            "operationName": "GET /api/v1/users/login",
            "duration": 1200,
            "startTime": 1000000,
            "tags": [],
            "processID": "p1",
        },
        {
            "traceID": "trace001",
            "spanID": "span002",
            "references": [{"refType": "CHILD_OF", "spanID": "span001"}],
            "operationName": "POST /api/v1/executePayment",
            "duration": 4500,
            "startTime": 1001000,
            "tags": [],
            "processID": "p2",
        },
        {
            "traceID": "trace001",
            "spanID": "span003",
            "references": [{"refType": "CHILD_OF", "spanID": "span002"}],
            "operationName": "GET /api/v1/order",
            "duration": 800,
            "startTime": 1002000,
            "tags": [{"key": "error", "value": True}],
            "processID": "p3",
        },
    ],
    "processes": {
        "p1": {"serviceName": "ts-gateway-service"},
        "p2": {"serviceName": "ts-payment-service"},
        "p3": {"serviceName": "ts-order-service"},
    },
}

FIXTURE_SINGLE_SPAN = {
    "traceID": "trace002",
    "spans": [
        {
            "traceID": "trace002",
            "spanID": "span010",
            "references": [],
            "operationName": "GET /health",
            "duration": 50,
            "startTime": 2000000,
            "tags": [],
            "processID": "p1",
        }
    ],
    "processes": {"p1": {"serviceName": "ts-auth-service"}},
}


def test_parse_span_count():
    """Vérifie que les 3 spans de la trace simple sont parsés."""
    parser = SpanParser()
    records = parser.parse_trace(FIXTURE_SIMPLE_TRACE)
    assert len(records) == 3

def test_parse_span_fields():
    """Vérifie les champs du premier span."""
    parser = SpanParser()
    records = parser.parse_trace(FIXTURE_SIMPLE_TRACE)
    root = next(r for r in records if r.span_id == "span001")
    assert root.trace_id == "trace001"
    assert root.service_name == "ts-gateway-service"
    assert root.parent_span_id is None
    assert root.duration_us == 1200
    assert root.error is False

def test_parent_child_relationship():
    """Vérifie que le parent_span_id est correctement extrait."""
    parser = SpanParser()
    records = parser.parse_trace(FIXTURE_SIMPLE_TRACE)
    child = next(r for r in records if r.span_id == "span002")
    assert child.parent_span_id == "span001"

def test_error_detection():
    """Vérifie que le tag error=True est correctement détecté."""
    parser = SpanParser()
    records = parser.parse_trace(FIXTURE_SIMPLE_TRACE)
    error_span = next(r for r in records if r.span_id == "span003")
    no_error_span = next(r for r in records if r.span_id == "span001")
    assert error_span.error is True
    assert no_error_span.error is False

def test_parse_all_multiple_traces():
    """Vérifie que parse_all agrège correctement plusieurs traces."""
    parser = SpanParser()
    records = parser.parse_all([FIXTURE_SIMPLE_TRACE, FIXTURE_SINGLE_SPAN])
    assert len(records) == 4  # 3 + 1

# ── Tests TraceReconstructor ──────────────────────────────

def test_reconstruct_test_path():
    """Vérifie qu'un TestPath est créé depuis la trace simple."""
    parser = SpanParser()
    spans = parser.parse_trace(FIXTURE_SIMPLE_TRACE)
    reconstructor = TraceReconstructor()
    test_suite, _ = reconstructor.run(spans)
    assert len(test_suite) == 1
    tp = test_suite[0]
    assert tp.trace_id == "trace001"
    assert len(tp.invocation_chain) >= 1

def test_invocation_chain_no_self_loop():
    """Vérifie qu'aucun arc intra-service n'apparaît dans la chaîne."""
    parser = SpanParser()
    spans = parser.parse_trace(FIXTURE_SIMPLE_TRACE)
    reconstructor = TraceReconstructor()
    test_suite, _ = reconstructor.run(spans)
    for tp in test_suite:
        for src, tgt in tp.invocation_chain:
            assert src != tgt, f"Arc intra-service détecté : {src} → {src}"

def test_single_span_no_test_path():
    """Une trace avec un seul span (pas de relation parent) ne produit pas de TestPath."""
    parser = SpanParser()
    spans = parser.parse_trace(FIXTURE_SINGLE_SPAN)
    reconstructor = TraceReconstructor()
    test_suite, _ = reconstructor.run(spans)
    assert len(test_suite) == 0

def test_edge_list_contains_error_info():
    """Vérifie que l'edge_list contient bien le flag error."""
    parser = SpanParser()
    spans = parser.parse_trace(FIXTURE_SIMPLE_TRACE)
    reconstructor = TraceReconstructor()
    _, edge_list = reconstructor.run(spans)
    # L'arc vers ts-order-service doit avoir error=True
    order_edges = [(s, t, d, e) for s, t, d, e in edge_list if t == "ts-order-service"]
    assert len(order_edges) > 0
    assert any(e for _, _, _, e in order_edges)