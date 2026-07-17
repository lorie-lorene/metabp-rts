#!/bin/bash
# Run complet MetaBP-RTS — Train-Ticket — journalisé
set -o pipefail
BASE=~/Bureau/MEMOIRE-2026/metabp-rts/metabp-rts
LOG=$BASE/run_$(date +%Y%m%d_%H%M%S).log
DELTA_S="ts-station-service ts-admin-basic-info-service  ts-contacts-service ts-order-other-service "

echo "=== RUN COMPLET MetaBP-RTS — $(date) ===" | tee $LOG
echo "ΔS = $DELTA_S" | tee -a $LOG

echo -e "\n\n########## PHASE 1 : Observation → G, T, scores, MR ##########" | tee -a $LOG
cd $BASE/phase1/scripts && python run_phase1.py --config ../config/system_config.yaml 2>&1 | tee -a $LOG

echo -e "\n\n########## PHASE 2 : BP → CIT, tiering ##########" | tee -a $LOG
cd $BASE/phase2/scripts && python run_phase2.py --config ../config/phase2_config.yaml --delta-s $DELTA_S 2>&1 | tee -a $LOG

echo -e "\n\n########## PHASE 3 : MRPS + PSO → T_sel ##########" | tee -a $LOG
cd $BASE/phase3/scripts && python run_phase3.py --config ../config/phase3_config.yaml 2>&1 | tee -a $LOG

echo -e "\n\n########## PHASE 4 : mutation + vérification MR ##########" | tee -a $LOG
cd $BASE/phase4/scripts && python run_phase4.py --config ../config/phase4_config.yaml 2>&1 | tee -a $LOG

echo -e "\n\n########## ÉTAGE 1 : catalogue MR online (système sain) ##########" | tee -a $LOG
cd $BASE/phase4/metamorphic/online && python run_etage1.py 2>&1 | tee -a $LOG

echo -e "\n\n########## ÉTAGE 2a : détection (fautes niveau réponse) ##########" | tee -a $LOG
python run_etage2.py 2>&1 | tee -a $LOG

echo -e "\n\n########## ÉTAGE 2b : détection (faute niveau service, proxy) ##########" | tee -a $LOG
python run_etage2b.py 2>&1 | tee -a $LOG

echo -e "\n\n########## PARTIE C : sélection ↔ détection ##########" | tee -a $LOG
python run_partC.py 2>&1 | tee -a $LOG

echo -e "\n\n=== FIN — journal : $LOG ===" | tee -a $LOG
