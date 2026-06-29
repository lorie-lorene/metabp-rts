"""
compare_pathmr.py
Compare le pouvoir discriminant des deux catalogues POUR PathMR,
sans relancer tout le pipeline. Mesure ce que PathMR voit vraiment :
la repartition service -> ensemble d'identifiants de MR.
"""
import yaml
from collections import defaultdict

OPENAPI_BAK = "/home/spring-shogun/Bureau/MEMOIRE-2026/metabp-rts/metabp-rts/phase1/data/outputs/mr_catalog.yaml.openapi.bak"
TRACES      = "/home/spring-shogun/Bureau/MEMOIRE-2026/metabp-rts/metabp-rts/phase4/latence/mr_full.yaml"
# Si pas de .bak, on utilisera le catalogue actuel comme openapi
import os
if not os.path.exists(OPENAPI_BAK):
    OPENAPI_BAK = "/home/spring-shogun/Bureau/MEMOIRE-2026/metabp-rts/metabp-rts/phase1/data/outputs/mr_catalog.yaml"

def load(path):
    with open(path, encoding="utf-8") as f:
        cat = yaml.safe_load(f) or {}
    s2m = defaultdict(set)
    for mr in cat.get("mr_catalog", []):
        svc = mr.get("service")
        mid = mr.get("id")
        if svc:
            s2m[svc].add(mid)
    return s2m

def analyze(name, s2m):
    print(f"\n===== {name} =====")
    print(f"Services couverts          : {len(s2m)}")
    total_mr = sum(len(v) for v in s2m.values())
    print(f"Total MR (ids)             : {total_mr}")
    # Pouvoir discriminant : combien de 'mr_set' DISTINCTS par service ?
    distinct_sets = set(frozenset(v) for v in s2m.values())
    print(f"mr_set distincts (/service): {len(distinct_sets)} sur {len(s2m)} services")
    # Si tous les services ont le meme mr_set -> 1 seul set distinct -> aucun pouvoir discriminant
    if len(s2m):
        ratio = len(distinct_sets) / len(s2m)
        print(f"Ratio discriminant         : {ratio:.2%}  (100% = chaque service a un set unique)")
    # Echantillon
    print("Exemples service -> nb MR  :")
    for svc in list(s2m)[:6]:
        print(f"    {svc:34s} {len(s2m[svc])} MR  {sorted(s2m[svc])[:3]}")

oa = load(OPENAPI_BAK)
tr = load(TRACES)
analyze("CATALOGUE OPENAPI", oa)
analyze("CATALOGUE TRACES", tr)

# Test cle : sur les services REELLEMENT traces, lequel discrimine le mieux ?
common = set(oa) & set(tr)
print(f"\n===== POUVOIR DISCRIMINANT SUR LES {len(common)} SERVICES COMMUNS =====")
for name, s2m in (("OpenAPI", oa), ("Traces", tr)):
    sub = {s: s2m[s] for s in common}
    distinct = set(frozenset(v) for v in sub.values())
    print(f"  {name:8s}: {len(distinct)} mr_set distincts sur {len(common)} services "
          f"({len(distinct)/max(len(common),1):.0%} discriminant)")
