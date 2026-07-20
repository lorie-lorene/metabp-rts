Bonne démarche : avant de te lister ce qu'il manque, je vérifie ce qui est **déjà dans le dépôt** pour ne te demander que le strict nécessaire. Je regarde `final_results.csv`, le dossier `data/` et le dossier `phase4/`.Le dossier `phase4/metrics/` est probablement là où vivent tes résultats FCS/Pmr (QR3). Je vérifie s'ils sont déjà committés.Vérification faite. Voici l'état réel : je peux déjà écrire **une partie** du chapitre, mais **trois sections sur cinq sont bloquées** faute de résultats committés — et je ne les inventerai pas.

## Ce que j'ai déjà (ne rien ajouter)

- **Résultats de sélection S1–S4** (EN, Recall, Precision, F) → `scenarios_results.csv` + `final_results.csv` ✓
- **Comparatif 6 techniques × 4 scénarios** (avec colonne accès) → `comparatif_baselines.csv` ✓
- **3 figures propres** → `fig_metabp_scenarios.png`, `fig_loi_topologique.png`, `fig_comparatif_baselines.png` ✓

Avec ça seul, je peux rédiger **§4.2.2 (QR2, partie sélection)** et **§4.3.1 (comparaison)**. Le reste est bloqué.

## Ce qui BLOQUE la rédaction (sans ça, il faudrait inventer)

Le plus simple : **committe les fichiers de sortie que ton pipeline génère déjà** (JSON ou CSV), plutôt que de les reconstruire à la main. Il me manque quatre lots :

**1. Résultats QR1 — Écho-Dormants et résonance** *(bloque §4.2.1, Fig 4.2, T4.1)*
La sortie de Phase 1 + Phase 2 avec :
- la liste des **9 Écho-Dormants** et leur score `Θ_dormant` (+ les composantes C, P, F par service) ;
- les **poids EWM-CRITIC** ω_C, ω_P, ω_F ;
- le **seuil** τ_dormant et le **gap** de séparation K-means (le 0,1596 dont je parlais est non vérifié) ;
- la **table de résonance** : pour chaque scénario, quels Écho-Dormants sont devenus Écho-Impact (c'est ce qui prouve le **9/10**).
> Format idéal : `results/qr1_echo_dormant.csv` (service, C, P, F, Θ, dormant) + `results/qr1_resonance.csv` (scenario, service, dormant, echo_impact) + un petit `results/weights.json`.

**2. Résultats QR3 — validation sans oracle** *(bloque totalement §4.2.3)*
Actuellement `phase4/metrics/` ne contient que `recall.py` (du code, **aucun résultat**). Il me faut la sortie chiffrée de Phase 4 :
- **FCS global** + FCS **par opérateur** (latence / erreur / suppression) ;
- **Pmr** (précision métamorphique) ;
- nombre de **mutants total / tués**.
> Format idéal : `results/qr3_validation.csv` (scenario, FCS_total, FCS_latence, FCS_erreur, FCS_suppression, Pmr, mutants_total, mutants_tues).

**3. ET — gain de temps** *(bloque la moitié de §4.2.2)*
Aucun CSV ne contient ET, seulement EN. Il me faut, par scénario, soit **ET directement**, soit ses composantes **T_O, T_R, T_S**.
> Format idéal : `results/qr2_et.csv` (scenario, T_O, T_R, T_S, ET).

**4. Catalogue MR réel** *(bloque T4.2, la section que tu veux mettre en avant)*
La sortie du catalogue Phase 1 pour Train-Ticket : pour chaque MR — type (fonctionnelle/comportementale), service, transformation, relation, et le **seuil appris** (θ_lat P99, θ_err, θ_cmp) pour les comportementales.
> Format idéal : committe le `mr_catalogue.json` que Phase 1 produit déjà.

## Images à ajouter

- **Fig 4.1 — graphe G** : un **export propre** (PNG/PDF) de la visualisation HTML de Phase 1. Surtout **pas** la capture terminal `2026-07-17`.
- **Fig 4.2 — Θ_dormant + seuil** : à **générer** (elle n'existe pas parmi les 3 PNG). Ton `3_generer_figures.py` peut la produire une fois le lot QR1 committé.
- **Captures terminal / Jaeger UI** (dont `phase4/capture/` et la capture existante) → elles vont en **annexe** comme preuve de reproductibilité, jamais dans le corps.

## À me donner directement (pas un fichier)

La **configuration matérielle et logicielle** de la machine d'expérimentation, pour T4.1 / §4.1.1 : CPU, RAM, OS, version Docker, version Jaeger, version Python. Je ne l'ai nulle part de vérifié (la config Linux Mint / i5 que j'ai en mémoire venait d'un **autre** mémoire, pas du tien — à ne pas réutiliser).

## Ce que je NE te demande pas (je le lis moi-même)

Les **paramètres** (α=0,5 / β=0,3 / γ=0,2, params BPSO, k=3, δ, Λ) sont dans tes fichiers de config du dépôt (`phase*/config/`) — je les lirai directement pour T4.4, ne les recopie pas.

---

En résumé, quatre fichiers de résultats à committer (`qr1_echo_dormant.csv`, `qr1_resonance.csv`, `qr3_validation.csv`, `qr2_et.csv`), le `mr_catalogue.json`, deux images (graphe G propre + Fig 4.2), et la config machine par message. Le reste, je l'ai ou je le lis.

Veux-tu que je te prépare un petit script qui extrait ces quatre CSV depuis les sorties existantes de tes phases, pour t'éviter de les monter à la main ?