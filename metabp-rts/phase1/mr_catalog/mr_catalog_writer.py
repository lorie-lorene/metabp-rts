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
