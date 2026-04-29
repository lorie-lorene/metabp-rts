# MetaBP-RTS — Phase 3 : Optimisation de la Suite de Tests

> **Entrées** : Tier 1, Tier 2, CIT, mr_catalog (Phases 1 & 2)
> **Sorties** : T_sel = Tier1 ∪ Tier2_sel → Phase 4

---

## Vue d'ensemble

La Phase 3 reçoit le tiering produit par la Phase 2 et applique deux algorithmes successifs pour construire la suite de tests finale T_sel :

- **MRPS** *(Metamorphic Relation Path Signature)* — déduplique Tier 2 en regroupant les chemins redondants et en conservant un représentant par groupe
- **Binary PSO** *(Particle Swarm Optimization)* — sélectionne le sous-ensemble optimal de chemins dans Tier2_dédupliqué, maximisant la couverture des services tout en minimisant le nombre de chemins

Le résultat est une réduction significative de T sans perte de couverture sur les chemins critiques.

```
T_sel = Tier 1 (100% conservés) ∪ Tier2_sel (optimisé MRPS + PSO)
```

---

## Architecture des fichiers

```
phase3/
├── config/
│   └── phase3_config.yaml        ← paramètres MRPS et PSO
├── mrps/
│   └── mrps.py                   ← Étape 1 : déduplication MRPS
├── pso/
│   └── binary_pso.py             ← Étape 2 : sélection Binary PSO
├── scripts/
│   └── run_phase3.py             ← orchestrateur principal
└── data/
    └── outputs/
        ├── mrps_groups.json       ← groupes MRPS (signature → trace_ids)
        ├── tier2_deduplicated.json← Tier2 après MRPS (1 représentant/groupe)
        ├── pso_history.json       ← convergence PSO itération par itération
        ├── tier2_selected.json    ← Tier2_sel (sélection PSO optimale)
        ├── T_sel.json             ← suite finale Tier1 ∪ Tier2_sel
        └── phase3_report.json     ← métriques complètes
```

---

## Prérequis

- Phase 2 exécutée avec succès (artefacts dans `phase2/data/outputs/`)
- Environnement virtuel MetaBP-RTS activé
- `PyYAML` installé

```bash
source ~/Bureau/MEMOIRE-2026/metabp-project/venv-metabp/bin/activate
```

---

## Configuration — `phase3_config.yaml`

### Section MRPS

```yaml
mrps:
  mode: "enriched"      # structural | enriched
  representative: "cit" # cit | first
```

| Paramètre | Valeurs | Description |
|---|---|---|
| `mode` | `structural` | sig(t) = frozenset(services) uniquement |
| `mode` | `enriched` | sig(t) = (services, MR_associées) — recommandé |
| `representative` | `cit` | représentant = chemin avec score CIT maximal |
| `representative` | `first` | représentant = premier chemin du groupe |

### Section PSO

```yaml
pso:
  n_particles:    30      # taille du swarm
  max_iterations: 100     # nombre max d'itérations
  patience:       20      # arrêt si pas d'amélioration pendant N iter
  w:              0.7     # inertie
  c1:             1.5     # attraction vers pbest (cognitif)
  c2:             1.5     # attraction vers gbest (social)
  w_coverage:     0.6     # poids couverture services
  w_size:         0.3     # poids réduction nombre de chemins
  w_cit:          0.1     # poids scores CIT des services couverts
  threshold:      0.5     # seuil sigmoid pour binarisation
  init_strategy:  "greedy"# greedy | random
```

### Fitness function du PSO

```
fitness(p) =   w_coverage × couverture_services(p)
             + w_cit      × sum_cit_normalisé(p)
             - w_size     × taille_normalisée(p)
```

---

## Exécution

```bash
cd ~/Bureau/MEMOIRE-2026/metabp-rts/metabp-rts/phase3/scripts

python run_phase3.py --config ../config/phase3_config.yaml
```

---

## Séquence d'exécution — 3 étapes

### Étape 1 — MRPS : déduplication de Tier 2

MRPS calcule la signature de chaque chemin et regroupe les doublons.

**Problème résolu :** dans notre suite T de 3430 chemins, beaucoup sont structurellement identiques — le même scénario a été rejoué plusieurs fois lors de la génération du trafic. Les exécuter toutes ne détecte rien de plus qu'en exécuter une seule.

**Signature structurelle :**
```
sig(t) = frozenset(services traversés)
cancel → order → payment  et  cancel → order → payment  →  identiques
```

