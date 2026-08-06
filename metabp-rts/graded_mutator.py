#!/usr/bin/env python3
"""
graded_mutator.py — Mutation de traces à AMPLITUDE CALIBREE PAR SERVICE.

POURQUOI CE MODULE
------------------
TraceMutator injecte une latence CONSTANTE (Lambda = 5 000 ms = 5 000 000 us).
Sur DeathStarBench, les seuils appris valent :

    user             73 us          recommendation      175 us
    geo             396 us          profile           1 482 us
    rate         12 750 us          search           17 682 us
    reservation  48 321 us          frontend         61 785 us

L'injection constante est donc 80 a 68 000 fois superieure au seuil. TOUT mutant
de latence est tue, quel que soit le service. M(Delta_S) redevient alors
{t | t exerce Delta_S}, c.-a-d. le modele STRUCTUREL que l'on cherche a quitter,
et Firewall-0 redevient tautologique.

CE QUE FAIT CE MODULE
---------------------
L'amplitude est exprimee comme un MULTIPLICATEUR du seuil appris du service
cible :  duration_mutee = facteur * theta_lat(service).

Un balayage de facteurs (0.5, 0.9, 1.1, 2.0 par defaut) produit des mutants
dont certains survivent et d'autres meurent, PAR CONSTRUCTION du gradient :

    facteur < 1.0  -> mutant sous le seuil  -> doit SURVIVRE
    facteur > 1.0  -> mutant au-dessus      -> doit ETRE TUE

Cela donne deux choses :
  1. un M(Delta_S) discriminant, non tautologique ;
  2. une courbe de sensibilite de l'oracle, qui repond directement a la critique
     "les taux de 100% ne sont pas informatifs".

Le meme principe s'applique a la completude : on supprime k spans, avec k choisi
relativement a theta_cmp(service).

L'operateur error_injection est DESACTIVE PAR DEFAUT sur DeathStarBench :
l'instrumentation Go ne propage pas les erreurs applicatives aux spans des
services aval (mesure : 74 spans en erreur sur 9 700 pour le frontend, 0 sur les
8 services metier, malgre 48 reponses non-200 sur 300 requetes). Le taux nominal
est donc nul partout, theta_err = 0.10 uniformement, et l'operateur ne discrimine
rien. Utiliser --with-error pour le reactiver malgre tout.

USAGE
-----
  python graded_mutator.py \
      --traces  phase1/data/raw/corpus_dsb_FINAL.json \
      --corpus  phase1/data/outputs/test_suite_T.json \
      --catalog phase1/data/outputs/mr_catalog_dsb.yaml \
      --delta   profile \
      --out     results_dsb/mutants_profile.json

  # balayage personnalise
  --factors 0.25 0.5 0.75 0.9 1.1 1.5 2.0 5.0
"""

import argparse
import json
import logging
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML requis :  pip install pyyaml")

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
log = logging.getLogger("graded_mutator")

DEFAULT_FACTORS = [0.5, 0.9, 1.1, 2.0]


# ---------------------------------------------------------------------------
# Chargement des seuils — meme format que MutationVerifier
# ---------------------------------------------------------------------------
def load_thresholds(path):
    with open(path, encoding="utf-8") as f:
        cat = yaml.safe_load(f) or {}
    rel = cat.get("mr_catalog") or cat.get("relations") or []
    lat, err, cmp_ = {}, {}, {}
    for mr in rel:
        svc, t = mr.get("service"), mr.get("type")
        if t == "Latence" and "threshold_us" in mr:
            lat[svc] = int(mr["threshold_us"])
        elif t == "Erreur" and "threshold_error_rate" in mr:
            err[svc] = float(mr["threshold_error_rate"])
        elif t == "Completude" and "threshold_min_spans" in mr:
            cmp_[svc] = int(mr["threshold_min_spans"])
    log.info("Seuils charges : %d Lat, %d Err, %d Cmp", len(lat), len(err), len(cmp_))
    return lat, err, cmp_


