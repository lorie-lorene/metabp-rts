"""
ALGORITHME: MRPS — Metamorphic Relation Path Signature

    Calcule la signature de chaque chemin Tier 2 et regroupe les chemins
    redondants. Pour chaque groupe, conserve un représentant unique.
    Réduit Tier2 sans perdre de couverture sémantique.

SIGNATURE :
    Mode structural :
        sig(t) = frozenset(services traversés)
        Deux chemins avec les mêmes services = redondants

    Mode enriched (recommandé) :
        sig(t) = (frozenset(services), frozenset(MR_associées))
        MR(t)  = { mr | service(mr) ∈ services(t) }
        Deux chemins structurellement identiques mais vérifiant
        des MR différentes NE sont PAS redondants.

REPRÉSENTANT :
    Pour chaque groupe de chemins redondants, on conserve celui
    dont le score CIT est le plus élevé — il est le plus susceptible
    de détecter des régressions liées à ΔS.

"""

import json
import logging
import yaml
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class MRPS:

    def __init__(
        self,
        mode: str = "enriched",
        representative: str = "cit",
    ):
       
        assert mode in ("structural", "enriched"), \
            f"Mode inconnu : {mode}"
        assert representative in ("cit", "first"), \
            f"Représentant inconnu : {representative}"
        self.mode           = mode
        self.representative = representative

    def _extract_services(self, tp: Dict) -> List[str]:
        """Extrait la liste ordonnée des services depuis un chemin."""
        chain = tp.get("invocation_chain", [])
        if chain:
            seen = []
            for pair in chain:
                for svc in pair:
                    if svc not in seen:
                        seen.append(svc)
            return seen
        return tp.get("services", tp.get("path", []))

    def _load_mr_catalog(self, catalog_path: str) -> Dict[str, List[str]]:
 
        with open(catalog_path, encoding="utf-8") as f:
            catalog = yaml.safe_load(f)

        service_to_mrs: Dict[str, List[str]] = defaultdict(list)

        relations = catalog.get("relations", catalog.get("mr", []))
        for mr in relations:
            svc = mr.get("service", mr.get("service_name", ""))
            mr_id = mr.get("id", mr.get("mr_id", str(mr)))
            if svc:
                service_to_mrs[svc].append(mr_id)

        logger.info(
            "MRPS — catalogue MR chargé : %d MR sur %d services",
            sum(len(v) for v in service_to_mrs.values()),
            len(service_to_mrs),
        )
        return dict(service_to_mrs)

    def _compute_signature(
        self,
        services: List[str],
        service_to_mrs: Dict[str, List[str]],
    ) -> Tuple:
        """
        Calcule la signature d'un chemin.

        Mode structural  : (frozenset(services),)
        Mode enriched    : (frozenset(services), frozenset(MR_associées))
        """
        svc_set = frozenset(services)

        if self.mode == "structural":
            return (svc_set,)

        # Mode enriched : MR(t) = union des MR de tous les services traversés
        mr_set = frozenset(
            mr_id
            for svc in services
            for mr_id in service_to_mrs.get(svc, [])
        )
        return (svc_set, mr_set)

    def _select_representative(
        self,
        group: List[Dict],
        cit: Dict[str, float],
    ) -> Dict:
        """
        Sélectionne le représentant du groupe.

        "cit"   : chemin dont le score max CIT est le plus élevé
        "first" : premier chemin du groupe
        """
        if self.representative == "first" or not cit:
            return group[0]

        def path_cit_score(tp):
            services = tp.get("services", [])
            scores = [cit.get(s, 0.0) for s in services]
            return max(scores) if scores else 0.0

        return max(group, key=path_cit_score)

    def deduplicate(
        self,
        tier2_tests: List[Dict],
        mr_catalog_path: str,
        cit: Optional[Dict[str, float]] = None,
    ) -> Dict:
       
        service_to_mrs = self._load_mr_catalog(mr_catalog_path)
        cit = cit or {}

        # Calculer la signature de chaque chemin
        groups: Dict[Tuple, List[Dict]] = defaultdict(list)

        for tp in tier2_tests:
            services = self._extract_services(tp)

            # Enrichir le chemin avec les services extraits
            tp = dict(tp)
            tp["services"] = services

            sig = self._compute_signature(services, service_to_mrs)
            groups[sig].append(tp)

        # Sélectionner le représentant de chaque groupe
        representatives = []
        groups_serializable = {}

        for sig, group in groups.items():
            rep = self._select_representative(group, cit)
            representatives.append(rep)

            # Clé sérialisable pour JSON
            sig_key = str(sorted(list(sig[0])))
            groups_serializable[sig_key] = [
                tp.get("test_id", tp.get("trace_id", "?"))
                for tp in group
            ]

        n_input  = len(tier2_tests)
        n_groups = len(representatives)
        dedup_rate = round(1 - n_groups / max(n_input, 1), 4)

        # Distribution des tailles de groupes
        group_sizes = [len(g) for g in groups.values()]
        avg_group_size = round(sum(group_sizes) / max(len(group_sizes), 1), 2)
        max_group_size = max(group_sizes, default=0)
        singletons     = sum(1 for s in group_sizes if s == 1)

        logger.info(
            "MRPS — mode=%s | %d chemins → %d groupes uniques | "
            "réduction=%.1f%% | avg_groupe=%.1f | max_groupe=%d | singletons=%d",
            self.mode, n_input, n_groups,
            dedup_rate * 100, avg_group_size, max_group_size, singletons,
        )

        return {
            "mode":            self.mode,
            "representative":  self.representative,
            "n_input":         n_input,
            "n_groups":        n_groups,
            "dedup_rate":      dedup_rate,
            "groups":          groups_serializable,
            "representatives": representatives,
            "stats": {
                "n_input":        n_input,
                "n_groups":       n_groups,
                "dedup_rate":     dedup_rate,
                "dedup_pct":      f"{dedup_rate*100:.1f}%",
                "avg_group_size": avg_group_size,
                "max_group_size": max_group_size,
                "singletons":     singletons,
                "singleton_pct":  f"{singletons/max(n_groups,1)*100:.1f}%",
            },
        }

    def save(self, result: Dict, groups_path: str, dedup_path: str) -> None:
        """Sauvegarde les groupes et les représentants."""
        # Groupes (pour analyse)
        p1 = Path(groups_path)
        p1.parent.mkdir(parents=True, exist_ok=True)
        with open(p1, "w", encoding="utf-8") as f:
            json.dump({
                "mode":       result["mode"],
                "stats":      result["stats"],
                "groups":     result["groups"],
            }, f, indent=2, ensure_ascii=False)
        logger.info("MRPS groupes → %s", p1)

        # Représentants = Tier2_dédupliqué
        p2 = Path(dedup_path)
        p2.parent.mkdir(parents=True, exist_ok=True)
        with open(p2, "w", encoding="utf-8") as f:
            json.dump(result["representatives"], f, indent=2, ensure_ascii=False)
        logger.info("MRPS Tier2_dédupliqué → %s (%d représentants)", p2, len(result["representatives"]))