**Signature enrichie (mode recommandé) :**
```
sig(t) = (frozenset(services), frozenset(MR_associées))

MR(t) = { mr | service(mr) ∈ services(t) }

Deux chemins avec mêmes services mais MR différentes → NON redondants
→ ils vérifient des propriétés métamorphiques différentes
```

**Représentant :** dans chaque groupe de chemins redondants, le représentant est celui dont le score CIT est le plus élevé — il est le plus susceptible de détecter des régressions liées à ΔS.

**Résultat :**
```
Tier2 (2951 chemins) → Tier2_dédupliqué (N groupes uniques)
```

### Étape 2 — Binary PSO : sélection optimale

Le PSO cherche le sous-ensemble de Tier2_dédupliqué qui maximise la couverture des services tout en minimisant le nombre de chemins sélectionnés.

**Représentation d'une particule :**
```
particule = [1, 0, 1, 1, 0, ..., 1]
             ↑     ↑  ↑           ↑
           inclus  inclus      inclus
```

Chaque bit représente un chemin de Tier2_dédupliqué. `1` = inclus dans Tier2_sel.

**Mise à jour des vitesses :**
```
v_i(t+1) = w  × v_i(t)
          + c1 × r1 × (pbest_i - x_i)    ← attraction vers sa propre meilleure position
          + c2 × r2 × (gbest_i - x_i)    ← attraction vers la meilleure position globale

P(xi=1)  = sigmoid(v_i)
xi(t+1)  = 1 si random() < P(xi=1) sinon 0
```

**Initialisation gloutonne :** la première particule est initialisée par un algorithme glouton de couverture — on sélectionne itérativement le chemin qui couvre le plus de services non encore couverts. Cela accélère la convergence car le swarm part d'une bonne solution initiale.

**Résultat :**
```
Tier2_dédupliqué (N chemins) → Tier2_sel (M chemins optimaux)
```

### Étape 3 — Assemblage T_sel

```
T_sel = Tier 1 (conservé à 100%) ∪ Tier2_sel (optimisé)
```

Tier 1 n'est jamais touché — garantie de Recall sur les chemins critiques qui traversent les Services Écho-Impact. Tier 2 est réduit au minimum nécessaire pour maintenir la couverture des services non-critiques.

---

## Apport MetaBP-RTS vs Chen et al. (2023)

| Dimension | Chen et al. | MetaBP-RTS Phase 3 |
|---|---|---|
| Déduplication | Absente | MRPS — signature enrichie par MR |
| Sélection | Coupure binaire sur seuil p | Binary PSO — optimisation multi-objectif |
| Critère de sélection | CIT(s) ≥ p | fitness = couverture + CIT − taille |
| Chemins critiques | Mêlés avec les autres | Tier 1 conservé à 100% |
| Résultat | T_sel par seuillage | T_sel optimisé par heuristique |

---

## Artefacts produits → Phase 4

| Fichier | Contenu | Utilisé par Phase 4 |
|---|---|---|
| `T_sel.json` | Suite de tests finale — Tier1 ∪ Tier2_sel | Entrée principale |
| `phase3_report.json` | Métriques MRPS + PSO + réduction globale | Évaluation |
| `mrps_groups.json` | Groupes de déduplication | Analyse |
| `pso_history.json` | Courbe de convergence PSO | Visualisation |

---

## Nomenclature

**MRPS** *(Metamorphic Relation Path Signature)* — acronyme original, vérifié absent de la littérature de test de régression et de cybersécurité. Décrit le mécanisme : on calcule la signature (Signature) d'un chemin (Path) enrichie par ses relations métamorphiques (Metamorphic Relation).

**PathMR** *(Path-based Metamorphic Reduction)* — désigne le résultat produit par MRPS : la réduction de la suite de tests par signature métamorphique de chemin.

---

## Dépannage

**MRPS produit 0 groupes** : vérifier que `tier2_tests.json` contient bien une clé `tests` ou une liste directe de chemins.

**PSO ne converge pas** : augmenter `patience` ou réduire `n_particles`. Sur de petits graphes (peu de services), le PSO converge très rapidement — réduire `max_iterations` à 50.

**Tier2_sel = Tier2_dédupliqué entier** : la fitness `w_size` est trop faible. Augmenter `w_size` à 0.5 pour forcer une réduction plus agressive.

**Couverture < 100%** : certains services de Tier 2 ne sont couverts par aucun chemin — vérifier le trafic généré sur ces services en Phase 1.
