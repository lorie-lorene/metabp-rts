#!/usr/bin/env python3
"""
Génère les figures publiables du chapitre 4 (style barres groupées, façon Chen Fig.9).
Lit final_results.csv et comparatif_baselines.csv.
Produit des PNG haute résolution dans figures/.

À lancer depuis la racine metabp-rts/metabp-rts/ APRÈS les scripts 1 et 2.
"""
import csv
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

Path("figures").mkdir(exist_ok=True)

PALETTE = {"EN":"#4C72B0", "Recall":"#55A868", "Precision":"#C44E52", "F":"#8172B3"}

# ─────────────────────────────────────────────────────────────
# FIGURE 1 : MetaBP-RTS — métriques par scénario (barres groupées)
# ─────────────────────────────────────────────────────────────
rows = list(csv.DictReader(open("final_results.csv")))
labels = {"S1_station":"S1 · station\n(feuille)", "S2_order":"S2 · order\n(hub)",
          "S3_basic":"S3 · basic\n(intermédiaire)", "S4_multiple":"S4 · multiple\n(3 services)"}
scen = [labels.get(r["scenario"], r["scenario"]) for r in rows]
EN  = [float(r["EN"]) for r in rows]
RE  = [float(r["Recall"]) for r in rows]
PR  = [float(r["Precision"]) for r in rows]
FM  = [float(r["F"])*100 for r in rows]

x = np.arange(len(scen)); w = 0.20
fig, ax = plt.subplots(figsize=(11,6))
bars = [
    ("EN (réduction)", EN, PALETTE["EN"], -1.5),
    ("Recall (sûreté)", RE, PALETTE["Recall"], -0.5),
    ("Précision", PR, PALETTE["Precision"], 0.5),
    ("F-measure", FM, PALETTE["F"], 1.5),
]
for lab, vals, col, off in bars:
    b = ax.bar(x + off*w, vals, w, label=lab, color=col)
    for bar in b:
        h = bar.get_height()
        ax.annotate(f"{h:.0f}", (bar.get_x()+bar.get_width()/2, h),
                    xytext=(0,2), textcoords="offset points", ha="center", fontsize=7)
ax.set_ylabel("Pourcentage (%)", fontsize=12)
ax.set_title("MetaBP-RTS — Métriques par scénario de changement ΔS (Train-Ticket)",
             fontsize=13, fontweight="bold")
ax.set_xticks(x); ax.set_xticklabels(scen, fontsize=10)
ax.set_ylim(0,108); ax.axhline(100, color=PALETTE["Recall"], ls=":", alpha=0.5)
ax.legend(loc="lower right", framealpha=0.95); ax.grid(axis="y", ls="--", alpha=0.4)
plt.tight_layout(); plt.savefig("figures/fig_metabp_scenarios.png", dpi=200, bbox_inches="tight")
print("✓ figures/fig_metabp_scenarios.png")

# ─────────────────────────────────────────────────────────────
# FIGURE 2 : Comparatif Recall par technique (façon Chen Fig.8)
# ─────────────────────────────────────────────────────────────
try:
    comp = list(csv.DictReader(open("comparatif_baselines.csv")))
    techs = ["Retest-All","Random-N×30","Firewall-0","Firewall-1","MetaBP-RTS"]
    scen_ids = ["S1_station","S2_order","S3_basic","S4_multiple"]
    # Recall moyen par technique
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14,5.5))
    colT = {"Retest-All":"#999999","Random-N×30":"#DD8452","Firewall-0":"#C44E52",
            "Firewall-1":"#CCB974","MetaBP-RTS":"#4C72B0"}

    # Recall groupé par scénario
    xs = np.arange(len(scen_ids)); wt = 0.15
    for i,tech in enumerate(techs):
        vals = [next((float(r["Recall"]) for r in comp
                      if r["scenario"]==s and r["technique"]==tech), 0) for s in scen_ids]
        ax1.bar(xs + (i-2)*wt, vals, wt, label=tech, color=colT[tech])
    ax1.set_title("Recall (sûreté) par technique", fontweight="bold")
    ax1.set_ylabel("Recall (%)"); ax1.set_xticks(xs)
    ax1.set_xticklabels([s.replace("_","\n") for s in scen_ids], fontsize=9)
    ax1.set_ylim(0,108); ax1.legend(fontsize=8, loc="lower left"); ax1.grid(axis="y", ls="--", alpha=0.4)

    # EN groupé par scénario
    for i,tech in enumerate(techs):
        vals = [next((float(r["EN"]) for r in comp
                      if r["scenario"]==s and r["technique"]==tech), 0) for s in scen_ids]
        ax2.bar(xs + (i-2)*wt, vals, wt, label=tech, color=colT[tech])
    ax2.set_title("EN (réduction) par technique", fontweight="bold")
    ax2.set_ylabel("EN (%)"); ax2.set_xticks(xs)
    ax2.set_xticklabels([s.replace("_","\n") for s in scen_ids], fontsize=9)
    ax2.set_ylim(0,100); ax2.grid(axis="y", ls="--", alpha=0.4)

    plt.suptitle("Comparaison MetaBP-RTS vs baselines (Train-Ticket)", fontsize=13, fontweight="bold")
    plt.tight_layout(); plt.savefig("figures/fig_comparatif_baselines.png", dpi=200, bbox_inches="tight")
    print("✓ figures/fig_comparatif_baselines.png")
except FileNotFoundError:
    print("⚠ comparatif_baselines.csv absent — lancer le script 2 d'abord")

# ─────────────────────────────────────────────────────────────
# FIGURE 3 : Loi topologique EN vs nb tests touchant ΔS
# ─────────────────────────────────────────────────────────────
import json
try:
    T = json.load(open("phase1/data/outputs/test_suite_T.json"))
    def svcs(t):
        s=set()
        for p in (t.get("invocation_chain") or []):
            for x in p: s.add(x)
        if t.get("entry_service"): s.add(t["entry_service"])
        return s
    deltas = {"S1_station":["ts-station-service"],"S2_order":["ts-order-service"],
              "S3_basic":["ts-basic-service"],"S4_multiple":["ts-station-service","ts-order-service","ts-contacts-service"]}
    pts=[]
    en_map = {r["scenario"]: float(r["EN"]) for r in rows}
    for name,ds in deltas.items():
        dset=set(ds)
        n_touch = sum(1 for t in T if svcs(t)&dset)
        pts.append((n_touch, en_map.get(name,0), name))
    pts.sort()
    fig, ax = plt.subplots(figsize=(9,5.5))
    xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
    ax.plot(xs, ys, "o-", color="#4C72B0", markersize=10, linewidth=2)
    for x,y,n in pts:
        ax.annotate(n.replace("_","\n"), (x,y), textcoords="offset points",
                    xytext=(8,8), fontsize=9)
    ax.set_xlabel("Nombre de tests exerçant ΔS", fontsize=11)
    ax.set_ylabel("EN — réduction (%)", fontsize=11)
    ax.set_title("Loi topologique : la réduction décroît avec le nombre de tests exerçant ΔS",
                 fontsize=12, fontweight="bold")
    ax.grid(ls="--", alpha=0.4)
    plt.tight_layout(); plt.savefig("figures/fig_loi_topologique.png", dpi=200, bbox_inches="tight")
    print("✓ figures/fig_loi_topologique.png")
except Exception as e:
    print(f"⚠ figure loi topologique : {e}")

print("\nFigures générées dans figures/")
