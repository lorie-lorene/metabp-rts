"""
test_echo_dormant.py
====================
BLOC      : Tests Phase 1
ROLE      : Vérifie le Théorème de Sécurité d'Exclusion et la
            classification Écho-Dormant / Non-Dormant.
            Cas testés :
              - Service avec Θ_dormant = 0.45 → is_dormant = True
              - Service avec Θ_dormant = 0.35 → is_dormant = False
              - Théorème : tout Non-Dormant a Θ < 0.70 quoi que soit B(si)
                  car Θ = Θ_dormant + 0.30×B ≤ 0.35 + 0.30×1.0 = 0.65 < 0.70
              - S_dormant contient exactement les services avec Θ_dormant ≥ 0.40
              - Renormalisation : ω_C + ω_P + ω_F = 1.0 (tolérance 1e-9)
              - Cas limite Θ_dormant = 0.40 exactement → is_dormant = True
ENTREES   : Scores synthétiques couvrant les cas limites (définis inline)
SORTIES   : Rapport pytest (pass/fail) — test de propriété formelle
LIBRAIRIES: pytest
"""

# TODO: écrire les fixtures et les fonctions de test
# Structure attendue :
#   - FIXTURE_SCORES_ABOVE_THRESHOLD : Dict  (Θ_dormant = 0.45)
#   - FIXTURE_SCORES_BELOW_THRESHOLD : Dict  (Θ_dormant = 0.35)
#   - FIXTURE_SCORES_BOUNDARY        : Dict  (Θ_dormant = 0.40)
#   - test_classification_above()
#   - test_classification_below()
#   - test_boundary_case()
#   - test_safety_theorem()         ← propriété formelle clé
#   - test_omega_normalization()
#   - test_dormant_set_membership()
