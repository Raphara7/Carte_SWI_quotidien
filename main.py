import os
import gzip
import requests
import gdown
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg') # Indispensable pour GitHub Actions (sans écran)
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from datetime import datetime, timedelta
import geopandas as gpd
from shapely.geometry import box
import json

# ==========================================
# 1. CONFIGURATION ET CHEMINS
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
chemin_json = os.path.join(dossier_static, "info.json")

# ==========================================
# 2. FONCTION DE TÉLÉCHARGEMENT ET D'ANALYSE
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
# 3. COMPÉTITION DES API & PRÉPARATION CUMULS
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

# Calculs des cumuls sur 15 jours
print("   -> Calcul des cumuls sur 15 jours...")
col_date = "DATE" if "DATE" in df_api.columns else "date"
date_moins_15 = derniere_date - timedelta(days=14)
df_15j = df_api[(df_api[col_date] >= date_moins_15) & (df_api[col_date] <= derniere_date)].copy()

col_preliq = "PRELIQ_Q" if "PRELIQ_Q" in df_15j.columns else "PRELIQ"
col_prenei = "PRENEI_Q" if "PRENEI_Q" in df_15j.columns else "PRENEI"
col_pe = "PE_Q" if "PE_Q" in df_15j.columns else "PE"
col_wg = "WG_RACINE_Q" if "WG_RACINE_Q" in df_jour.columns else "WG_RACINE"
col_evap = "EVAP_Q" if "EVAP_Q" in df_jour.columns else "EVAP"

df_15j["PLUIE_TOTALE"] = df_15j[col_preliq] + df_15j[col_prenei]
df_cumuls = df_15j.groupby(["LAMBX", "LAMBY"])[["PLUIE_TOTALE", col_pe]].sum().reset_index()

# ==========================================
# 4. HISTORIQUE GOOGLE DRIVE & ANOMALIE
# ==========================================
print("2. Téléchargement de l'historique Parquet (Google Drive)...")
os.makedirs(dossier_parquet, exist_ok=True)
lien_drive = f"https://drive.google.com/drive/folders/{id_dossier_drive}?usp=sharing"
gdown.download_folder(url=lien_drive, output=dossier_parquet, quiet=False, use_cookies=False)

print("3. Lecture Parquet et calcul normale/anomalie...")
liste_dates_historiques = []
for annee in range(1991, 2021):
    try:
        d = datetime(annee, derniere_date.month, derniere_date.day)
        liste_dates_historiques.append(int(d.strftime("%Y%m%d")))
    except ValueError:
        pass

df_hist = pd.read_parquet(dossier_parquet, filters=[("DATE", "in", liste_dates_historiques)])
df_normale = df_hist.groupby(["LAMBX", "LAMBY"])["SWI"].mean().reset_index(name="SWI_NORMALE")

# On intègre l'anomalie directement dans df_jour
df_jour = pd.merge(df_jour, df_normale, on=["LAMBX", "LAMBY"], how="inner")
df_jour["ECART"] = ((df_jour["SWI"] - df_jour["SWI_NORMALE"]) / (df_jour["SWI_NORMALE"] + 1e-6)) * 100

# ==========================================
# 5. GESTION DU FOND DE CARTE ET MASQUES (SIG)
# ==========================================
print("4. Préparation de la géométrie de la France...")
# Ajustement des coordonnées
if df_jour["LAMBY"].max() < 100000:
    df_jour["LAMBX"] *= 100
    df_jour["LAMBY"] *= 100
    df_cumuls["LAMBX"] *= 100
    df_cumuls["LAMBY"] *= 100

epsg_code = 2154 if df_jour["LAMBY"].max() > 5000000 else 27572
xmin, xmax = df_jour["LAMBX"].min() - 4000, df_jour["LAMBX"].max() + 4000
ymin, ymax = df_jour["LAMBY"].min() - 4000, df_jour["LAMBY"].max() + 4000
extent_raster = [xmin, xmax, ymin, ymax]

# Téléchargement/Lecture des frontières
if not os.path.exists(fichier_geojson):
    gdf_dep = gpd.read_file(url_geojson)
    gdf_dep.to_file(fichier_geojson, driver="GeoJSON")
else:
    gdf_dep = gpd.read_file(fichier_geojson)

