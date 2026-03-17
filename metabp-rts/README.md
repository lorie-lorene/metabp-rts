# MetaBP-RTS — Phase 1

Méthodologie MetaBP-RTS — Phase 1 : Modélisation Architecturale & Extraction.
 source venv-metabp/bin/activate
## Prérequis
1. Déployer Train-Ticket : `docker-compose up -d`
2. Générer du trafic : `python phase1/scripts/generate_traffic.py`

## Lancement Phase 1
```bash
pip install -r requirements.txt
python phase1/scripts/run_phase1.py --config phase1/config/system_config.yaml
```

## Artefacts produits
- `phase1/data/outputs/service_graph.json`   — Graphe G = (V, E)
- `phase1/data/outputs/service_scores.json`  — Scores C, P, F, Θ_dormant
- `phase1/data/outputs/test_suite_T.json`    — Suite de tests T
- `phase1/data/outputs/mr_catalog.yaml`      — Catalogue MR

# MetaBP-RTS — Phase 1 : Guide Opérationnel Complet

**Auteur** : NIKOUM Modeste Lorene  
**Encadrante** : Pr. DJAM KIMBI Xaveria Youh  
**Programme** : Master II SIGL — Université de Yaoundé I  
**Objectif Phase 1** : Produire le graphe de services G, la suite de tests T et le catalogue MR depuis les traces Jaeger de Train-Ticket.

---

## Table des matières

