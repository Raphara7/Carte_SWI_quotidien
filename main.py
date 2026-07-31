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

# MODIFIÉ : le nom correspond à ton index.html
chemin_sauvegarde = os.path.join(dossier_static, "carte.png") 

# ==========================================
# ÉTAPE 1 : TÉLÉCHARGEMENT API
# ==========================================
print("1. Téléchargement API...")
response = requests.get(url_api)

if response.status_code == 200:
    if response.content.startswith(b"\x1f\x8b"):
        with open(nom_fichier_api, "wb") as f:
            f.write(gzip.decompress(response.content))
    else:
        with open(nom_fichier_api, "wb") as f:
            f.write(response.content)
else:
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
# ÉTAPE 2 : GOOGLE DRIVE
# ==========================================
print("2. Vérification Parquet...")
os.makedirs(dossier_parquet, exist_ok=True)
fichiers_locaux = [f for f in os.listdir(dossier_parquet) if f.endswith(".parquet")]

if len(fichiers_locaux) < 25: 
    print("Téléchargement Google Drive...")
    gdown.download_folder(url=f"https://drive.google.com/drive/folders/{id_dossier_drive}", output=dossier_parquet, quiet=False, use_cookies=False)

# ==========================================
# ÉTAPE 3 : CALCUL NORMALE
# ==========================================
print("3. Lecture Parquet...")
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
print("4. Calcul Anomalie...")
df_final = pd.merge(df_jour[["LAMBX", "LAMBY", "SWI"]].rename(columns={"SWI": "SWI_TODAY"}), df_normale, on=["LAMBX", "LAMBY"], how="inner")
df_final["ECART"] = ((df_final["SWI_TODAY"] - df_final["SWI_NORMALE"]) / (df_final["SWI_NORMALE"] + 1e-6)) * 100



# ==========================================
# ÉTAPE 5 : CARTE AVEC FRONTIÈRES
# ==========================================
print("5. Génération Image...")
grille = df_final.pivot(index="LAMBY", columns="LAMBX", values="ECART")
fig, ax = plt.subplots(figsize=(10, 8))

# 1. Calcul de l'étendue (extent) spatiale pour imshow
# Indispensable pour que l'image corresponde aux coordonnées géographiques
xmin, xmax = df_final["LAMBX"].min(), df_final["LAMBX"].max()
ymin, ymax = df_final["LAMBY"].min(), df_final["LAMBY"].max()
extent = [xmin, xmax, ymin, ymax]

bounds = [-500, -90, -80, -70, -60, -50, -40, -30, -20, -10, 0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 500]
cmap_colors = plt.cm.RdBu(np.linspace(0, 1, len(bounds)-1))
cmap_discrete = ListedColormap(cmap_colors)
norm_discrete = BoundaryNorm(bounds, cmap_discrete.N)

# Ajout de l'argument "extent" ici
im = ax.imshow(grille, origin="lower", cmap=cmap_discrete, norm=norm_discrete, extent=extent)

# 2. Ajout des frontières départementales via GeoPandas
print("   -> Téléchargement et tracé des départements...")
url_geojson = "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/departements.geojson"
try:
    gdf_dep = gpd.read_file(url_geojson)
    
    # Reprojection dans le même système de coordonnées que les données Météo-France
    # EPSG:2154 = Lambert 93 (standard français moderne)
    # Note : Si vos frontières semblent décalées, essayez epsg=27572 (Lambert II étendu, ancien standard)
    gdf_dep = gdf_dep.to_crs(epsg=2154) 
    
    # Tracé par-dessus l'axe existant
    gdf_dep.plot(ax=ax, facecolor="none", edgecolor="black", linewidth=0.5, alpha=0.7)
except Exception as e:
    print(f"   -> Avertissement : Impossible d'ajouter les frontières ({e})")

ax.set_title(f"Anomalie d'humidité des sols (SWI) - {date_propre}\nÉcart relatif à la normale 1991-2020", fontsize=14, fontweight="bold")
cbar = fig.colorbar(im, ax=ax, orientation="horizontal", fraction=0.04, pad=0.1, aspect=40, ticks=bounds[1:-1])
cbar.set_label("Anomalie humidité des sols (SWI) en %", fontsize=12)

# Masquer les axes numériques (optionnel mais plus esthétique pour une carte)
ax.set_xticks([])
ax.set_yticks([])

plt.savefig(chemin_sauvegarde, bbox_inches="tight", dpi=150)
plt.close()
print("Terminé !")
