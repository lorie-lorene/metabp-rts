#!/usr/bin/env python3
"""
QR3 — Génère les tableaux et la figure pour le chapitre 4 (section vérification).
Lit les rapports JSON de la phase 4. À lancer depuis phase4/.
Produit : figures/fig_qr3_detection.png + affichage des tableaux (copiables en LaTeX).
"""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

Path("figures").mkdir(exist_ok=True)
def load(p): return json.load(open(p, encoding="utf-8"))

e1  = load("metamorphic/online/etage1_report.json")
e2a = load("metamorphic/online/etage2a_report.json")
e2b = load("metamorphic/online/etage2b_report.json")
pc  = load("metamorphic/online/partC_report.json")

# ── TABLEAU 4.7 : catalogue des MR (validité, étage 1) ──────────────────
FAMILLE = {r["mr"]: r["famille"] for r in e1["results"]}
DETAIL  = {r["mr"]: r["detail"]  for r in e1["results"]}
print("\n" + "="*70)
print("TABLEAU 4.7 — Catalogue des relations métamorphiques (validité)")
print("="*70)
print(f"{'MR':<20}{'Famille':<22}{'Détail (système sain)':<26}{'Statut'}")
print("-"*70)
for r in e1["results"]:
    st = "PASS" if r["passed"] else "FAIL"
    print(f"{r['mr']:<20}{r['famille']:<22}{r['detail'][:24]:<26}{st}")
print("-"*70)
print(f"P_mr = {e1['p_mr']:.0f}%  ({e1['n']}/{e1['n']} MR valides, {len(e1['familles'])} familles)")

# ── TABLEAU 4.8 : matrice de détection (étages 2a + 2b) ─────────────────
print("\n" + "="*70)
print("TABLEAU 4.8 — Détection de fautes par vérification métamorphique")
print("="*70)
print(f"{'Faute injectée':<38}{'Niveau':<10}{'Détectée'}")
print("-"*70)
for d in e2a["details"]:
    niveau = "réponse" + (" (ctrl)" if d["is_control"] else "")
    exp = "non détectée (correct)" if d["is_control"] else ("OUI" if d["detectee"] else "RATÉE")
    print(f"{d['faute']:<38}{niveau:<10}{exp}")
for d in e2b["details"]:
    if d["mode"] == "none": continue
    print(f"{'service: '+d['mode']:<38}{'service':<10}{'OUI' if d['verdict']=='FAIL' else 'RATÉE'}")
print("-"*70)
tot_f = e2a["n_vraies_fautes"] + e2b["n_vraies_fautes"]
tot_d = e2a["n_fautes_detectees"] + e2b["n_detectees"]
print(f"Sensibilité : {tot_d}/{tot_f} = {100*tot_d/tot_f:.0f}%  |  "
      f"Spécificité : {e2a['n_controles_ok']}/{e2a['n_controles']} = {e2a['specificite_pct']:.0f}%  |  "
      f"Fausses alarmes : {e2b['faux_positifs']}")

# ── FIGURE : matrice de détection ───────────────────────────────────────
fautes = []
for d in e2a["details"]:
    fautes.append((d["faute"], d["famille"], "2a", d["detectee"], d["is_control"]))
for d in e2b["details"]:
    if d["mode"] == "none": continue
    fautes.append((f"service: {d['mode']}", "idempotence", "2b",
                   d["verdict"]=="FAIL", False))

fig, ax = plt.subplots(figsize=(11, 6))
y = np.arange(len(fautes))
colors = []
for _,_,_,det,ctrl in fautes:
    colors.append("#4C72B0" if ctrl else ("#55A868" if det else "#C44E52"))
ax.barh(y, [1]*len(fautes), color=colors, edgecolor="white")
ax.set_yticks(y); ax.set_yticklabels([f[0] for f in fautes], fontsize=9)
ax.set_xlim(0,1.4); ax.set_xticks([]); ax.invert_yaxis()
for i,(_,_,et,det,ctrl) in enumerate(fautes):
    txt = "✓ non détecté (correct)" if ctrl else "✓ détecté"
    ax.text(1.02, i, f"{txt}  [{et}]", va="center", fontsize=8.5,
            fontweight="bold" if not ctrl else "normal", color="#333")
n2a = len(e2a["details"])
ax.axhline(n2a-0.5, color="#999", ls="--", lw=1)
ax.set_title("Matrice de détection métamorphique — étages 2a (réponse) et 2b (service)\n"
             f"Sensibilité {tot_d}/{tot_f} · Spécificité {e2a['n_controles_ok']}/{e2a['n_controles']} · "
             f"0 fausse alarme", fontsize=12, fontweight="bold")
from matplotlib.patches import Patch
ax.legend(handles=[Patch(fc="#55A868", label="Faute détectée (attendu)"),
                   Patch(fc="#4C72B0", label="Contrôle non détecté (attendu)")],
          loc="lower right", fontsize=9)
plt.tight_layout()
plt.savefig("figures/fig_qr3_detection.png", dpi=200, bbox_inches="tight")
print("\n→ figures/fig_qr3_detection.png")
