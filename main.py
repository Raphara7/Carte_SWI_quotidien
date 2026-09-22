import os
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

fichier_geojson = os.path.join(BASE_DIR, "departements.geojson")

# Liens et IDs
URL_PARQUET = "https://hydra.s3.rbx.io.cloud.ovh.net/parquet/a2bbcf56-32c9-4821-b195-7b676c5854db.parquet"
url_geojson = "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/departements.geojson"

id_dossier_drive_historique = "1b2KJodhjiQZ7X9fx8JZ8_vZDbY2Dz1QX"
id_fichier_ecoclimap = "1kGuFKtgF5nnchteIyF2Xh50s4o2n1htb"

dossier_parquet = os.path.join(BASE_DIR, "SWI_Parquet_Annuel")
fichier_ecoclimap = os.path.join(BASE_DIR, "grille_ecoclimap_safran.parquet")

dossier_static = os.path.join(BASE_DIR, "static")
os.makedirs(dossier_static, exist_ok=True)
chemin_json = os.path.join(dossier_static, "info.json")

# Paramètres engin Terranimo (Charge: 4000 kg, Pression: 1 bar)
CHARGE_KG = 4000.0
PRESSION_BAR = 1.0
CONTRAINTE_BAR = 0.42 * PRESSION_BAR + (CHARGE_KG / 10000.0) * 1.03  # 0.832 bar

# ==========================================
# 2. RÉCUPÉRATION DES DONNÉES SIM2 (MÉTÉO-FRANCE)
# ==========================================
print("1. Téléchargement et lecture des données récentes (S3 Parquet)...")
try:
    df_api = pd.read_parquet(URL_PARQUET)
except Exception as e:
    raise RuntimeError(f"❌ Impossible d'accéder aux données Parquet : {e}")

# Normalisation des colonnes principales
col_date = next((c for c in df_api.columns if c.upper() == "DATE"), "DATE")
col_x = next((c for c in df_api.columns if c.upper() in ["LAMBX", "LAMBX_Q"]), "LAMBX")
col_y = next((c for c in df_api.columns if c.upper() in ["LAMBY", "LAMBY_Q"]), "LAMBY")
df_api.rename(columns={col_x: "LAMBX", col_y: "LAMBY", col_date: "DATE"}, inplace=True)

# Formatage des dates et nettoyage
if not pd.api.types.is_datetime64_any_dtype(df_api["DATE"]):
    df_api["DATE"] = pd.to_datetime(df_api["DATE"].astype(str).str.replace('-', ''), format='%Y%m%d', errors='coerce')

df_api = df_api.dropna(subset=["DATE", "LAMBX", "LAMBY"])

# SÉCURITÉ : Conversion immédiate en mètres avant toute manipulation
if df_api["LAMBY"].max() < 100000:
    df_api["LAMBX"] *= 100
    df_api["LAMBY"] *= 100

# Extraction de la date max
derniere_date = df_api["DATE"].max()
date_propre = derniere_date.strftime("%d/%m/%Y")
print(f"   -> Date retenue : {date_propre}")

df_jour = df_api[df_api["DATE"] == derniere_date].copy().drop_duplicates(subset=["LAMBY", "LAMBX"])

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
# 3. CALCUL DES ANOMALIES (HISTORIQUE) ET INDICES PHYSIQUES (ECOCLIMAP)
# ==========================================
print("2. Récupération des fichiers externes (Drive)...")

# A. Téléchargement de la grille ECOCLIMAP
if not os.path.exists(fichier_ecoclimap):
    print("   -> Téléchargement de grille_ecoclimap_safran.parquet...")
    url_eco = f'https://drive.google.com/uc?id={id_fichier_ecoclimap}'
    gdown.download(url_eco, fichier_ecoclimap, quiet=False)

df_stat = pd.read_parquet(fichier_ecoclimap)
if df_stat["LAMBY"].max() < 100000:
    df_stat["LAMBX"] *= 100
    df_stat["LAMBY"] *= 100

