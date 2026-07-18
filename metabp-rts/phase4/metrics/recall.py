"""
Recall / Precision / F-measure d'une sélection de tests (sûreté RTS).

Fondé sur les mutants générés à partir de T COMPLET :
  M = { test_id : le test tue >= 1 mutant }   (tests révélateurs de faute)
  R = |S ∩ M| / |M|        (recall / sûreté — Formule 11 de Chen)
  P = |S ∩ M| / |S|        (précision      — Formule 12)
  F = 2PR / (P+R)          (F-measure       — Formule 13)
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Set

logger = logging.getLogger(__name__)


def fault_revealing_set(mutation_results: List[Dict]) -> Set[str]:
    """M = ensemble des test_id qui tuent au moins un mutant."""
    M = set()
    for r in mutation_results:
        if r.get("killed") and r.get("test_id"):
            M.add(r["test_id"])
    return M


def selection_ids(selection: List[Dict]) -> Set[str]:
    return {t["test_id"] for t in selection if t.get("test_id")}


def recall_precision_f(selection: List[Dict], M: Set[str]) -> Dict:
    """R, P, F d'une sélection donnée, relativement à M."""
    S = selection_ids(selection)
    inter = S & M
    R = len(inter) / len(M) if M else 0.0
    P = len(inter) / len(S) if S else 0.0
    F = 2 * P * R / (P + R) if (P + R) > 0 else 0.0
    return {
        "n_selection": len(S),
        "n_fault_revealing_total": len(M),
        "n_fault_revealing_selected": len(inter),
        "recall": round(R * 100, 2),      # sûreté
        "precision": round(P * 100, 2),
        "f_measure": round(F, 4),
    }


def save_fault_revealing(M: Set[str], path: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    json.dump(sorted(M), open(p, "w", encoding="utf-8"), indent=2)
    logger.info("Ensemble révélateur de fautes M (%d tests) -> %s", len(M), p)


def load_fault_revealing(path: str) -> Set[str]:
    return set(json.load(open(path, encoding="utf-8")))
