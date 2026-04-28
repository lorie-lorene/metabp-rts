# metabp-rts
# MetaBP-RTS — Phase 2 : Analyse d'Impact par Belief Propagation

> **Entrées** : artefacts Phase 1 + ΔS (services modifiés)  
> **Sorties** : CIT, S_écho-impact, Tier 1 / Tier 2 → Phase 3

---

## Vue d'ensemble

La Phase 2 reçoit le graphe de services G et les scores C/P/F/Θ produits par la Phase 1, ainsi que ΔS — la liste des services qui viennent d'être modifiés. Elle calcule, par propagation de croyances (Belief Propagation), la probabilité que chaque service soit impacté par ce changement. Elle produit ensuite la Change Impact Table (CIT), identifie les Services Écho-Impact, et prépare le tiering Tier 1 / Tier 2 pour la Phase 3.

### Principe de résonance différée

```
Écho-Dormant (Phase 1) + ΔS  →  Écho-Impact (Phase 2)
```

Un service Écho-Dormant identifié en Phase 1 possède une forte centralité et fragilité structurelle. Après un changement ΔS, la BP lui envoie davantage de messages (forte centralité) qu'il amplifie (fort potentiel local ψ). Il entre en **résonance** : il reçoit l'impact, l'amplifie, et le repropage à travers ses propres chaînes de dépendances sortantes. Il devient un **Service Écho-Impact** — source secondaire de propagation de régression. Tous les chemins de test qui le traversent, en entrée comme en sortie, deviennent urgents.

---

## Architecture des fichiers

```
phase2/
├── config/
│   └── phase2_config.yaml      
├── bp/
│   ├── graph_inverter.py        
│   ├── bp_initializer.py        
│   ├── bp_propagator.py         
│   └── cit_builder.py          
├── selection/
│   └── test_scorer.py           
├── scripts/
│   └── run_phase2.py            
└── data/
    └── outputs/                 
        ├── dg_graph.json
        ├── change_impact_table.json
        ├── echo_impact_services.json
        ├── theta_complet.json
        ├── test_scores.json
        ├── selected_tests.json
        ├── tier1_tests.json
        └── tier2_tests.json
```

---

## Prérequis

- Phase 1 exécutée avec succès (artefacts dans `phase1/data/outputs/`)
- Environnement virtuel MetaBP-RTS activé
- `PyYAML` installé (`pip install pyyaml`)

```bash
source ~/Bureau/MEMOIRE-2026/metabp-project/venv-metabp/bin/activate
```

---

## Configuration — `phase2_config.yaml`

C'est le seul fichier à modifier entre deux expériences. Il contrôle tout sans toucher au code Python.

```yaml
belief_propagation:
  mode: "noisy_or"       # noisy_or (MetaBP-RTS) | max_product (Chen et al.)
  compare: false         # true = lance les deux modes et produit un rapport
  tau_impact: 0.30       # seuil identification Service Écho-Impact
  omega_B: 0.30          # poids de B(si) dans Θ_complet
  max_iterations: 100
  convergence_threshold: 1.0e-6

initializer:
  use_phase1_scores: true  # true = MetaBP-RTS | false = Chen et al. binaire

selection:
  strategy: "existent"   # existent | complete | k_existent
  k: 2
  threshold_p: null      # null = min non-zero de la CIT
```

### Modes de propagation

| Mode | Formule | Quand l'utiliser |
|---|---|---|
| `noisy_or` | `P(affecté) = 1 - ∏(1 - w_ki × p_t(sk))` | Plusieurs services modifiés simultanément |
| `max_product` | `p_{t+1} = max(p_t, max_j m_ji)` | Comparaison avec Chen et al. 2023 |

Sur des graphes à faible degré entrant (peu de parents par service), les deux modes convergent vers des résultats proches. La différence est significative lorsque plusieurs parents sont simultanément affectés.

---

## Exécution

```bash
cd ~/Bureau/MEMOIRE-2026/metabp-rts/metabp-rts/phase2/scripts
```

### Cas standard

```bash
python run_phase2.py \
  --config ../config/phase2_config.yaml \
  --delta-s ts-cancel-service
```

### Plusieurs services modifiés

