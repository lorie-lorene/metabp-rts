"""
Partie C — Lien sélection RTS <-> détection métamorphique.
Démontre que T_sel (réduit) préserve la capacité de détecter une faute dans ΔS,
par rapport à T complet. Mapping : une MR "couvre" un service ; un chemin
"touche" ΔS si ΔS ∈ services(chemin).
"""
import json
from pathlib import Path

P = Path("/home/spring-shogun/Bureau/MEMOIRE-2026/metabp-rts/metabp-rts")
T_FULL = json.load(open(P/"phase2/data/outputs/selected_tests.json"))
T_SEL  = json.load(open(P/"phase3/data/outputs/T_sel.json"))

DELTA_S = "ts-station-service"     # service modifié (on a le proxy dessus)

# --- mapping MR -> service testé (tes 9 MR de l'étage 1) --------------------
MR_SERVICE = {
    "MR01_idem_stations":  "ts-station-service",
    "MR02_idem_trains":    "ts-train-service",
    "MR03_idem_consigns":  "ts-consign-service",
    "MR04_card_contacts":  "ts-contacts-service",
    "MR05_card_consigns":  "ts-consign-service",
    "MR06_auth_contacts":  "ts-contacts-service",
    "MR08_auth_consigns":  "ts-consign-service",
    "MR09_equiv_name_id":  "ts-station-service",
    "MR10_xsvc_contacts":  "ts-contacts-service",  # + admin-basic
}

def services_of(suite):
    """ensemble des services couverts par une suite de chemins."""
    s = set()
    for t in suite:
        s.update(t.get("services", []))
    return s

def paths_touching(suite, svc):
    return [t for t in suite if svc in t.get("services", [])]

# --- 1. couverture de services : T_sel vs T complet ------------------------
sv_full = services_of(T_FULL)
sv_sel  = services_of(T_SEL)
print(f"|T| complet      : {len(T_FULL)} chemins, {len(sv_full)} services couverts")
print(f"|T_sel| réduit   : {len(T_SEL)} chemins, {len(sv_sel)} services couverts")
print(f"réduction        : {round(100*(1-len(T_SEL)/len(T_FULL)),1)}% des chemins")
print(f"services perdus par la réduction : {sv_full - sv_sel or 'AUCUN'}")

# --- 2. chemins touchant ΔS ------------------------------------------------
tf = paths_touching(T_FULL, DELTA_S)
ts = paths_touching(T_SEL, DELTA_S)
print(f"\nΔS = {DELTA_S}")
print(f"chemins touchant ΔS dans T      : {len(tf)}")
print(f"chemins touchant ΔS dans T_sel  : {len(ts)}")

# --- 3. MR sélectionnées : celles dont le service est touché par T_sel ------
svc_in_tsel = services_of(T_SEL)
MR_sel = {mr:svc for mr,svc in MR_SERVICE.items() if svc in svc_in_tsel}
MR_delta = {mr:svc for mr,svc in MR_SERVICE.items() if svc == DELTA_S}
print(f"\nMR dont le service est couvert par T_sel : {len(MR_sel)}/{len(MR_SERVICE)}")
for mr,svc in MR_sel.items(): print(f"  {mr:22s} -> {svc}")
print(f"\nMR ciblant ΔS ({DELTA_S}) : {list(MR_delta)}")

# --- 4. conclusion de couverture -------------------------------------------
print("\n" + "="*66)
if DELTA_S in sv_sel:
    print(f"✅ ΔS est couvert par T_sel → la faute dans {DELTA_S} EST détectable")
    print(f"   par {len(MR_delta)} MR ({list(MR_delta)}) via la suite réduite.")
else:
    print(f"❌ ΔS n'est PAS couvert par T_sel → réduction trop agressive")
print("="*66)

json.dump({
    "delta_s": DELTA_S,
    "n_T": len(T_FULL), "n_T_sel": len(T_SEL),
    "services_T": len(sv_full), "services_T_sel": len(sv_sel),
    "services_lost": list(sv_full - sv_sel),
    "paths_touching_deltaS_T": len(tf), "paths_touching_deltaS_Tsel": len(ts),
    "MR_selected": MR_sel, "MR_targeting_deltaS": MR_delta,
}, open("partC_report.json","w"), indent=2, ensure_ascii=False)
print("rapport -> partC_report.json")
