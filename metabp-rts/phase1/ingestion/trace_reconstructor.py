"""
Groupe les spans par traceID pour reconstruire :
            * La suite de tests T : chaque traceID → un TestPath (chaîne d'invocations représentant un cas de test)
            * L'edge_list : liste de (si, sj, duration, error)pour la construction du graphe G
ENTREES   : Liste de SpanRecord (sortie de span_parser.py)
SORTIES   : (test_suite T, edge_list)
"""

import logging
from collections import defaultdict
from typing import List, Dict, Tuple
from models.models import SpanRecord, TestPath

logger = logging.getLogger(__name__)


class TraceReconstructor:

    def run(
        self,
        spans: List[SpanRecord],
    ) -> Tuple[List[TestPath], List[Tuple[str, str, int, bool]]]:
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

    def _group_by_trace(
        self,
        spans: List[SpanRecord],
    ) -> Dict[str, List[SpanRecord]]:

        #Groupe les spans par trace_id rt chaque groupe représente une requête utilisateur complète
        grouped: Dict[str, List[SpanRecord]] = defaultdict(list)
        for span in spans:
            grouped[span.trace_id].append(span)
        return dict(grouped)

    def _build_span_map(
        self,
        spans: List[SpanRecord],
    ) -> Dict[str, SpanRecord]:

        return {span.span_id: span for span in spans}

    def _compute_trace_duration(
        self,
        trace_spans: List[SpanRecord],
    ) -> int:
        """
        Durée totale d'exécution de la trace = durée du span racine.
        Le span racine (sans parent dans la trace) englobe toute la requête.
        """
        span_ids = {s.span_id for s in trace_spans}
        roots = [
            s for s in trace_spans
            if not s.parent_span_id or s.parent_span_id not in span_ids
        ]
        if roots:
            return max(s.duration_us for s in roots)
        return max((s.duration_us for s in trace_spans), default=0)
    
    def _build_test_path(
        self,
        trace_id: str,
        trace_spans: List[SpanRecord],
    ) -> TestPath | None:
        #Construit un TestPath depuis les spans d'une trace.
        #La chaîne d'invocations est dédupliquée et ordonnée par start_time_us pour respecter l'ordre chronologique
      
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
        duration_us = self._compute_trace_duration(trace_spans)
        
        return TestPath(trace_id=trace_id,
            invocation_chain=chain,
            duration_us=duration_us,)

    def _build_edges(
        self,
        trace_spans: List[SpanRecord],
        span_map: Dict[str, SpanRecord],
    ) -> List[Tuple[str, str, int, bool]]:
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