#!/usr/bin/env python3
"""
run_baselines_dsb_mutation.py — Baselines RTS sur DeathStarBench avec
MODELE DE FAUTE PAR MUTATION REELLE (aligne sur Train-Ticket).

CE QUI CHANGE PAR RAPPORT A run_baselines_dsb.py
------------------------------------------------
Ancien modele (structurel) :
    M(Delta_S) = {t | t exerce Delta_S}
  -> Firewall-0 == M PAR CONSTRUCTION -> F = 1.000 tautologique.
  -> Firewall-0 et Firewall-1 rendaient des chiffres identiques (781/781,
     737/737, 982/982, 1763/1763) : signature du probleme.

Nouveau modele (mutation) :
    M(Delta_S) = {t | au moins un mutant injecte dans Delta_S sur la trace de t
                      est TUE par les seuils comportementaux appris}
  -> Un test n'est "revelateur" que s'il rend la faute OBSERVABLE, pas
     simplement s'il traverse le service modifie.
  -> Firewall-0 redevient une approximation, pas la verite terrain.

PREREQUIS
---------
1. Catalogue MR comportemental DSB :
       python build_mr_catalog_dsb.py --traces <traces_dsb.json> \
              --out phase1/data/outputs/mr_catalog_dsb.yaml
2. Les traces Jaeger BRUTES de DSB (meme fichier que ci-dessus).
3. Les T_sel de Phase 3 deja produits : data/dsb/Tsel_<service>.json

SORTIES
-------
  baselines_dsb_mutation.csv   : comparatif complet (remplace l'ancien CSV)
  results_dsb/fcs_<scen>.json  : FCS par scenario (metrique QR3 sur DSB)
  results_dsb/M_<scen>.json    : composition de M(Delta_S), pour audit

USAGE
-----
  python run_baselines_dsb_mutation.py \
      --traces   /chemin/traces_dsb_brutes.json \
      --catalog  phase1/data/outputs/mr_catalog_dsb.yaml
"""

import argparse
import json
import logging
import random
import statistics
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
log = logging.getLogger("baselines_dsb")

random.seed(42)

BASE = Path.home() / "Bureau/MEMOIRE-2026/metabp-rts/metabp-rts"

# Les modules de Phase 4 sont reutilises TELS QUELS : ils sont agnostiques
# au domaine (mutation de spans bruts + verdict par seuil).
sys.path.insert(0, str(BASE / "phase4"))
try:
    from mutation.trace_mutator import TraceMutator
    from mutation.mutation_verifier import MutationVerifier
except ImportError as e:
    sys.exit(f"Import Phase 4 impossible ({e}).\n"
             f"Verifie que BASE est correct : {BASE}\n"
             f"et que phase4/mutation/ contient trace_mutator.py et "
             f"mutation_verifier.py (branche metapb-train-ticket-exp1).")

SCEN = {
    "D1_recommendation": ["recommendation"],
    "D2_user":           ["user"],
    "D3_search":         ["search"],
    "D4_profile":        ["profile"],
}


# ---------------------------------------------------------------------------
def tid(t):
    if isinstance(t, str):
        return t
    return t.get("test_id") or t.get("trace_id")


def svcs(t):
    s = set()
    for pair in (t.get("invocation_chain") or []):
        for x in pair:
            s.add(x)
    if t.get("entry_service"):
        s.add(t["entry_service"])
    return s


def rpf(sel_ids, M):
    inter = sel_ids & M
    R = len(inter) / len(M) if M else 0
    P = len(inter) / len(sel_ids) if sel_ids else 0
    F = 2 * P * R / (P + R) if (P + R) > 0 else 0
    return round(R * 100, 2), round(P * 100, 2), round(F, 4)


