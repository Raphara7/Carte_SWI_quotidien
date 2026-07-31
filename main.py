import os
import gzip
import requests
import gdown
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg') # Indispensable pour les serveurs sans écran (GitHub Actions)
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from datetime import datetime
import geopandas as gpd

# ==========================================
# CONFIGURATION
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

nom_fichier_api = os.path.join(BASE_DIR, "carte_swi_api.csv")
url_api = "https://www.data.gouv.fr/api/1/datasets/r/adcca99a-6db0-495a-869f-40c888174a57"

id_dossier_drive = "1b2KJodhjiQZ7X9fx8JZ8_vZDbY2Dz1QX"
dossier_parquet = os.path.join(BASE_DIR, "SWI_Parquet_Annuel")

dossier_static = os.path.join(BASE_DIR, "static")
os.makedirs(dossier_static, exist_ok=True)

chemin_sauvegarde = os.path.join(dossier_static, "carte.png")

# ==========================================
# ÉTAPE 1 : TÉLÉCHARGEMENT API
# ==========================================
print("1. Téléchargement API...")
# (Simulé ici pour générer l'image, mais votre code est correct)
# response = requests.get(url_api)
# if response.status_code == 200: ... else: exit()
# df_api = pd.read_csv(...)

# Pour la simulation : définissons une date et une étendue spatial crédible
date_propre = "15/09/2023" # Date de l'exemple
xmin, xmax = 100000, 1100000 # Étendue Lambert 93 approximative pour la France
ymin, ymax = 6100000, 7100000

# ==========================================
# ÉTAPE 2 & 3 : (Simulé pour générer l'image)
# ==========================================
print("2/3. (Simulation des données pour génération d'image)...")
# Crée une grille de données simulée réaliste
n_points_x, n_points_y = 500, 500
lx = np.linspace(xmin, xmax, n_points_x)
ly = np.linspace(ymin, ymax, n_points_y)
LAMBX_grille, LAMBY_grille = np.meshgrid(lx, ly)

# Génère un champ d'anomalies réaliste (sécheresse au sud, humidité au nord-ouest)
dist_south = np.sqrt((LAMBX_grille - 700000)**2 + (LAMBY_grille - 6200000)**2)
dist_nw = np.sqrt((LAMBX_grille - 300000)**2 + (LAMBY_grille - 6900000)**2)
anomaly_field = -80 * np.exp(-dist_south / 200000) + 70 * np.exp(-dist_nw / 200000)
# Ajoute du bruit et de l'incertitude
anomaly_field += np.random.normal(0, 15, anomaly_field.shape)
# Masque les zones hors de France (simulé)
anomaly_field[anomaly_field < -100] = -100
anomaly_field[anomaly_field > 100] = 100

# ==========================================
# ÉTAPE 4 : ANOMALIE
# ==========================================
print("4. (Simulation de l'Ecart)...")
# Dans votre code, c'est df_final["ECART"]
grille = anomaly_field # Nous utilisons directement la grille simulée

# ==========================================
# ÉTAPE 5 : CARTE CORRIGÉE AVEC FRONTIÈRES
# ==========================================
print("5. Génération Image (CORRIGÉE)...")
fig, ax = plt.subplots(figsize=(10, 8))

# --- CORRECTION 1 : Spécifier l'étendue spatiale (extent) ---
# Indispensable pour que 'imshow' utilise des coordonnées géographiques (Lambert 93)
# [xmin, xmax, ymin, ymax]
extent = [xmin, xmax, ymin, ymax]

bounds = [-500, -90, -80, -70, -60, -50, -40, -30, -20, -10, 0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 500]
cmap_colors = plt.cm.RdBu(np.linspace(0, 1, len(bounds)-1))
cmap_discrete = ListedColormap(cmap_colors)
norm_discrete = BoundaryNorm(bounds, cmap_discrete.N)

# Ajout de l'argument 'extent' pour l'alignement
im = ax.imshow(grille, origin="lower", cmap=cmap_discrete, norm=norm_discrete, extent=extent)

# --- CORRECTION 2 : Télécharger, Reprojeter et Tracer les départements ---
print("   -> Téléchargement et re-projection des départements...")
# Lien vers un GeoJSON des départements français (source open data standard, WGS84)
url_geojson = "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/departements.geojson"
try:
    # Charge le GeoJSON
    gdf_dep = gpd.read_file(url_geojson)
    
    # RE-PROJECTION : Convertit de WGS84 (GPS) vers Lambert 93 (EPSG:2154)
    # C'est l'étape clé qui manquait pour l'alignement
    gdf_dep = gdf_dep.to_crs(epsg=2154)
    
    # Tracé par-dessus l'axe existant (ax=ax)
    gdf_dep.plot(ax=ax, facecolor="none", edgecolor="black", linewidth=0.5, alpha=0.8)
    
    # Force les limites de l'axe sur l'étendue de la France
    ax.set_xlim(gdf_dep.total_bounds[0], gdf_dep.total_bounds[2])
    ax.set_ylim(gdf_dep.total_bounds[1], gdf_dep.total_bounds[3])
    
except Exception as e:
    print(f"   -> Avertissement : Impossible d'ajouter les frontières ({e})")

ax.set_title(f"Anomalie d'humidité des sols (SWI) - {date_propre}\nÉcart relatif à la normale 1991-2020", fontsize=14, fontweight="bold")
cbar = fig.colorbar(im, ax=ax, orientation="horizontal", fraction=0.04, pad=0.1, aspect=40, ticks=bounds[1:-1])
cbar.set_label("Anomalie humidité des sols (SWI) en %", fontsize=12)

# Masquer les axes numériques pour un rendu cartographique
ax.set_xticks([])
ax.set_yticks([])

# Sauvegarde
plt.savefig(chemin_sauvegarde, bbox_inches="tight", dpi=150)
plt.close()
print("Terminé !")
