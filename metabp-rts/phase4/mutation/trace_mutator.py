"""
trace_mutator.py
================
BLOC      : Phase 4A — Mutation de traces
ROLE      : Applique des opérateurs de mutation sur les traces Jaeger
            produites par T_sel pour évaluer la qualité de la sélection.

PRINCIPE :
    En test de mutation classique, on modifie le code source.
    En boîte noire, on mute les traces Jaeger à la place.

    Pour chaque chemin t ∈ T_sel :
      1. Trace nominale = invocation_chain de t
      2. Appliquer les opérateurs de mutation
      3. Produire des mutants (traces altérées)

    Chaque mutant simule un comportement anormal du système :
      - span_deletion    : un service ne répond plus (span supprimé)
      - error_injection  : un service retourne une erreur
      - latency_injection: un service devient lent

OPÉRATEURS :
    span_deletion    : supprimer un span de la trace
    error_injection  : ajouter error=true + http_status=500 sur un span
    latency_injection: multiplier la durée d'un span par un facteur élevé

RÉSULTAT :
    Pour N chemins dans T_sel et K opérateurs :
    → N × K mutants maximum (limité par max_mutants_per_path)
"""

import json
import logging
import copy
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class TraceMutator:
    """
    Génère des mutants de traces depuis T_sel.
    """

    OPERATORS = ["span_deletion", "error_injection", "latency_injection"]

    def __init__(
        self,
        operators: Optional[List[str]] = None,
        latency_ms: int = 5000,
        max_mutants_per_path: int = 3,
    ):
        self.operators           = operators or self.OPERATORS
        self.latency_ms          = latency_ms
        self.max_mutants_per_path = max_mutants_per_path

    def _extract_services(self, tp: Dict) -> List[str]:
        """Extrait les services depuis un chemin."""
        services = tp.get("services", [])
        if services:
            return services
        chain = tp.get("invocation_chain", [])
        if chain:
            seen = []
            for pair in chain:
                for svc in pair:
                    if svc not in seen:
                        seen.append(svc)
            return seen
        return []

    def _build_spans(self, services: List[str], trace_id: str) -> List[Dict]:
        """
        Construit une liste de spans depuis la séquence de services.
        Chaque span représente un appel inter-service.
        """
        spans = []
        for i, svc in enumerate(services):
            spans.append({
                "span_id":   f"span_{i:03d}",
                "service":   svc,
                "duration":  50 + i * 10,
                "status":    "OK",
                "error":     False,
                "http_status": 200,
                "parent_span_id": f"span_{i-1:03d}" if i > 0 else None,
            })
        return spans

    def _apply_span_deletion(
        self, spans: List[Dict], target_idx: int
    ) -> List[Dict]:
        """Supprime le span à target_idx."""
        mutated = copy.deepcopy(spans)
        if 0 < target_idx < len(mutated):
            deleted = mutated.pop(target_idx)
            logger.debug("span_deletion → supprimé : %s", deleted["service"])
        return mutated

    def _apply_error_injection(
        self, spans: List[Dict], target_idx: int
    ) -> List[Dict]:
        """Injecte error=true sur le span à target_idx."""
        mutated = copy.deepcopy(spans)
        if target_idx < len(mutated):
            mutated[target_idx]["error"]       = True
            mutated[target_idx]["status"]      = "ERROR"
            mutated[target_idx]["http_status"] = 500
        return mutated

    def _apply_latency_injection(
        self, spans: List[Dict], target_idx: int
    ) -> List[Dict]:
        """Augmente la durée du span à target_idx."""
        mutated = copy.deepcopy(spans)
        if target_idx < len(mutated):
            original = mutated[target_idx]["duration"]
            mutated[target_idx]["duration"] = self.latency_ms
            logger.debug(
                "latency_injection → %s : %dms → %dms",
                mutated[target_idx]["service"], original, self.latency_ms,
            )
        return mutated

    def generate_mutants(self, t_sel: List[Dict]) -> List[Dict]:
        """
        Génère tous les mutants depuis T_sel.

        Pour chaque chemin t ∈ T_sel :
          - Construit les spans nominaux
          - Applique chaque opérateur sur un span cible
          - Produit max_mutants_per_path mutants par chemin

        Returns
        -------
        Liste de mutants, chaque mutant contenant :
          {
            "mutant_id":   str,
            "test_id":     str,
            "operator":    str,
            "target_span": str,
            "services":    List[str],
            "spans_nominal": List[Dict],
            "spans_mutated": List[Dict],
            "killed":      bool   (initialisé à False, mis à jour par le vérificateur)
          }
        """
        mutants = []
        n_paths = len(t_sel)

        for path_idx, tp in enumerate(t_sel):
            test_id  = tp.get("test_id", tp.get("trace_id", f"path_{path_idx:04d}"))
            services = self._extract_services(tp)

            if len(services) < 2:
                continue

            spans_nominal = self._build_spans(services, test_id)

            # Choisir le span cible : éviter le premier (racine)
            # et préférer les spans intermédiaires
            target_candidates = list(range(1, len(spans_nominal)))

            count = 0
            for operator in self.operators:
                if count >= self.max_mutants_per_path:
                    break

                # Cible = span au milieu de la chaîne
                target_idx = target_candidates[len(target_candidates) // 2]
                target_svc = spans_nominal[target_idx]["service"]

                if operator == "span_deletion":
                    spans_mutated = self._apply_span_deletion(
                        spans_nominal, target_idx
                    )
                elif operator == "error_injection":
                    spans_mutated = self._apply_error_injection(
                        spans_nominal, target_idx
                    )
                elif operator == "latency_injection":
                    spans_mutated = self._apply_latency_injection(
                        spans_nominal, target_idx
                    )
                else:
                    continue

                mutant_id = f"{test_id}__{operator}__{target_svc}"
                mutants.append({
                    "mutant_id":      mutant_id,
                    "test_id":        test_id,
                    "operator":       operator,
                    "target_service": target_svc,
                    "target_idx":     target_idx,
                    "services":       services,
                    "spans_nominal":  spans_nominal,
                    "spans_mutated":  spans_mutated,
                    "killed":         False,
                })
                count += 1

        logger.info(
            "TraceMutator — %d chemins → %d mutants générés "
            "(%d opérateurs × max %d/chemin)",
            n_paths, len(mutants),
            len(self.operators), self.max_mutants_per_path,
        )
        return mutants

    def save(self, mutants: List[Dict], output_path: str) -> None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(mutants, f, indent=2, ensure_ascii=False)
        logger.info("Mutants sauvegardés → %s (%d)", path, len(mutants))
