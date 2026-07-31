import os
import gzip
import requests
import gdown
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg') # Indispensable pour GitHub Actions
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from datetime import datetime
import geopandas as gpd
from shapely.geometry import box
import json

# ==========================================
# CONFIGURATION ET CHEMINS
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

nom_fichier_api = os.path.join(BASE_DIR, "carte_swi_api.csv")
fichier_geojson = os.path.join(BASE_DIR, "departements.geojson")

url_api_1 = "https://www.data.gouv.fr/api/1/datasets/r/adcca99a-6db0-495a-869f-40c888174a57"
url_api_2 = "https://www.data.gouv.fr/api/1/datasets/r/15ffddfb-0d1b-4509-ae5a-613fad496d05"
url_geojson = "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/departements.geojson"

id_dossier_drive = "1b2KJodhjiQZ7X9fx8JZ8_vZDbY2Dz1QX"
dossier_parquet = os.path.join(BASE_DIR, "SWI_Parquet_Annuel")

dossier_static = os.path.join(BASE_DIR, "static")
os.makedirs(dossier_static, exist_ok=True)
chemin_sauvegarde = os.path.join(dossier_static, "carte.png")
chemin_json = os.path.join(dossier_static, "info.json")

# ==========================================
# FONCTION DE TÉLÉCHARGEMENT ET D'ANALYSE
# ==========================================
def tester_api(url, fichier_temp):
    print(f"   -> Test de l'URL : {url}")
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            if response.content.startswith(b"\x1f\x8b"):
                with open(fichier_temp, "wb") as f:
                    f.write(gzip.decompress(response.content))
            else:
                with open(fichier_temp, "wb") as f:
                    f.write(response.content)
            
            try:
                df = pd.read_csv(fichier_temp, compression="gzip", sep=";")
            except:
                df = pd.read_csv(fichier_temp, sep=";")
                
            col_date = "DATE" if "DATE" in df.columns else "date"
            df[col_date] = pd.to_datetime(df[col_date].astype(str).str.replace('-', ''), format='%Y%m%d', errors='coerce')
            
            date_max = df[col_date].max()
            df_jour = df[df[col_date] == date_max].copy().drop_duplicates(subset=["LAMBY", "LAMBX"])
            return date_max, df_jour, df
        else:
            return None, None, None
    except Exception:
        return None, None, None

# ==========================================
# ÉTAPE 1 : COMPÉTITION DES API
# ==========================================
print("1. Récupération des données et test des API...")
date_1, df_jour_1, df_api_1 = tester_api(url_api_1, nom_fichier_api.replace(".csv", "_1.csv"))
date_2, df_jour_2, df_api_2 = tester_api(url_api_2, nom_fichier_api.replace(".csv", "_2.csv"))

if date_1 and date_2:
    if date_2 > date_1:
        derniere_date, df_jour, df_api, url_retenue = date_2, df_jour_2, df_api_2, url_api_2
    else:
        derniere_date, df_jour, df_api, url_retenue = date_1, df_jour_1, df_api_1, url_api_1
elif date_1:
    derniere_date, df_jour, df_api, url_retenue = date_1, df_jour_1, df_api_1, url_api_1
elif date_2:
    derniere_date, df_jour, df_api, url_retenue = date_2, df_jour_2, df_api_2, url_api_2
else:
    print("❌ Les deux API ont échoué.")
    exit()

date_propre = derniere_date.strftime("%d/%m/%Y")
print(f"   -> Date retenue : {date_propre}")

# Sauvegarde des infos pour le HTML
with open(chemin_json, "w", encoding="utf-8") as f:
    json.dump({"date": date_propre, "api_url": url_retenue}, f, ensure_ascii=False, indent=4)

# ==========================================
# ÉTAPE 2 : HISTORIQUE GOOGLE DRIVE
# ==========================================
print("2. Téléchargement de l'historique Parquet (Google Drive)...")
os.makedirs(dossier_parquet, exist_ok=True)
lien_drive = f"https://drive.google.com/drive/folders/{id_dossier_drive}?usp=sharing"
gdown.download_folder(url=lien_drive, output=dossier_parquet, quiet=False, use_cookies=False)

# ==========================================
# ÉTAPE 3 : CALCUL NORMALE
# ==========================================
print("3. Lecture Parquet et calcul normale...")
liste_dates_historiques = []
for annee in range(1991, 2021):
    try:
        d = datetime(annee, derniere_date.month, derniere_date.day)
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
# ÉTAPE 5 : CARTE
# ==========================================
print("5. Préparation de la cartographie (SIG)...")
if df_final["LAMBY"].max() < 100000:
    df_final["LAMBX"] = df_final["LAMBX"] * 100
    df_final["LAMBY"] = df_final["LAMBY"] * 100

epsg_code = 2154 if df_final["LAMBY"].max() > 5000000 else 27572

grille = df_final.pivot(index="LAMBY", columns="LAMBX", values="ECART")
xmin, xmax = df_final["LAMBX"].min() - 4000, df_final["LAMBX"].max() + 4000
ymin, ymax = df_final["LAMBY"].min() - 4000, df_final["LAMBY"].max() + 4000
extent_raster = [xmin, xmax, ymin, ymax]

gdf_dep = gpd.read_file(url_geojson)
gdf_dep = gdf_dep.to_crs(epsg=epsg_code)

france_geom = gdf_dep.unary_union 
bounding_box = box(xmin - 100000, ymin - 100000, xmax + 100000, ymax + 100000)
masque_exterieur = bounding_box.difference(france_geom)
gdf_masque = gpd.GeoDataFrame(geometry=[masque_exterieur], crs=epsg_code)

fig, ax = plt.subplots(figsize=(10, 10))
bounds = [-500, -90, -80, -70, -60, -50, -40, -30, -20, -10, 0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 500]
cmap_colors = plt.cm.RdBu(np.linspace(0, 1, len(bounds)-1))
cmap_discrete = ListedColormap(cmap_colors)
norm_discrete = BoundaryNorm(bounds, cmap_discrete.N)

im = ax.imshow(grille, origin="lower", cmap=cmap_discrete, norm=norm_discrete, extent=extent_raster, zorder=1)
gdf_masque.plot(ax=ax, facecolor="white", edgecolor="none", zorder=1.5)
gdf_dep.plot(ax=ax, facecolor="none", edgecolor="black", linewidth=0.6, alpha=0.8, zorder=2)

ax.set_xlim(extent_raster[0], extent_raster[1])
ax.set_ylim(extent_raster[2], extent_raster[3])
ax.set_title(f"Anomalie d'humidité des sols (SWI) - {date_propre}\nÉcart relatif à la normale 1991-2020", fontsize=14, fontweight="bold")
ax.axis("off") 

cbar = fig.colorbar(im, ax=ax, orientation="horizontal", fraction=0.04, pad=0.05, aspect=40, ticks=bounds[1:-1])
cbar.set_label("Anomalie humidité des sols (SWI) en %", fontsize=12)

plt.savefig(chemin_sauvegarde, bbox_inches="tight", dpi=150)
plt.close()
print("Terminé ! Carte et données JSON générées avec succès.")
