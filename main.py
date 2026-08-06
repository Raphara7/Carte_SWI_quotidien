import os
import io
import requests
import gdown
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Indispensable pour GitHub Actions (sans écran)
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from datetime import datetime, timedelta
import geopandas as gpd
from shapely.geometry import box
import json
import warnings
warnings.filterwarnings('ignore')

# ==========================================
# 1. CONFIGURATION ET CHEMINS
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

nom_fichier_api = os.path.join(BASE_DIR, "carte_swi_api.csv")
fichier_geojson = os.path.join(BASE_DIR, "departements.geojson")

# ID exact de la ressource QUOT_SIM2_latest (data.gouv.fr)
RESOURCE_ID_LATEST = "a2bbcf56-32c9-4821-b195-7b676c5854db"

# API REST Tabular de data.gouv.fr (endpoint CSV avec toutes les lignes)
URL_API_PRINCIPALE = f"https://www.data.gouv.fr/api/resources/{RESOURCE_ID_LATEST}/data/csv/?page_size=all"

# Fallback miroir S3 direct si l'API REST est indisponible ou en maintenance
URL_API_FALLBACK = "https://object.files.data.gouv.fr/meteofrance/data/synop/SIM2/QUOT_SIM2_latest.csv.gz"

url_geojson = "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/departements.geojson"

id_dossier_drive = "1b2KJodhjiQZ7X9fx8JZ8_vZDbY2Dz1QX"
dossier_parquet = os.path.join(BASE_DIR, "SWI_Parquet_Annuel")

dossier_static = os.path.join(BASE_DIR, "static")
os.makedirs(dossier_static, exist_ok=True)
chemin_json = os.path.join(dossier_static, "info.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (GitHubActions/Automation Script)",
    "Accept": "text/csv,application/json"
}

# ==========================================
# 2. FONCTION INTERROGEANT L'API REST
# ==========================================
def interroger_api_data_gouv(url):
    print(f"   -> Appel de l'API : {url}")
    try:
        # Requete HTTP GET vers l'endpoint de l'API
        response = requests.get(url, headers=HEADERS, timeout=180)
        
        if response.status_code == 200:
            # Lecture du flux CSV directement depuis la reponse texte de l'API
            content_type = response.headers.get('Content-Type', '')
            
            # Gestion du cas compressé / brut
            if response.content.startswith(b"\x1f\x8b"):
                import gzip
                decompressed = gzip.decompress(response.content)
                df = pd.read_csv(io.BytesIO(decompressed), sep=";", low_memory=False)
            else:
                # L'API REST renvoie du text/csv
                df = pd.read_csv(io.StringIO(response.text), sep=";", low_memory=False)

            if df.empty:
                print("      [Échec] L'API a renvoyé une réponse vide.")
                return None, None, None

            # Normalisation du nom de la colonne DATE
            col_date = next((c for c in df.columns if c.upper() == "DATE"), "DATE")
            df[col_date] = pd.to_datetime(
                df[col_date].astype(str).str.replace('-', ''), 
                format='%Y%m%d', 
                errors='coerce'
            )
            df = df.dropna(subset=[col_date])

            # Normalisation des coordonnées spatiales Lambert
            col_x = next((c for c in df.columns if c.upper() in ["LAMBX", "LAMBX_Q"]), "LAMBX")
            col_y = next((c for c in df.columns if c.upper() in ["LAMBY", "LAMBY_Q"]), "LAMBY")
            df.rename(columns={col_x: "LAMBX", col_y: "LAMBY", col_date: "DATE"}, inplace=True)

            date_max = df["DATE"].max()
            df_jour = df[df["DATE"] == date_max].copy().drop_duplicates(subset=["LAMBY", "LAMBX"])
            
            return date_max, df_jour, df
        else:
            print(f"      [Échec API] Code statut HTTP: {response.status_code}")
            return None, None, None

    except Exception as e:
        print(f"      [Erreur de connexion à l'API] : {e}")
        return None, None, None

# ==========================================
# 3. RÉCUPÉRATION ET PRÉPARATION DES DONNÉES
# ==========================================
print("1. Interrogation de l'API REST data.gouv.fr (QUOT_SIM2_latest)...")
derniere_date, df_jour, df_api = interroger_api_data_gouv(URL_API_PRINCIPALE)
url_retenue = URL_API_PRINCIPALE

# Secours automatique sur le miroir S3 si l'API REST est indisponible
if derniere_date is None:
    print("   -> Échec de l'API REST data.gouv.fr. Bascule vers le miroir S3 Météo-France...")
    derniere_date, df_jour, df_api = interroger_api_data_gouv(URL_API_FALLBACK)
    url_retenue = URL_API_FALLBACK

if derniere_date is None:
    raise RuntimeError("❌ Impossible d'accéder aux données via l'API REST ni via le miroir S3.")

