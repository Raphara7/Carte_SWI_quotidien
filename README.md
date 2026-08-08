# Cartes Agroclimatiques (Météo-France)

Ce script Python génère six cartes météorologiques et agronomiques sur l'état des sols en France. Il se base sur le modèle SIM2 de Météo-France.

## Source des données

Le script utilise deux sources de données :
1. **Données du jour** : Fichier `.parquet` hébergé sur le stockage S3 de data.gouv.fr.
2. **Données historiques (1991-2020)** : Fichiers `.parquet` stockés sur un dossier Google Drive (pour le calcul des anomalies).

## Cartes produites

Les images sont générées au format PNG dans le dossier `static/` :
* **carte_swi_actuel.png** : Indice d'humidité des sols (SWI).
* **carte_engorgement.png** : Teneur en eau et engorgement des sols.
* **carte_anomalie.png** : Écart du SWI par rapport à la normale 1991-2020.
* **carte_etr.png** : Évapotranspiration réelle (ETR).
* **carte_pluie_15j.png** : Cumul pluviométrique sur 15 jours.
* **carte_pe_15j.png** : Cumul des précipitations efficaces sur 15 jours.

Un fichier `info.json` est produit dans le même dossier. Il contient la date des données et la liste des cartes.

## Installation et Prérequis

Python 3.x est requis.

Installez les dépendances avec la commande suivante :
```bash
pip install -r requirements.txt
