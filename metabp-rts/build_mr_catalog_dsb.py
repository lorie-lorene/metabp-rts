#!/usr/bin/env python3
"""
build_mr_catalog_dsb.py — Construction du catalogue MR COMPORTEMENTAL pour
DeathStarBench hotelReservation.

POURQUOI CE SCRIPT
------------------
Le catalogue MR de Train-Ticket combine deux familles :
  - MR fonctionnelles  : inferees d'OpenAPI, ou a defaut de regles regex sur
                         les operationName (jaeger_fallback_mr.py). Ces regles
                         sont ecrites pour le domaine Train-Ticket (pay, refund,
                         travel, seats...) et ne matchent RIEN sur DSB.
  - MR comportementales: seuils APPRIS des traces (P99 latence, taux d'erreur
                         nominal + delta, P5 nb de spans). Purement statistiques,
                         donc AGNOSTIQUES AU DOMAINE.

MutationVerifier n'utilise QUE les MR comportementales (types Latence, Erreur,
Completude). Le catalogue produit ici est donc suffisant pour :
  - definir M(Delta_S) par mutation reelle, comme sur Train-Ticket ;
  - calculer FCS et P_mr sur DSB.

Les MR fonctionnelles ne sont PAS generees ici. Elles ne servent qu'a PathMR
(Phase 3), qui a deja tourne. Si tu veux les ajouter plus tard, ecris des regles
DSB dans jaeger_fallback_mr.py (reservation, search, profile, rate, geo, user).

FORMAT DE SORTIE
----------------
Compatible MutationVerifier._load_thresholds : cle racine `mr_catalog`,
entrees {service, type, threshold_*}. NE PAS renommer la cle racine.

USAGE
-----
  python build_mr_catalog_dsb.py \
      --traces  /chemin/vers/traces_dsb_brutes.json \
      --out     phase1/data/outputs/mr_catalog_dsb.yaml \
      --delta   0.10

Le fichier --traces doit etre le JSON Jaeger BRUT (meme format que celui lu par
TraceMutator._load_trace_index), c.-a-d. soit une liste de traces, soit un objet
{"data": [...]}, chaque trace ayant "traceID", "processes" et "spans".
"""

import argparse
import json
import logging
import statistics
import sys
from collections import defaultdict
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML requis :  pip install pyyaml")

logging.basicConfig(level=logging.INFO,
                    format="%(levelname)-8s %(message)s")
log = logging.getLogger("mr_catalog_dsb")


# ---------------------------------------------------------------------------
# Lecture des traces brutes — logique alignee sur TraceMutator
# ---------------------------------------------------------------------------
def load_traces(path):
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    traces = raw.get("data", raw) if isinstance(raw, dict) else raw
    log.info("Traces chargees : %d", len(traces))
    return traces


def extract_spans(traces):
    """
    Retourne :
      durations[svc]      -> liste des durees de span (us)
      errors[svc]         -> (n_spans_en_erreur, n_spans_total)
      spans_per_trace[svc]-> liste du nb de spans de svc par trace ou svc apparait
    """
    durations = defaultdict(list)
    err_count = defaultdict(int)
    tot_count = defaultdict(int)
    spans_per_trace = defaultdict(list)

    for tr in traces:
        procs = {p: v.get("serviceName", "unknown")
                 for p, v in tr.get("processes", {}).items()}
        per_svc_here = defaultdict(int)

        for s in tr.get("spans", []):
            svc = procs.get(s.get("processID", ""), "unknown")
            dur = int(s.get("duration", 0))
            is_err = any(t.get("key") == "error" and t.get("value") is True
                         for t in s.get("tags", []))
            durations[svc].append(dur)
            tot_count[svc] += 1
            if is_err:
                err_count[svc] += 1
            per_svc_here[svc] += 1

        for svc, n in per_svc_here.items():
            spans_per_trace[svc].append(n)

    return durations, err_count, tot_count, spans_per_trace


# ---------------------------------------------------------------------------
# Percentiles — implementation explicite (pas de dependance numpy)
# ---------------------------------------------------------------------------
def percentile(values, p):
    """Percentile par interpolation lineaire. p dans [0, 100]."""
    if not values:
        return 0
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    k = (len(xs) - 1) * (p / 100.0)
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    if lo == hi:
        return xs[lo]
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


