# metabp-rts


#!/usr/bin/env bash
# =============================================================================
# MetaBP-RTS — Script de démarrage complet
# =============================================================================
# Usage : bash start_metabp.sh [--skip-traffic] [--traffic-n 20000]
#
# Ce script :
#   1. Démarre Train-Ticket + Jaeger
#   2. Configure MongoDB avec tous les alias DNS
#   3. Lance ts-ui-dashboard avec le nginx corrigé
#   4. Lance ts-ticketinfo-service
#   5. Redémarre tous les services Java
#   6. Génère du trafic (optionnel)
#   7. Lance la Phase 1 MetaBP-RTS
# =============================================================================

set -euo pipefail

# ── Couleurs ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

log()     { echo -e "${CYAN}[$(date +%H:%M:%S)]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERREUR]${NC} $*"; exit 1; }
step()    { echo -e "\n${BOLD}${BLUE}━━━ $* ━━━${NC}"; }

# ── Chemins ───────────────────────────────────────────────────────────────────
BASE_DIR="$HOME/Bureau/MEMOIRE-2026"
TT_DIR="$BASE_DIR/train-ticket-master"
PHASE1_DIR="$BASE_DIR/metabp-rts/metabp-rts/phase1"
VENV="$BASE_DIR/metabp-project/venv-metabp/bin/activate"
NETWORK="train-ticket-master_my-network"

# ── Arguments ─────────────────────────────────────────────────────────────────
SKIP_TRAFFIC=false
TRAFFIC_N=20000
TRAFFIC_WORKERS=5

for arg in "$@"; do
  case $arg in
    --skip-traffic)   SKIP_TRAFFIC=true ;;
    --traffic-n=*)    TRAFFIC_N="${arg#*=}" ;;
    --workers=*)      TRAFFIC_WORKERS="${arg#*=}" ;;
  esac
done

echo -e "${BOLD}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║         MetaBP-RTS — Phase 1 — Démarrage complet        ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo "  Train-Ticket : $TT_DIR"
echo "  Phase 1      : $PHASE1_DIR"
echo "  Trafic       : $([[ $SKIP_TRAFFIC == true ]] && echo 'désactivé' || echo "$TRAFFIC_N requêtes")"
echo ""

# ════════════════════════════════════════════════════════════════════════════
# ÉTAPE 1 — Vérifications préalables
# ════════════════════════════════════════════════════════════════════════════
step "ÉTAPE 1/7 — Vérifications préalables"

[[ -d "$TT_DIR" ]]     || error "Dossier train-ticket-master introuvable : $TT_DIR"
[[ -d "$PHASE1_DIR" ]] || error "Dossier phase1 introuvable : $PHASE1_DIR"
[[ -f "$VENV" ]]       || error "Venv introuvable : $VENV"
[[ -f "$TT_DIR/docker-compose.yml" ]]  || error "docker-compose.yml introuvable"
[[ -f "$TT_DIR/nginx.conf" ]]          || error "nginx.conf introuvable dans $TT_DIR"

command -v docker   >/dev/null 2>&1 || error "Docker non installé"
command -v python3  >/dev/null 2>&1 || error "Python3 non installé"

success "Toutes les vérifications passées"

# ════════════════════════════════════════════════════════════════════════════
# ÉTAPE 2 — Démarrage Train-Ticket
# ════════════════════════════════════════════════════════════════════════════
step "ÉTAPE 2/7 — Démarrage de Train-Ticket + Jaeger"

cd "$TT_DIR"

# Libérer le port 8080 si occupé
log "Libération du port 8080..."
sudo docker ps --format '{{.Names}}' | grep -v "train-ticket-master" | while read cname; do
  if sudo docker port "$cname" 2>/dev/null | grep -q "8080"; then
    warn "Port 8080 occupé par $cname — arrêt..."
    sudo docker stop "$cname" >/dev/null 2>&1 || true
  fi
done

# Démarrer tous les services
log "Démarrage de docker compose..."
sudo docker compose up -d 2>&1 | tail -5

# Recréer Jaeger avec les ports exposés
log "Recréation de Jaeger avec ports exposés..."
sudo docker compose up -d --force-recreate jaeger 2>&1 | tail -3

# Attendre le démarrage initial
log "Attente du démarrage Spring Boot (90 secondes)..."
sleep 90

UP=$(sudo docker compose ps 2>/dev/null | grep -c "Up" || echo "0")
log "Services Up : $UP"
[[ $UP -lt 50 ]] && warn "Moins de 50 services Up — certains services peuvent encore démarrer"

success "Train-Ticket lancé ($UP services Up)"

# ════════════════════════════════════════════════════════════════════════════
# ÉTAPE 3 — MongoDB avec alias DNS
# ════════════════════════════════════════════════════════════════════════════
step "ÉTAPE 3/7 — Configuration MongoDB"

