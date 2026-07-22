import os
import gzip
import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm

nom_fichier = "carte_swi.csv"
url = "https://www.data.gouv.fr/api/1/datasets/r/adcca99a-6db0-495a-869f-40c888174a57"

print("Téléchargement en cours...")
response = requests.get(url)

if response.status_code == 200:
    if response.content.startswith(b"\x1f\x8b"):
        contenu_decomprime = gzip.decompress(response.content)
        with open(nom_fichier, "wb") as f:
            f.write(contenu_decomprime)
    else:
        with open(nom_fichier, "wb") as f:
            f.write(response.content)
    print("Téléchargement réussi.")
else:
    print(f"Erreur de téléchargement : {response.status_code}")

# Lecture sécurisée du fichier
try:
    df = pd.read_csv(nom_fichier, compression="gzip", sep=";")
except Exception:
    df = pd.read_csv(nom_fichier, sep=";")

# Sélection de la date la plus récente
derniere_date = df["DATE"].max()
df_date = df[df["DATE"] == derniere_date].copy()

# Multiplier le SWI par 100 pour correspondre à l'échelle en pourcentage
df_date["SWI"] = df_date["SWI"] * 100

# Transformation en grille 2D (raster)
grille_raster = df_date.pivot(index="LAMBY", columns="LAMBX", values="SWI")

# Définition des seuils
bornes = [
    0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 
    65, 70, 75, 80, 85, 90, 100, 110, 120, 130, 150
]

couleurs = [
    "gray", "dimgray", "#3d2314", "#593514", "#825831", "#a3815c", 
    "#bcbc3a", "#e6e600", "#cccc00", "#7bcd00", "#00cc00", "#009900", 
    "#006600", "#004433", "#003366", "#0066cc", "#0088ff", "#66b3ff", 
    "#b3d1ff", "#e6b8ff", "#d24dff", "#9900cc", "#4b0082"
]

cmap = ListedColormap(couleurs)
cmap.set_bad(color="white")
norm = BoundaryNorm(bornes, ncolors=len(couleurs), clip=True)

# Création du dossier static s'il n'existe pas
os.makedirs("static", exist_ok=True)

# Affichage et sauvegarde de la carte
plt.figure(figsize=(9, 9))
im = plt.imshow(grille_raster, origin="lower", cmap=cmap, norm=norm)
plt.colorbar(im, label="SWI (%)", ticks=bornes[:-1])
plt.title(f"Carte SWI de la France (%) - Date : {derniere_date}")
plt.xlabel("Coordonnée LAMBX")
plt.ylabel("Coordonnée LAMBY")

# Sauvegarde de l'image
plt.savefig("static/carte.png", bbox_inches="tight", dpi=150)
plt.close()
print("Carte générée et sauvegardée avec succès !")
