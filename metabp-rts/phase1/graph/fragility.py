"""
fragility.py
============
BLOC      : Bloc B — Construction G
ROLE      : Calcule F(si) = fragilité opérationnelle observée pour
            chaque service — 100% automatique depuis les données Jaeger,
            sans aucune entrée manuelle (remplace l'ancien M(si)/SIL).
            Formule :
              err_out(si) = Σ erreurs(si→sj) / Σ freq(si→sj)
                            pour tous sj successeurs de si
              F(si) = norm(err_out(si))
                    = err_out(si) / max(err_out sur tous les services)
            Un service avec beaucoup d'erreurs sortantes est
            opérationnellement fragile → score F élevé.
ENTREES   : Dict {(si,sj): EdgeWeight}  (sortie de weight_calculator)
SORTIES   : Dict {service_name: float}  — scores F dans [0, 1]
LIBRAIRIES: numpy
NOTE      : Si un service n'a aucun arc sortant, F(si) = 0.0
"""

# TODO: implémenter FragilityCalculator
# Méthodes attendues :
#   - compute(edge_weights) -> Dict[str, float]
#   - _aggregate_errors(edge_weights) -> Dict[str, Tuple[int, int]]
#   - _normalize(raw_scores) -> Dict[str, float]