```bash
python run_phase2.py \
  --config ../config/phase2_config.yaml \
  --delta-s ts-admin-basic-info-service ts-cancel-service
```

### Forcer un mode spécifique (surcharge la config)

```bash
python run_phase2.py \
  --config ../config/phase2_config.yaml \
  --delta-s ts-cancel-service \
  --mode max_product
```

### Comparaison des deux modes (section expérimentale)

```bash
python run_phase2.py \
  --config ../config/phase2_config.yaml \
  --delta-s ts-cancel-service \
  --compare
```

Produit `data/outputs/bp_mode_comparison.json` avec les différences service par service — utile pour la section expérimentale du mémoire.

### Conserver l'historique des itérations BP

```bash
python run_phase2.py \
  --config ../config/phase2_config.yaml \
  --delta-s ts-cancel-service \
  --history
```

---

## Séquence d'exécution — 5 étapes

### Étape 1 — Inversion G → DG (`graph_inverter.py`)

Le graphe G de Phase 1 modélise les appels inter-services : `si → sj` signifie "si appelle sj". Pour la propagation d'impact, on a besoin de savoir "si sj change, qui sera touché ?" — c'est-à-dire tous ceux qui dépendent de sj.

On inverse donc tous les arcs :
```
G  : si → sj  (si appelle sj)
DG : sj → si  (si sj change, l'impact remonte vers si)
```

Les poids `w_ij` sont conservés. Tous les noeuds sont présents dans la liste d'adjacence même sans arcs sortants — sinon les messages BP vers eux seraient silencieusement perdus.

### Étape 2 — Initialisation enrichie p0 (`bp_initializer.py`)

Apport MetaBP-RTS vs Chen et al. :

| Service | Chen et al. | MetaBP-RTS |
|---|---|---|
| si ∈ ΔS | ψ = 1.0 | ψ = 1.0 |
| si ∈ S_dormant | ψ = 0.0 | ψ = Θ(si) |
| autre | ψ = 0.0 | ψ = 0.0 |

Un service Écho-Dormant a un potentiel local ψ(si) = Θ(si) > 0 dès le départ. Il amplifie les messages BP entrants dès la première itération — c'est le principe de résonance différée.

### Étape 3 — Propagation BP (`bp_propagator.py`)

**Mode Noisy-OR (MetaBP-RTS) :**
```
P(si = sain)    = ∏_{sk ∈ parents(si)} (1 - w_ki × p_t(sk))
P(si = affecté) = 1 - P(si = sain)
p_{t+1}(si)     = max(p_t(si), P(si = affecté))
```

**Mode Max-Product (Chen et al. 2023) :**
```
m_ij            = p_t(si) × w(eij)
p_{t+1}(si)     = max(p_t(si), max_j m_ji)
```

Dans les deux modes :
- `p_{t+1}(si) ≥ p_t(si)` — monotone croissante, convergence garantie
- Convergence détectée quand `max|p_{t+1} - p_t| < epsilon`

### Étape 4 — CIT + Θ_complet + S_écho-impact (`cit_builder.py`)

**Change Impact Table :**
```
CIT = { si : p_final(si) }   avec p_final ∈ [0, 1]
```

**Score Θ_complet (contribution MetaBP-RTS) :**
```
Θ_complet(si) = Θ_dormant(si) + ω_B × CIT(si)
```
Ce score unifie la fragilité structurelle statique (Phase 1) et la probabilité d'impact dynamique (Phase 2) en un seul indicateur.

**Identification S_écho-impact :**
```
S_écho-impact = { si | CIT(si) > τ_impact  ET  si ∉ ΔS }
```

Le flag `resonance: true` dans `echo_impact_services.json` indique qu'un service était Écho-Dormant en Phase 1 et est devenu Écho-Impact en Phase 2 — **validation empirique du principe de résonance différée**.

### Étape 5 — Tiering + Scoring des tests (`test_scorer.py`)

**Score d'un chemin :**
```
score(tp) = max{ CIT(si) | si ∈ S_tp }
```
Un chemin est aussi urgent que le service le plus impacté qu'il traverse.

**Tiering :**
```
Tier 1 : chemin traverse au moins un service de S_écho
         → conservé à 100% — Recall garanti sur chemins critiques
Tier 2 : chemin ne traverse aucun service de S_écho
         → candidat au PSO Phase 3
```

