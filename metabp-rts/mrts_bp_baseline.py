#!/usr/bin/env python3
"""
MRTS-BP réimplémenté (Chen et al. 2023) — comparateur central pour le chapitre 4.

Reproduction FIDÈLE du cœur algorithmique de Chen (Formules 3-6, Algorithme 4),
sur LE MÊME graphe de dépendances reconstruit par observabilité — ce qui fait de
MRTS-BP réimplémenté exactement l'ablation "MetaBP-RTS sans a priori Écho-Dormant".

Différences avec MetaBP-RTS (= les contributions de ce mémoire) :
  ┌────────────────┬─────────────────────────┬──────────────────────────────┐
  │                │ MRTS-BP (Chen)          │ MetaBP-RTS (ce travail)      │
  ├────────────────┼─────────────────────────┼──────────────────────────────┤
  │ p0 (Formule 3) │ 1 si ∈ΔS, 0 sinon       │ 1/Θ/0 (a priori Écho-Dormant)│
  │ propagation    │ max-product (Formule 4) │ noisy-OR                     │
  │ sélection      │ existent satisfaction   │ tiering + PathMR + PSO       │
  │                │ (Formule 6, p=min CIT)  │                              │
  └────────────────┴─────────────────────────┴──────────────────────────────┘

RÉSERVE (à écrire dans le mémoire) : la génération du SDM par fouille de motifs
fréquents (Formules 1-2) est remplacée par le graphe reconstruit des traces.
On reproduit donc la PROPAGATION et la SÉLECTION de Chen, pas son extraction SDM.
Nommé "MRTS-BP*" pour cette raison.

Usage (depuis la racine metabp-rts/metabp-rts/) :
    python3 mrts_bp_baseline.py --delta-s ts-station-service
"""
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path("phase2").resolve()))
from bp.graph_inverter import GraphInverter          # ton module
from bp.bp_propagator  import BPPropagator            # ton module (mode max_product)


def load(p): return json.load(open(p, encoding="utf-8"))


def tid(t): return t.get("test_id") or t.get("trace_id")


def svcs(t):
    """Services traversés par un test = chaîne ∪ entry_service (cohérent avec MetaBP)."""
    s = set()
    for pair in (t.get("invocation_chain") or []):
        for x in pair: s.add(x)
    if t.get("entry_service"): s.add(t["entry_service"])
    return s


def mrts_bp_select(delta_s, base="."):
    base = Path(base)

    # 1) Graphe inversé (identique à MetaBP — même observabilité)
    inverter = GraphInverter()
    dg = inverter.invert(str(base/"phase1/data/outputs/service_graph.json"),
                         delta_s=delta_s)

    nodes = dg["nodes"]

    # 2) p0 SELON CHEN (Formule 3) : 1 si ∈ΔS, 0 sinon — PAS d'a priori Écho-Dormant
    delta_set = set(delta_s)
    p0 = {n: (1.0 if n in delta_set else 0.0) for n in nodes}

    # 3) Propagation MAX-PRODUCT (Formule 4-5) — le mode de Chen
    prop = BPPropagator(mode="max_product")
    cit, n_iter, converged, _ = prop.propagate(dg, p0)

    # 4) Seuil p = valeur non nulle minimale de la CIT (choix de Chen pour la sûreté)
    non_zero = [v for s, v in cit.items() if s not in delta_set and v > 0]
    p_threshold = min(non_zero) if non_zero else 0.0

    # 5) Sélection EXISTENT SATISFACTION (Formule 6) :
    #    un test est sélectionné si AU MOINS UN de ses services a CIT ≥ p
    T = load(base/"phase1/data/outputs/test_suite_T.json")
    selected = []
    for t in T:
        services = svcs(t)
        # un service de ΔS a CIT=1 (≥p), donc tout test touchant ΔS est pris (sûreté)
        if any(cit.get(s, 0.0) >= p_threshold and cit.get(s, 0.0) > 0 for s in services) \
           or (services & delta_set):
            selected.append(t)

    return {
        "t_sel": selected,
        "n_total": len(T),
        "n_selected": len(selected),
        "cit": cit,
        "p_threshold": p_threshold,
        "n_iter": n_iter,
        "n_impacted": sum(1 for v in cit.values() if v > 0),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--delta-s", nargs="+", required=True)
    ap.add_argument("--base", default=".")
    ap.add_argument("--out", default=None, help="chemin de sortie T_sel (optionnel)")
    args = ap.parse_args()

    r = mrts_bp_select(args.delta_s, args.base)
    en = 100 * (1 - r["n_selected"] / r["n_total"])
    print(f"MRTS-BP* (Chen réimpl.) — ΔS={args.delta_s}")
    print(f"  propagation max-product : {r['n_iter']} itér | "
          f"{r['n_impacted']} services impactés | seuil p={r['p_threshold']:.4f}")
    print(f"  T_sel = {r['n_selected']}/{r['n_total']}  |  EN = {en:.1f}%")

    if args.out:
        json.dump(r["t_sel"], open(args.out, "w"), ensure_ascii=False, indent=2)
        print(f"  T_sel → {args.out}")


if __name__ == "__main__":
    main()