# B. Téléchargement de l'historique Parquet
os.makedirs(dossier_parquet, exist_ok=True)
lien_drive_hist = f"https://drive.google.com/drive/folders/{id_dossier_drive_historique}?usp=sharing"
gdown.download_folder(url=lien_drive_hist, output=dossier_parquet, quiet=False, use_cookies=False)

print("3. Calcul de l'anomalie SWI et des indices physiques de sol...")
liste_dates_historiques = []
for annee in range(1991, 2021):
    try:
        d = datetime(annee, derniere_date.month, derniere_date.day)
        liste_dates_historiques.append(int(d.strftime("%Y%m%d")))
    except ValueError:
        pass  # Prise en compte du 29 février

df_hist = pd.read_parquet(dossier_parquet, filters=[("DATE", "in", liste_dates_historiques)])
if df_hist["LAMBY"].max() < 100000:
    df_hist["LAMBX"] *= 100
    df_hist["LAMBY"] *= 100

# Calcul de la normale et fusion
df_normale = df_hist.groupby(["LAMBX", "LAMBY"])["SWI"].mean().reset_index(name="SWI_NORMALE")
df_jour = pd.merge(df_jour, df_normale, on=["LAMBX", "LAMBY"], how="inner")
df_jour["ECART"] = ((df_jour["SWI"] - df_jour["SWI_NORMALE"]) / (df_jour["SWI_NORMALE"] + 1e-6)) * 100

# Fusion avec ECOCLIMAP pour Terranimo (Portance / Succion)
df_jour = pd.merge(df_jour, df_stat, on=["LAMBX", "LAMBY"], how="inner")

if df_jour.empty:
    raise ValueError("Erreur : La fusion des données a généré un tableau vide. Vérifiez l'échelle des coordonnées (LAMBX/LAMBY).")

# ==========================================
# 4. CALCULS AGRONOMIQUES ET TERRANIMO ACTUALISÉS
# ==========================================
# 1. Teneur massique en argile (%) inversée depuis b
df_jour["CLAY_PCT"] = np.clip((df_jour["B"] - 3.5) / 0.137, 0.0, 100.0)

# 2. Calcul analytique ou semi-analytique de la succion (Clapp & Hornberger 1978)
col_wg_val = next((c for c in df_jour.columns if c.upper() in ["WG_RACINE_Q", "WG_RACINE"]), None)

if col_wg_val and df_jour[col_wg_val].notna().all() and "W_SAT" in df_jour.columns and "PSI_SAT_KPA" in df_jour.columns:
    # Voie analytique directe (si teneur volumique dispo)
    se = np.clip(df_jour[col_wg_val].astype(float).values / df_jour["W_SAT"].values, 0.05, 1.0)
    succion_kpa = df_jour["PSI_SAT_KPA"].values * (se ** (-df_jour["B"].values))
    succion_kpa = np.clip(succion_kpa, 0.0, 1500.0)
    pf = np.log10(np.maximum(succion_kpa * 10.197, 1.0))
else:
    # Voie par repli via le SWI
    swi_safe = np.clip(df_jour["SWI"].values, 0.0, 1.2)
    b_norm = df_jour["B"].values / 5.0
    pf = np.where(
        swi_safe <= 1.0,
        4.2 - 2.2 * (swi_safe ** (1.0 / b_norm)),
        2.0 - 1.0 * (swi_safe - 1.0)
    )
    pf = np.clip(pf, 0.8, 4.2)
    succion_kpa = (10.0 ** pf) / 10.197

df_jour["PF"] = pf
df_jour["SUCCION_KPA"] = succion_kpa

# 3. Résistance du sol Terranimo avec seuil de validité à 50 cbar (1 kPa = 1 cbar)
succion_cbar_terranimo = np.clip(df_jour["SUCCION_KPA"].values, 0.0, 50.0)
df_jour["RESISTANCE_BAR"] = 0.55 + 0.02 * df_jour["CLAY_PCT"] + 0.023 * succion_cbar_terranimo

