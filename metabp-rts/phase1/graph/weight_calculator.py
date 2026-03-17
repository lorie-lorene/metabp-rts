"""
weight_calculator.py
====================
BLOC      : Bloc B — Construction G
ROLE      : Calcule les trois composantes du poids w_ij pour chaque
            arc (si → sj) depuis l'edge_list :
              - rate_ij  = freq_ij / total_spans(si)
              - lat_norm = mean(duration si→sj) / max(duration global)
              - err_ij   = erreurs(si→sj) / freq_ij
              - w_ij     = α×rate + β×lat_norm + γ×err
ENTREES   : edge_list : List[Tuple[str, str, int, bool]]
            config    : {alpha, beta, gamma}
SORTIES   : Dict {(si,sj): EdgeWeight}
LIBRAIRIES: numpy, collections
"""

# TODO: implémenter WeightCalculator
# Méthodes attendues :
#   - __init__(alpha, beta, gamma)
#   - compute(edge_list) -> Dict[Tuple, EdgeWeight]
#   - _compute_rates(edge_list) -> Dict
#   - _compute_latencies(edge_list) -> Dict
#   - _compute_errors(edge_list) -> Dict
#   - _normalize(values) -> Dict
