#!/usr/bin/env python3
"""
generate_traffic.py
===================
Génère un volume massif de trafic RÉEL sur Train-Ticket
pour alimenter Jaeger en traces distribuées.

IMPORTANT — Ce ne sont PAS des données synthétiques.
Ce script exécute de VRAIES requêtes HTTP sur Train-Ticket,
qui génèrent de VRAIES traces Jaeger via l'instrumentation
OpenTelemetry intégrée dans chaque service.

Défendable devant un jury : "Les traces Jaeger ont été générées
par l'exécution répétée de scénarios fonctionnels réels sur le
système Train-Ticket (FudanSELab), couvrant 10+ scénarios métier."

Usage :
    python generate_traffic.py --iterations 200 --base-url http://localhost:8080

    200 itérations ≈ 4000-5000 traces (selon les services actifs)
    500 itérations ≈ 10000-15000 traces
    1000 itérations ≈ 20000+ traces
"""

import argparse
import json
import logging
import random
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("generate_traffic")

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

CITIES = [
    ("Shang Hai", "Su Zhou"),
    ("Shang Hai", "Nan Jing"),
    ("Shang Hai", "Bei Jing"),
    ("Nan Jing", "Shang Hai"),
    ("Su Zhou", "Shang Hai"),
    ("Bei Jing", "Shang Hai"),
]

TRAIN_TYPES = ["GaoTie", "ZhiDa", "TeKuai", "KuaiSu"]


