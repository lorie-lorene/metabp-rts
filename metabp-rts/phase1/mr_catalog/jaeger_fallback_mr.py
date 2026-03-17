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

import logging
import re
from collections import defaultdict
from typing import Dict, List, Optional

from models.models import MRInstance, SpanRecord

logger = logging.getLogger(__name__)

# Règles d'inférence : (pattern_regex, mr_type, phi_template, rho_template)
_RULES = [
    (
        r"^POST\s+.*payment.*",
        "Idempotence",
        "Même body avec même paymentId envoyé 2 fois",
        "total_charged == montant_unique (pas de double débit)",
    ),
    (
        r"^POST\s+.*",
        "Idempotence",
        "Même body avec même id unique envoyé 2 fois",
        "Résultat identique à la première invocation",
    ),
    (
        r"^GET\s+.*\?.*&.*",
        "Permutation",
        "Permutation de l'ordre des query parameters",
        "Résultat identique quelle que soit l'ordre des paramètres",
    ),
    (
        r"^GET\s+.*[?&]filter",
        "Sous-ensemble",
        "Ajout d'un filtre supplémentaire",
        "résultats_filtrés ⊆ résultats_sans_filtre",
    ),
    (
        r"^GET\s+.*[?&](sort|order)",
        "Ordonnancement",
        "Requête avec sort=asc puis sort=desc",
        "Listes retournées sont inverses l'une de l'autre",
    ),
    (
        r"^GET\s+.*[?&](limit|page|size)",
        "Cardinalité",
        "Requête avec limit=N",
        "len(résultats) <= N",
    ),
    (
        r"^GET\s+.*(stock|inventory|count)",
        "Monotonie",
        "Achat d'une unité puis requête du stock",
        "stock_après <= stock_avant",
    ),
]


class JaegerFallbackMR:
    """
    Infère des MR partielles depuis les operationName des spans Jaeger.
    Activé quand les specs OpenAPI ne sont pas accessibles.

    Limitation connue : pas d'information sur les schémas de réponse.
    Les MR produites sont de type "jaeger_fallback" dans le catalogue.
    """

    def infer(self, spans: List[SpanRecord]) -> List[MRInstance]:
        """
        Parcourt les operationName uniques de chaque service et
        applique les règles d'inférence.

        Retourne
        --------
        List[MRInstance] — source = "jaeger_fallback"
        """
        operations = self._extract_operations(spans)
        instances: List[MRInstance] = []
        counters: Dict[str, int] = defaultdict(int)

        for service, ops in operations.items():
            for op in ops:
                instance = self._apply_rules(service, op, counters)
                if instance is not None:
                    instances.append(instance)

        logger.info(
            "JaegerFallbackMR → %d MR inférées depuis operationName (%d services)",
            len(instances), len(operations),
        )
        return instances

    # ── Méthodes privées ──────────────────────────────────

    def _extract_operations(
        self,
        spans: List[SpanRecord],
    ) -> Dict[str, List[str]]:
        """
        Extrait les operationName uniques par service.
        """
        ops: Dict[str, set] = defaultdict(set)
        for span in spans:
            if span.operation_name:
                ops[span.service_name].add(span.operation_name)
        return {svc: list(op_set) for svc, op_set in ops.items()}

    def _apply_rules(
        self,
        service: str,
        operation: str,
        counters: Dict[str, int],
    ) -> Optional[MRInstance]:
        """
        Applique la première règle qui correspond à l'operation.
        Retourne None si aucune règle ne correspond.
        """
        for pattern, mr_type, phi, rho in _RULES:
            if re.search(pattern, operation, re.IGNORECASE):
                counters[mr_type] += 1
                mr_id = f"MR-FB-{mr_type[:3].upper()}-{counters[mr_type]:02d}"
                # Extraire méthode HTTP et endpoint depuis operation
                parts = operation.split(" ", 1)
                http_method = parts[0] if len(parts) == 2 else "GET"
                endpoint = parts[1] if len(parts) == 2 else operation

                return MRInstance(
                    mr_id=mr_id,
                    mr_type=mr_type,
                    service=service,
                    endpoint=endpoint,
                    http_method=http_method,
                    phi=phi,
                    rho=rho,
                    source="jaeger_fallback",
                )
        return None