# ---------------------------------------------------------------------------
# Construction du catalogue
# ---------------------------------------------------------------------------
def build_catalog(durations, err_count, tot_count, spans_per_trace,
                  delta, min_spans_required):
    entries = []
    skipped = []

    for svc in sorted(durations):
        n = tot_count[svc]
        if n < min_spans_required:
            skipped.append((svc, n))
            continue

        # --- Latence : seuil = P99 des durees observees -------------------
        p99 = int(round(percentile(durations[svc], 99)))
        entries.append({
            "mr_id": f"MR-BEH-LAT-{svc}",
            "type": "Latence",
            "service": svc,
            "threshold_us": p99,
            "rho": "d(x) <= theta_lat(s)",
            "n_observations": n,
            "source": "learned_from_traces",
        })

        # --- Erreur : seuil = taux nominal + delta -------------------------
        r_nom = err_count[svc] / n if n else 0.0
        entries.append({
            "mr_id": f"MR-BEH-ERR-{svc}",
            "type": "Erreur",
            "service": svc,
            "threshold_error_rate": round(min(r_nom + delta, 1.0), 4),
            "rho": "r(s,t) <= theta_err(s)",
            "nominal_error_rate": round(r_nom, 4),
            "n_observations": n,
            "source": "learned_from_traces",
        })

        # --- Completude : seuil = P5 du nb de spans par trace --------------
        p5 = int(round(percentile(spans_per_trace[svc], 5)))
        entries.append({
            "mr_id": f"MR-BEH-CMP-{svc}",
            "type": "Completude",
            "service": svc,
            "threshold_min_spans": max(p5, 1),
            "rho": "n_spans(s,t) >= theta_cmp(s)",
            "n_traces": len(spans_per_trace[svc]),
            "source": "learned_from_traces",
        })

    return entries, skipped


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--traces", required=True,
                    help="JSON Jaeger brut des traces DSB")
    ap.add_argument("--out", required=True,
                    help="Chemin du catalogue YAML a produire")
    ap.add_argument("--delta", type=float, default=0.10,
                    help="Marge du seuil d'erreur (defaut 0.10, comme Train-Ticket)")
    ap.add_argument("--min-spans", type=int, default=30,
                    help="Nb minimal de spans pour calibrer un service (defaut 30). "
                         "En dessous, un P99 n'a pas de sens statistique.")
    args = ap.parse_args()

    traces = load_traces(args.traces)
    if not traces:
        sys.exit("Aucune trace lue — verifie le chemin et le format du fichier.")

    durations, err_count, tot_count, spans_per_trace = extract_spans(traces)
    log.info("Services observes : %d", len(durations))

    entries, skipped = build_catalog(durations, err_count, tot_count,
                                     spans_per_trace, args.delta, args.min_spans)

    catalog = {
        "benchmark": "DeathStarBench-hotelReservation",
        "generated_from": str(args.traces),
        "n_traces": len(traces),
        "delta_error_margin": args.delta,
        "note": ("Catalogue COMPORTEMENTAL uniquement (seuils appris des traces). "
                 "Les MR fonctionnelles ne sont pas incluses : les regles de "
                 "jaeger_fallback_mr.py sont specifiques au domaine Train-Ticket. "
                 "Suffisant pour MutationVerifier (Latence/Erreur/Completude)."),
        "mr_catalog": entries,   # <-- NE PAS RENOMMER : cle attendue par le verifier
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        yaml.safe_dump(catalog, f, allow_unicode=True, sort_keys=False)

    n_svc = len(entries) // 3
    log.info("Catalogue ecrit -> %s", out)
    log.info("  %d services calibres, %d MR comportementales", n_svc, len(entries))
    if skipped:
        log.warning("  %d services ecartes (moins de %d spans) :",
                    len(skipped), args.min_spans)
        for svc, n in skipped:
            log.warning("    %-30s %d spans", svc, n)
        log.warning("  Ces services n'auront PAS de seuil : les mutants les "
                    "ciblant seront comptes comme survivants et feront BAISSER "
                    "le FCS. A documenter dans l'article.")

    print("\n--- Apercu des seuils appris ---")
    print(f"{'service':<32}{'P99 lat (us)':>14}{'seuil err':>12}{'min spans':>11}")
    print("-" * 69)
    by_svc = defaultdict(dict)
    for e in entries:
        by_svc[e["service"]][e["type"]] = e
    for svc in sorted(by_svc):
        d = by_svc[svc]
        print(f"{svc:<32}"
              f"{d['Latence']['threshold_us']:>14}"
              f"{d['Erreur']['threshold_error_rate']:>12}"
              f"{d['Completude']['threshold_min_spans']:>11}")


if __name__ == "__main__":
    main()
