"""
Partie C — La selection RTS preserve-t-elle la detection metamorphique ?
Principe : une MR est APPLICABLE a une suite si son endpoint y est present.
On compare MR_applicables(T) vs MR_applicables(T_sel), puis on verifie que
la faute injectee dans DeltaS est detectee via T_sel.
"""
import json
from pathlib import Path
from collections import Counter

P = Path("/home/spring-shogun/Bureau/MEMOIRE-2026/metabp-rts/metabp-rts")
T     = json.load(open(P/"phase1/data/outputs/test_suite_T.json"))
T_SEL = json.load(open(P/"phase3/data/outputs/T_sel.json"))
DELTA_S = "ts-station-service"

# --- catalogue MR (etage 1) : MR -> (endpoint, service) --------------------
MR = {
 "MR01_idem_stations":  ("/api/v1/stationservice/stations",        "ts-station-service"),
 "MR09_equiv_name_id":  ("/api/v1/stationservice/stations/idlist", "ts-station-service"),
 "MR02_idem_trains":    ("/api/v1/trainservice/trains",            "ts-train-service"),
 "MR03_idem_consigns":  ("/api/v1/consignservice/consigns/account","ts-consign-service"),
 "MR05_card_consigns":  ("/api/v1/consignservice/consigns/account","ts-consign-service"),
 "MR04_card_contacts":  ("/api/v1/contactservice/contacts/account", "ts-contacts-service"),
 "MR06_auth_contacts":  ("/api/v1/contactservice/contacts/account", "ts-contacts-service"),
 "MR08_auth_consigns":  ("/api/v1/consignservice/consigns/account","ts-consign-service"),
 "MR10_xsvc_contacts":  ("/api/v1/adminbasicservice/adminbasic/contacts","ts-admin-basic-info-service"),
}
# MR qui detectent une faute dans DeltaS (verifie a l'etage 2b : drop_one/corrupt_id)
MR_DETECT_DELTA = ["MR01_idem_stations", "MR09_equiv_name_id"]

def endpoints(suite):
    return {t["endpoint"] for t in suite if t.get("endpoint")}

def applicable(suite):
    eps = endpoints(suite)
    return {m for m,(ep,_) in MR.items() if any(e.startswith(ep) for e in eps)}

ep_T, ep_S = endpoints(T), endpoints(T_SEL)
mr_T, mr_S = applicable(T), applicable(T_SEL)

print("="*70)
print(f"|T|     = {len(T):5d} tests | {len(ep_T):2d} endpoints distincts | {len(mr_T)} MR applicables")
print(f"|T_sel| = {len(T_SEL):5d} tests | {len(ep_S):2d} endpoints distincts | {len(mr_S)} MR applicables")
print(f"reduction (EN) = {100*(1-len(T_SEL)/len(T)):.1f}%")
print("="*70)

lost = mr_T - mr_S
print(f"\nMR PERDUES par la reduction : {sorted(lost) if lost else 'AUCUNE'}")
print(f"MR conservees : {len(mr_S)}/{len(mr_T)} ({100*len(mr_S)/max(len(mr_T),1):.0f}%)")

print(f"\n--- Scenario : faute injectee dans {DELTA_S} ---")
print(f"MR capables de detecter cette faute (etage 2b) : {MR_DETECT_DELTA}")
kept = [m for m in MR_DETECT_DELTA if m in mr_S]
print(f"  -> presentes dans T_sel : {kept}")
ok = len(kept) == len(MR_DETECT_DELTA)
print()
print("="*70)
if ok:
    print(f"[OK] DETECTION PRESERVEE : T_sel ({len(T_SEL)} tests, -{100*(1-len(T_SEL)/len(T)):.0f}%)")
    print(f"     conserve 100% des MR capables de detecter la faute dans {DELTA_S}.")
    print("     => La reduction n'a PAS degrade la capacite de detection.")
else:
    print(f"[KO] DETECTION DEGRADEE : MR manquantes {set(MR_DETECT_DELTA)-set(kept)}")
print("="*70)

json.dump({
  "delta_s": DELTA_S, "n_T": len(T), "n_T_sel": len(T_SEL),
  "EN_pct": round(100*(1-len(T_SEL)/len(T)),2),
  "endpoints_T": len(ep_T), "endpoints_T_sel": len(ep_S),
  "MR_applicables_T": sorted(mr_T), "MR_applicables_T_sel": sorted(mr_S),
  "MR_perdues": sorted(lost),
  "MR_detectant_deltaS": MR_DETECT_DELTA,
  "MR_detectant_deltaS_dans_T_sel": kept,
  "detection_preservee": ok,
}, open("partC_report.json","w"), indent=2, ensure_ascii=False)
print("rapport -> partC_report.json")
