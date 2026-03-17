"""
generate_traffic.py
===================
BLOC      : Prérequis — Génération trafic (Section 0.2)
ROLE      : Génère le trafic applicatif sur Train-Ticket pour alimenter
            Jaeger en traces distribuées avant l'ingestion (Bloc A).
            Exécute des scénarios HTTP scénarisés vers l'API Gateway :
              1. login          → POST /api/v1/users/login
              2. search_ticket  → GET  /api/v1/travel/query
              3. book_ticket    → POST /api/v1/preserve
              4. pay_ticket     → POST /api/v1/inside_pay/pay
              5. query_order    → GET  /api/v1/order
              6. cancel_order   → GET  /api/v1/cancel/refound/{orderId}
            Chaque scénario est exécuté N fois (configurable) avec
            un délai entre les requêtes pour éviter la saturation.
ENTREES   : - URL API Gateway (system_config.yaml)
            - Nombre de requêtes par scénario
            - Délai entre requêtes (ms)
SORTIES   : Traces créées dans Jaeger — log du nombre de requêtes
            envoyées par scénario
LIBRAIRIES: requests, time, random, logging, argparse
USAGE     : python generate_traffic.py --config ../config/system_config.yaml
"""

# TODO: implémenter TrafficGenerator
# Méthodes attendues :
#   - __init__(gateway_url, config)
#   - run_all_scenarios(n_requests, delay_ms) -> Dict[str, int]
#   - scenario_login() -> bool
#   - scenario_search(from_station, to_station, date) -> bool
#   - scenario_book(trip_id, contact_id) -> bool
#   - scenario_pay(order_id) -> bool
#   - scenario_query_order(user_id) -> bool
#   - scenario_cancel(order_id) -> bool
#   - _post(endpoint, body) -> Optional[dict]
#   - _get(endpoint, params) -> Optional[dict]
