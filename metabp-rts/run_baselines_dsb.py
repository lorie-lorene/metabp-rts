#!/usr/bin/env python3
"""
Baselines RTS comparées à MetaBP-RTS sur DeathStarBench hotelReservation.

Modèle de faute : M(ΔS) = tests exerçant ΔS (définition de sûreté RTS standard).
  Faute d'un catalogue métamorphique instrumenté pour les services DSB, M est
  défini structurellement : un test peut détecter une régression dans ΔS seulement
  s'il exécute ΔS. C'est la définition de référence du "modèle de faute idéal" en RTS.
  → À documenter comme différence méthodologique avec Train-Ticket (mutation réelle).

Techniques :
  - Retest-All : tout T (borne)
  - Firewall-0 : tests touchant ΔS   (= M par construction → optimal ici)
  - Firewall-1 : tests touchant ΔS ou voisin direct dans G
  - Random-N   : |T_sel| tests au hasard ×30
  - MetaBP-RTS : T_sel réel (phase 3)

Métriques : EN, Recall, Precision, F (mêmes formules que Train-Ticket).
"""
import json, random, statistics
from pathlib import Path

random.seed(42)
BASE = Path.home()/"Bureau/MEMOIRE-2026/metabp-rts/metabp-rts"

T     = json.load(open(BASE/"phase1/data/outputs/test_suite_T.json"))
graph = json.load(open(BASE/"phase1/data/outputs/service_graph.json"))

neigh = {}
for e in graph["links"]:
    neigh.setdefault(e["source"], set()).add(e["target"])
    neigh.setdefault(e["target"], set()).add(e["source"])

def tid(t):
    if isinstance(t, str): return t
    return t.get("test_id") or t.get("trace_id")
def svcs(t):
    s = set()
    for pair in (t.get("invocation_chain") or []):
        for x in pair: s.add(x)
    if t.get("entry_service"): s.add(t["entry_service"])
    return s
def rpf(sel_ids, M):
    inter = sel_ids & M
    R = len(inter)/len(M) if M else 0
    P = len(inter)/len(sel_ids) if sel_ids else 0
    F = 2*P*R/(P+R) if (P+R)>0 else 0
    return round(R*100,2), round(P*100,2), round(F,4)

SCEN = {
    "D1_recommendation": ["recommendation"],
    "D2_user":           ["user"],
    "D3_search":         ["search"],
    "D4_profile":        ["profile"],
}

allids = [tid(t) for t in T]
N = len(T)
rows = []

for name, delta in SCEN.items():
    delta_set = set(delta)
    # M(ΔS) = tests touchant ΔS
    M = {tid(t) for t in T if svcs(t) & delta_set}

    # MetaBP-RTS : T_sel réel
    tsel = json.load(open(BASE/f"data/dsb/Tsel_{delta[0]}.json"))
    tsel_ids = {tid(t) for t in tsel}
    R,P,F = rpf(tsel_ids, M)
    EN = round(100*(1-len(tsel_ids)/N),1)
    rows.append((name, "MetaBP-RTS", len(tsel_ids), EN, R, P, F, "traces"))

    # Retest-All
    R,P,F = rpf(set(allids), M)
    rows.append((name, "Retest-All", N, 0.0, R, P, F, "aucun"))

    # Firewall-0 : touchant ΔS (= M)
    fw0 = {tid(t) for t in T if svcs(t) & delta_set}
    R,P,F = rpf(fw0, M)
    rows.append((name, "Firewall-0", len(fw0), round(100*(1-len(fw0)/N),1), R, P, F, "code"))

    # Firewall-1 : ΔS + voisins directs
    fw1set = set(delta) | {n for d in delta for n in neigh.get(d, set())}
    fw1 = {tid(t) for t in T if svcs(t) & fw1set}
    R,P,F = rpf(fw1, M)
    rows.append((name, "Firewall-1", len(fw1), round(100*(1-len(fw1)/N),1), R, P, F, "code"))

    # Random-N ×30 (taille = T_sel MetaBP-RTS)
    k = min(len(tsel_ids), N)
    Rs, Ps, Fs = [], [], []
    for _ in range(30):
        sample = set(random.sample(allids, k))
        r,p,f = rpf(sample, M)
        Rs.append(r); Ps.append(p); Fs.append(f)
    rows.append((name, "Random-N(x30)", k, round(100*(1-k/N),1),
                 f"{statistics.mean(Rs):.1f}±{statistics.pstdev(Rs):.1f}",
                 f"{statistics.mean(Ps):.1f}±{statistics.pstdev(Ps):.1f}",
                 f"{statistics.mean(Fs):.3f}", "aucun"))

# affichage + CSV
out = BASE/"baselines_dsb_results.csv"
with open(out,"w") as f:
    f.write("scenario,technique,T_sel,EN,Recall,Precision,F,acces\n")
    for r in rows:
        f.write(",".join(str(x) for x in r)+"\n")

print(f"{'scénario':<20}{'technique':<15}{'T_sel':>6}{'EN':>7}{'Recall':>14}{'Prec':>14}{'F':>8}{'Accès':>8}")
print("-"*92)
prev = None
for r in rows:
    if prev and prev != r[0]: print()
    prev = r[0]
    print(f"{r[0]:<20}{r[1]:<15}{r[2]:>6}{str(r[3]):>7}{str(r[4]):>14}{str(r[5]):>14}{str(r[6]):>8}{r[7]:>8}")
print(f"\nCSV → {out}")
print("\nNote : M(ΔS) = tests exerçant ΔS. Firewall-0 = M par construction (optimal).")
print("MetaBP-RTS : Recall 100% attendu, Precision moindre (garde Écho-Dormants),")
print("mais SANS accès au code (traces seules) + oracle métamorphique en plus.")
