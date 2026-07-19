"""
Baselines RTS comparees a MetaBP-RTS, sur les memes M par scenario.
  - Retest-All : tout T
  - Random-N   : |T_sel| tests au hasard, x30 repetitions
  - Firewall-0 : tests touchant DeltaS
  - Firewall-1 : tests touchant DeltaS ou un voisin direct dans G
Metriques : EN, Recall, Precision, F  (memes formules que MetaBP-RTS)
"""
import json, random, statistics
from pathlib import Path

random.seed(42)
BASE = Path.home()/"Bureau/MEMOIRE-2026/metabp-rts/metabp-rts"

T     = json.load(open(BASE/"phase1/data/outputs/test_suite_T.json"))
graph = json.load(open(BASE/"phase1/data/outputs/service_graph.json"))

# voisins directs dans G (source->target ET target->source : firewall = fermeture)
neigh = {}
for e in graph["links"]:
    neigh.setdefault(e["source"], set()).add(e["target"])
    neigh.setdefault(e["target"], set()).add(e["source"])

def tid(t): return t.get("test_id") or t.get("trace_id")
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
  "S1_station":  ["ts-station-service"],
  "S2_order":    ["ts-order-service"],
  "S3_basic":    ["ts-basic-service"],
  "S4_multiple": ["ts-station-service","ts-order-service","ts-contacts-service"],
}
# tailles de T_sel MetaBP-RTS par scenario (pour Random-N a taille egale)
NSEL = {"S1_station":1327, "S2_order":622, "S3_basic":226, "S4_multiple":1609}

allids = [tid(t) for t in T]
N = len(T)
rows = []

for name, delta in SCEN.items():
    M = set(json.load(open(BASE/f"data/baselines/M_par_scenario/M_{name}.json")))
    delta_set = set(delta)
    fw1_set = set(delta) | {n for d in delta for n in neigh.get(d, set())}

    # Retest-All
    allset = set(allids)
    R,P,F = rpf(allset, M)
    rows.append((name, "Retest-All", N, round(100*(1-N/N),1), R, P, F))

    # Firewall-0 : touchant DeltaS
    fw0 = {tid(t) for t in T if svcs(t) & delta_set}
    R,P,F = rpf(fw0, M)
    rows.append((name, "Firewall-0", len(fw0), round(100*(1-len(fw0)/N),1), R, P, F))

    # Firewall-1 : DeltaS + voisins directs
    fw1 = {tid(t) for t in T if svcs(t) & fw1_set}
    R,P,F = rpf(fw1, M)
    rows.append((name, "Firewall-1", len(fw1), round(100*(1-len(fw1)/N),1), R, P, F))

    # Random-N x30 (taille = T_sel MetaBP-RTS)
    k = min(NSEL[name], N)
    Rs, Ps, Fs = [], [], []
    for _ in range(30):
        sample = set(random.sample(allids, k))
        r,p,f = rpf(sample, M)
        Rs.append(r); Ps.append(p); Fs.append(f)
    rows.append((name, "Random-N(x30)", k,
                 round(100*(1-k/N),1),
                 f"{statistics.mean(Rs):.1f}±{statistics.pstdev(Rs):.1f}",
                 f"{statistics.mean(Ps):.1f}±{statistics.pstdev(Ps):.1f}",
                 f"{statistics.mean(Fs):.3f}"))

# affichage + CSV
out = BASE/"baselines_results.csv"
with open(out,"w") as f:
    f.write("scenario,technique,T_sel,EN,Recall,Precision,F\n")
    for r in rows:
        f.write(",".join(str(x) for x in r)+"\n")

print(f"{'scenario':<13}{'technique':<15}{'T_sel':>6}{'EN':>7}{'Recall':>14}{'Prec':>14}{'F':>8}")
print("-"*77)
for r in rows:
    print(f"{r[0]:<13}{r[1]:<15}{r[2]:>6}{str(r[3]):>7}{str(r[4]):>14}{str(r[5]):>14}{str(r[6]):>8}")
print(f"\nCSV -> {out}")