gdf_dep = gdf_dep.to_crs(epsg=epsg_code)
france_geom = gdf_dep.unary_union 
bounding_box = box(xmin - 100000, ymin - 100000, xmax + 100000, ymax + 100000)
masque_exterieur = bounding_box.difference(france_geom)
gdf_masque = gpd.GeoDataFrame(geometry=[masque_exterieur], crs=epsg_code)

# ==========================================
# 6. FONCTION MODULAIRE DE GÉNÉRATION DE CARTES
# ==========================================
def creer_et_sauvegarder_carte(df_data, colonne, nom_fichier, titre, label_cbar, cmap_name="viridis", is_anomalie=False):
    print(f"   -> Génération de : {nom_fichier}...")
    fig, ax = plt.subplots(figsize=(10, 10))
    grille = df_data.pivot(index="LAMBY", columns="LAMBX", values=colonne)
    
    if is_anomalie:
        bounds = [-500, -90, -80, -70, -60, -50, -40, -30, -20, -10, 0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 500]
        cmap = ListedColormap(plt.cm.RdBu(np.linspace(0, 1, len(bounds)-1)))
        norm = BoundaryNorm(bounds, cmap.N)
        im = ax.imshow(grille, origin="lower", cmap=cmap, norm=norm, extent=extent_raster, zorder=1)
    else:
        im = ax.imshow(grille, origin="lower", cmap=cmap_name, extent=extent_raster, zorder=1)

    # Superposition des masques et frontières
    gdf_masque.plot(ax=ax, facecolor="white", edgecolor="none", zorder=1.5)
    gdf_dep.plot(ax=ax, facecolor="none", edgecolor="black", linewidth=0.6, alpha=0.8, zorder=2)

    ax.set_xlim(extent_raster[0], extent_raster[1])
    ax.set_ylim(extent_raster[2], extent_raster[3])
    ax.set_title(titre, fontsize=14, fontweight="bold")
    ax.axis("off") 

    cbar = fig.colorbar(im, ax=ax, orientation="horizontal", fraction=0.04, pad=0.05, aspect=40, 
                        ticks=bounds[1:-1] if is_anomalie else None)
    cbar.set_label(label_cbar, fontsize=12)

    chemin_complet = os.path.join(dossier_static, nom_fichier)
    plt.savefig(chemin_complet, bbox_inches="tight", dpi=150)
    plt.close()

# ==========================================
# 7. ROUTEUR DE CARTES (AJOUTER/RETIRER ICI)
# ==========================================
print("5. Création des cartes demandées...")

# Liste des cartes à générer. Il suffit de commenter une ligne pour désactiver une carte.
cartes_a_produire = [
    {
        "df_data": df_jour, "colonne": "SWI", "nom_fichier": "carte_swi_actuel.png", 
        "titre": f"Humidité des sols (SWI) actuelle - {date_propre}", "label_cbar": "Indice SWI", "cmap_name": "Spectral"
    },
    {
        "df_data": df_jour, "colonne": col_wg, "nom_fichier": "carte_engorgement.png", 
        "titre": f"Engorgement des sols - {date_propre}", "label_cbar": "Teneur en eau (indice)", "cmap_name": "Blues"
    },
    {
        "df_data": df_jour, "colonne": "ECART", "nom_fichier": "carte_anomalie.png", 
        "titre": f"Anomalie humidité des sols (SWI) - {date_propre}\nÉcart relatif à la normale 1991-2020", "label_cbar": "Écart à la normale (%)", "is_anomalie": True
    },
    {
        "df_data": df_jour, "colonne": col_evap, "nom_fichier": "carte_etr.png", 
        "titre": f"Evapotranspiration réelle (ETR) - {date_propre}", "label_cbar": "ETR (mm)", "cmap_name": "YlGn"
    },
    {
        "df_data": df_cumuls, "colonne": "PLUIE_TOTALE", "nom_fichier": "carte_pluie_15j.png", 
        "titre": f"Cumul pluviométrique (15 derniers jours)", "label_cbar": "Précipitations (mm)", "cmap_name": "Blues"
    },
    {
        "df_data": df_cumuls, "colonne": col_pe, "nom_fichier": "carte_pe_15j.png", 
        "titre": f"Cumul précipitations efficaces (15 derniers jours)", "label_cbar": "Précipitations efficaces (mm)", "cmap_name": "BrBG"
    }
]

# Boucle génératrice
for config in cartes_a_produire:
    creer_et_sauvegarder_carte(**config)

print("✅ Terminé ! Toutes les cartes et le JSON sont prêts pour GitHub Pages.")