# Vérifier si ts-mongo existe déjà
if sudo docker ps -a --format '{{.Names}}' | grep -q "^ts-mongo$"; then
  MONGO_STATUS=$(sudo docker inspect ts-mongo --format='{{.State.Status}}' 2>/dev/null)
  if [[ "$MONGO_STATUS" != "running" ]]; then
    log "Redémarrage de ts-mongo..."
    sudo docker start ts-mongo >/dev/null 2>&1 || true
  fi

  # Vérifier si déjà dans le bon réseau avec alias
  ALIASES=$(sudo docker inspect ts-mongo 2>/dev/null | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    nets = data[0]['NetworkSettings']['Networks']
    aliases = nets.get('$NETWORK', {}).get('Aliases') or []
    print(' '.join(aliases))
except: print('')
" 2>/dev/null)

  if echo "$ALIASES" | grep -q "ts-auth-mongo"; then
    success "ts-mongo déjà configuré avec les alias DNS"
  else
    log "Reconfiguration des alias DNS de ts-mongo..."
    sudo docker network disconnect "$NETWORK" ts-mongo 2>/dev/null || true
    sudo docker network connect \
      --alias ts-auth-mongo \
      --alias ts-user-mongo \
      --alias ts-order-mongo \
      --alias ts-order-other-mongo \
      --alias ts-route-mongo \
      --alias ts-contacts-mongo \
      --alias ts-config-mongo \
      --alias ts-station-mongo \
      --alias ts-train-mongo \
      --alias ts-travel-mongo \
      --alias ts-travel2-mongo \
      --alias ts-price-mongo \
      --alias ts-security-mongo \
      --alias ts-inside-payment-mongo \
      --alias ts-payment-mongo \
      --alias ts-rebook-mongo \
      --alias ts-assurance-mongo \
      --alias ts-consign-mongo \
      --alias ts-consign-price-mongo \
      --alias ts-news-mongo \
      "$NETWORK" ts-mongo
    success "Alias DNS configurés"
  fi
else
  log "Création du conteneur ts-mongo..."
  sudo docker run -d \
    --name ts-mongo \
    --network "$NETWORK" \
    --restart always \
    mongo:4.4 >/dev/null

  sleep 5

  log "Ajout des alias DNS..."
  sudo docker network disconnect "$NETWORK" ts-mongo 2>/dev/null || true
  sudo docker network connect \
    --alias ts-auth-mongo \
    --alias ts-user-mongo \
    --alias ts-order-mongo \
    --alias ts-order-other-mongo \
    --alias ts-route-mongo \
    --alias ts-contacts-mongo \
    --alias ts-config-mongo \
    --alias ts-station-mongo \
    --alias ts-train-mongo \
    --alias ts-travel-mongo \
    --alias ts-travel2-mongo \
    --alias ts-price-mongo \
    --alias ts-security-mongo \
    --alias ts-inside-payment-mongo \
    --alias ts-payment-mongo \
    --alias ts-rebook-mongo \
    --alias ts-assurance-mongo \
    --alias ts-consign-mongo \
    --alias ts-consign-price-mongo \
    --alias ts-news-mongo \
    "$NETWORK" ts-mongo
  success "ts-mongo créé et configuré"
fi

# ════════════════════════════════════════════════════════════════════════════
# ÉTAPE 4 — ts-ui-dashboard avec nginx corrigé
# ════════════════════════════════════════════════════════════════════════════
step "ÉTAPE 4/7 — Démarrage ts-ui-dashboard"

if sudo docker ps --format '{{.Names}}' | grep -q "ts-ui-dashboard"; then
  STATUS=$(sudo docker inspect train-ticket-master-ts-ui-dashboard-1 \
    --format='{{.State.Status}}' 2>/dev/null || echo "unknown")
  if [[ "$STATUS" == "running" ]]; then
    success "ts-ui-dashboard déjà en cours"
  else
    sudo docker rm -f train-ticket-master-ts-ui-dashboard-1 2>/dev/null || true
    STATUS="stopped"
  fi
fi

if [[ "${STATUS:-stopped}" != "running" ]]; then
  log "Démarrage de ts-ui-dashboard avec nginx corrigé..."
  sudo docker run -d \
    --name train-ticket-master-ts-ui-dashboard-1 \
    --network "$NETWORK" \
    -p 8080:8080 \
    --restart always \
    -v "$TT_DIR/nginx.conf:/usr/local/openresty/nginx/conf/nginx.conf:ro" \
    codewisdom/ts-ui-dashboard-with-jaeger:v1 >/dev/null
  sleep 5
  success "ts-ui-dashboard démarré"
fi

# ════════════════════════════════════════════════════════════════════════════
# ÉTAPE 5 — ts-ticketinfo-service
# ════════════════════════════════════════════════════════════════════════════
step "ÉTAPE 5/7 — Démarrage ts-ticketinfo-service"

if sudo docker ps -a --format '{{.Names}}' | grep -q "ts-ticketinfo-service-1"; then
  TINFO_STATUS=$(sudo docker inspect train-ticket-master-ts-ticketinfo-service-1 \
    --format='{{.State.Status}}' 2>/dev/null || echo "stopped")

  if [[ "$TINFO_STATUS" != "running" ]]; then
    sudo docker start train-ticket-master-ts-ticketinfo-service-1 >/dev/null 2>&1 || true
  fi

  # Vérifier l'alias DNS
  ALIASES=$(sudo docker inspect train-ticket-master-ts-ticketinfo-service-1 2>/dev/null | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    nets = data[0]['NetworkSettings']['Networks']
    aliases = nets.get('$NETWORK', {}).get('Aliases') or []
    print(' '.join(aliases))
except: print('')
" 2>/dev/null)

  if ! echo "$ALIASES" | grep -q "ts-ticketinfo-service"; then
    sudo docker network disconnect "$NETWORK" train-ticket-master-ts-ticketinfo-service-1 2>/dev/null || true
    sudo docker network connect \
      --alias ts-ticketinfo-service \
      "$NETWORK" \
      train-ticket-master-ts-ticketinfo-service-1 2>/dev/null || true
  fi
  success "ts-ticketinfo-service configuré"
else
  log "Création de ts-ticketinfo-service..."
  sudo docker run -d \
    --name train-ticket-master-ts-ticketinfo-service-1 \
    --network "$NETWORK" \
    --restart always \
    -p 15681:15681 \
    codewisdom/ts-ticketinfo-service-with-jaeger:v1 >/dev/null

  sleep 5

  sudo docker network disconnect "$NETWORK" \
    train-ticket-master-ts-ticketinfo-service-1 2>/dev/null || true
  sudo docker network connect \
    --alias ts-ticketinfo-service \
    "$NETWORK" \
    train-ticket-master-ts-ticketinfo-service-1
  success "ts-ticketinfo-service créé"
fi

# Redémarrer les services Java pour qu'ils se connectent à MongoDB
step "Redémarrage des services Java"
log "Redémarrage en cours (attendre 90 secondes)..."
cd "$TT_DIR"
sudo docker compose restart \
  ts-auth-service \
  ts-user-service \
  ts-order-service \
  ts-order-other-service \
  ts-travel-service \
  ts-travel2-service \
  ts-preserve-service \
  ts-preserve-other-service \
  ts-payment-service \
  ts-inside-payment-service \
  ts-cancel-service \
  ts-route-service \
  ts-train-service \
  ts-station-service \
  ts-seat-service \
  ts-security-service 2>&1 | tail -3

sleep 90

# Vérification Jaeger
JAEGER_OK=$(curl -s "http://localhost:16686/api/services" 2>/dev/null | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    svcs = [s for s in d.get('data', []) if s != 'jaeger-all-in-one']
    print(len(svcs))
except: print(0)
" 2>/dev/null || echo "0")

success "Jaeger accessible — $JAEGER_OK service(s) connu(s)"

# ════════════════════════════════════════════════════════════════════════════
# ÉTAPE 6 — Génération du trafic
# ════════════════════════════════════════════════════════════════════════════
step "ÉTAPE 6/7 — Génération du trafic"

if [[ "$SKIP_TRAFFIC" == "true" ]]; then
  warn "Génération de trafic ignorée (--skip-traffic)"
else
  log "Génération de $TRAFFIC_N requêtes avec $TRAFFIC_WORKERS workers..."
  source "$VENV"
  python3 "$PHASE1_DIR/scripts/generate_traffic_tt.py" \
    --n "$TRAFFIC_N" \
    --workers "$TRAFFIC_WORKERS" \
    --delay 50

  SPANS=$(curl -s "http://localhost:16686/api/services" 2>/dev/null | python3 -c "
import json, sys, urllib.request
try:
    data = json.load(sys.stdin)
    svcs = [s for s in data.get('data', []) if s != 'jaeger-all-in-one']
    total = 0
    for svc in svcs:
        url = f'http://localhost:16686/api/traces?service={svc}&limit=5000'
        with urllib.request.urlopen(url) as r:
            traces = json.loads(r.read()).get('data', [])
            total += sum(len(t['spans']) for t in traces)
    print(total)
except: print(0)
" 2>/dev/null || echo "0")
  success "Trafic généré — $SPANS spans capturés dans Jaeger"
fi

# ════════════════════════════════════════════════════════════════════════════
# ÉTAPE 7 — Exécution Phase 1
# ════════════════════════════════════════════════════════════════════════════
step "ÉTAPE 7/7 — Exécution Phase 1 MetaBP-RTS"

log "Activation du venv..."
source "$VENV"

log "Lancement de run_phase1.py..."
cd "$PHASE1_DIR/scripts"
python run_phase1.py --config ../config/system_config.yaml

echo ""
echo -e "${GREEN}${BOLD}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║              Phase 1 terminée avec succès !             ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo "  Artefacts : $PHASE1_DIR/data/outputs/"
echo "  Graphe    : $PHASE1_DIR/data/outputs/graph_visualization.html"
echo "  Jaeger    : http://localhost:16686"
echo "  Gateway   : http://localhost:8080"
echo ""
log "Pour ouvrir la visualisation :"
echo "  xdg-open $PHASE1_DIR/data/outputs/graph_visualization.html"