# ---------------------------------------------------------------------------
def build_M_by_mutation(T, delta, traces_path, verifier, outdir, scen_name):
    """
    M(Delta_S) = tests dont AU MOINS UN mutant injecte dans Delta_S est tue.

    On mute la suite COMPLETE T (pas seulement T_sel) : M est la verite terrain,
    elle doit etre independante de la selection evaluee. C'est le point critique
    de correction methodologique.
    """
    mutator = TraceMutator(traces_path=str(traces_path),
                           latency_ms=5000,
                           max_mutants_per_path=3,
                           seed=42)
    mutants = mutator.generate_mutants(T, delta_s=delta)
    if not mutants:
        log.error("Aucun mutant genere pour %s. Causes possibles : traceID "
                  "absents de l'index, ou aucun span des services %s.",
                  scen_name, delta)
        return set(), None

    verif = verifier.verify_mutants(mutants)

    M = {m["test_id"] for m in verif["results"] if m["killed"]}

    outdir.mkdir(parents=True, exist_ok=True)
    with open(outdir / f"fcs_{scen_name}.json", "w", encoding="utf-8") as f:
        json.dump({k: verif[k] for k in
                   ("fcs", "n_total", "n_killed", "n_survived", "by_operator")},
                  f, indent=2, ensure_ascii=False)
    with open(outdir / f"M_{scen_name}.json", "w", encoding="utf-8") as f:
        json.dump(sorted(M), f, indent=2)

    log.info("%s : %d mutants, %d tues (FCS=%.2f%%) -> |M| = %d",
             scen_name, verif["n_total"], verif["n_killed"], verif["fcs"], len(M))
    return M, verif


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--traces", required=True, help="JSON Jaeger brut DSB")
    ap.add_argument("--catalog", required=True, help="mr_catalog_dsb.yaml")
    ap.add_argument("--out", default=str(BASE / "baselines_dsb_mutation.csv"))
    ap.add_argument("--resultsdir", default=str(BASE / "results_dsb"))
    args = ap.parse_args()

    T = json.load(open(BASE / "phase1/data/outputs/test_suite_T.json"))
    graph = json.load(open(BASE / "phase1/data/outputs/service_graph.json"))
    log.info("Suite T : %d chemins | graphe : %d services",
             len(T), len(graph.get("nodes", [])))

    neigh = {}
    for e in graph["links"]:
        neigh.setdefault(e["source"], set()).add(e["target"])
        neigh.setdefault(e["target"], set()).add(e["source"])

    verifier = MutationVerifier(mr_catalog_path=args.catalog)
    if not verifier.lat:
        sys.exit("Aucun seuil de latence charge. Le catalogue est-il bien au "
                 "format attendu (cle racine 'mr_catalog') ?")

    outdir = Path(args.resultsdir)
    allids = [tid(t) for t in T]
    N = len(T)
    rows = []

    for name, delta in SCEN.items():
        delta_set = set(delta)
        log.info("=== %s | Delta_S = %s ===", name, delta)

        M, verif = build_M_by_mutation(T, delta, args.traces, verifier,
                                       outdir, name)
        if not M:
            log.warning("M vide pour %s — scenario ignore.", name)
            continue

        # --- MetaBP-RTS -----------------------------------------------------
        tsel = json.load(open(BASE / f"data/dsb/Tsel_{delta[0]}.json"))
        tsel_ids = {tid(t) for t in tsel}
        R, P, F = rpf(tsel_ids, M)
        EN = round(100 * (1 - len(tsel_ids) / N), 1)
        rows.append((name, "MetaBP-RTS", len(tsel_ids), EN, R, P, F, "traces"))

        # --- Retest-All -----------------------------------------------------
        R, P, F = rpf(set(allids), M)
        rows.append((name, "Retest-All", N, 0.0, R, P, F, "aucun"))

        # --- Firewall-0 : tests touchant Delta_S ----------------------------
        # N'est PLUS egal a M : M est desormais defini par observabilite de la
        # faute, pas par traversee du service.
        fw0 = {tid(t) for t in T if svcs(t) & delta_set}
        R, P, F = rpf(fw0, M)
        rows.append((name, "Firewall-0", len(fw0),
                     round(100 * (1 - len(fw0) / N), 1), R, P, F, "code"))

        # --- Firewall-1 : Delta_S + voisins directs -------------------------
        fw1set = set(delta) | {n for d in delta for n in neigh.get(d, set())}
        fw1 = {tid(t) for t in T if svcs(t) & fw1set}
        R, P, F = rpf(fw1, M)
        rows.append((name, "Firewall-1", len(fw1),
                     round(100 * (1 - len(fw1) / N), 1), R, P, F, "code"))

        # --- Random-N x30 ---------------------------------------------------
        k = min(len(tsel_ids), N)
        Rs, Ps, Fs = [], [], []
        for _ in range(30):
            sample = set(random.sample(allids, k))
            r, p, f = rpf(sample, M)
            Rs.append(r); Ps.append(p); Fs.append(f)
        rows.append((name, "Random-N(x30)", k, round(100 * (1 - k / N), 1),
                     f"{statistics.mean(Rs):.1f}+-{statistics.pstdev(Rs):.1f}",
                     f"{statistics.mean(Ps):.1f}+-{statistics.pstdev(Ps):.1f}",
                     f"{statistics.mean(Fs):.3f}", "aucun"))

    if not rows:
        sys.exit("Aucun resultat produit.")

    out = Path(args.out)
    with open(out, "w", encoding="utf-8") as f:
        f.write("scenario,technique,T_sel,EN,Recall,Precision,F,acces\n")
        for r in rows:
            f.write(",".join(str(x) for x in r) + "\n")

    print(f"\n{'scenario':<20}{'technique':<15}{'T_sel':>7}{'EN':>7}"
          f"{'Recall':>14}{'Prec':>14}{'F':>9}{'Acces':>9}")
    print("-" * 95)
    prev = None
    for r in rows:
        if prev and prev != r[0]:
            print()
        prev = r[0]
        print(f"{r[0]:<20}{r[1]:<15}{r[2]:>7}{str(r[3]):>7}"
              f"{str(r[4]):>14}{str(r[5]):>14}{str(r[6]):>9}{r[7]:>9}")

    print(f"\nCSV -> {out}")
    print(f"FCS et M par scenario -> {outdir}")
    print("\nCONTROLE A FAIRE : si Firewall-0 rend encore F = 1.000 partout et "
          "des tailles identiques a Firewall-1, le modele de faute n'a pas "
          "change — verifie que M provient bien de la mutation.")


if __name__ == "__main__":
    main()
