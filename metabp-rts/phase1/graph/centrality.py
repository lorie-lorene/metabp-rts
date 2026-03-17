"""
centrality.py
=============
BLOC      : Bloc B — Construction G
ROLE      : Calcule C(si) = centralité structurelle pour chaque service :
              C(si) = α × norm(fan_in(si)) + β × norm(fan_out(si))
            fan_in  = nombre de services qui appellent si
            fan_out = nombre de services que si appelle
            norm(x) = x / max(x sur tous les services)
ENTREES   : NetworkX DiGraph G
SORTIES   : Dict {service_name: float}  — scores C dans [0, 1]
LIBRAIRIES: networkx
"""

# TODO: implémenter CentralityCalculator
# Méthodes attendues :
#   - compute(graph) -> Dict[str, float]
#   - _fan_in(graph) -> Dict[str, int]
#   - _fan_out(graph) -> Dict[str, int]
#   - _normalize(scores) -> Dict[str, float]
