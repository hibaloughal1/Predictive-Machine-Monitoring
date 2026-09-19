# Predictive Machine Monitoring — Prétraitement et Modélisation

Ce dossier contient les notebooks et scripts utilisés pour préparer les données, créer le label de ralentissement, construire les variables de prédiction, entraîner les modèles et lancer le dashboard.

## Ordre d'exécution

Les notebooks sont à exécuter dans l'ordre suivant :

`01 → 03 → 04 → 05 → 06 → 07 → 08 → 09 → 10 → 11`

---

## 01 — `01_eda.ipynb`

**Rôle :** effectuer l'analyse exploratoire du dataset nettoyé.

**Input :**
- `data/processed/cleaned_metrics.csv`

**Ce code permet de :**
- charger et visualiser les données ;
- vérifier leur structure et leurs types ;
- convertir les timestamps ;
- rechercher les doublons ;
- analyser les valeurs manquantes ;
- calculer les statistiques descriptives ;
- visualiser les distributions et les valeurs aberrantes.

**Output :**
- analyses et graphiques affichés dans le notebook.

---

## 03 — `03_time_structure_audit.ipynb`

**Rôle :** vérifier que la structure temporelle des données est correcte.

**Input :**
- `data/processed/cleaned_metrics.csv`

**Ce code permet de :**
- analyser les machines et les `run_id` ;
- vérifier les timestamps ;
- détecter les timestamps invalides, dupliqués ou dans le mauvais ordre ;
- détecter les gaps importants ;
- vérifier les éventuels chevauchements entre runs.

**Output :**
- `reports/time_structure_audit.csv`
- `reports/run_summary.csv`

---

## 04 — `04_gap_investigation.ipynb`

**Rôle :** analyser les gaps détectés et segmenter les séries temporelles.

**Input :**
- `data/processed/cleaned_metrics.csv`
- `reports/time_structure_audit.csv`
- `reports/run_summary.csv`

**Ce code permet de :**
- analyser chaque gap ;
- étudier les 30 secondes précédant le gap ;
- rechercher les causes possibles du gap ;
- créer un nouveau segment après chaque gap ;
- vérifier si les segments sont suffisamment longs pour les horizons de prédiction.

**Output :**
- `reports/gap_investigation.csv`
- `reports/segment_summary.csv`
- `data/interim/segmented_metrics.csv`

---

## 05 — `05_gap_validation.ipynb`

**Rôle :** valider les diagnostics réalisés sur les gaps.

**Input :**
- `reports/gap_investigation.csv`
- `data/interim/segmented_metrics.csv`
- `data/processed/cleaned_metrics.csv`

**Ce code permet de :**
- vérifier les informations associées aux gaps ;
- analyser les indicateurs de ressources ;
- vérifier les éventuelles erreurs capteurs ;
- comparer les diagnostics avant et après validation.

**Output :**
- `reports/gap_validation.csv`
- `reports/gap_validation_summary.csv`

---

## 06 — `06_label_definition.ipynb`

**Rôle :** définir et comparer les règles permettant d'identifier un ralentissement.

**Input :**
- `data/interim/segmented_metrics.csv`
- `reports/segment_summary.csv`
- `reports/gap_validation.csv`
- `data/processed/cleaned_metrics.csv`

**Ce code permet de :**
- définir les seuils de CPU, RAM et autres ressources ;
- calculer des mesures sur des fenêtres temporelles ;
- construire plusieurs règles candidates de ralentissement ;
- mesurer la continuité des événements de ralentissement ;
- comparer la distribution des labels par machine et par run ;
- proposer une règle provisoire.

**Output :**
- `reports/label_rule_comparison.csv`
- `reports/label_distribution_by_machine.csv`
- `reports/label_distribution_by_run.csv`

---

## 07 — `07_future_label_creation.ipynb`

**Rôle :** créer le label indiquant si un ralentissement apparaîtra dans le futur.

**Input :**
- `data/interim/segmented_metrics.csv`
- `data/processed/cleaned_metrics.csv`

**Ce code permet de :**
- reconstruire le ralentissement actuel `slowdown_now` ;
- utiliser la règle de labeling retenue ;
- calculer les fenêtres temporelles de 30 et 60 secondes ;
- rechercher un ralentissement dans les horizons futurs ;
- créer les labels à **5 minutes et 10 minutes** ;
- vérifier que le calcul du label n'utilise pas de données provenant d'un autre segment.

**Output :**
- `data/interim/labeled_metrics.csv`
- `reports/future_label_summary.csv`
- `reports/future_label_by_machine.csv`
- `reports/future_label_by_run.csv`

---

## 08 — `08_prepare_dataset_for_split.ipynb`

**Rôle :** préparer le dataset labellisé avant le découpage Train / Validation / Test.