1. [Prérequis système](#1-prérequis-système)
2. [Cloner et installer Train-Ticket](#2-cloner-et-installer-train-ticket)
3. [Démarrer Train-Ticket avec Docker](#3-démarrer-train-ticket-avec-docker)
4. [Vérifier que Jaeger fonctionne](#4-vérifier-que-jaeger-fonctionne)
5. [Installer les dépendances Python](#5-installer-les-dépendances-python)
6. [Structure du projet Phase 1](#6-structure-du-projet-phase-1)
7. [Configuration](#7-configuration)
8. [Générer le trafic applicatif](#8-générer-le-trafic-applicatif)
9. [Exécuter la Phase 1](#9-exécuter-la-phase-1)
10. [Vérifier les artefacts produits](#10-vérifier-les-artefacts-produits)
11. [Lancer les tests unitaires](#11-lancer-les-tests-unitaires)
12. [Résolution des problèmes courants](#12-résolution-des-problèmes-courants)
13. [Référence des commandes](#13-référence-des-commandes)

---

## 1. Prérequis système

Avant de commencer, vérifier que les outils suivants sont installés.

### 1.1 Docker et Docker Compose

```bash
# Vérifier Docker
docker --version
# Attendu : Docker version 24.x ou supérieur

# Vérifier Docker Compose
docker compose version
# Attendu : Docker Compose version 2.x ou supérieur
```

Si Docker n'est pas installé :

```bash
# Ubuntu / Debian
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin

# Ajouter l'utilisateur courant au groupe docker (évite sudo)
sudo usermod -aG docker $USER
newgrp docker
```

### 1.2 Python

```bash
python3 --version
# Attendu : Python 3.10 ou supérieur
```

Si Python n'est pas installé :

```bash
sudo apt-get install -y python3 python3-pip python3-venv
```

### 1.3 Git

```bash
git --version
# Attendu : git version 2.x ou supérieur
```

### 1.4 Ressources matérielles minimales

| Ressource | Minimum recommandé |
|---|---|
| RAM | 16 Go (Train-Ticket = 40+ conteneurs) |
| Espace disque | 20 Go libres |
| CPU | 4 cœurs |
| OS | Ubuntu 20.04 / 22.04 ou macOS 12+ |

> **Note** : Si la machine dispose de moins de 16 Go de RAM, déployer uniquement
> les services essentiels de Train-Ticket (voir Section 3.3).

---

## 2. Cloner et installer Train-Ticket

### 2.1 Cloner le dépôt Train-Ticket

```bash
# Se placer dans le répertoire de travail
cd ~

# Cloner Train-Ticket (dépôt officiel FudanSELab)
git clone --depth=1 https://github.com/FudanSELab/train-ticket.git

# Vérifier la structure clonée
ls train-ticket/
# Attendu : docker-compose.yml, ts-*/ (répertoires services), deployment/
```

### 2.2 Cloner MetaBP-RTS

```bash
# Cloner le projet MetaBP-RTS (ou copier le dossier metabp-rts/)
# Si vous avez le dossier depuis les livrables :
cp -r metabp-rts/ ~/metabp-rts/

# Vérifier la structure
ls ~/metabp-rts/
# Attendu : phase1/  requirements.txt  README.md
```

### 2.3 Organisation finale des répertoires

```
~/
├── train-ticket/          ← dépôt Train-Ticket
│   └── docker-compose.yml
└── metabp-rts/            ← projet MetaBP-RTS
    ├── phase1/
    └── requirements.txt
```

---

## 3. Démarrer Train-Ticket avec Docker

### 3.1 Démarrage complet (recommandé si 16 Go+ de RAM)

```bash
cd ~/train-ticket

# Démarrer tous les services en arrière-plan
# L'option --with-tracing active Jaeger automatiquement
docker compose up -d

# Surveiller le démarrage (peut prendre 3 à 5 minutes)
docker compose ps
```

Attendre que tous les conteneurs affichent le statut `Up` ou `healthy`.

```bash
# Vérifier le nombre de conteneurs actifs
docker compose ps | grep -c "Up"
# Attendu : 40 ou plus
```

### 3.2 Vérifier que l'API Gateway répond

```bash
curl -s http://localhost:8080/api/v1/users/hello
# Attendu : une réponse JSON (pas de "Connection refused")
```

Si la commande échoue, attendre encore 1 à 2 minutes et réessayer.
Train-Ticket démarre les services progressivement.

### 3.3 Démarrage minimal (si moins de 16 Go de RAM)

Si la machine manque de ressources, démarrer uniquement les services
nécessaires aux scénarios de trafic :

```bash
cd ~/train-ticket

docker compose up -d \
  ts-gateway-service \
  ts-auth-service \
  ts-user-service \
  ts-order-service \
  ts-travel-service \
  ts-payment-service \
  ts-preserve-service \
  ts-seat-service \
  ts-route-service \
  ts-train-service \
  ts-station-service \
  ts-security-service \
  ts-price-service \
  ts-contacts-service \
  ts-config-service \
  ts-cancel-service \
  ts-inside-payment-service \
  jaeger \
  rabbitmq \
  mysql
```

> **Note** : Le démarrage minimal produit un graphe G moins dense,
> mais suffisant pour valider la Phase 1.

### 3.4 Arrêter Train-Ticket

```bash
cd ~/train-ticket
docker compose down
```

Pour supprimer aussi les volumes (données) :

```bash
docker compose down -v
```

---

## 4. Vérifier que Jaeger fonctionne

### 4.1 Interface web Jaeger

Ouvrir dans un navigateur :

```
http://localhost:16686
```

Vérifier que la page s'affiche correctement et que le menu déroulant
"Service" contient au moins `ts-gateway-service`.

### 4.2 Vérification via l'API REST Jaeger

```bash
# Lister les services connus de Jaeger
curl -s "http://localhost:16686/api/services" | python3 -m json.tool

# Attendu : {"data": ["ts-gateway-service", "ts-auth-service", ...], "total": N}
```

Si Jaeger ne liste aucun service, les conteneurs n'ont pas encore
généré de trafic. Passer à la Section 8 pour générer du trafic,
puis revérifier.

### 4.3 Cas : Jaeger ne démarre pas

```bash
# Vérifier les logs du conteneur Jaeger
docker compose logs jaeger | tail -20

# Redémarrer uniquement Jaeger
docker compose restart jaeger
```

---

## 5. Installer les dépendances Python

### 5.1 Créer un environnement virtuel (recommandé)

```bash
cd ~/metabp-rts

# Créer l'environnement
python3 -m venv venv

# Activer l'environnement
source venv/bin/activate
# Sur Windows : venv\Scripts\activate

# Vérifier l'activation
which python
# Attendu : ~/metabp-rts/venv/bin/python
```

### 5.2 Installer les dépendances

```bash
pip install -r requirements.txt
```

Dépendances installées :

| Librairie | Version | Utilisation |
|---|---|---|
| networkx | 3.1 | Construction et analyse du graphe G |
| numpy | 1.24.0 | Calculs numériques (normalisation, moyennes) |
| pandas | 2.0.0 | Manipulation des données tabulaires |
| requests | 2.31.0 | Appels HTTP vers Jaeger et Train-Ticket |
| pyyaml | 6.0.1 | Lecture des fichiers de configuration |
| openapi-spec-validator | 0.7.1 | Validation des specs OpenAPI |
| pytest | 7.4.0 | Exécution des tests unitaires |
| pytest-cov | 4.1.0 | Couverture de code des tests |

### 5.3 Vérifier l'installation

```bash
python3 -c "import networkx, numpy, requests, yaml; print('OK')"
# Attendu : OK
```

---

## 6. Structure du projet Phase 1

```
metabp-rts/
├── requirements.txt
├── README.md
└── phase1/
    ├── pytest.ini                    ← configuration pytest
    │
    ├── config/
    │   ├── system_config.yaml        ← paramètres globaux (Jaeger, poids, seuils)
    │   └── services_map.yaml         ← mapping service → port (OpenAPI)
    │
    ├── models/
    │   └── models.py                 ← dataclasses partagées (SpanRecord, etc.)
    │
    ├── ingestion/                    ← BLOC A
    │   ├── jaeger_client.py          ← récupération traces Jaeger
    │   ├── span_parser.py            ← parsing des spans bruts
    │   └── trace_reconstructor.py   ← reconstruction T et edge_list
    │
    ├── graph/                        ← BLOC B
    │   ├── weight_calculator.py      ← calcul des poids w_ij
    │   ├── graph_builder.py          ← construction du graphe G
    │   ├── centrality.py             ← calcul C(si)
    │   ├── propagation_coeff.py      ← calcul P(si)
    │   ├── fragility.py              ← calcul F(si)
    │   └── echo_dormant.py           ← classification Écho-Dormant
    │
    ├── mr_catalog/                   ← BLOC C
    │   ├── openapi_reader.py         ← lecture specs OpenAPI
    │   ├── jaeger_fallback_mr.py     ← inférence MR sans OpenAPI
    │   ├── mr_inferrer.py            ← application des 6 règles MR
    │   └── mr_catalog_writer.py      ← écriture mr_catalog.yaml
    │
    ├── scripts/
    │   ├── generate_traffic.py       ← génération trafic Train-Ticket
    │   └── run_phase1.py             ← orchestrateur principal
    │
    ├── tests/
    │   ├── test_span_parser.py       ← tests Bloc A (10 tests)
    │   ├── test_graph_builder.py     ← tests Bloc B (15 tests)
    │   └── test_echo_dormant.py      ← tests Écho-Dormant + Théorème (10 tests)
    │
    └── data/
        ├── raw/
        │   └── traces_raw.json       ← traces brutes (créé à l'exécution)
        └── outputs/
            ├── service_graph.json    ← ARTEFACT : Graphe G
            ├── service_scores.json   ← ARTEFACT : Scores C, P, F, Θ
            ├── test_suite_T.json     ← ARTEFACT : Suite de tests T
            └── mr_catalog.yaml       ← ARTEFACT : Catalogue MR
```

---

## 7. Configuration

### 7.1 system_config.yaml — paramètres importants

Fichier : `phase1/config/system_config.yaml`

```yaml
jaeger:
  base_url: "http://localhost:16686"   # URL de l'interface Jaeger
  default_service: "ts-gateway-service" # Service de départ pour la collecte
  lookback: "1h"                        # Fenêtre temporelle : "1h", "6h", "24h"
  limit: 5000                           # Nb max de traces à récupérer

weights:
  alpha: 0.5    # Poids de rate_ij dans w_ij  (fréquence)
  beta: 0.3     # Poids de lat_norm dans w_ij  (latence)
  gamma: 0.2    # Poids de err_ij dans w_ij    (erreur)
  # INVARIANT : alpha + beta + gamma = 1.0

echo_dormant:
  tau_dormant: 0.40   # Seuil de classification Écho-Dormant
  omega_C: 0.357      # Poids de C(si) dans Θ_dormant
  omega_P: 0.357      # Poids de P(si) dans Θ_dormant
  omega_F: 0.286      # Poids de F(si) dans Θ_dormant
  # INVARIANT : omega_C + omega_P + omega_F = 1.0

traffic_generation:
  num_requests: 500            # Nb de requêtes par scénario
  delay_between_requests_ms: 100  # Délai entre requêtes (ms)
```

> **Important** : Ne pas modifier les invariants mathématiques
> (`alpha+beta+gamma=1` et `omega_C+omega_P+omega_F=1`).
> Le code vérifie ces contraintes au démarrage et lève une erreur sinon.

### 7.2 Adapter la fenêtre temporelle selon le trafic généré

| Trafic généré | Paramètre lookback recommandé |
|---|---|
| Session courte (< 30 min) | `"1h"` |
| Session de la journée | `"6h"` |
| Trafic multi-sessions | `"24h"` |
| Toutes les traces disponibles | `"168h"` (une semaine) |

### 7.3 services_map.yaml — ports OpenAPI

Ce fichier liste les ports exposés par chaque service Train-Ticket.
Il est pré-configuré avec les ports par défaut du docker-compose.yml
officiel. Ne le modifier que si Train-Ticket est déployé avec des
ports personnalisés.

```bash
# Vérifier les ports réellement exposés par Docker
docker compose ps | grep -E "ts-.*-service"
```

---

## 8. Générer le trafic applicatif

Cette étape est **obligatoire**. Sans trafic, Jaeger ne contient
aucune trace et la Phase 1 ne peut rien produire.

### 8.1 Activer l'environnement virtuel

```bash
cd ~/metabp-rts
source venv/bin/activate
```

### 8.2 Lancer la génération de trafic

```bash
cd ~/metabp-rts/phase1/scripts

python generate_traffic.py --config ../config/system_config.yaml
```

Sortie attendue :

```
10:15:32 [INFO] Gateway : http://localhost:8080
10:15:32 [INFO] Requêtes par scénario : 500
10:15:32 [INFO] Délai entre requêtes  : 100ms
10:15:32 [INFO] Scénario : login (500 fois)
10:16:22 [INFO]   login → 487/500 succès
10:16:22 [INFO] Scénario : search_ticket (500 fois)
10:17:12 [INFO]   search_ticket → 500/500 succès
10:17:12 [INFO] Scénario : query_order (500 fois)
...
10:20:45 [INFO] Trafic généré : 2874 requêtes réussies au total
10:20:45 [INFO] Jaeger devrait maintenant contenir des traces.
10:20:45 [INFO] Vérifiez : http://localhost:16686
```

### 8.3 Scénarios exécutés

| Scénario | Endpoint appelé | Ce que ça produit dans Jaeger |
|---|---|---|
| `login` | `POST /api/v1/users/login` | Traces auth-service, user-service |
| `search_ticket` | `GET /api/v1/travel/query` | Traces travel, route, train, station |
| `query_order` | `GET /api/v1/order` | Traces order-service |
| `book_ticket` | `POST /api/v1/preserve` | Traces preserve, seat, contact |
| `pay_ticket` | `POST /api/v1/inside_pay/pay` | Traces payment-service |
| `cancel_order` | `GET /api/v1/cancel/refound/{id}` | Traces cancel-service |

### 8.4 Paramètre personnalisé : nombre de requêtes

Pour un test rapide avec moins de requêtes :

```bash
python generate_traffic.py \
  --config ../config/system_config.yaml \
  --n-requests 50
```

> **Recommandation** : Utiliser au minimum 200 requêtes par scénario
> pour obtenir un graphe G statistiquement représentatif.

### 8.5 Vérifier que Jaeger a reçu les traces

```bash
curl -s "http://localhost:16686/api/services" | python3 -m json.tool
```

Attendu : au moins 10 services listés (ts-gateway-service,
ts-auth-service, ts-order-service, etc.).

Ou dans l'interface web Jaeger (`http://localhost:16686`) :
sélectionner `ts-gateway-service` dans le menu Service,
cliquer `Find Traces`, et vérifier que des traces apparaissent.

---

## 9. Exécuter la Phase 1

### 9.1 Exécution complète (recommandée)

```bash
cd ~/metabp-rts/phase1/scripts

python run_phase1.py --config ../config/system_config.yaml
```

### 9.2 Sortie attendue

```
10:25:01 [INFO] run_phase1 — MetaBP-RTS Phase 1 — démarrage
10:25:01 [INFO] run_phase1 — Config     : .../system_config.yaml
10:25:01 [INFO] run_phase1 — Services   : 40 services chargés
10:25:01 [INFO] run_phase1 — ── Étape 1/12 : Récupération traces Jaeger
10:25:03 [INFO] jaeger_client — Jaeger → service=ts-gateway-service | traces récupérées=1243
10:25:03 [INFO] run_phase1 — ── Étape 2/12 : Parsing des spans
10:25:04 [INFO] span_parser — SpanParser → 8751 spans parsés depuis 1243 traces
10:25:04 [INFO] run_phase1 — ── Étape 3/12 : Reconstruction T et edge_list
10:25:04 [INFO] trace_reconstructor — TraceReconstructor → T=1198 test paths | edge_list=6823 arcs bruts
10:25:04 [INFO] run_phase1 — ── Étape 4/12 : Calcul des poids w_ij
10:25:04 [INFO] weight_calculator — WeightCalculator → 47 arcs uniques calculés
10:25:04 [INFO] run_phase1 — ── Étape 5/12 : Construction du graphe G
10:25:04 [INFO] graph_builder — GraphBuilder → G créé : 23 services | 47 dépendances
10:25:05 [INFO] run_phase1 — Résumé G : {'nodes': 23, 'edges': 47, 'density': 0.0929, ...}
10:25:05 [INFO] run_phase1 — ── Étape 6/12 : Calcul centralité C(si)
10:25:05 [INFO] run_phase1 — ── Étape 7/12 : Calcul propagation P(si)
10:25:05 [INFO] run_phase1 — ── Étape 8/12 : Calcul fragilité F(si)
10:25:05 [INFO] run_phase1 — ── Étape 9/12 : Classification Écho-Dormant
10:25:05 [INFO] echo_dormant — EchoDormantClassifier → 23 services | 8 Écho-Dormants | 15 Non-Dormants
10:25:05 [INFO] echo_dormant — Théorème de Sécurité d'Exclusion : OK ✓
10:25:05 [INFO] run_phase1 — ── Étape 10/12 : Lecture specs OpenAPI
10:25:12 [INFO] openapi_reader — OpenAPIReader → 21/40 services avec spec OpenAPI accessible
10:25:12 [INFO] run_phase1 — ── Étape 11/12 : Inférence MR
10:25:12 [INFO] mr_inferrer — MRInferrer → 143 MR inférées depuis OpenAPI
10:25:12 [INFO] mr_fallback — JaegerFallbackMR → 34 MR inférées depuis operationName
10:25:12 [INFO] run_phase1 — ── Étape 12/12 : Écriture mr_catalog.yaml
10:25:12 [INFO] =======================================================
10:25:12 [INFO] Phase 1 terminée — Artefacts produits :
10:25:12 [INFO]   G        : 23 noeuds, 47 arcs
10:25:12 [INFO]   T        : 1198 cas de test
10:25:12 [INFO]   Scores   : 23 services (8 Écho-Dormants)
10:25:12 [INFO]   MR       : 177 relations (143 OpenAPI + 34 fallback)
10:25:12 [INFO] =======================================================
```

### 9.3 Erreur : "Impossible de joindre Jaeger"

```
ConnectionError: Impossible de joindre Jaeger à http://localhost:16686.
Vérifiez que Jaeger est démarré (docker-compose up).
```

Solution :
```bash
# Vérifier que Jaeger tourne
docker compose ps jaeger

# Si absent, redémarrer
cd ~/train-ticket && docker compose up -d jaeger

# Attendre 10 secondes, relancer
sleep 10
python run_phase1.py --config ../config/system_config.yaml
```

### 9.4 Erreur : "ARRÊT : Théorème de Sécurité violé"

Ce message indique une incohérence dans les paramètres de configuration.
Vérifier que `tau_dormant = 0.40` et `omega_C + omega_P + omega_F = 1.0`
dans `system_config.yaml`.

---

## 10. Vérifier les artefacts produits

### 10.1 Vérification rapide de l'existence des fichiers

```bash
ls -lh ~/metabp-rts/phase1/data/outputs/
```

Attendu :

```
-rw-r--r-- service_graph.json    ← Graphe G (NetworkX node-link JSON)
-rw-r--r-- service_scores.json   ← Scores C, P, F, Θ_dormant
-rw-r--r-- test_suite_T.json     ← Suite de tests T
-rw-r--r-- mr_catalog.yaml       ← Catalogue MR
```

### 10.2 Vérifier service_graph.json

```bash
python3 -c "
import json
with open('phase1/data/outputs/service_graph.json') as f:
    g = json.load(f)
nodes = len(g['nodes'])
links = len(g['links'])
print(f'Graphe G : {nodes} noeuds, {links} arcs')
# Vérifier qu'un arc a bien l'attribut w_ij
sample = g['links'][0]
print(f'Exemple arc : {sample[\"source\"]} → {sample[\"target\"]} | w_ij={sample[\"w_ij\"]}')
"
```

Attendu :
```
Graphe G : 23 noeuds, 47 arcs
Exemple arc : ts-gateway-service → ts-order-service | w_ij=0.523
```

### 10.3 Vérifier service_scores.json

```bash
python3 -c "
import json
with open('phase1/data/outputs/service_scores.json') as f:
    scores = json.load(f)
print(f'Nombre de services scorés : {len(scores)}')
# Afficher les 3 services avec le Θ_dormant le plus élevé
top3 = sorted(scores, key=lambda s: s['theta_dormant'], reverse=True)[:3]
for s in top3:
    status = 'DORMANT' if s['is_dormant'] else 'non-dormant'
    print(f\"  {s['service_name']:<40} Θ={s['theta_dormant']:.4f}  [{status}]\")
"
```

Attendu :
```
Nombre de services scorés : 23
  ts-order-service                         Θ=0.7124  [DORMANT]
  ts-gateway-service                       Θ=0.6891  [DORMANT]
  ts-payment-service                       Θ=0.5243  [DORMANT]
```

### 10.4 Vérifier test_suite_T.json

```bash
python3 -c "
import json
with open('phase1/data/outputs/test_suite_T.json') as f:
    T = json.load(f)
print(f'Suite T : {len(T)} cas de test')
# Afficher le premier cas de test
tp = T[0]
print(f'Exemple trace_id : {tp[\"trace_id\"]}')
print(f'Chaîne d invocat : {tp[\"invocation_chain\"][:3]}...')
"
```

Attendu :
```
Suite T : 1198 cas de test
Exemple trace_id : abc123def456
Chaîne d invocat : [['ts-gateway-service', 'ts-order-service'], ...]
```

### 10.5 Vérifier mr_catalog.yaml

```bash
python3 -c "
import yaml
with open('phase1/data/outputs/mr_catalog.yaml') as f:
    catalog = yaml.safe_load(f)
mrs = catalog['mr_catalog']
print(f'Catalogue MR : {len(mrs)} relations')
# Compter par type
from collections import Counter
types = Counter(mr['type'] for mr in mrs)
for t, count in sorted(types.items()):
    print(f'  {t:<20} : {count} instances')
"
```

Attendu :
```
Catalogue MR : 177 relations
  Cardinalité          : 28 instances
  Idempotence          : 35 instances
  Monotonie            : 12 instances
  Ordonnancement       : 31 instances
  Permutation          : 42 instances
  Sous-ensemble        : 29 instances
```

---

## 11. Lancer les tests unitaires

### 11.1 Exécuter tous les tests

```bash
cd ~/metabp-rts/phase1
python -m pytest tests/ -v
```

Résultat attendu :

```
============================= test session starts ==============================
collected 34 items

tests/test_echo_dormant.py::test_classification_above_threshold PASSED
tests/test_echo_dormant.py::test_classification_below_threshold PASSED
tests/test_echo_dormant.py::test_boundary_case_at_threshold PASSED
tests/test_echo_dormant.py::test_dormant_set_membership PASSED
tests/test_echo_dormant.py::test_scores_sorted_descending PASSED
tests/test_echo_dormant.py::test_safety_theorem_holds PASSED       ← propriété formelle
tests/test_echo_dormant.py::test_safety_theorem_non_dormant_constraint PASSED
tests/test_echo_dormant.py::test_omega_normalization PASSED
tests/test_echo_dormant.py::test_invalid_omega_raises PASSED
tests/test_echo_dormant.py::test_missing_service_in_one_score_dict PASSED
tests/test_graph_builder.py::test_weight_bounds PASSED
tests/test_graph_builder.py::test_weight_alpha_beta_gamma_sum PASSED
tests/test_graph_builder.py::test_weight_invalid_sum_raises PASSED
tests/test_graph_builder.py::test_weight_err_ij_correct PASSED
tests/test_graph_builder.py::test_weight_empty_edge_list PASSED
tests/test_graph_builder.py::test_graph_construction PASSED
tests/test_graph_builder.py::test_graph_arc_has_w_ij PASSED
tests/test_graph_builder.py::test_centrality_scores_in_bounds PASSED
tests/test_graph_builder.py::test_centrality_most_connected_node PASSED
tests/test_graph_builder.py::test_propagation_leaf_is_zero PASSED
tests/test_graph_builder.py::test_propagation_scores_in_bounds PASSED
tests/test_graph_builder.py::test_fragility_no_errors PASSED
tests/test_graph_builder.py::test_fragility_normalization PASSED
tests/test_graph_builder.py::test_fragility_partial_errors PASSED
tests/test_graph_builder.py::test_fragility_empty PASSED
tests/test_span_parser.py::test_parse_span_count PASSED
tests/test_span_parser.py::test_parse_span_fields PASSED
tests/test_span_parser.py::test_parent_child_relationship PASSED
tests/test_span_parser.py::test_error_detection PASSED
tests/test_span_parser.py::test_parse_all_multiple_traces PASSED
tests/test_span_parser.py::test_reconstruct_test_path PASSED
tests/test_span_parser.py::test_invocation_chain_no_self_loop PASSED
tests/test_span_parser.py::test_single_span_no_test_path PASSED
tests/test_span_parser.py::test_edge_list_contains_error_info PASSED

============================== 34 passed in 1.46s ==============================
```

### 11.2 Lancer un fichier de tests spécifique

```bash
# Tests Bloc A uniquement
python -m pytest tests/test_span_parser.py -v

# Tests Bloc B uniquement
python -m pytest tests/test_graph_builder.py -v

# Tests Écho-Dormant + Théorème uniquement
python -m pytest tests/test_echo_dormant.py -v
```

### 11.3 Lancer avec couverture de code

```bash
python -m pytest tests/ --cov=. --cov-report=term-missing
```

### 11.4 Critère de validation de la Phase 1

La Phase 1 est considérée **validée** quand :

- [ ] 34/34 tests unitaires passent
- [ ] `service_graph.json` contient au moins 10 noeuds et 15 arcs
- [ ] `service_scores.json` contient au moins 1 service Écho-Dormant
- [ ] `test_suite_T.json` contient au moins 100 cas de test
- [ ] `mr_catalog.yaml` contient au moins 20 relations MR
- [ ] Le log de `run_phase1.py` affiche `Théorème de Sécurité d'Exclusion : OK ✓`

---

## 12. Résolution des problèmes courants

### Problème 1 : ModuleNotFoundError lors de l'import

```
ModuleNotFoundError: No module named 'models'
```

Cause : le script est lancé depuis le mauvais répertoire.

```bash
# Toujours lancer depuis phase1/scripts/
cd ~/metabp-rts/phase1/scripts
python run_phase1.py --config ../config/system_config.yaml
```

### Problème 2 : Jaeger retourne 0 traces

```
Jaeger → service=ts-gateway-service | traces récupérées=0
```

Causes possibles et solutions :

```bash
# Cause 1 : trafic pas encore généré
python generate_traffic.py --config ../config/system_config.yaml

# Cause 2 : fenêtre temporelle trop courte
# Modifier system_config.yaml : lookback: "6h"

# Cause 3 : le service Jaeger suit un autre nom dans Train-Ticket
curl -s "http://localhost:16686/api/services" | python3 -m json.tool
# Copier le nom exact du service gateway et le mettre dans default_service
```

### Problème 3 : Peu de services dans le graphe G (< 5 noeuds)

Le trafic généré n'a pas touché assez de services.

```bash
# Augmenter le nombre de requêtes
python generate_traffic.py \
  --config ../config/system_config.yaml \
  --n-requests 1000

# Puis relancer la Phase 1
python run_phase1.py --config ../config/system_config.yaml
```

### Problème 4 : Aucun service Écho-Dormant détecté

Si tous les services ont `Θ_dormant < 0.40`, réduire le seuil temporairement
pour valider le pipeline, puis le restaurer :

```yaml
# Dans system_config.yaml, modifier temporairement :
echo_dormant:
  tau_dormant: 0.20    # seuil réduit pour validation
```

> Restaurer `tau_dormant: 0.40` après validation.

### Problème 5 : Erreur de permission Docker

```
Got permission denied while trying to connect to the Docker daemon
```

```bash
sudo usermod -aG docker $USER
newgrp docker
# Ou redémarrer la session
```

### Problème 6 : Manque de mémoire RAM

```
docker: Error response from daemon: OOM killer
```

```bash
# Arrêter les services non essentiels
cd ~/train-ticket
docker compose stop ts-admin-basic-info-service \
                     ts-news-service \
                     ts-avatar-service \
                     ts-voucher-service \
                     ts-ticket-office-service
```

---

## 13. Référence des commandes

### Commandes Docker Train-Ticket

```bash
# Démarrer tous les services
cd ~/train-ticket && docker compose up -d

# Arrêter tous les services
cd ~/train-ticket && docker compose down

# Voir les logs d'un service
docker compose logs ts-order-service -f

# Redémarrer un service
docker compose restart ts-payment-service

# Voir l'utilisation mémoire
docker stats --no-stream
```

### Commandes MetaBP-RTS Phase 1

```bash
# Activer l'environnement
source ~/metabp-rts/venv/bin/activate

# Générer le trafic (rapide)
cd ~/metabp-rts/phase1/scripts
python generate_traffic.py --config ../config/system_config.yaml --n-requests 200

# Générer le trafic (complet, recommandé)
python generate_traffic.py --config ../config/system_config.yaml

# Exécuter la Phase 1
python run_phase1.py --config ../config/system_config.yaml

# Lancer les tests
cd ~/metabp-rts/phase1 && python -m pytest tests/ -v

# Vérifier les artefacts
python3 -c "
import json, yaml
g = json.load(open('data/outputs/service_graph.json'))
s = json.load(open('data/outputs/service_scores.json'))
t = json.load(open('data/outputs/test_suite_T.json'))
m = yaml.safe_load(open('data/outputs/mr_catalog.yaml'))
print(f'G: {len(g[\"nodes\"])} noeuds | T: {len(t)} tests | MR: {len(m[\"mr_catalog\"])} relations')
dormants = [x for x in s if x['is_dormant']]
print(f'Services Écho-Dormants ({len(dormants)}) : {[x[\"service_name\"] for x in dormants]}')
"
```

### Interfaces web disponibles

| Interface | URL | Usage |
|---|---|---|
| Train-Ticket | `http://localhost:8080` | Application web (login, réservation) |
| Jaeger UI | `http://localhost:16686` | Visualisation des traces distribuées |

---

*NIKOUM Modeste Lorene — MetaBP-RTS Phase 1 — Université de Yaoundé I — 2025/2026*