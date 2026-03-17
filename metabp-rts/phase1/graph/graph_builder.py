"""
graph_builder.py
================
BLOC      : Bloc B — Construction G
ROLE      : Construit le graphe orienté pondéré G = (V, E) à partir
            des arcs et poids calculés. Chaque noeud = un service,
            chaque arc = une dépendance observée avec son poids w_ij.
ENTREES   : Dict {(si,sj): EdgeWeight} (sortie de weight_calculator.py)
SORTIES   : NetworkX DiGraph avec attributs :
            - noeud : service_name
            - arc   : w_ij, rate_ij, lat_norm, err_ij, freq
            Sérialisable en JSON via networkx.node_link_data()
            Persisté dans data/outputs/service_graph.json
LIBRAIRIES: networkx, json
"""

# TODO: implémenter GraphBuilder
# Méthodes attendues :
#   - build(edge_weights) -> nx.DiGraph
#   - save(graph, output_path) -> None
#   - load(input_path) -> nx.DiGraph
#   - summary(graph) -> dict   (nb noeuds, arcs, densité)
