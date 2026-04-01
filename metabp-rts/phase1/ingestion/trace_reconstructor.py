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

import logging
from collections import defaultdict
from typing import List, Dict, Tuple

from models.models import SpanRecord, TestPath

logger = logging.getLogger(__name__)


class TraceReconstructor:
    """
    Reconstruit les deux artefacts clés depuis la liste de SpanRecord :

    1. Suite de tests T (List[TestPath])
       Groupement par trace_id → chaque trace = un cas de test.
       La chaîne d'invocations est ordonnée par start_time_us.

    2. edge_list (List[Tuple[str, str, int, bool]])
       Chaque tuple = (service_source, service_cible, duration_us, error)
       Construit via la relation parent_span_id → span_id.
    """

    def run(
        self,
        spans: List[SpanRecord],
    ) -> Tuple[List[TestPath], List[Tuple[str, str, int, bool]]]:
        """
        Point d'entrée principal.
        Retourne (test_suite_T, edge_list).
        """
        grouped = self._group_by_trace(spans)
        span_map = self._build_span_map(spans)

        test_suite: List[TestPath] = []
        edge_list: List[Tuple[str, str, int, bool]] = []

        for trace_id, trace_spans in grouped.items():
            test_path = self._build_test_path(trace_id, trace_spans)
            if test_path is not None:
                test_suite.append(test_path)

            edges = self._build_edges(trace_spans, span_map)
            edge_list.extend(edges)

        logger.info(
            "TraceReconstructor → T=%d test paths | edge_list=%d arcs bruts",
            len(test_suite), len(edge_list),
        )
        return test_suite, edge_list

    # ── Méthodes privées ──────────────────────────────────

    def _group_by_trace(
        self,
        spans: List[SpanRecord],
    ) -> Dict[str, List[SpanRecord]]:
        """
        Groupe les spans par trace_id.
        Chaque groupe représente une requête utilisateur complète.
        """
        grouped: Dict[str, List[SpanRecord]] = defaultdict(list)
        for span in spans:
            grouped[span.trace_id].append(span)
        return dict(grouped)

    def _build_span_map(
        self,
        spans: List[SpanRecord],
    ) -> Dict[str, SpanRecord]:
        """
        Construit le mapping span_id → SpanRecord.
        Nécessaire pour retrouver le service_name du span parent.
        """
        return {span.span_id: span for span in spans}

    def _build_test_path(
        self,
        trace_id: str,
        trace_spans: List[SpanRecord],
    ) -> TestPath | None:
        """
        Construit un TestPath depuis les spans d'une trace.
        La chaîne d'invocations est dédupliquée et ordonnée
        par start_time_us pour respecter l'ordre chronologique.
        """
        sorted_spans = sorted(trace_spans, key=lambda s: s.start_time_us)
        span_lookup = {s.span_id: s for s in trace_spans}
        seen = set()
        chain: List[Tuple[str, str]] = []

        for span in sorted_spans:
            if span.parent_span_id and span.parent_span_id in span_lookup:
                parent = span_lookup[span.parent_span_id]
                if parent.service_name != span.service_name:
                    arc = (parent.service_name, span.service_name)
                    if arc not in seen:
                        seen.add(arc)
                        chain.append(arc)

        if not chain:
            return None

        return TestPath(trace_id=trace_id, invocation_chain=chain)

    def _build_edges(
        self,
        trace_spans: List[SpanRecord],
        span_map: Dict[str, SpanRecord],
    ) -> List[Tuple[str, str, int, bool]]:
        """
        Construit la liste d'arcs depuis les spans d'une trace.
        Chaque arc = (service_source, service_cible, duration_us, error).
        Les arcs intra-service (si→si) sont ignorés.
        """
        edges = []
        for span in trace_spans:
            if span.parent_span_id and span.parent_span_id in span_map:
                parent = span_map[span.parent_span_id]
                if parent.service_name != span.service_name:
                    edges.append((
                        parent.service_name,
                        span.service_name,
                        span.duration_us,
                        span.error,
                    ))
        return edges