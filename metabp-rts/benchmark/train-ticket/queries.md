# Cloner le dépôt
cd ~/Bureau/MEMOIRE-2026
git clone https://github.com/FudanSELab/train-ticket-auto-query.git
cd train-ticket-auto-query

# Installer les dépendances (requests probablement)
pip install requests --break-system-packages

# Exécuter tous les scénarios
python3 << 'EOF'
import logging
from queries import Query
from scenarios import *

logging.basicConfig(level=logging.INFO)

url = "http://localhost:8080"
q = Query(url)

if not q.login():
    logging.fatal("Login failed")
    exit(1)

print("Login OK — exécution des scénarios...")

# Exécuter chaque scénario plusieurs fois pour générer
# suffisamment de traces diversifiées
for i in range(50):
    try:
        query_and_preserve(q)
        query_and_cancel(q)
        query_order_and_pay(q)
        query_and_rebook(q)
        query_and_collect_ticket(q)
        query_and_enter_station(q)
        query_and_put_consign(q)
        query_food(q)
    except Exception as e:
        logging.warning(f"Itération {i}: {e}")
    
    if i % 10 == 0:
        print(f"  Itération {i}/50")

print("Terminé — vérifier Jaeger")
EOF