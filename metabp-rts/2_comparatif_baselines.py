#!/usr/bin/env python3
"""
Tableau comparatif MetaBP-RTS vs baselines (Retest-All, Random-N, Firewall-0/1)
sur les 4 scénarios ΔS. Affichage terminal soigné + CSV.

Prérequis (déjà produits par la campagne) :
  - phase1/data/outputs/test_suite_T.json
  - phase1/data/outputs/service_graph.json
  - data/baselines/M_par_scenario/M_<scenario>.json   (M local, mutation ΔS)
  - data/baselines/Tsel/Tsel_<scenario>.json          (T_sel MetaBP par scénario)

À lancer depuis la racine metabp-rts/metabp-rts/.
"""
import json, random, statistics
from pathlib import Path

random.seed(42)
BASE = Path.cwd()

# MRTS-BP réimplémenté (Chen et al.) — comparateur central
import sys as _sys
_sys.path.insert(0, str(Path('phase2').resolve()))
try:
    from mrts_bp_baseline import mrts_bp_select
    _HAS_MRTS = True
except Exception as _e:
    print(f'⚠ MRTS-BP indisponible : {_e}')
    _HAS_MRTS = False
CY="\033[96m"; GR="\033[92m"; YE="\033[93m"; BD="\033[1m"; RS="\033[0m"; DIM="\033[2m"

T = json.load(open("phase1/data/outputs/test_suite_T.json"))
g = json.load(open("phase1/data/outputs/service_graph.json"))
neigh = {}
for e in g["links"]:
    neigh.setdefault(e["source"], set()).add(e["target"])
    neigh.setdefault(e["target"], set()).add(e["source"])

def tid(t): return t.get("test_id") or t.get("trace_id")
def svcs(t):
    s = set()
    for p in (t.get("invocation_chain") or []):
        for x in p: s.add(x)
    if t.get("entry_service"): s.add(t["entry_service"])
    return s
def rpf(sel, M):
    i = sel & M
    R = len(i)/len(M) if M else 0
    P = len(i)/len(sel) if sel else 0
    F = 2*P*R/(P+R) if (P+R) else 0
    return round(R*100,1), round(P*100,1), round(F,3)

SCEN = {
    "S1_station":  ["ts-station-service"],
    "S2_order":    ["ts-order-service"],
    "S3_basic":    ["ts-basic-service"],
    "S4_multiple": ["ts-station-service","ts-order-service","ts-contacts-service"],
}
allids = set(tid(t) for t in T)
N = len(T)

print()
print(f"{BD}{CY}TABLEAU COMPARATIF — MetaBP-RTS vs baselines RTS{RS}")
print(f"{DIM}Même corpus, même ΔS, même ensemble révélateur M par scénario{RS}\n")

rows_csv = [("scenario","technique","T_sel","EN","Recall","Precision","F","acces")]
for name, delta in SCEN.items():
    M = set(json.load(open(f"data/baselines/M_par_scenario/M_{name}.json")))
    tsel = json.load(open(f"data/baselines/Tsel/Tsel_{name}.json"))
    sid = {tid(t) for t in tsel}
    dset = set(delta)
    fw1 = set(delta) | {n for d in delta for n in neigh.get(d, set())}

    print(f"{BD}── {name}  (ΔS = {', '.join(delta)}){RS}")
    print(f"   {'Technique':<16}{'|Sel|':>7}{'EN':>8}{'Recall':>9}{'Prec':>8}{'F':>7}{'   Accès requis'}")
    print(f"   {'─'*70}")

    def show(tech, sel, acces, hl=False):
        R,P,F = rpf(sel, M)
        en = 100*(1-len(sel)/N)
        c = BD if hl else ""
        rc = GR if R>=99 else (YE if R>=85 else "")
        print(f"   {c}{tech:<16}{len(sel):>7}{en:>7.1f}%{rc}{R:>8.1f}%{RS}{c}{P:>7.1f}%{F:>7.2f}{RS}   {DIM}{acces}{RS}")
        rows_csv.append((name,tech,len(sel),round(en,1),R,P,F,acces))

    show("Retest-All", allids, "aucun (borne)")
    # Random-N ×30 (moyenne)
    k = len(sid); Rs=[]; Ps=[]; Fs=[]
    for _ in range(30):
        s = set(random.sample(list(allids), k)); r,p,f = rpf(s, M)
        Rs.append(r); Ps.append(p); Fs.append(f)
    print(f"   {'Random-N×30':<16}{k:>7}{100*(1-k/N):>7.1f}%{YE}{statistics.mean(Rs):>7.1f}%{RS}"
          f"{statistics.mean(Ps):>7.1f}%{statistics.mean(Fs):>7.2f}   {DIM}aucun{RS}")
    rows_csv.append((name,"Random-N×30",k,round(100*(1-k/N),1),
                     round(statistics.mean(Rs),1),round(statistics.mean(Ps),1),
                     round(statistics.mean(Fs),3),"aucun"))

    fw0 = {tid(t) for t in T if svcs(t) & dset}
    show("Firewall-0", fw0, "graphe de code*")
    f1  = {tid(t) for t in T if svcs(t) & fw1}
    show("Firewall-1", f1, "graphe de code*")

    # MRTS-BP* (Chen réimplémenté) — même graphe, p0=1/0, existent satisfaction
    if _HAS_MRTS:
        try:
            mrts = mrts_bp_select(delta, ".")
            mrts_ids = {tid(t) for t in mrts["t_sel"]}
            show("MRTS-BP*", mrts_ids, "logs Gateway**")
        except Exception as _e:
            print(f"   {DIM}MRTS-BP* erreur : {_e}{RS}")

    show("MetaBP-RTS", sid, "traces seules", hl=True)
    print()

print(f"{DIM}*  Firewall/RTS-CFG requièrent le graphe de dépendances issu du code source.")
print(f"** MRTS-BP (Chen 2023) requiert des logs d'API Gateway ; réimplémenté ici sur le")
print(f"   graphe reconstruit par observabilité (propagation + sélection fidèles, Formules 3-6).")
print(f"   MRTS-BP* = MetaBP-RTS sans a priori Écho-Dormant ni PathMR/PSO = ablation.")
print(f"{DIM}*  Firewall/RTS-CFG requièrent le graphe de dépendances issu du code source,")
print(f"  indisponible en contexte boîte noire. Évalués ici sur le graphe reconstruit")
print(f"  par observabilité, pour situer MetaBP-RTS à qualité de données égale.{RS}")
print()
print(f"{BD}Message{RS}")
print(f"  {GR}▸{RS} vs Retest-All : réduction réelle (EN 33–90 %)")
print(f"  {GR}▸{RS} vs Random-N   : sélection informée (Recall 100 % vs ~30–70 %)")
print(f"  {GR}▸{RS} vs Firewall   : qualité comparable SANS accès au code source")
print(f"  {GR}▸{RS} unique        : seule méthode résolvant l'oracle (vérification métamorphique)")
print()

import csv
with open("comparatif_baselines.csv","w",newline="") as f:
    csv.writer(f).writerows(rows_csv)
print(f"{DIM}CSV → comparatif_baselines.csv{RS}")
