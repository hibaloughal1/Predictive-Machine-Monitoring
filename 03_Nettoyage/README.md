Exécuter le script `nettoyage_donees.py`.

* Charge les données de `system_metrics` depuis la base fusionnée `data/metrics_db_fusionnees.db`
* Vérifie et corrige les `machine_id` et les timestamps.
* Identifie les échantillons non fiables.
* Supprime les doublons.
* Trie les données par machine, run et timestamp.
* Exporte le dataset nettoyé vers `data/exports/cleaned_metrics.csv`.
