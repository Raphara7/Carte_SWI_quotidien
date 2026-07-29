# 🌍 Suivi de l'Indice d'Humidité des Sols (SWI) en France

Ce projet génère quotidiennement et de manière entièrement automatisée une carte des anomalies d'humidité des sols (Soil Wetness Index - SWI) pour la France métropolitaine. Il compare la situation actuelle aux normales climatologiques de la période 1991-2020.

👉 **[Voir la carte mise à jour automatiquement ici](https://raphara7.github.io/NOM_DE_TON_DEPOT/)** *(N'oublie pas de remplacer ce lien par ton vrai lien GitHub Pages !)*

---

## ⚙️ Comment ça marche ? (Le Pipeline)

Ce dépôt utilise **GitHub Actions** pour exécuter un script Python tous les matins. Voici ce que fait le robot en arrière-plan :

1. **Extraction de la situation actuelle** : Téléchargement du dernier fichier d'observation Météo-France via l'API de [data.gouv.fr](https://www.data.gouv.fr/fr/datasets/donnees-quotidiennes-dhumidite-des-sols-produites-par-le-modele-sim2-de-meteo-france-1/).
2. **Récupération de l'historique** : Pour contourner les limites de stockage de GitHub, les données climatologiques historiques de référence (1991-2020) sont stockées au format ultra-compressé `.parquet` sur un Google Drive. Le script télécharge ces données automatiquement via `gdown`.
3. **Calcul de l'anomalie** : Le code isole les données du jour J dans l'historique (ex: tous les 22 juillet sur 30 ans), calcule la moyenne stricte, puis détermine l'écart relatif en pourcentage de la journée actuelle.
4. **Génération de la carte** : Utilisation de `matplotlib` pour dessiner une carte raster calquée fidèlement sur la palette de couleurs officielle (GeoBretagne / DREAL).
5. **Déploiement Web** : L'image finale (`static/carte.png`) est publiée sur la branche `gh-pages` pour alimenter un site web statique en HTML.

---

## 🛠️ Technologies utilisées

* **Langage :** Python 3.10
* **Data Science :** `pandas`, `numpy`, `pyarrow` (pour la lecture instantanée du format Parquet)
* **Dataviz :** `matplotlib`
* **Web & CI/CD :** HTML/CSS basique, GitHub Actions, GitHub Pages

---

## 💻 Utilisation en local (Pour les développeurs)

Si vous souhaitez faire tourner ce projet sur votre propre machine :

1. Clonez ce dépôt :
   ```bash
   git clone [https://github.com/VOTRE_NOM/VOTRE_DEPOT.git](https://github.com/VOTRE_NOM/VOTRE_DEPOT.git)
   cd VOTRE_DEPOT
