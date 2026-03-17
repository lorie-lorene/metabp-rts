"""
propagation_coeff.py
====================
BLOC      : Bloc B — Construction G
ROLE      : Calcule P(si) = coefficient de propagation pour chaque
            service — mesure la transmissivité logique vers les
            successeurs directs :
              P(si) = (1 / |Succ(si)|) × Σ w_ij   pour sj ∈ Succ(si)
            Si |Succ(si)| = 0, alors P(si) = 0.
ENTREES   : NetworkX DiGraph G (avec attribut w_ij sur chaque arc)
SORTIES   : Dict {service_name: float}  — scores P dans [0, 1]
LIBRAIRIES: networkx, numpy
"""

# TODO: implémenter PropagationCalculator
# Méthodes attendues :
#   - compute(graph) -> Dict[str, float]
#   - _successors_weights(graph, node) -> List[float]
