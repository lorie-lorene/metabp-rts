"""
echo_dormant.py
===============
BLOC      : Bloc B — Construction G
ROLE      : Calcule Θ_dormant(si) et classifie chaque service :
              Θ_dormant(si) = ω_C×C(si) + ω_P×P(si) + ω_F×F(si)
            Classification :
              Θ_dormant >= τ_dormant (0.40) → Service Écho-Dormant
              Θ_dormant <  τ_dormant        → Service Non-Dormant
            Propriété garantie (Théorème de Sécurité d'Exclusion) :
              Tout service Non-Dormant ne peut PAS être un
              Service Écho-Impact en Phase 2.
              Preuve : Θ(si) = Θ_dormant(si) + ω3×B(si)
                             < 0.40 + 0.30×1.0 = 0.70 = τ_echo ∎
ENTREES   : - Dict C : {service_name: float}
            - Dict P : {service_name: float}
            - Dict F : {service_name: float}
            - config  : {tau_dormant, omega_C, omega_P, omega_F}
SORTIES   : - List[ServiceScore] avec theta_dormant et is_dormant
            - S_dormant : List[str]  (noms des services Écho-Dormants)
            Persisté dans data/outputs/service_scores.json
LIBRAIRIES: numpy, dataclasses, json
"""

# TODO: implémenter EchoDormantClassifier
# Méthodes attendues :
#   - __init__(tau_dormant, omega_C, omega_P, omega_F)
#   - classify(C_scores, P_scores, F_scores) -> List[ServiceScore]
#   - get_dormant_set(scores) -> List[str]
#   - save(scores, output_path) -> None
#   - verify_safety_theorem(scores) -> bool
#     (vérifie que la liste Non-Dormant ne contient aucun candidat Écho)