# 4. Décision Terranimo (Nomogramme 35 cm)
conditions_prat = [
    df_jour["RESISTANCE_BAR"] >= 2.0 * CONTRAINTE_BAR,
    df_jour["RESISTANCE_BAR"] >= 0.92 * CONTRAINTE_BAR
]
df_jour["CLASSE_PRATICABILITE"] = np.select(conditions_prat, [3, 2], default=1)

# ==========================================
# 5. GESTION DU FOND DE CARTE ET MASQUES (SIG)
# ==========================================
print("4. Préparation de la géométrie de la France...")
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
def creer_et_sauvegarder_carte(df_data, colonne, nom_fichier, titre, label_cbar, cmap="viridis", norm=None, ticks=None, tick_labels=None, is_anomalie=False):
    print(f"   -> Génération de : {nom_fichier}...")
    fig, ax = plt.subplots(figsize=(10, 10))
    grille = df_data.pivot(index="LAMBY", columns="LAMBX", values=colonne)
    
    if is_anomalie:
        bounds_anom = [-500, -90, -80, -70, -60, -50, -40, -30, -20, -10, 0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 500]
        cmap_anom = ListedColormap(plt.cm.RdBu(np.linspace(0, 1, len(bounds_anom)-1)))
        norm_anom = BoundaryNorm(bounds_anom, cmap_anom.N)
        im = ax.imshow(grille, origin="lower", cmap=cmap_anom, norm=norm_anom, extent=extent_raster, zorder=1)
        ticks_to_use = bounds_anom[1:-1]
    else:
        im = ax.imshow(grille, origin="lower", cmap=cmap, norm=norm, extent=extent_raster, zorder=1)
        ticks_to_use = ticks

    # Superposition du masque blanc extérieur et des limites de départements
    gdf_masque.plot(ax=ax, facecolor="white", edgecolor="none", zorder=1.5)
    gdf_dep.plot(ax=ax, facecolor="none", edgecolor="black", linewidth=0.6, alpha=0.8, zorder=2)

    ax.set_xlim(extent_raster[0], extent_raster[1])
    ax.set_ylim(extent_raster[2], extent_raster[3])
    ax.set_title(titre, fontsize=14, fontweight="bold", pad=12)
    ax.axis("off") 

    cbar = fig.colorbar(im, ax=ax, orientation="horizontal", fraction=0.04, pad=0.05, aspect=40, ticks=ticks_to_use)
    cbar.set_label(label_cbar, fontsize=12)
    
    # Remplacement des étiquettes si fourni (utile pour la carte de praticabilité)
    if tick_labels:
        cbar.ax.set_xticklabels(tick_labels, fontsize=10)

    chemin_complet = os.path.join(dossier_static, nom_fichier)
    plt.savefig(chemin_complet, bbox_inches="tight", dpi=150)
    plt.close()

# ==========================================
# 7. EXÉCUTION DE LA GÉNÉRATION DES CARTES
# ==========================================
print("5. Création des cartes demandées...")

# Palettes de couleurs spécifiques
bounds_pf = [1.0, 1.8, 2.0, 2.3, 2.7, 3.5, 4.2]
cmap_pf = ListedColormap(["#7f0000", "#d73027", "#fee08b", "#d9ef8b", "#91cf60", "#1a9850"])
norm_pf = BoundaryNorm(bounds_pf, cmap_pf.N)

bounds_kpa = [0, 5, 10, 20, 50, 100, 250, 500, 1500]
cmap_kpa = ListedColormap(plt.cm.Spectral(np.linspace(0, 1, len(bounds_kpa) - 1)))
norm_kpa = BoundaryNorm(bounds_kpa, cmap_kpa.N)

bounds_prat = [0.5, 1.5, 2.5, 3.5]
cmap_prat = ListedColormap(["#e06c62", "#f7b963", "#c4deb2"])
norm_prat = BoundaryNorm(bounds_prat, cmap_prat.N)

