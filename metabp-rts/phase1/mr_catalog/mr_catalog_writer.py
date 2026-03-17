"""
mr_catalog_writer.py
====================
BLOC      : Bloc C — Catalogue MR
ROLE      : Sérialise le catalogue MR final (liste de MRInstance)
            en fichier mr_catalog.yaml consommable par la Phase 4
            (Validation Métamorphique).
            Format YAML produit :
              mr_catalog:
                - id: MR-PAY-01
                  type: Idempotence
                  service: ts-payment-service
                  endpoint: POST /api/v1/executePayment
                  phi: "même body envoyé 2 fois avec même paymentId"
                  rho: "total_charged == montant_unique (pas de double débit)"
                  source: openapi
ENTREES   : List[MRInstance]
SORTIES   : Fichier data/outputs/mr_catalog.yaml
LIBRAIRIES: pyyaml
"""

# TODO: implémenter MRCatalogWriter
# Méthodes attendues :
#   - write(mr_instances, output_path) -> None
#   - _to_dict(mr_instance) -> dict
#   - summary(mr_instances) -> dict  (stats par type et par service)

"""
mr_catalog_writer.py
====================
BLOC      : Bloc C — Catalogue MR
ROLE      : Sérialise le catalogue MR final (liste de MRInstance)
            en fichier mr_catalog.yaml consommable par la Phase 4
            (Validation Métamorphique).
            Format YAML produit :
              mr_catalog:
                - id: MR-PAY-01
                  type: Idempotence
                  service: ts-payment-service
                  endpoint: POST /api/v1/executePayment
                  phi: "même body envoyé 2 fois avec même paymentId"
                  rho: "total_charged == montant_unique (pas de double débit)"
                  source: openapi
ENTREES   : List[MRInstance]
SORTIES   : Fichier data/outputs/mr_catalog.yaml
LIBRAIRIES: pyyaml
"""

import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

import yaml

from models.models import MRInstance

logger = logging.getLogger(__name__)


class MRCatalogWriter:
    """
    Sérialise le catalogue MR final en fichier mr_catalog.yaml.
    Format consommable directement par la Phase 4.
    """

    def write(self, mr_instances: List[MRInstance], output_path: str) -> None:
        """
        Écrit le catalogue MR en YAML.
        Crée les répertoires parents si nécessaire.
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        catalog = {
            "mr_catalog": [self._to_dict(mr) for mr in mr_instances]
        }

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(
                catalog,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )

        stats = self.summary(mr_instances)
        logger.info(
            "MRCatalogWriter → %s écrit (%d MR | %d types | %d services)",
            path, stats["total"], stats["by_type_count"], stats["service_count"],
        )

    def summary(self, mr_instances: List[MRInstance]) -> dict:
        """
        Statistiques du catalogue — utile pour le log final de run_phase1.py.
        """
        by_type: Dict[str, int] = defaultdict(int)
        by_service: Dict[str, int] = defaultdict(int)
        by_source: Dict[str, int] = defaultdict(int)

        for mr in mr_instances:
            by_type[mr.mr_type] += 1
            by_service[mr.service] += 1
            by_source[mr.source] += 1

        return {
            "total": len(mr_instances),
            "by_type": dict(by_type),
            "by_type_count": len(by_type),
            "by_source": dict(by_source),
            "service_count": len(by_service),
        }

    # ── Méthode privée ────────────────────────────────────

    def _to_dict(self, mr: MRInstance) -> dict:
        """Convertit un MRInstance en dict ordonné pour YAML."""
        return {
            "id": mr.mr_id,
            "type": mr.mr_type,
            "service": mr.service,
            "endpoint": mr.endpoint,
            "http_method": mr.http_method,
            "phi": mr.phi,
            "rho": mr.rho,
            "source": mr.source,
        }