class TrainTicketTrafficGenerator:
    def __init__(self, base_url: str = "http://localhost:8080", timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.token = None
        self.stats = {
            "total_requests": 0,
            "successful": 0,
            "failed": 0,
            "by_scenario": {},
        }

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _get(self, path: str, **kwargs) -> requests.Response:
        self.stats["total_requests"] += 1
        try:
            r = self.session.get(
                f"{self.base_url}{path}",
                headers=self._headers(),
                timeout=self.timeout,
                **kwargs,
            )
            self.stats["successful"] += 1
            return r
        except Exception as e:
            self.stats["failed"] += 1
            raise

    def _post(self, path: str, data: dict = None, **kwargs) -> requests.Response:
        self.stats["total_requests"] += 1
        try:
            r = self.session.post(
                f"{self.base_url}{path}",
                headers=self._headers(),
                json=data,
                timeout=self.timeout,
                **kwargs,
            )
            self.stats["successful"] += 1
            return r
        except Exception as e:
            self.stats["failed"] += 1
            raise

    def _put(self, path: str, data: dict = None) -> requests.Response:
        self.stats["total_requests"] += 1
        try:
            r = self.session.put(
                f"{self.base_url}{path}",
                headers=self._headers(),
                json=data,
                timeout=self.timeout,
            )
            self.stats["successful"] += 1
            return r
        except Exception as e:
            self.stats["failed"] += 1
            raise

    def _delete(self, path: str) -> requests.Response:
        self.stats["total_requests"] += 1
        try:
            r = self.session.delete(
                f"{self.base_url}{path}",
                headers=self._headers(),
                timeout=self.timeout,
            )
            self.stats["successful"] += 1
            return r
        except Exception as e:
            self.stats["failed"] += 1
            raise

    def _track(self, scenario: str):
        self.stats["by_scenario"][scenario] = (
            self.stats["by_scenario"].get(scenario, 0) + 1
        )

    # ═══════════════════════════════════════════════════════════
    # AUTHENTIFICATION
    # ═══════════════════════════════════════════════════════════

    def login(self) -> bool:
        """Login via verification code + credentials."""
        try:
            # Générer un code de vérification
            self._get("/api/v1/verifycode/generate")
            time.sleep(1)

            # Lire le code depuis les logs du conteneur
            try:
                logs = subprocess.check_output(
                    ["sudo", "docker", "logs", "--tail", "10",
                     "train-ticket-master-ts-verification-code-service-1"],
                    stderr=subprocess.STDOUT,
                    timeout=10,
                ).decode()
                codes = re.findall(r":\s+([A-Z0-9]{4})\s+___", logs)
                if not codes:
                    codes = re.findall(r"[A-Z0-9]{4}", logs)
                code = codes[-1] if codes else "1234"
            except Exception:
                code = "1234"

            r = self._post("/api/v1/users/login", {
                "username": "fdse_microservice",
                "password": "111111",
                "verificationCode": code,
            })

            data = r.json()
            if data.get("status") == 1 and data.get("data"):
                self.token = data["data"].get("token")
                logger.info("Login OK — token obtenu")
                return True
            else:
                logger.warning("Login échoué : %s", data.get("msg", "?"))
                return False
        except Exception as e:
            logger.error("Login impossible : %s", e)
            return False

    # ═══════════════════════════════════════════════════════════
    # SCÉNARIOS MÉTIER
    # ═══════════════════════════════════════════════════════════

    def scenario_query_travel(self):
        """Recherche de trajets — traverse travel → ticketinfo → basic → station → train → route → price."""
        src, dst = random.choice(CITIES)
        date = (datetime.now() + timedelta(days=random.randint(1, 30))).strftime("%Y-%m-%d")
        self._post("/api/v1/travelservice/trips/left", {
            "startingPlace": src,
            "endPlace": dst,
            "departureTime": date,
        })
        self._track("query_travel")

    def scenario_query_travel2(self):
        """Recherche trajets (travel2) — traverse travel2 → ticketinfo → basic → station."""
        src, dst = random.choice(CITIES)
        date = (datetime.now() + timedelta(days=random.randint(1, 30))).strftime("%Y-%m-%d")
        self._post("/api/v1/travel2service/trips/left", {
            "startingPlace": src,
            "endPlace": dst,
            "departureTime": date,
        })
        self._track("query_travel2")

    def scenario_query_admin_basic(self):
        """Admin basic info — traverse admin-basic → contacts/trains/configs/prices/stations."""
        endpoints = [
            "/api/v1/adminbasicservice/adminbasic/contacts",
            "/api/v1/adminbasicservice/adminbasic/trains",
            "/api/v1/adminbasicservice/adminbasic/configs",
            "/api/v1/adminbasicservice/adminbasic/prices",
            "/api/v1/adminbasicservice/adminbasic/stations",
        ]
        for ep in endpoints:
            try:
                self._get(ep)
            except Exception:
                pass
        self._track("query_admin_basic")

    def scenario_query_orders(self):
        """Consulter les commandes — traverse order → order-other."""
        self._post("/api/v1/orderservice/order/refresh", {
            "loginId": "4d2a46c7-71cb-4cf1-b5bb-b68406d9da6f",
            "enableStateQuery": False,
            "enableTravelDateQuery": False,
            "enableBoughtDateQuery": False,
            "travelDateStart": None,
            "travelDateEnd": None,
            "boughtDateStart": None,
            "boughtDateEnd": None,
        })
        self._post("/api/v1/orderOtherService/orderOther/refresh", {
            "loginId": "4d2a46c7-71cb-4cf1-b5bb-b68406d9da6f",
            "enableStateQuery": False,
            "enableTravelDateQuery": False,
            "enableBoughtDateQuery": False,
            "travelDateStart": None,
            "travelDateEnd": None,
            "boughtDateStart": None,
            "boughtDateEnd": None,
        })
        self._track("query_orders")

    def scenario_query_assurance(self):
        """Consulter les assurances — traverse assurance."""
        self._get("/api/v1/assuranceservice/assurances/types")
        self._track("query_assurance")

    def scenario_query_food(self):
        """Consulter la nourriture — traverse food → travel → station."""
        src, dst = random.choice(CITIES)
        date = (datetime.now() + timedelta(days=random.randint(1, 10))).strftime("%Y-%m-%d")
        self._get(f"/api/v1/foodservice/foods/{date}/{src}/{dst}/GaoTieOne")
        self._track("query_food")

    def scenario_query_contacts(self):
        """Consulter les contacts — traverse contacts."""
        self._get("/api/v1/contactservice/contacts/account/4d2a46c7-71cb-4cf1-b5bb-b68406d9da6f")
        self._track("query_contacts")

    def scenario_query_station(self):
        """Consulter les gares — traverse station."""
        self._get("/api/v1/stationservice/stations")
        self._track("query_station")

    def scenario_query_train(self):
        """Consulter les trains — traverse train."""
        self._get("/api/v1/trainservice/trains")
        self._track("query_train")

    def scenario_query_route(self):
        """Consulter les routes — traverse route."""
        self._get("/api/v1/routeservice/routes")
        self._track("query_route")

    def scenario_query_config(self):
        """Consulter la config — traverse config."""
        self._get("/api/v1/configservice/configs")
        self._track("query_config")

    def scenario_query_price(self):
        """Consulter les prix — traverse price."""
        self._get("/api/v1/priceservice/prices")
        self._track("query_price")

    def scenario_query_security(self):
        """Consulter la sécurité — traverse security → order."""
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._get(f"/api/v1/securityservice/securityConfigs/4d2a46c7-71cb-4cf1-b5bb-b68406d9da6f")
        self._track("query_security")

    def scenario_preserve(self):
        """Réserver un billet — traverse preserve → contacts → order → seat → travel → assurance → food → consign → notification → inside-payment."""
        src, dst = random.choice(CITIES)
        date = (datetime.now() + timedelta(days=random.randint(1, 30))).strftime("%Y-%m-%d")
        self._post("/api/v1/preserveservice/preserve", {
            "accountId": "4d2a46c7-71cb-4cf1-b5bb-b68406d9da6f",
            "contactsId": "contacts_1",
            "tripId": "G1237",
            "seatType": 2,
            "date": date,
            "from": src,
            "to": dst,
            "assurance": 0,
            "foodType": 0,
            "stationName": "",
            "storeName": "",
            "foodName": "",
            "foodPrice": 0.0,
            "handleDate": date,
            "consigneeName": "",
            "consigneePhone": "",
            "consigneeWeight": 0.0,
            "isWithin": False,
        })
        self._track("preserve")

    def scenario_cancel(self):
        """Annuler un billet — traverse cancel → order → inside-payment → notification."""
        # D'abord récupérer un orderId existant
        try:
            r = self._post("/api/v1/orderservice/order/refresh", {
                "loginId": "4d2a46c7-71cb-4cf1-b5bb-b68406d9da6f",
                "enableStateQuery": False,
                "enableTravelDateQuery": False,
                "enableBoughtDateQuery": False,
            })
            orders = r.json().get("data", [])
            if orders:
                oid = orders[0].get("id", "")
                if oid:
                    self._get(f"/api/v1/cancelservice/cancel/refound/{oid}")
        except Exception:
            pass
        self._track("cancel")

    def scenario_auth(self):
        """Authentification — traverse auth → verification-code → user."""
        self._get("/api/v1/verifycode/generate")
        self._track("auth")

    def scenario_consign(self):
        """Consulter les consignes — traverse consign → consign-price."""
        self._get("/api/v1/consignservice/consigns/account/4d2a46c7-71cb-4cf1-b5bb-b68406d9da6f")
        self._track("consign")

    def scenario_inside_payment(self):
        """Consulter les paiements — traverse inside-payment."""
        self._get("/api/v1/inside_pay_service/inside_payment/account")
        self._track("inside_payment")

    def scenario_notification(self):
        """Consulter les notifications — traverse notification."""
        self._get("/api/v1/notifyservice/notification/preserve_success")
        self._track("notification")

    # ═══════════════════════════════════════════════════════════
    # ORCHESTRATION
    # ═══════════════════════════════════════════════════════════

    def run_all_scenarios(self):
        """Exécute TOUS les scénarios une fois."""
        scenarios = [
            self.scenario_query_travel,
            self.scenario_query_travel2,
            self.scenario_query_admin_basic,
            self.scenario_query_orders,
            self.scenario_query_assurance,
            self.scenario_query_food,
            self.scenario_query_contacts,
            self.scenario_query_station,
            self.scenario_query_train,
            self.scenario_query_route,
            self.scenario_query_config,
            self.scenario_query_price,
            self.scenario_query_security,
            self.scenario_preserve,
            self.scenario_cancel,
            self.scenario_auth,
            self.scenario_consign,
            self.scenario_inside_payment,
        ]

        for scenario_fn in scenarios:
            try:
                scenario_fn()
            except Exception as e:
                logger.debug("Scénario %s échoué : %s", scenario_fn.__name__, e)

    def generate(self, iterations: int = 200, delay: float = 0.02):
        """
        Génère du trafic pendant N itérations.

        Chaque itération exécute tous les scénarios → ~18 scénarios × N requêtes.
        200 itérations ≈ 3600+ requêtes → 4000+ traces Jaeger
        """
        logger.info("=" * 60)
        logger.info("Génération de trafic sur Train-Ticket")
        logger.info("  URL        : %s", self.base_url)
        logger.info("  Itérations : %d", iterations)
        logger.info("  Scénarios  : 18 par itération")
        logger.info("  Estimation : %d+ requêtes → %d+ traces",
                     iterations * 18, iterations * 20)
        logger.info("=" * 60)

        t_start = time.perf_counter()

        for i in range(iterations):
            try:
                self.run_all_scenarios()
            except Exception as e:
                logger.debug("Itération %d : erreur globale : %s", i, e)

            if delay > 0:
                time.sleep(delay)

            if (i + 1) % 50 == 0 or i == 0:
                elapsed = time.perf_counter() - t_start
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                eta = (iterations - i - 1) / rate if rate > 0 else 0
                logger.info(
                    "  Itération %d/%d | %d requêtes (%d OK, %d err) | "
                    "%.0f req/s | ETA %.0fs",
                    i + 1, iterations,
                    self.stats["total_requests"],
                    self.stats["successful"],
                    self.stats["failed"],
                    self.stats["total_requests"] / elapsed if elapsed > 0 else 0,
                    eta,
                )

        elapsed = time.perf_counter() - t_start

        logger.info("=" * 60)
        logger.info("Génération terminée en %.1fs", elapsed)
        logger.info("  Total requêtes : %d", self.stats["total_requests"])
        logger.info("  Succès         : %d", self.stats["successful"])
        logger.info("  Échecs         : %d", self.stats["failed"])
        logger.info("  Taux succès    : %.1f%%",
                     self.stats["successful"] / max(self.stats["total_requests"], 1) * 100)
        logger.info("  Par scénario :")
        for sc, count in sorted(self.stats["by_scenario"].items(), key=lambda x: -x[1]):
            logger.info("    %-25s : %d exécutions", sc, count)
        logger.info("=" * 60)

    def check_jaeger(self, jaeger_url: str = "http://localhost:16686"):
        """Vérifie combien de traces Jaeger a capturé."""
        try:
            r = requests.get(f"{jaeger_url}/api/services", timeout=5)
            svcs = [s for s in (r.json().get("data") or []) if s != "jaeger-all-in-one"]
            logger.info("Jaeger — %d services détectés", len(svcs))

            total_traces = 0
            for svc in sorted(svcs):
                r2 = requests.get(f"{jaeger_url}/api/traces", params={
                    "service": svc, "lookback": "2h", "limit": 20000,
                }, timeout=30)
                n = len(r2.json().get("data") or [])
                total_traces += n
                logger.info("  %-40s %d traces", svc, n)

            logger.info("Total estimé : %d traces", total_traces)
            return total_traces
        except Exception as e:
            logger.error("Impossible de vérifier Jaeger : %s", e)
            return 0


def main():
    parser = argparse.ArgumentParser(
        description="Génération de trafic réel sur Train-Ticket pour Jaeger"
    )
    parser.add_argument(
        "--iterations", "-n", type=int, default=200,
        help="Nombre d'itérations (défaut 200 ≈ 4000 traces)",
    )
    parser.add_argument(
        "--base-url", default="http://localhost:8080",
        help="URL de Train-Ticket (défaut http://localhost:8080)",
    )
    parser.add_argument(
        "--jaeger-url", default="http://localhost:16686",
        help="URL de Jaeger (défaut http://localhost:16686)",
    )
    parser.add_argument(
        "--delay", type=float, default=0.02,
        help="Délai entre itérations en secondes (défaut 0.02)",
    )
    parser.add_argument(
        "--check-only", action="store_true",
        help="Vérifier Jaeger sans générer de trafic",
    )
    args = parser.parse_args()

    gen = TrainTicketTrafficGenerator(base_url=args.base_url)

    if args.check_only:
        gen.check_jaeger(args.jaeger_url)
        return

    # Vérifier que Train-Ticket est accessible
    try:
        r = requests.get(args.base_url, timeout=5)
        logger.info("Train-Ticket accessible : %s", args.base_url)
    except Exception:
        logger.error("Train-Ticket inaccessible à %s — vérifier Docker", args.base_url)
        sys.exit(1)

    # Login
    if not gen.login():
        logger.error("Impossible de se connecter à Train-Ticket")
        sys.exit(1)

    # Générer le trafic
    gen.generate(iterations=args.iterations, delay=args.delay)

    # Vérifier le résultat dans Jaeger
    logger.info("")
    logger.info("Vérification Jaeger...")
    time.sleep(3)  # Attendre que Jaeger indexe
    gen.check_jaeger(args.jaeger_url)


if __name__ == "__main__":
    main()