cartes_a_produire = [
    # Cartes d'origine
    {"df_data": df_jour, "colonne": "SWI", "nom_fichier": "carte_swi_actuel.png", "titre": f"Humidité des sols (SWI) actuelle - {date_propre}", "label_cbar": "Indice SWI", "cmap": "Spectral"},
    {"df_data": df_jour, "colonne": col_wg, "nom_fichier": "carte_engorgement.png", "titre": f"Engorgement des sols - {date_propre}", "label_cbar": "Teneur en eau (indice)", "cmap": "Blues"},
    {"df_data": df_jour, "colonne": "ECART", "nom_fichier": "carte_anomalie.png", "titre": f"Anomalie humidité des sols (SWI) - {date_propre}\nÉcart relatif à la normale 1991-2020", "label_cbar": "Écart à la normale (%)", "is_anomalie": True},
    {"df_data": df_jour, "colonne": col_evap, "nom_fichier": "carte_etr.png", "titre": f"Evapotranspiration réelle (ETR) - {date_propre}", "label_cbar": "ETR (mm)", "cmap": "YlGn"},
    {"df_data": df_cumuls, "colonne": "PLUIE_TOTALE", "nom_fichier": "carte_pluie_15j.png", "titre": "Cumul pluviométrique (15 derniers jours)", "label_cbar": "Précipitations (mm)", "cmap": "Blues"},
    {"df_data": df_cumuls, "colonne": col_pe, "nom_fichier": "carte_pe_15j.png", "titre": "Cumul précipitations efficaces (15 derniers jours)", "label_cbar": "Précipitations efficaces (mm)", "cmap": "BrBG"},
    
    # Nouvelles cartes (Indicateurs physiques)
    {"df_data": df_jour, "colonne": "CLAY_PCT", "nom_fichier": "carte_argile_ecoclimap.png", "titre": "Teneur en argile estimée des sols", "label_cbar": "Argile (%)", "cmap": "YlOrBr"},
    {"df_data": df_jour, "colonne": "PF", "nom_fichier": "carte_pf_portance.png", "titre": f"Indice de rétention en eau (pF) - {date_propre}\n< 2.0: Risque d'orniérage | > 2.5: Sol portant", "label_cbar": "Indice pF (log10 |h| en cm d'eau)", "cmap": cmap_pf, "norm": norm_pf, "ticks": bounds_pf},
    {"df_data": df_jour, "colonne": "SUCCION_KPA", "nom_fichier": "carte_succion_kpa.png", "titre": f"Force de succion matricielle (|ψ|) - {date_propre}", "label_cbar": "Succion matricielle (kPa)", "cmap": cmap_kpa, "norm": norm_kpa, "ticks": bounds_kpa},
    
    # Carte finale Terranimo
    {"df_data": df_jour, "colonne": "CLASSE_PRATICABILITE", "nom_fichier": "carte_praticabilite_actuel.png", "titre": f"Praticabilité des sols (Terranimo) - {date_propre}\n(Charge: {int(CHARGE_KG)}kg | Pneu: {PRESSION_BAR}bar)", "label_cbar": "Classes de Praticabilité", "cmap": cmap_prat, "norm": norm_prat, "ticks": [1, 2, 3], "tick_labels": ["Non praticable\n(Risque sévère)", "Dangereux\n(Vigilance)", "Praticable\n(Favorable)"]}
]

for config in cartes_a_produire:
    creer_et_sauvegarder_carte(**config)

# Export du fichier de métadonnées JSON
with open(chemin_json, "w", encoding="utf-8") as f:
    json.dump({
        "date": date_propre,
        "derniere_mise_a_jour": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_donnees": URL_PARQUET,
        "terranimo_params": {"charge_kg": CHARGE_KG, "pression_bar": PRESSION_BAR},
        "cartes_disponibles": [c["nom_fichier"] for c in cartes_a_produire]
    }, f, ensure_ascii=False, indent=4)

print("✅ Terminé ! Toutes les cartes ont été générées dans 'static/'.")