# ---------------------------------------------------------------------------
# Index des traces brutes — logique alignee sur TraceMutator
# ---------------------------------------------------------------------------
def build_trace_index(path):
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    traces = raw.get("data", raw) if isinstance(raw, dict) else raw
    index = {}
    for tr in traces:
        procs = {p: v.get("serviceName", "unknown")
                 for p, v in tr.get("processes", {}).items()}
        spans = []
        for s in tr.get("spans", []):
            spans.append({
                "span_id": s.get("spanID", ""),
                "service": procs.get(s.get("processID", ""), "unknown"),
                "duration": int(s.get("duration", 0)),
                "error": any(t.get("key") == "error" and t.get("value") is True
                             for t in s.get("tags", [])),
            })
        index[tr.get("traceID")] = spans
    log.info("Traces indexees : %d", len(index))
    return index


def tid(t):
    if isinstance(t, str):
        return t
    return t.get("test_id") or t.get("trace_id")


# ---------------------------------------------------------------------------
# Generation des mutants gradues
# ---------------------------------------------------------------------------
def generate_graded_mutants(corpus, index, delta_set, lat, cmp_,
                            factors, with_error, err_thresholds, seed=42):
    random.seed(seed)
    mutants = []
    n_no_trace = n_no_delta = n_no_threshold = 0

    for t in corpus:
        tidv = tid(t)
        spans_all = index.get(tidv)
        if not spans_all:
            n_no_trace += 1
            continue

        spans = [s for s in spans_all if s["service"] in delta_set]
        if not spans:
            n_no_delta += 1
            continue

        target = random.choice(spans)
        svc = target["service"]

        if svc not in lat:
            n_no_threshold += 1
            continue

        theta = lat[svc]

        # --- Latence graduee : un mutant par facteur ------------------------
        for fct in factors:
            mutated = int(round(fct * theta))
            mutants.append({
                "mutant_id": f"{tidv}__lat__{svc}__x{fct}",
                "test_id": tidv,
                "operator": "latency_injection",
                "target_service": svc,
                "factor": fct,
                "threshold_us": theta,
                "mutated_duration_us": mutated,
                "expected_killed": mutated > theta,   # verite attendue
                "killed": False,
            })

        # --- Completude graduee ---------------------------------------------
        # On supprime k spans du service ; le verdict depend de theta_cmp.
        n_svc = sum(1 for s in spans_all if s["service"] == svc)
        theta_c = cmp_.get(svc)
        if theta_c is not None:
            for k in (1, 2):
                after = n_svc - k
                if after < 0:
                    continue
                mutants.append({
                    "mutant_id": f"{tidv}__del{k}__{svc}",
                    "test_id": tidv,
                    "operator": "span_deletion",
                    "target_service": svc,
                    "n_deleted": k,
                    "threshold_min_spans": theta_c,
                    "spans_after_deletion": after,
                    "expected_killed": after < theta_c,
                    "killed": False,
                })

        # --- Erreur (desactivee par defaut) ---------------------------------
        if with_error and svc in err_thresholds:
            sains = [s for s in spans if not s["error"]]
            if sains:
                tot = n_svc
                nerr = sum(1 for x in spans_all
                           if x["service"] == svc and x["error"])
                taux = (nerr + 1) / tot if tot else 1.0
                mutants.append({
                    "mutant_id": f"{tidv}__err__{svc}",
                    "test_id": tidv,
                    "operator": "error_injection",
                    "target_service": svc,
                    "mutated_error_rate": round(taux, 4),
                    "threshold_error_rate": err_thresholds[svc],
                    "expected_killed": taux > err_thresholds[svc],
                    "killed": False,
                })

    log.info("Mutants generes : %d  (%d sans trace, %d hors Delta_S, "
             "%d sans seuil)", len(mutants), n_no_trace, n_no_delta,
             n_no_threshold)
    return mutants


# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------
def verify(mutants, lat, err, cmp_):
    by_factor = defaultdict(lambda: {"killed": 0, "total": 0})
    by_op = defaultdict(lambda: {"killed": 0, "total": 0})
    mismatches = 0

    for m in mutants:
        op, svc = m["operator"], m["target_service"]
        killed = False
        if op == "latency_injection" and svc in lat:
            killed = m["mutated_duration_us"] > lat[svc]
        elif op == "span_deletion" and svc in cmp_:
            killed = m["spans_after_deletion"] < cmp_[svc]
        elif op == "error_injection" and svc in err:
            killed = m["mutated_error_rate"] > err[svc]
        m["killed"] = killed

        if killed != m.get("expected_killed"):
            mismatches += 1

        by_op[op]["total"] += 1
        if killed:
            by_op[op]["killed"] += 1
        if op == "latency_injection":
            f = m["factor"]
            by_factor[f]["total"] += 1
            if killed:
                by_factor[f]["killed"] += 1

    if mismatches:
        log.warning("%d mutants ou killed != expected_killed — incoherence "
                    "entre generation et verdict, a investiguer.", mismatches)

    return by_op, by_factor


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--traces", required=True)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--delta", required=True, nargs="+",
                    help="services modifies, ex: profile")
    ap.add_argument("--out", required=True)
    ap.add_argument("--factors", type=float, nargs="+", default=DEFAULT_FACTORS)
    ap.add_argument("--with-error", action="store_true",
                    help="reactiver error_injection (desactive par defaut sur DSB)")
    args = ap.parse_args()

    lat, err, cmp_ = load_thresholds(args.catalog)
    index = build_trace_index(args.traces)
    corpus = json.load(open(args.corpus, encoding="utf-8"))
    log.info("Corpus : %d chemins", len(corpus))

    delta_set = set(args.delta)
    mutants = generate_graded_mutants(corpus, index, delta_set, lat, cmp_,
                                      args.factors, args.with_error, err)
    if not mutants:
        sys.exit("Aucun mutant genere. Verifie que les traceID du corpus "
                 "correspondent a ceux du fichier de traces brutes.")

    by_op, by_factor = verify(mutants, lat, err, cmp_)

    M = sorted({m["test_id"] for m in mutants if m["killed"]})

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(mutants, f, indent=2, ensure_ascii=False)
    with open(out.with_name(out.stem + "_M.json"), "w", encoding="utf-8") as f:
        json.dump(M, f, indent=2)

    total = len(mutants)
    killed = sum(1 for m in mutants if m["killed"])
    print(f"\nDelta_S = {sorted(delta_set)}")
    print(f"Mutants : {total} | tues : {killed} | FCS = {100*killed/total:.2f}%")
    print(f"|M(Delta_S)| = {len(M)} tests revelateurs\n")

    print("Par operateur :")
    for op, s in by_op.items():
        print(f"  {op:<20} {s['killed']:>6}/{s['total']:<6} "
              f"({100*s['killed']/max(s['total'],1):.1f}%)")

    print("\nCourbe de sensibilite (latence) :")
    print(f"  {'facteur':>9}{'tues':>8}{'total':>8}{'taux':>9}")
    for f in sorted(by_factor):
        s = by_factor[f]
        print(f"  {f:>9}{s['killed']:>8}{s['total']:>8}"
              f"{100*s['killed']/max(s['total'],1):>8.1f}%")

    print(f"\nMutants  -> {out}")
    print(f"M(Delta_S) -> {out.with_name(out.stem + '_M.json')}")
    print("\nCONTROLE : la courbe doit montrer 0% sous facteur 1.0 et 100% "
          "au-dessus. Si elle est plate a 100%, le gradient n'a pas ete "
          "applique.")


if __name__ == "__main__":
    main()
