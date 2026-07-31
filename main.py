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
from shapely.geometry import box

# ==========================================
# CONFIGURATION ET CHEMINS
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

nom_fichier_api = os.path.join(BASE_DIR, "carte_swi_api.csv")
url_api = "https://www.data.gouv.fr/api/1/datasets/r/adcca99a-6db0-495a-869f-40c888174a57"
url_geojson = "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/departements.geojson"

id_dossier_drive = "1b2KJodhjiQZ7X9fx8JZ8_vZDbY2Dz1QX"
dossier_parquet = os.path.join(BASE_DIR, "SWI_Parquet_Annuel")

dossier_static = os.path.join(BASE_DIR, "static")
os.makedirs(dossier_static, exist_ok=True)
chemin_sauvegarde = os.path.join(dossier_static, "carte.png")

# ==========================================
# ÉTAPE 1 : TÉLÉCHARGEMENT API (SANS CACHE)
# ==========================================
print("1. Récupération des données API...")
response = requests.get(url_api)
if response.status_code == 200:
    if response.content.startswith(b"\x1f\x8b"):
        with open(nom_fichier_api, "wb") as f:
            f.write(gzip.decompress(response.content))
    else:
        with open(nom_fichier_api, "wb") as f:
            f.write(response.content)
else:
    print("Erreur de téléchargement API.")
    exit()

try:
    df_api = pd.read_csv(nom_fichier_api, compression="gzip", sep=";")
except:
    df_api = pd.read_csv(nom_fichier_api, sep=";")

col_date = "DATE" if "DATE" in df_api.columns else "date"
df_api[col_date] = df_api[col_date].astype(str)
derniere_date_str = df_api[col_date].max()
df_jour = df_api[df_api[col_date] == derniere_date_str].copy().drop_duplicates(subset=["LAMBY", "LAMBX"])

try:
    obj_date_today = datetime.strptime(derniere_date_str, "%Y%m%d")
except:
    obj_date_today = datetime.strptime(derniere_date_str, "%Y-%m-%d")

date_propre = obj_date_today.strftime("%d/%m/%Y")

# ==========================================
# ÉTAPE 2 : TÉLÉCHARGEMENT HISTORIQUE (GOOGLE DRIVE)
# ==========================================
print("2. Téléchargement de l'historique Parquet (Google Drive)...")
os.makedirs(dossier_parquet, exist_ok=True)
lien_drive = f"https://drive.google.com/drive/folders/{id_dossier_drive}?usp=sharing"
gdown.download_folder(url=lien_drive, output=dossier_parquet, quiet=False, use_cookies=False)

# ==========================================
# ÉTAPE 3 : CALCUL NORMALE
# ==========================================
print("3. Lecture Parquet et calcul de la normale...")
liste_dates_historiques = []
for annee in range(1991, 2021):
    try:
        d = datetime(annee, obj_date_today.month, obj_date_today.day)
        liste_dates_historiques.append(int(d.strftime("%Y%m%d")))
    except ValueError:
        pass

df_hist = pd.read_parquet(dossier_parquet, filters=[("DATE", "in", liste_dates_historiques)])
df_normale = df_hist.groupby(["LAMBX", "LAMBY"])["SWI"].mean().reset_index(name="SWI_NORMALE")

# ==========================================
# ÉTAPE 4 : ANOMALIE
# ==========================================
print("4. Calcul de l'anomalie...")
df_final = pd.merge(df_jour[["LAMBX", "LAMBY", "SWI"]].rename(columns={"SWI": "SWI_TODAY"}), df_normale, on=["LAMBX", "LAMBY"], how="inner")
df_final["ECART"] = ((df_final["SWI_TODAY"] - df_final["SWI_NORMALE"]) / (df_final["SWI_NORMALE"] + 1e-6)) * 100

# ==========================================
# ÉTAPE 5 : CARTE AVEC DÉCOUPAGE STRICT
# ==========================================
print("5. Préparation de la cartographie (SIG)...")

# Ajustement automatique des coordonnées (hectomètres vers mètres si nécessaire)
if df_final["LAMBY"].max() < 100000:
    df_final["LAMBX"] = df_final["LAMBX"] * 100
    df_final["LAMBY"] = df_final["LAMBY"] * 100

# Détection de la projection
epsg_code = 2154 if df_final["LAMBY"].max() > 5000000 else 27572

# --- 5.1 Couche RASTER ---
grille = df_final.pivot(index="LAMBY", columns="LAMBX", values="ECART")
xmin, xmax = df_final["LAMBX"].min() - 4000, df_final["LAMBX"].max() + 4000
ymin, ymax = df_final["LAMBY"].min() - 4000, df_final["LAMBY"].max() + 4000
extent_raster = [xmin, xmax, ymin, ymax]

# --- 5.2 Couche VECTEUR (Lecture directe depuis l'URL) ---
print("   -> Récupération des frontières administratives...")
gdf_dep = gpd.read_file(url_geojson)
gdf_dep = gdf_dep.to_crs(epsg=epsg_code)

# --- 5.3 CRÉATION DU MASQUE INVERSÉ (STENCIL) ---
france_geom = gdf_dep.unary_union 
bounding_box = box(xmin - 100000, ymin - 100000, xmax + 100000, ymax + 100000)
masque_exterieur = bounding_box.difference(france_geom)
gdf_masque = gpd.GeoDataFrame(geometry=[masque_exterieur], crs=epsg_code)

# --- 5.4 ASSEMBLAGE ---
fig, ax = plt.subplots(figsize=(10, 10))

bounds = [-500, -90, -80, -70, -60, -50, -40, -30, -20, -10, 0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 500]
cmap_colors = plt.cm.RdBu(np.linspace(0, 1, len(bounds)-1))
cmap_discrete = ListedColormap(cmap_colors)
norm_discrete = BoundaryNorm(bounds, cmap_discrete.N)

# 1. Raster (Fond brut, zorder=1)
im = ax.imshow(grille, origin="lower", cmap=cmap_discrete, norm=norm_discrete, extent=extent_raster, zorder=1)

# 2. Le Masque Inversé (Blanc, zorder=1.5) -> Cache le raster hors frontières
gdf_masque.plot(ax=ax, facecolor="white", edgecolor="none", zorder=1.5)

# 3. Vecteur Administratif (Lignes noires, zorder=2) -> Dessiné par-dessus
gdf_dep.plot(ax=ax, facecolor="none", edgecolor="black", linewidth=0.6, alpha=0.8, zorder=2)

# On resserre la vue sur le territoire
ax.set_xlim(extent_raster[0], extent_raster[1])
ax.set_ylim(extent_raster[2], extent_raster[3])

# --- 5.5 HABILLAGE ---
ax.set_title(f"Anomalie d'humidité des sols (SWI) - {date_propre}\nÉcart relatif à la normale 1991-2020", fontsize=14, fontweight="bold")
ax.axis("off") 

cbar = fig.colorbar(im, ax=ax, orientation="horizontal", fraction=0.04, pad=0.05, aspect=40, ticks=bounds[1:-1])
cbar.set_label("Anomalie humidité des sols (SWI) en %", fontsize=12)

plt.savefig(chemin_sauvegarde, bbox_inches="tight", dpi=150)
plt.close()
print(f"Terminé ! La carte a été sauvegardée pour le déploiement.")
