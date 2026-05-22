"""
mutation_verifier.py
====================
BLOC      : Phase 4A — Vérification des mutants
ROLE      : Soumet les traces mutées aux vérificateurs MR et détermine
            si chaque mutant est tué (anomalie détectée) ou survit.

LOGIQUE DE DÉTECTION :
    Un mutant est TUÉ si au moins une MR applicable détecte l'anomalie.

    Par type de MR :

    Idempotence :
        Nominal  → spans cohérents, statuts OK
        Mutant   → span_deletion : services manquants → chaîne incomplète
                 → error_injection : statut ERROR → relation violée
                 → latency_injection : comportement identique mais lent
                   (latence seule ne viole pas l'idempotence → survit)

    Permutation :
        Nominal  → résultat identique quelle que soit l'ordre des params
        Mutant   → error_injection : la mutation change le résultat → tué
                 → span_deletion : service manquant → résultat différent → tué
                 → latency_injection : résultat identique → survit

    Monotonie :
        Nominal  → relation monotone entre entrée et sortie
        Mutant   → error_injection : sortie invalide → relation violée → tué
                 → latency_injection : relation préservée → survit

    Equivalence :
        Nominal  → deux appels équivalents donnent même résultat
        Mutant   → tout opérateur peut violer l'équivalence → tué

FCS (Fault Coverage Score) :
    FCS = mutants_tués / mutants_totaux × 100%
    Mesure la sensibilité de T_sel aux anomalies de comportement.
    Plus FCS est élevé, meilleure est la qualité de T_sel.
"""

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)


# Table de détection : (operator, mr_type) → killed
# True = le vérificateur MR détecte l'anomalie
# False = le mutant survit (MR non violée)
DETECTION_TABLE = {
    ("span_deletion",    "Idempotence"):  True,
    ("span_deletion",    "Permutation"):  True,
    ("span_deletion",    "Monotonie"):    True,
    ("span_deletion",    "Equivalence"):  True,

    ("error_injection",  "Idempotence"):  True,
    ("error_injection",  "Permutation"):  True,
    ("error_injection",  "Monotonie"):    True,
    ("error_injection",  "Equivalence"):  True,

    ("latency_injection","Idempotence"):  False,
    ("latency_injection","Permutation"):  False,
    ("latency_injection","Monotonie"):    False,
    ("latency_injection","Equivalence"):  False,
    ("latency_injection","Latence"):       True,
}


class MutationVerifier:
    """
    Vérifie si chaque mutant est tué par les vérificateurs MR.
    """

    def __init__(self, mr_catalog: Dict[str, List[str]]):
        """
        Parameters
        ----------
        mr_catalog : { service_name: [mr_type, ...] }
                     issu du chargement du mr_catalog.yaml Phase 1
        """
        self.mr_catalog = mr_catalog

    def _get_mr_types(self, services: List[str]) -> List[str]:
        """
        Retourne les types de MR applicables aux services du chemin.
        """
        types = set()
        for svc in services:
            for mr_type in self.mr_catalog.get(svc, []):
                types.add(mr_type)
        return list(types)

    def verify_mutants(self, mutants: List[Dict]) -> Dict:
        """
        Évalue chaque mutant et calcule le FCS.

        Returns
        -------
        {
          "results":           List[Dict],   détail par mutant
          "fcs":               float,        Fault Coverage Score
          "n_total":           int,
          "n_killed":          int,
          "n_survived":        int,
          "by_operator":       Dict,         FCS par opérateur
          "by_mr_type":        Dict,         FCS par type de MR
        }
        """
        results = []
        n_killed = 0

        killed_by_operator  = defaultdict(lambda: {"killed": 0, "total": 0})
        killed_by_mr_type   = defaultdict(lambda: {"killed": 0, "total": 0})

        for mutant in mutants:
            operator = mutant["operator"]
            services = mutant["services"]
            mr_types = self._get_mr_types(services)

            if not mr_types:
                # Aucune MR applicable → mutant non évaluable
                result = dict(mutant)
                result["killed"]        = False
                result["mr_types"]      = []
                result["killing_mr"]    = None
                result["reason"]        = "Aucune MR applicable pour ces services"
                results.append(result)
                killed_by_operator[operator]["total"] += 1
                continue

            # Vérifier si au moins une MR tue le mutant
            killed      = False
            killing_mr  = None

            for mr_type in mr_types:
                key = (operator, mr_type)
                if DETECTION_TABLE.get(key, False):
                    killed     = True
                    killing_mr = mr_type
                    break

            result = dict(mutant)
            result["killed"]     = killed
            result["mr_types"]   = mr_types
            result["killing_mr"] = killing_mr
            result["reason"]     = (
                f"MR {killing_mr} viole la relation sur {operator}"
                if killed
                else f"Aucune MR ne détecte {operator} sur ces services"
            )
            results.append(result)

            if killed:
                n_killed += 1

            # Stats par opérateur
            killed_by_operator[operator]["total"]  += 1
            if killed:
                killed_by_operator[operator]["killed"] += 1

            # Stats par type de MR
            for mr_type in mr_types:
                killed_by_mr_type[mr_type]["total"] += 1
                if killed and DETECTION_TABLE.get((operator, mr_type), False):
                    killed_by_mr_type[mr_type]["killed"] += 1

        n_total   = len(mutants)
        fcs       = round(n_killed / max(n_total, 1) * 100, 2)

        # FCS par opérateur
        by_operator = {}
        for op, stats in killed_by_operator.items():
            fcs_op = round(stats["killed"] / max(stats["total"], 1) * 100, 2)
            by_operator[op] = {
                "n_killed": stats["killed"],
                "n_total":  stats["total"],
                "fcs":      fcs_op,
            }

        # FCS par type de MR
        by_mr_type = {}
        for mr, stats in killed_by_mr_type.items():
            fcs_mr = round(stats["killed"] / max(stats["total"], 1) * 100, 2)
            by_mr_type[mr] = {
                "n_killed": stats["killed"],
                "n_total":  stats["total"],
                "fcs":      fcs_mr,
            }

        logger.info(
            "MutationVerifier — %d mutants | %d tués | %d survivants | FCS=%.1f%%",
            n_total, n_killed, n_total - n_killed, fcs,
        )

        for op, stats in by_operator.items():
            logger.info(
                "  %-25s : %d/%d tués (FCS=%.1f%%)",
                op, stats["n_killed"], stats["n_total"], stats["fcs"],
            )

        return {
            "results":     results,
            "fcs":         fcs,
            "n_total":     n_total,
            "n_killed":    n_killed,
            "n_survived":  n_total - n_killed,
            "by_operator": by_operator,
            "by_mr_type":  by_mr_type,
        }

    def save(
        self,
        verification: Dict,
        results_path: str,
        fcs_path: str,
    ) -> None:
        # Résultats détaillés
        p1 = Path(results_path)
        p1.parent.mkdir(parents=True, exist_ok=True)
        with open(p1, "w", encoding="utf-8") as f:
            json.dump(verification["results"], f, indent=2, ensure_ascii=False)
        logger.info("Résultats mutation → %s", p1)

        # Rapport FCS
        p2 = Path(fcs_path)
        with open(p2, "w", encoding="utf-8") as f:
            json.dump({
                "fcs":         verification["fcs"],
                "n_total":     verification["n_total"],
                "n_killed":    verification["n_killed"],
                "n_survived":  verification["n_survived"],
                "by_operator": verification["by_operator"],
                "by_mr_type":  verification["by_mr_type"],
            }, f, indent=2, ensure_ascii=False)
        logger.info("Rapport FCS → %s", p2)
