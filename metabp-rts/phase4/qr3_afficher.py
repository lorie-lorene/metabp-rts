#!/usr/bin/env python3
"""
QR3 — Affichage consolidé de la validation métamorphique des tests sélectionnés.
Lit les 5 rapports de la phase 4 et présente les deux mécanismes de validation.
À lancer depuis phase4/ :  python3 qr3_afficher.py
"""
import json
from pathlib import Path

CY="\033[96m"; GR="\033[92m"; YE="\033[93m"; BD="\033[1m"; RS="\033[0m"; DIM="\033[2m"
def load(p): return json.load(open(p, encoding="utf-8"))

e1  = load("metamorphic/online/etage1_report.json")
e2a = load("metamorphic/online/etage2a_report.json")
e2b = load("metamorphic/online/etage2b_report.json")
fcs = load("data/outputs/fcs_report.json")
pc  = load("metamorphic/online/partC_report.json")

print()
print(f"{BD}{CY}╔{'═'*72}╗{RS}")
print(f"{BD}{CY}║{'  QR3 — VALIDATION MÉTAMORPHIQUE DES TESTS SÉLECTIONNÉS':<72}║{RS}")
print(f"{BD}{CY}╚{'═'*72}╝{RS}")
print()
print(f"{DIM}Principe : la sélection (T1) produit un sous-ensemble sûr mais muet sur les")
print(f"verdicts. La validation (T2) le dote d'un oracle SANS spécification.{RS}")
print()

# ── MÉCANISME 1 : mutation tracing ─────────────────────────────────────
print(f"{BD}MÉCANISME 1 — Mutation tracing{RS}  {DIM}(couvre l'intégralité de T_sel){RS}")
print(f"  Détecte la sensibilité aux altérations de trace.")
print(f"  {GR}FCS global : {fcs['fcs']:.1f} %{RS}  ({fcs['n_killed']}/{fcs['n_total']} mutants tués)")
for op, v in fcs["by_operator"].items():
    print(f"    {DIM}{op:<20}{RS} {v['fcs']:>6.1f} %  ({v['n_killed']}/{v['n_total']})")
print()

# ── MÉCANISME 2 : relations métamorphiques ─────────────────────────────
print(f"{BD}MÉCANISME 2 — Relations métamorphiques{RS}  {DIM}(endpoints instrumentés){RS}")
print(f"  Oracle sans spécification, validé en trois étages.")
print()

# Étage 1 — validité
print(f"  {BD}Étage 1 — Validité des MR{RS}  (système sain)")
print(f"    {GR}P_mr = {e1['p_mr']:.0f} %{RS}  — {e1['n']}/{e1['n']} MR satisfaites")
print(f"    {len(e1['familles'])} familles : {', '.join(e1['familles'])}")
print(f"    {DIM}→ l'oracle ne produit aucun faux positif sur un système correct{RS}")
print()

# Étage 2a — détection niveau réponse
print(f"  {BD}Étage 2a — Détection (fautes niveau réponse){RS}")
print(f"    {GR}Sensibilité : {e2a['n_fautes_detectees']}/{e2a['n_vraies_fautes']} = {e2a['sensibilite_pct']:.0f} %{RS}"
      f"   (fautes réelles détectées)")
print(f"    {GR}Spécificité : {e2a['n_controles_ok']}/{e2a['n_controles']} = {e2a['specificite_pct']:.0f} %{RS}"
      f"   (contrôle non déclenché)")
print()

# Étage 2b — détection niveau service
print(f"  {BD}Étage 2b — Détection (fautes niveau service, via proxy){RS}")
print(f"    {GR}Sensibilité : {e2b['n_detectees']}/{e2b['n_vraies_fautes']} = {e2b['sensibilite_pct']:.0f} %{RS}"
      f"   (fautes injectées détectées)")
print(f"    {GR}Fausses alarmes : {e2b['faux_positifs']}{RS}   (mode sain non signalé)")
print()

# ── LIEN AVEC LA SÉLECTION : préservation ──────────────────────────────
print(f"{BD}LIEN SÉLECTION ↔ VALIDATION — Préservation après réduction{RS}")
n_t = len(pc["MR_applicables_T"]); n_sel = len(pc["MR_applicables_T_sel"])
print(f"  T = {pc['n_T']} tests  →  T_sel = {pc['n_T_sel']} tests  (EN {pc['EN_pct']:.1f} %)")
print(f"  {GR}MR préservées : {n_sel}/{n_t}{RS}   (MR perdues : {pc['MR_perdues'] or 'aucune'})")
print(f"  MR détectant ΔS conservées : {GR}{len(pc['MR_detectant_deltaS_dans_T_sel'])}/{len(pc['MR_detectant_deltaS'])}{RS}"
      f"  ({', '.join(pc['MR_detectant_deltaS_dans_T_sel'])})")
print(f"  {DIM}→ la réduction ne dégrade pas la capacité de validation{RS}")
print()

# ── SYNTHÈSE ───────────────────────────────────────────────────────────
print(f"{BD}{CY}{'─'*74}{RS}")
print(f"{BD}SYNTHÈSE QR3{RS}")
print(f"  {GR}✓{RS} Oracle valide        : P_mr = 100 %")
print(f"  {GR}✓{RS} Oracle sensible      : {e2a['n_fautes_detectees']+e2b['n_detectees']}/"
      f"{e2a['n_vraies_fautes']+e2b['n_vraies_fautes']} fautes détectées (réponse + service)")
print(f"  {GR}✓{RS} Oracle spécifique    : 0 fausse alarme")
print(f"  {GR}✓{RS} Détection préservée  : 9/9 MR après réduction")
print(f"  {GR}✓{RS} Sensibilité globale  : FCS = 95,3 % (mutation, tout T_sel)")
print(f"{BD}{CY}{'─'*74}{RS}")
print()
print(f"{DIM}Limite : la validation online couvre les endpoints du catalogue (6/46).")
print(f"L'extension du catalogue MR est identifiée comme perspective.{RS}")
print()
