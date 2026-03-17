"""
jaeger_client.py
================
BLOC      : Bloc A — Ingestion
ROLE      : Communique avec l'API REST de Jaeger pour récupérer
            les traces brutes d'un service sur une fenêtre temporelle.
ENTREES   : - URL Jaeger (ex: http://localhost:16686)
            - Nom du service cible (ex: ts-gateway-service)
            - Fenêtre temporelle (lookback) et limite de traces
SORTIES   : Liste brute de traces JSON [{traceID, spans[]}]
            Persistée dans data/raw/traces_raw.json
LIBRAIRIES: requests, json
"""

# TODO: implémenter JaegerClient
# Méthodes attendues :
#   - __init__(base_url, config)
#   - get_services() -> List[str]
#   - get_traces(service, lookback, limit) -> List[dict]
#   - save_raw(traces, output_path) -> None