**Input :**
- `data/interim/labeled_metrics.csv`

**Ce code permet de :**
- vérifier la présence du label `slowdown_in_5min` ;
- vérifier les valeurs du label ;
- supprimer les éventuelles lignes ne pouvant pas être utilisées ;
- convertir le label dans le format attendu.

**Output :**
- `data/processed/metrics_labeling.csv`

---

## 09 — `09_temporal_split.ipynb`

**Rôle :** séparer les données en Train, Validation et Test en respectant l'ordre temporel.

**Input :**
- `data/processed/metrics_labeling.csv`

**Ce code permet de :**
- regrouper les données par `run_id` ;
- calculer la durée et les caractéristiques de chaque run ;
- attribuer les runs chronologiquement aux trois ensembles ;
- conserver un run complet dans un seul ensemble ;
- vérifier l'absence de fuite temporelle.

**Output :**
- `data/processed/train_dataset.csv`
- `data/processed/val_dataset.csv`
- `data/processed/test_dataset.csv`
- `reports/split_summary.csv`

---

## 10 — `10_feature_engineering.ipynb`

**Rôle :** créer les variables utilisées par les modèles.

**Input :**
- `data/processed/train_dataset.csv`
- `data/processed/val_dataset.csv`
- `data/processed/test_dataset.csv`

**Ce code permet de créer notamment :**
- les valeurs précédentes (`lag`) ;
- les premières différences ;
- les moyennes glissantes ;
- les écarts-types glissants ;
- les maximums glissants ;
- des variables liées au domaine CPU / RAM / système ;
- des indicateurs de valeurs manquantes.

Les calculs sont réalisés séparément pour Train, Validation et Test et utilisent uniquement les observations courantes et passées.

**Output :**
- `data/processed/train_features.csv`
- `data/processed/val_features.csv`
- `data/processed/test_features.csv`

---

## 11 — `11_preprocessing_and_modeling.ipynb`

**Rôle :** effectuer le preprocessing, entraîner les modèles et sélectionner le meilleur modèle.

**Input :**
- `data/processed/train_features.csv`
- `data/processed/val_features.csv`
- `data/processed/test_features.csv`

**Ce code permet de :**
- séparer les variables explicatives et le target `slowdown_in_5min` ;
- analyser les valeurs manquantes et l'équilibre des classes ;
- construire les pipelines de preprocessing ;
- imputer les valeurs manquantes ;
- standardiser les variables lorsque nécessaire ;
- entraîner plusieurs modèles ;
- évaluer les modèles sur la validation ;
- sélectionner le meilleur modèle ;
- effectuer l'évaluation finale sur le test ;
- calculer Accuracy, Precision, Recall, F1-score et ROC AUC.

**Modèles utilisés :**
- Logistic Regression
- Random Forest
- XGBoost
- LightGBM

**Output :**
- `reports/model_comparison.csv`
- `models/best_slowdown_model.joblib`

---

# Autres fichiers

## `12_run_dashboard.py`

Script principal permettant de démarrer le dashboard.

**Input :**
- `models/best_slowdown_model.joblib`
- les composants du dossier `dashboard/`

**Rôle :**
- lancer le serveur du dashboard avec Uvicorn.

---

## `dashboard/`

Contient le code du dashboard :

- `app.py` → application et endpoints du dashboard.
- `runtime.py` → collecte des métriques, création des features, prédiction et gestion des alertes.
- `static/` → interface web du dashboard.

Le modèle utilisé par le dashboard est :

`models/best_slowdown_model.joblib`

Les données et prédictions du dashboard sont enregistrées dans :

`data/dashboard.db`

---

## `RUN_DASHBOARD.bat`

Script Windows permettant de lancer facilement le dashboard sans exécuter manuellement la commande Python.

---

## `requirements-dashboard.txt`

Liste des bibliothèques Python nécessaires au fonctionnement du dashboard.

Installation :

```bash
pip install -r requirements-dashboard.txt
```

---

## `DASHBOARD.md`

Documentation spécifique au fonctionnement et à l'utilisation du dashboard.

---

## `tests/`

Contient les tests automatisés du dashboard.

- `test_dashboard.py` → vérifie le fonctionnement de différents composants du dashboard.

---

## Dossiers de données

### `data/processed/`

Contient les datasets préparés pour les différentes étapes du pipeline :

- données nettoyées ;
- données labellisées ;
- Train / Validation / Test ;
- datasets après Feature Engineering.

### `data/interim/`

Contient les données intermédiaires produites pendant les étapes de segmentation et de labeling.

### `reports/`

Contient les rapports et résultats produits pendant les différentes étapes du pipeline.

### `models/`

Contient les modèles entraînés et sauvegardés.
