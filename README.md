#  Suivi Anomalie de l'Indice d'Humidité des Sols (SWI) en France

Ce projet génère quotidiennement et de manière entièrement automatisée une carte des anomalies d'humidité des sols (Soil Wetness Index - SWI) pour la France métropolitaine. Il compare la situation actuelle aux normales climatologiques de la période 1991-2020.

 **[Voir la carte mise à jour automatiquement ici](https://raphara7.github.io/Carte_SWI_quotidien/)** 

--- 

##  Pipeline

Ce dépôt utilise **GitHub Actions** pour exécuter un script Python tous les matins. Voici ce que fait le robot en arrière-plan :

1. **Extraction de la situation actuelle (Stratégie Double API)** : Afin de pallier les éventuels retards de publication des serveurs de Météo-France, le script teste automatiquement deux points de terminaison officiels sur data.gouv.fr (l'API historique de référence et l'API alternative issue des données de changement climatique SIM. Il compare les dates maximales disponibles et **retient dynamiquement l'API qui fournit la donnée la plus récente**. La méthode s'inspire des suivis hydrologiques institutionnels, à l'instar de ceux documentés par la DREAL Bretagne.
2. **Préparation et récupération de l'historique** : L'historique de référence 1991-2020 provient de [meteo.data.gouv.fr](https://meteo.data.gouv.fr/datasets/6569b27598256cc583c917a7) sous forme de fichiers CSV. Pour l'analyse, ce jeu de données a été nettoyé et converti au format compressé **Parquet** (découpé par année). Pour contourner les limites de stockage de GitHub, ces données optimisées sont hébergées sur un Google Drive. Le script télécharge ces données automatiquement via la librairie `gdown`.
3. **Calcul de l'anomalie** : Le code isole les données du jour J dans l'historique Parquet, calcule la moyenne, puis détermine l'écart relatif en pourcentage de la journée actuelle.
4. **Génération de la carte** : Utilisation de `matplotlib` et `geopandas` pour dessiner un raster calqué sur les limites administratives avec la palette de couleurs officielle. Un fichier `info.json` est également généré pour afficher dynamiquement la source et la date exacte sur la page web.
5. **Déploiement Web** : L'image finale (`static/carte.png`) et les métadonnées sont publiées sur la branche `gh-pages` pour alimenter un site web statique en HTML.

---

## 🛠️ Technologies utilisées

* **Langage :** Python 3.10
* **Data Science & SIG :** `pandas`, `numpy`, `pyarrow`, `geopandas`, `shapely`
* **Dataviz :** `matplotlib`
* **Web & CI/CD :** HTML/CSS, JavaScript (pour l'affichage dynamique de la source), GitHub Actions, GitHub Pages

---

## 💻 Utilisation en local (Pour les développeurs)

Si vous souhaitez faire tourner ce projet sur votre propre machine :

1. Clonez ce dépôt :
   ```bash
   git clone [https://github.com/VOTRE_NOM/VOTRE_DEPOT.git](https://github.com/VOTRE_NOM/VOTRE_DEPOT.git)
   cd VOTRE_DEPOT
