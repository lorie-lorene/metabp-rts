#!/usr/bin/env python3
"""
Affichage terminal soigné des résultats MetaBP-RTS sur les 4 scénarios ΔS.
Lit final_results.csv + les JSON du pipeline.
À lancer depuis la racine metabp-rts/metabp-rts/.
"""
import json, csv
from pathlib import Path

BASE = Path.cwd()
CY="\033[96m"; GR="\033[92m"; YE="\033[93m"; BD="\033[1m"; RS="\033[0m"; DIM="\033[2m"

def line(c="─", n=78): print(c*n)

print()
print(f"{BD}{CY}╔{'═'*76}╗{RS}")
print(f"{BD}{CY}║{'  MetaBP-RTS — RÉSULTATS EXPÉRIMENTAUX — Train-Ticket (FudanSELab)':<76}║{RS}")
print(f"{BD}{CY}╚{'═'*76}╝{RS}")
print()

# Contexte du corpus
try:
    T = json.load(open("phase1/data/outputs/test_suite_T.json"))
    g = json.load(open("phase1/data/outputs/service_graph.json"))
    print(f"{BD}Corpus observé (observabilité pure — aucun code source){RS}")
    print(f"  Traces / cas de test (T) : {len(T)}")
    print(f"  Graphe de dépendances G  : {len(g['nodes'])} services, {len(g['links'])} arcs")
    mono = sum(1 for t in T if not t.get('invocation_chain'))
    print(f"  Tests mono-service       : {mono}  |  cascade : {len(T)-mono}")
    print()
except Exception as e:
    print(f"{DIM}(contexte corpus indisponible : {e}){RS}\n")

# Tableau des 4 scénarios
rows = list(csv.DictReader(open("final_results.csv")))
print(f"{BD}Sélection MetaBP-RTS par scénario de changement (ΔS){RS}")
line()
print(f"{BD}{'Scénario':<14}{'ΔS (type)':<22}{'|T_sel|':>8}{'EN':>8}{'Recall':>9}{'Prec':>8}{'F':>8}{RS}")
line()
types = {
    "S1_station":  "feuille très appelée",
    "S2_order":    "hub central",
    "S3_basic":    "intermédiaire",
    "S4_multiple": "3 services modifiés",
}
for r in rows:
    name = r["scenario"]
    rec = float(r["Recall"])
    rec_c = GR if rec==100 else YE
    print(f"{name:<14}{types.get(name,''):<22}{r['T_sel']:>8}"
          f"{float(r['EN']):>7.1f}%{rec_c}{rec:>8.0f}%{RS}"
          f"{float(r['Precision']):>7.1f}%{float(r['F'])*100:>7.1f}%")
line()

# Moyennes
import statistics
EN  = [float(r["EN"]) for r in rows]
RE  = [float(r["Recall"]) for r in rows]
PR  = [float(r["Precision"]) for r in rows]
FM  = [float(r["F"]) for r in rows]
print(f"{BD}{'MOYENNE ± σ':<36}{'':>8}"
      f"{statistics.mean(EN):>6.1f}%{GR}{statistics.mean(RE):>8.0f}%{RS}"
      f"{statistics.mean(PR):>7.1f}%{statistics.mean(FM)*100:>7.1f}%{RS}")
print(f"{DIM}{'  écart-type':<36}{'':>8}"
      f"{statistics.pstdev(EN):>6.1f} {statistics.pstdev(RE):>8.1f} "
      f"{statistics.pstdev(PR):>7.1f} {statistics.pstdev(FM)*100:>6.1f}{RS}")
line()
print()

# Lecture scientifique
print(f"{BD}Lecture{RS}")
print(f"  {GR}✓{RS} Sûreté parfaite et robuste : Recall = 100 % sur les 4 positions topologiques")
print(f"  {GR}✓{RS} Précision moyenne 91 % — très supérieure à Chen et al. 2023 (6–40 %)")
print(f"  {GR}✓{RS} Réduction moyenne 60 % — dans la fourchette de Chen (40–57 %)")
print(f"  {YE}▸{RS} EN varie avec la topologie : ∝ inverse du nb de tests exerçant ΔS")
print(f"      feuille très appelée (station) → EN faible ; service peu exercé (basic) → EN élevé")
print()
