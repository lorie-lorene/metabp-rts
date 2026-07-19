# Package Résultats MetaBP-RTS — Chapitre 4

Trois scripts à lancer **depuis la racine** `~/Bureau/MEMOIRE-2026/metabp-rts/metabp-rts/`,
dans l'ordre. Ils produisent : affichage terminal soigné (captures d'écran), tableau
comparatif, et figures publiables.

## Prérequis

La campagne des 4 scénarios doit avoir tourné (config Recall=100 %), produisant :
- `final_results.csv` (les 4 scénarios MetaBP-RTS)
- `data/baselines/M_par_scenario/M_*.json` (les 4 ensembles révélateurs M)
- `data/baselines/Tsel/Tsel_*.json` (les 4 T_sel par scénario)

Si les M/Tsel manquent, relancer la sauvegarde des M (mutation locale ΔS) et copier
les T_sel par scénario — voir la campagne `restore_campagne.sh`.

## Lancement

```bash
cd ~/Bureau/MEMOIRE-2026/metabp-rts/metabp-rts

# 1. Affichage terminal des 4 scénarios (→ capture d'écran pour annexe / chapitre)
python3 /chemin/vers/1_afficher_resultats.py

# 2. Tableau comparatif baselines (→ capture + comparatif_baselines.csv)
python3 /chemin/vers/2_comparatif_baselines.py

# 3. Figures publiables (→ figures/*.png pour le chapitre 4)
python3 /chemin/vers/3_generer_figures.py
```

## Ce que chaque script produit

| Script | Sortie terminal | Fichier |
|--------|-----------------|---------|
| 1 | Tableau 4 scénarios + moyennes + lecture | — |
| 2 | Comparatif MetaBP vs Retest-All/Random/Firewall | `comparatif_baselines.csv` |
| 3 | Confirmation génération | `figures/fig_metabp_scenarios.png`, `figures/fig_comparatif_baselines.png`, `figures/fig_loi_topologique.png` |

## Usage dans le mémoire

- **Chapitre 4 (corps)** : les figures PNG de `figures/` (barres groupées, comparatif, loi topologique).
- **Annexe / preuve d'exécution** : captures d'écran des sorties terminal des scripts 1 et 2
  (montrent l'exécution réelle du pipeline, les |T_sel|, les métriques).
- **Ne PAS** mettre de capture Jupyter/terminal dans le corps du chapitre 4 — réserver aux annexes.

## Note honnêteté

Le comparatif utilise le **M local** (mutation ciblée sur ΔS). Firewall-0 est alors
optimal *par construction* sur les fautes locales : c'est une propriété à documenter,
pas à combattre. Le message est « MetaBP-RTS égale la qualité de Firewall SANS accès au
code source, et résout l'oracle en prime » — pas « MetaBP-RTS bat Firewall ».
