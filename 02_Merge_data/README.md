### Script de fusion des bases de données

Exécuter le script `combin_db.py`.

* Recherche automatiquement toutes les bases de données `.db` présentes dans le dossier `data/`.
* Exclut la base de données de sortie `metrics_db_fusionnees.db` afin d’éviter de la fusionner avec elle-même.
* Lit les différentes tables présentes dans chaque base SQLite.
* Fusionne les données des tables `schema_meta`, `runs`, `events`, `capabilities` et `system_metrics`.
* Supprime les doublons en utilisant une clé spécifique pour chaque table.
* Régénère les identifiants auto-incrémentés des tables `events` et `system_metrics` afin d’éviter les collisions entre les différentes bases.
* Trie les données après la fusion lorsque les colonnes nécessaires sont disponibles.
* Crée une nouvelle base de données SQLite contenant toutes les tables fusionnées.
* Crée des index sur certaines colonnes afin d’améliorer les performances des recherches.
* Enregistre les résultats dans :
  * `data/metrics_db_fusionnees.db`
  * `data/metrics_db_fusionnees.csv`