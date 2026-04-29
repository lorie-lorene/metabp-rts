"""
 Étape 1
 Construit le DG de propagation d'impact en inversant les arcs de G.

RATIONALE :
    G  : si → sj  signifie "si appelle sj"  (sens des appels)
    DG : sj → si  signifie "si sj change, l'impact remonte vers si"

    DG = (N, E_inv) où E_inv = { (sj, si) | (si, sj) ∈ G.E }
    w(eij_inv) = w(eij_original)

AMÉLIORATIONS v2 :
    - Tous les noeuds garantis dans adjacency même sans arcs sortants
    - Validation que delta_s ⊆ nodes (warning si service inconnu)
    - Log des noeuds isolés pour faciliter le debug
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class GraphInverter:

    def invert(
        self,
        graph_path: str,
        delta_s: Optional[List[str]] = None,
    ) -> Dict:
        with open(graph_path, encoding="utf-8") as f:
            graph = json.load(f)

        nodes = [n["id"] for n in graph.get("nodes", [])]
        node_set = set(nodes)
        original_links = graph.get("links", [])

        if delta_s:
            unknown = [s for s in delta_s if s not in node_set]
            if unknown:
                logger.warning(
                    "GraphInverter — services de delta_s absents de G : %s. "
                    "Ces services auront p0=1.0 mais sans voisins dans DG.",
                    unknown,
                )

        # Inversion des arcs 
        inverted_edges = []
        for link in original_links:
            src = link.get("target")
            tgt = link.get("source")
            if src and tgt:
                inverted_edges.append({
                    "source": src,
                    "target": tgt,
                    "w_ij":   round(link.get("w_ij", 0.0), 6),
                })

        # Tous les noeuds présents dans adjacency (même sans arcs sortants)
        adjacency: Dict[str, List] = {n: [] for n in nodes}

        for edge in inverted_edges:
            for key in (edge["source"], edge["target"]):
                if key not in adjacency:
                    adjacency[key] = []
                    nodes.append(key)
                    logger.warning("GraphInverter — noeud implicite ajouté : %s", key)
            adjacency[edge["source"]].append({
                "neighbor": edge["target"],
                "w_ij":     edge["w_ij"],
            })

        # Détection des noeuds isolés
        srcs = {e["source"] for e in inverted_edges}
        tgts = {e["target"] for e in inverted_edges}
        isolated = [n for n in nodes if n not in srcs and n not in tgts]
        if isolated:
            logger.info(
                "GraphInverter — %d noeud(s) isolé(s) : %s",
                len(isolated), isolated,
            )

        dg = {"nodes": nodes, "edges": inverted_edges, "adjacency": adjacency}
        logger.info(
            "GraphInverter — DG : %d noeuds | %d arcs inversés | %d isolés",
            len(nodes), len(inverted_edges), len(isolated),
        )
        return dg

    def save(self, dg: Dict, output_path: str) -> None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(dg, f, indent=2, ensure_ascii=False)
        logger.info("DG sauvegardé → %s", path)
