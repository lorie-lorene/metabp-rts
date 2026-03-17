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

"""
generate_traffic.py — Prérequis Phase 1 : génération de trafic
"""
import argparse
import logging
import random
import sys
import time
from pathlib import Path
from typing import Dict, Optional

import requests
import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("generate_traffic")


class TrafficGenerator:
    """
    Envoie des requêtes HTTP scénarisées vers l'API Gateway de Train-Ticket
    pour alimenter Jaeger en traces distribuées.

    Les scénarios reproduisent des comportements utilisateurs réels :
    login → recherche → réservation → paiement → consultation → annulation.
    """

    def __init__(self, gateway_url: str, timeout: int = 10):
        self.gateway_url = gateway_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})
        self._token: Optional[str] = None

    def run_all_scenarios(
        self,
        n_requests: int = 100,
        delay_ms: int = 100,
    ) -> Dict[str, int]:
        """
        Exécute tous les scénarios N fois chacun.

        Retourne
        --------
        Dict {scenario_name: nb_succès}
        """
        results: Dict[str, int] = {}
        delay_s = delay_ms / 1000.0

        # Scénario login d'abord pour récupérer le token
        logger.info("Scénario : login (%d fois)", n_requests)
        login_ok = 0
        for _ in range(n_requests):
            if self._scenario_login():
                login_ok += 1
            time.sleep(delay_s)
        results["login"] = login_ok
        logger.info("  login → %d/%d succès", login_ok, n_requests)

        # Scénarios restants
        scenarios = [
            ("search_ticket", self._scenario_search),
            ("query_order",   self._scenario_query_order),
            ("book_ticket",   self._scenario_book),
            ("pay_ticket",    self._scenario_pay),
            ("cancel_order",  self._scenario_cancel),
        ]

        for name, func in scenarios:
            logger.info("Scénario : %s (%d fois)", name, n_requests)
            ok = 0
            for _ in range(n_requests):
                if func():
                    ok += 1
                time.sleep(delay_s)
            results[name] = ok
            logger.info("  %s → %d/%d succès", name, ok, n_requests)

        total = sum(results.values())
        logger.info("Trafic généré : %d requêtes réussies au total", total)
        return results

    # ── Scénarios ─────────────────────────────────────────

    def _scenario_login(self) -> bool:
        """POST /api/v1/users/login"""
        body = {
            "username": "fdse_microservice",
            "password": "111111",
            "verificationCode": "123456",
        }
        resp = self._post("/api/v1/users/login", body)
        if resp and resp.get("status") == 1:
            # Stocker le token pour les scénarios suivants
            data = resp.get("data", {})
            self._token = data.get("token")
            if self._token:
                self._session.headers["Authorization"] = f"Bearer {self._token}"
            return True
        return False

    def _scenario_search(self) -> bool:
        """GET /api/v1/travel/query — recherche de billets"""
        stations = [
            ("Shang Hai", "Su Zhou"),
            ("Nan Jing", "Shang Hai"),
            ("Su Zhou", "Nan Jing"),
        ]
        from_s, to_s = random.choice(stations)
        params = {
            "startingPlace": from_s,
            "endPlace": to_s,
            "departureTime": "2026-05-04",
        }
        resp = self._get("/api/v1/travel/query", params)
        return resp is not None and resp.get("status") == 1

    def _scenario_query_order(self) -> bool:
        """GET /api/v1/order"""
        resp = self._get("/api/v1/order", {})
        return resp is not None

    def _scenario_book(self) -> bool:
        """POST /api/v1/preserve — réservation"""
        body = {
            "accountId": "4d2a46c7-71cb-4cf1-b5bb-b68406d9da6f",
            "contactsId": "1",
            "tripId": "D1345",
            "seatType": "2",
            "date": "2026-05-04",
            "from": "Shang Hai",
            "to": "Su Zhou",
            "assurance": "0",
            "foodType": 1,
            "foodName": "Hamburger",
            "foodPrice": 3.0,
        }
        resp = self._post("/api/v1/preserve", body)
        return resp is not None and resp.get("status") == 1

    def _scenario_pay(self) -> bool:
        """POST /api/v1/inside_pay/pay"""
        body = {
            "orderId": "5ad7750b-a68b-49c0-a8c0-32776c067703",
            "tripId": "D1345",
            "price": "10.0",
        }
        resp = self._post("/api/v1/inside_pay/pay", body)
        return resp is not None

    def _scenario_cancel(self) -> bool:
        """GET /api/v1/cancel/refound/{orderId}"""
        order_id = "5ad7750b-a68b-49c0-a8c0-32776c067703"
        resp = self._get(f"/api/v1/cancel/refound/{order_id}", {})
        return resp is not None

    # ── Helpers HTTP ──────────────────────────────────────

    def _post(self, endpoint: str, body: dict) -> Optional[dict]:
        try:
            resp = self._session.post(
                f"{self.gateway_url}{endpoint}",
                json=body,
                timeout=self.timeout,
            )
            return resp.json()
        except Exception:
            return None

    def _get(self, endpoint: str, params: dict) -> Optional[dict]:
        try:
            resp = self._session.get(
                f"{self.gateway_url}{endpoint}",
                params=params,
                timeout=self.timeout,
            )
            return resp.json()
        except Exception:
            return None


def main():
    parser = argparse.ArgumentParser(
        description="MetaBP-RTS — Génération de trafic Train-Ticket"
    )
    parser.add_argument(
        "--config",
        default="../config/system_config.yaml",
        help="Chemin vers system_config.yaml",
    )
    parser.add_argument(
        "--n-requests",
        type=int,
        default=None,
        help="Nombre de requêtes par scénario (écrase la config)",
    )
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    tg_cfg = config.get("traffic_generation", {})
    gateway_url = config["train_ticket"]["api_gateway_url"]
    n_requests = args.n_requests or tg_cfg.get("num_requests", 100)
    delay_ms = tg_cfg.get("delay_between_requests_ms", 100)

    logger.info("Gateway : %s", gateway_url)
    logger.info("Requêtes par scénario : %d", n_requests)
    logger.info("Délai entre requêtes  : %dms", delay_ms)

    gen = TrafficGenerator(gateway_url)
    results = gen.run_all_scenarios(n_requests, delay_ms)

    logger.info("Résultats par scénario : %s", results)
    logger.info("Jaeger devrait maintenant contenir des traces.")
    logger.info("Vérifiez : http://localhost:16686")


if __name__ == "__main__":
    main()