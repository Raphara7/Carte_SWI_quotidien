import os
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
import pandas as pd
import numpy as np

nom_fichier = "carte_swi.csv"

# ... (ton code de téléchargement et de traitement pandas reste identique) ...

# Création du dossier static s'il n'existe pas
os.makedirs("static", exist_ok=True)

# Affichage et sauvegarde de la carte
plt.figure(figsize=(9, 9))
im = plt.imshow(grille_raster, origin="lower", cmap=cmap, norm=norm)
plt.colorbar(im, label="SWI (%)", ticks=bornes[:-1])
plt.title(f"Carte SWI de la France (%) - Date : {derniere_date}")
plt.xlabel("Coordonnée LAMBX")
plt.ylabel("Coordonnée LAMBY")

# Sauvegarde au lieu de plt.show()
plt.savefig("static/carte.png", bbox_inches="tight", dpi=150)
plt.close()