**Stratégies de sélection (Chen et al. 2023) :**

| Stratégie | Condition | Recall | Réduction |
|---|---|---|---|
| `existent` | ∃s ∈ S_tp : CIT(s) ≥ p | 100% | Faible |
| `complete` | ∀s ∈ S_tp : CIT(s) ≥ p | < 100% | Forte |
| `k_existent` | \|{s : CIT(s)≥p}\| ≥ k | Variable | Ajustable |

---

## Résultats obtenus — Train-Ticket

### ΔS = `ts-cancel-service`

```
Itérations BP         : 2 (convergé)
Services Écho-Impact  : 3 (τ=0.30)
Résonance confirmée   : 1/3
Tier 1                : 7 tests    (0.2%)
Tier 2                : 3423 tests (99.8%)
Top Écho-Impact :
  ts-ticketinfo-service  CIT=0.5355 | Θ_complet=0.6962 ← RÉSONANCE
  ts-travel-service      CIT=0.4121 | Θ_complet=0.4251
  ts-travel2-service     CIT=0.3516 | Θ_complet=0.3666
```

### ΔS = `ts-admin-basic-info-service`

```
Itérations BP         : 2 (convergé)
Services Écho-Impact  : 4 (τ=0.30)
Résonance confirmée   : 2/4
Tier 1                : 479 tests  (14.0%)
Tier 2                : 2951 tests (86.0%)
Top Écho-Impact :
  ts-cancel-service      CIT=0.5671 | Θ_complet=0.7372 ← RÉSONANCE
  ts-ticketinfo-service  CIT=0.5355 | Θ_complet=0.6962 ← RÉSONANCE
  ts-travel-service      CIT=0.4121 | Θ_complet=0.4251
  ts-travel2-service     CIT=0.3516 | Θ_complet=0.3666
```

---

## Artefacts produits → Phase 3

| Fichier | Contenu | Utilisé par Phase 3 |
|---|---|---|
| `dg_graph.json` | Graphe DG avec arcs inversés | Debug / visualisation |
| `change_impact_table.json` | CIT : score d'impact par service | Fitness function PSO |
| `echo_impact_services.json` | S_écho + flag résonance + stats | Tiering |
| `theta_complet.json` | Θ_complet par service | Priorisation |
| `test_scores.json` | Tous les 3430 chemins scorés | Analyse |
| `selected_tests.json` | Sélection selon stratégie | Intermédiaire |
| `tier1_tests.json` | **Tier 1 — conservés à 100%** | Phase 3 entrée directe |
| `tier2_tests.json` | **Tier 2 — candidats PSO** | Phase 3 entrée PSO |
| `bp_mode_comparison.json` | Comparaison Noisy-OR vs Max-Product | Section expérimentale mémoire |

---

## Apport MetaBP-RTS vs Chen et al. (2023)

| Dimension | Chen et al. | MetaBP-RTS |
|---|---|---|
| Initialisation p0 | Binaire {0, 1} | Enrichie : ψ(si) = Θ(si) si Écho-Dormant |
| Modèle de propagation | Max-Product | Noisy-OR (par défaut) + Max-Product (comparaison) |
| Score de synthèse | CIT seul | Θ_complet = Θ_dormant + ω_B × CIT |
| Sélection des tests | Coupure binaire | Tiering Tier 1 / Tier 2 + PSO Phase 3 |
| Validation | Absente | Phase 4 : tests métamorphiques |

---

## Dépannage

**Tier 1 = 0 tests** : les Services Écho-Impact ne sont pas traversés dans T. Générer du trafic ciblé sur les endpoints correspondants puis relancer Phase 1 avant Phase 2.

**Réduction = 0%** : le seuil p (min non-zero CIT) est trop bas car ΔS est très connecté. Augmenter `tau_impact` dans la config ou utiliser la stratégie `k_existent` avec k=2.

**BP ne converge pas** : augmenter `max_iterations` ou vérifier que `w_ij < 1` pour tous les arcs (garantit la convergence mathématique).

**Services de ΔS absents du graphe** : warning loggé — ces services auront p0=1.0 mais sans voisins dans DG, leur impact ne se propagera pas. Vérifier `services_map.yaml` Phase 1.