date_propre = derniere_date.strftime("%d/%m/%Y")
print(f"   -> Date retenue : {date_propre}")

# Calculs des cumuls sur 15 jours
print("   -> Calcul des cumuls sur 15 jours...")
date_moins_15 = derniere_date - timedelta(days=14)
df_15j = df_api[(df_api["DATE"] >= date_moins_15) & (df_api["DATE"] <= derniere_date)].copy()

col_preliq = next((c for c in df_15j.columns if c.upper() in ["PRELIQ_Q", "PRELIQ"]), "PRELIQ")
col_prenei = next((c for c in df_15j.columns if c.upper() in ["PRENEI_Q", "PRENEI"]), "PRENEI")
col_pe     = next((c for c in df_15j.columns if c.upper() in ["PE_Q", "PE"]), "PE")
col_wg     = next((c for c in df_jour.columns if c.upper() in ["WG_RACINE_Q", "WG_RACINE"]), "WG_RACINE")
col_evap   = next((c for c in df_jour.columns if c.upper() in ["EVAP_Q", "EVAP"]), "EVAP")

df_15j["PLUIE_TOTALE"] = df_15j[col_preliq].fillna(0) + df_15j[col_prenei].fillna(0)
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
        pass  # Prise en compte du 29 février (années bissextiles)

df_hist = pd.read_parquet(dossier_parquet, filters=[("DATE", "in", liste_dates_historiques)])
df_normale = df_hist.groupby(["LAMBX", "LAMBY"])["SWI"].mean().reset_index(name="SWI_NORMALE")

# Calcul de l'écart à la normale (%)
df_jour = pd.merge(df_jour, df_normale, on=["LAMBX", "LAMBY"], how="inner")
df_jour["ECART"] = ((df_jour["SWI"] - df_jour["SWI_NORMALE"]) / (df_jour["SWI_NORMALE"] + 1e-6)) * 100

# ==========================================
# 5. GESTION DU FOND DE CARTE ET MASQUES (SIG)
# ==========================================
print("4. Préparation de la géométrie de la France...")
if df_jour["LAMBY"].max() < 100000:
    df_jour["LAMBX"] *= 100
    df_jour["LAMBY"] *= 100
    df_cumuls["LAMBX"] *= 100
    df_cumuls["LAMBY"] *= 100

epsg_code = 2154 if df_jour["LAMBY"].max() > 5000000 else 27572
xmin, xmax = df_jour["LAMBX"].min() - 4000, df_jour["LAMBX"].max() + 4000
ymin, ymax = df_jour["LAMBY"].min() - 4000, df_jour["LAMBY"].max() + 4000
extent_raster = [xmin, xmax, ymin, ymax]

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

    # Superposition du masque blanc extérieur et des limites de départements
    gdf_masque.plot(ax=ax, facecolor="white", edgecolor="none", zorder=1.5)
    gdf_dep.plot(ax=ax, facecolor="none", edgecolor="black", linewidth=0.6, alpha=0.8, zorder=2)

    ax.set_xlim(extent_raster[0], extent_raster[1])
    ax.set_ylim(extent_raster[2], extent_raster[3])
    ax.set_title(titre, fontsize=14, fontweight="bold")
    ax.axis("off") 

    cbar = fig.colorbar(
        im, ax=ax, orientation="horizontal", fraction=0.04, pad=0.05, aspect=40, 
        ticks=bounds[1:-1] if is_anomalie else None
    )
    cbar.set_label(label_cbar, fontsize=12)

    chemin_complet = os.path.join(dossier_static, nom_fichier)
    plt.savefig(chemin_complet, bbox_inches="tight", dpi=150)
    plt.close()

# ==========================================
# 7. EXÉCUTION DE LA GÉNÉRATION DES CARTES
# ==========================================
print("5. Création des cartes demandées...")

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
        "titre": "Cumul pluviométrique (15 derniers jours)", "label_cbar": "Précipitations (mm)", "cmap_name": "Blues"
    },
    {
        "df_data": df_cumuls, "colonne": col_pe, "nom_fichier": "carte_pe_15j.png", 
        "titre": "Cumul précipitations efficaces (15 derniers jours)", "label_cbar": "Précipitations efficaces (mm)", "cmap_name": "BrBG"
    }
]

for config in cartes_a_produire:
    creer_et_sauvegarder_carte(**config)

# Export du fichier de métadonnées JSON
with open(chemin_json, "w", encoding="utf-8") as f:
    json.dump({
        "date": date_propre,
        "derniere_mise_a_jour": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "api_url": url_retenue,
        "cartes_disponibles": [c["nom_fichier"] for c in cartes_a_produire]
    }, f, ensure_ascii=False, indent=4)

print("✅ Terminé ! L'API REST a été interrogée et toutes les cartes ont été régénérées dans 'static/'.")
