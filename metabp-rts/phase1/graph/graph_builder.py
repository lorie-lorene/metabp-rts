"""
Construit le graphe orienté pondéré G = (V, E) à partir
des arcs et poids calculés. Chaque noeud = un service,
chaque arc = une dépendance observée avec son poids w_ij.
ENTREES   : Dict {(si,sj): EdgeWeight} (sortie de weight_calculator.py)
SORTIES   : NetworkX DiGraph avec attributs :
            - noeud : service_name
            - arc   : w_ij, rate_ij, lat_norm, err_ij, freq
            Sérialisable en JSON via networkx.node_link_data()
            Persisté dans data/outputs/service_graph.json
"""


import json
import logging
from pathlib import Path
from typing import Dict, Tuple

import networkx as nx

from models.models import EdgeWeight

logger = logging.getLogger(__name__)

Edge = Tuple[str, str]


class GraphBuilder:
    def build(self, edge_weights: Dict[Edge, EdgeWeight]) -> nx.DiGraph:
        G = nx.DiGraph()

        for (source, target), ew in edge_weights.items():
            # Les noeuds sont ajoutés automatiquement par add_edge
            G.add_edge(
                source,
                target,
                w_ij=ew.w_ij,
                rate_ij=ew.rate_ij,
                lat_norm=ew.lat_norm,
                err_ij=ew.err_ij,
                freq=ew.freq,
            )

        logger.info(
            "GraphBuilder → G créé : %d services (noeuds) | %d dépendances (arcs)",
            G.number_of_nodes(), G.number_of_edges(),
        )
        return G
#Sérialise G en JSON (format node-link de NetworkX).
    def save(self, graph: nx.DiGraph, output_path: str) -> None:

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = nx.node_link_data(graph)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("Graphe G sauvegardé → %s", path)

    def load(self, input_path: str) -> nx.DiGraph:
        """
        Charge G depuis un fichier JSON persisté.
        """
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        graph = nx.node_link_graph(data, directed=True)
        logger.info(
            "Graphe G chargé depuis %s (%d noeuds, %d arcs)",
            input_path, graph.number_of_nodes(), graph.number_of_edges(),
        )
        return graph

    def summary(self, graph: nx.DiGraph) -> dict:

        return {
            "nodes": graph.number_of_nodes(),
            "edges": graph.number_of_edges(),
            "density": round(nx.density(graph), 4),
            "is_weakly_connected": nx.is_weakly_connected(graph),
            "avg_w_ij": round(
                sum(d["w_ij"] for _, _, d in graph.edges(data=True))
                / max(graph.number_of_edges(), 1),
                4,
            ),
        }