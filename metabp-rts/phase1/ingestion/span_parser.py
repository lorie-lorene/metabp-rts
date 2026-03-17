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

import logging
from typing import List, Dict

from models.models import SpanRecord

logger = logging.getLogger(__name__)


class SpanParser:
    """
    Parse les traces Jaeger brutes en objets SpanRecord.

    Structure d'une trace Jaeger brute :
    {
      "traceID": "abc123",
      "spans": [
        {
          "traceID": "abc123",
          "spanID": "def456",
          "references": [{"refType": "CHILD_OF", "spanID": "parent789"}],
          "operationName": "POST /api/v1/executePayment",
          "duration": 4500,
          "startTime": 1700000000000000,
          "tags": [{"key": "error", "value": true}],
          "processID": "p1"
        }
      ],
      "processes": {
        "p1": {"serviceName": "ts-payment-service"}
      }
    }
    """

    def parse_all(self, traces: List[dict]) -> List[SpanRecord]:
        """
        Parse toutes les traces et retourne une liste plate de SpanRecord.
        Les spans non parsables sont ignorés avec un log d'avertissement.
        """
        records: List[SpanRecord] = []
        for trace in traces:
            try:
                records.extend(self.parse_trace(trace))
            except Exception as e:
                logger.warning(
                    "Trace ignorée (traceID=%s) : %s",
                    trace.get("traceID", "?"), e,
                )
        logger.info("SpanParser → %d spans parsés depuis %d traces", len(records), len(traces))
        return records

    def parse_trace(self, trace: dict) -> List[SpanRecord]:
        """
        Parse une trace en liste de SpanRecord.
        """
        processes: Dict[str, str] = self._extract_processes(trace)
        records = []
        for span in trace.get("spans", []):
            record = self._parse_span(span, trace["traceID"], processes)
            if record is not None:
                records.append(record)
        return records

    # ── Méthodes privées ──────────────────────────────────

    def _parse_span(
        self,
        span: dict,
        trace_id: str,
        processes: Dict[str, str],
    ) -> SpanRecord:
        """
        Convertit un span brut en SpanRecord.
        Retourne None si le service_name est introuvable.
        """
        process_id = span.get("processID", "")
        service_name = processes.get(process_id)
        if not service_name:
            logger.warning("processID=%s introuvable dans processes", process_id)
            return None

        return SpanRecord(
            trace_id=trace_id,
            span_id=span["spanID"],
            parent_span_id=self._extract_parent_id(span),
            service_name=service_name,
            operation_name=span.get("operationName", ""),
            duration_us=span.get("duration", 0),
            error=self._extract_error(span),
            start_time_us=span.get("startTime", 0),
        )

    def _extract_processes(self, trace: dict) -> Dict[str, str]:
        """
        Construit le mapping processID → serviceName depuis la section
        "processes" de la trace Jaeger.
        """
        return {
            pid: proc.get("serviceName", "unknown")
            for pid, proc in trace.get("processes", {}).items()
        }

    def _extract_parent_id(self, span: dict) -> str | None:
        """
        Extrait le parentSpanID depuis la liste references.
        Retourne None si le span est racine (pas de CHILD_OF).
        """
        for ref in span.get("references", []):
            if ref.get("refType") == "CHILD_OF":
                return ref.get("spanID")
        return None

    def _extract_error(self, span: dict) -> bool:
        """
        Détecte si le span est en erreur via les tags Jaeger.
        Jaeger stocke l'erreur comme : {"key": "error", "value": true}
        """
        for tag in span.get("tags", []):
            if tag.get("key") == "error" and tag.get("value") is True:
                return True
        return False