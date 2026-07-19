#!/bin/bash
# Campagne 4 scénarios ΔS — collecte EN / Recall / Precision / F
set -o pipefail
BASE=~/Bureau/MEMOIRE-2026/metabp-rts/metabp-rts
OUT=$BASE/scenarios_results.csv
echo "scenario,delta_s,T_sel,EN,Recall,Precision,F,M" > $OUT

run_scenario () {
  local NAME="$1"; shift
  local DELTA="$@"
  echo ""
  echo "########## SCÉNARIO $NAME : ΔS = $DELTA ##########"

  cd $BASE/phase2/scripts
  python run_phase2.py --config ../config/phase2_config.yaml --delta-s $DELTA 2>&1 \
    | grep -E "Tier1=|Écho-Impact  :"

  cd $BASE/phase3/scripts
  python run_phase3.py --config ../config/phase3_config.yaml 2>&1 \
    | grep -E "Tier1 scinde|PathMR Tier1|T_sel final|EN \(nombre\)"

  cd $BASE/phase4/scripts
  local L=$(python run_phase4.py --config ../config/phase4_config.yaml --delta-s $DELTA 2>&1 \
    | grep -E "Recall\(T_sel\)")
  echo "$L"

  # extraire les chiffres pour le CSV
  cd $BASE
  python3 - "$NAME" "$DELTA" << 'PY'
import json, sys
name, delta = sys.argv[1], sys.argv[2]
sel = json.load(open('phase3/data/outputs/T_sel.json'))
M   = set(json.load(open('phase4/data/outputs/fault_revealing_tests.json')))
rpf = json.load(open('phase4/data/outputs/recall_t_sel.json'))
T   = json.load(open('phase1/data/outputs/test_suite_T.json'))
en  = round(100*(1-len(sel)/len(T)),2)
row = f"{name},{delta.replace(' ','+')},{len(sel)},{en},{rpf['recall']},{rpf['precision']},{rpf['f_measure']},{rpf['n_fault_revealing_total']}"
open('scenarios_results.csv','a').write(row+"\n")
print("  →", row)
PY
}

# ---- Adapter les noms selon service_scores.json ----
run_scenario "S1_feuille"       ts-station-service
run_scenario "S2_hub"           ts-order-service
run_scenario "S3_intermediaire" ts-basic-service
run_scenario "S4_multiple"      ts-station-service ts-order-service ts-contacts-service

echo ""
echo "########## RÉCAPITULATIF ##########"
column -t -s, $OUT
