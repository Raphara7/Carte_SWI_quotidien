# 🌍 Suivi de l'Indice d'Humidité des Sols (SWI) en France

Ce projet génère quotidiennement et de manière entièrement automatisée une carte des anomalies d'humidité des sols (Soil Wetness Index - SWI) pour la France métropolitaine. Il compare la situation actuelle aux normales climatologiques de la période 1991-2020.

👉 **[Voir la carte mise à jour automatiquement ici](https://raphara7.github.io/Carte_SWI_quotidien/)** 

---

## ⚙️ Comment ça marche ? (Le Pipeline)

Ce dépôt utilise **GitHub Actions** pour exécuter un script Python tous les matins. Voici ce que fait le robot en arrière-plan :

1. **Extraction de la situation actuelle (Stratégie Double API)** : Afin de pallier les éventuels retards de publication des serveurs de Météo-France[cite: 1], le script teste automatiquement deux points de terminaison officiels sur data.gouv.fr (l'API historique de référence[cite: 1] et l'API alternative issue des données de changement climatique SIM[cite: 1]). Il compare les dates maximales disponibles et **retient dynamiquement l'API qui fournit la donnée la plus récente**[cite: 1]. La méthode s'inspire des suivis hydrologiques institutionnels, à l'instar de ceux documentés par la DREAL Bretagne[cite: 1].
2. **Préparation et récupération de l'historique** : L'historique de référence 1991-2020 provient originellement de [meteo.data.gouv.fr](https://meteo.data.gouv.fr/datasets/6569b27598256cc583c917a7) sous forme d'un fichier CSV extrêmement lourd (plusieurs Go). Pour rendre l'analyse instantanée, ce fichier a été nettoyé (conservation exclusive des colonnes utiles) et converti au format ultra-compressé **Parquet** (découpé par année). Pour contourner les limites de stockage de GitHub, ce jeu de données optimisé (réduit à ~120 Mo) est hébergé sur un Google Drive. Le script télécharge ces données automatiquement via la librairie `gdown`.
3. **Calcul de l'anomalie** : Le code isole instantanément les données du jour J dans l'historique Parquet (ex: tous les 22 juillet sur 30 ans), calcule la moyenne stricte, puis détermine l'écart relatif en pourcentage de la journée actuelle.
4. **Génération de la carte** : Utilisation de `matplotlib` et `geopandas` pour dessiner un raster calqué fidèlement sur les limites administratives (découpage strict) avec la palette de couleurs officielle. Un fichier `info.json` est également généré pour afficher dynamiquement la source et la date exacte sur la page web.
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
