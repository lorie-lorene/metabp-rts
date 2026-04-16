"""
Fallback activé quand les specs OpenAPI ne sont pas accessibles 
-Infère des MR partiels depuis les operationName des spans
-Jaeger en appliquant des règles sur la méthode HTTP et le pattern d'url
"""

import logging
import re
from collections import defaultdict
from typing import Dict, List, Optional

from models.models import MRInstance, SpanRecord

logger = logging.getLogger(__name__)

# Couvrent les spans gateway-service et services métier
_HTTP_RULES = [
    (
        r"^POST\s+.*(pay|payment|inside_pay).*",
        "Idempotence",
        "Même orderId envoyé deux fois à POST {endpoint}",
        "Le montant débité est identique à une seule exécution — pas de double débit",
    ),
   
    (
        r"^POST\s+.*refund.*",
        "Idempotence",
        "Même orderId envoyé deux fois à POST {endpoint}",
        "Le remboursement n'est effectué qu'une seule fois",
    ),
    
    (
        r"^POST\s+.*(create|preserve|reserve).*",
        "Idempotence",
        "Même body avec même identifiant unique envoyé deux fois à POST {endpoint}",
        "La ressource n'est créée qu'une seule fois — pas de doublon",
    ),
    
    (
        r"^POST\s+.*login.*",
        "Idempotence",
        "Mêmes credentials envoyés deux fois à POST {endpoint}",
        "Un token valide est retourné à chaque appel — pas de duplication de session",
    ),
   
    (
        r"^GET\s+.*cancel.*",
        "Idempotence",
        "Même orderId annulé deux fois via GET {endpoint}",
        "L'état final est 'annulé' quelle que soit la multiplicité de l'appel",
    ),
    
    (
        r"^GET\s+.*(travel|travels|query).*",
        "Permutation",
        "Permutation des paramètres from/to/date dans GET {endpoint}",
        "Le résultat est identique quelle que soit l'ordre des query parameters",
    ),
    
    (
        r"^GET\s+.*orders.*",
        "Sous-ensemble",
        "GET {endpoint} avec filtre status=paid vs sans filtre",
        "résultats_filtrés ⊆ résultats_sans_filtre",
    ),
  
    (
        r"^GET\s+.*seats.*",
        "Monotonie",
        "GET {endpoint} avant et après une réservation",
        "seats_disponibles_après <= seats_disponibles_avant",
    ),
]

_INTERNAL_RULES = [
    #  Monotonie
    (
        r"verify.balance",
        "Monotonie",
        "Vérification du solde avant et après un débit",
        "solde_après <= solde_avant",
    ),
    # Idempotence
    (
        r"charge.account",
        "Idempotence",
        "Même transaction envoyée deux fois à charge-account",
        "Le solde est débité une seule fois",
    ),
    #Idempotence
    (
        r"verify.credentials",
        "Idempotence",
        "Mêmes credentials vérifiés deux fois",
        "Le résultat d'authentification est identique",
    ),
    #  Idempotence
    (
        r"generate.token",
        "Idempotence",
        "Génération de token pour les mêmes credentials",
        "Le token est valide et unique à chaque appel",
    ),
    #  Monotonie
    (
        r"lock.seat|reserve.seat",
        "Monotonie",
        "Réservation d'un siège puis consultation de disponibilité",
        "seats_disponibles_après < seats_disponibles_avant",
    ),
    #  Monotonie
    (
        r"calculate.refund",
        "Monotonie",
        "Calcul du remboursement en fonction du délai d'annulation",
        "refund_amount <= prix_original",
    ),
    # Sous-ensemble
    (
        r"search.travel|query.*db|search.*db",
        "Sous-ensemble",
        "Requête avec filtre supplémentaire (date/trajet)",
        "résultats_filtrés ⊆ résultats_sans_filtre",
    ),
    # Idempotence
    (
        r"save.*db|update.*status",
        "Idempotence",
        "Même opération de sauvegarde exécutée deux fois",
        "L'état final est identique — pas de duplication en base",
    ),
    #  Idempotence
    (
        r"send.*confirm|notify",
        "Idempotence",
        "Même notification envoyée deux fois",
        "L'utilisateur reçoit une seule notification",
    ),
]

# Combinaison des deux ensembles de règles
_RULES = _HTTP_RULES + _INTERNAL_RULES


class JaegerFallbackMR:

    def infer(self, spans: List[SpanRecord]) -> List[MRInstance]:

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

    def _extract_operations(
        self,
        spans: List[SpanRecord],
    ) -> Dict[str, List[str]]:
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

        # Extraire méthode HTTP et endpoint
        parts = operation.split(" ", 1)
        if len(parts) == 2:
            http_method = parts[0].upper()
            endpoint = parts[1]
        else:
            # Span interne sans méthode HTTP
            http_method = "INTERNAL"
            endpoint = operation

        for pattern, mr_type, phi_tpl, rho in _RULES:
            if re.search(pattern, operation, re.IGNORECASE):
                counters[mr_type] += 1
                mr_id = f"MR-FB-{mr_type[:3].upper()}-{counters[mr_type]:02d}"

                # Instancier le template phi avec l'endpoint réel
                phi = phi_tpl.format(endpoint=endpoint)

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