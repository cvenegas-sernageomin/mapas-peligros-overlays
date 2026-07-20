# -*- coding: utf-8 -*-
"""
Rasteriza las capas vectoriales de CAIDA DE ROCAS (SIGMA / CIGIDEN) a un overlay
WebP transparente georreferenciado en WGS84 plate-carree, para la capa
"Mapas de peligro" de la PWA de remociones.

Fuente: Plataforma SIGMA (CIGIDEN) - ArcGIS Online, feature layers publicas
  - Area de Susceptibilidad (generacion/transporte/depositacion) de Caidas de Rocas
  - Area de Impacto de Caidas de Rocas
Extension: Cajon del Maipo / San Jose de Maipo (Region Metropolitana).

Requiere Python 3.12 (matplotlib, numpy, Pillow).  Correr con -X utf8.
"""
import json, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.path import Path
from matplotlib.patches import PathPatch
from matplotlib.collections import PathCollection
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SRC  = os.path.join(HERE, "fuentes")   # geojson de origen
OUT  = os.path.join(HERE, "overlays")
os.makedirs(OUT, exist_ok=True)

SUSC = os.path.join(SRC, "Area_Susceptibilidad_CaidaRocas.geojson")
IMP  = os.path.join(SRC, "Area_Impacto_CaidaRocas.geojson")

# Estilo
C_SUSC = "#F97316"   # naranjo -> susceptibilidad (generacion/transporte/depositacion)
C_IMP  = "#B91C1C"   # rojo    -> area de impacto
A_SUSC = 0.50
A_IMP  = 0.55
MAX_PX = 3000

def poly_paths(geojson_path):
    """Devuelve lista de matplotlib.Path (compuestos, con hoyos) por feature."""
    d = json.load(open(geojson_path, encoding="utf-8"))
    paths = []
    for ft in d["features"]:
        g = ft["geometry"]
        if g is None:
            continue
        if g["type"] == "Polygon":
            polys = [g["coordinates"]]
        elif g["type"] == "MultiPolygon":
            polys = g["coordinates"]
        else:
            continue
        for rings in polys:              # rings = [exterior, hueco1, ...]
            verts, codes = [], []
            for ring in rings:
                if len(ring) < 3:
                    continue
                verts.extend(ring)
                codes.append(Path.MOVETO)
                codes.extend([Path.LINETO] * (len(ring) - 2))
                codes.append(Path.CLOSEPOLY)
            if verts:
                paths.append(Path(np.asarray(verts), codes))
    return paths

def bounds_of(*path_lists):
    xs, ys = [], []
    for pl in path_lists:
        for p in pl:
            v = p.vertices
            xs.append(v[:, 0]); ys.append(v[:, 1])
    xs = np.concatenate(xs); ys = np.concatenate(ys)
    return xs.min(), ys.min(), xs.max(), ys.max()   # W, S, E, N

susc = poly_paths(SUSC)
imp  = poly_paths(IMP)
W, S, E, N = bounds_of(susc, imp)
print(f"bounds  W={W:.6f} S={S:.6f} E={E:.6f} N={N:.6f}")

lon_span, lat_span = E - W, N - S
if lat_span >= lon_span:
    h = MAX_PX; w = int(round(MAX_PX * lon_span / lat_span))
else:
    w = MAX_PX; h = int(round(MAX_PX * lat_span / lon_span))
DPI = 200
fig = plt.figure(figsize=(w / DPI, h / DPI), dpi=DPI)
ax = fig.add_axes([0, 0, 1, 1])          # llena todo el lienzo, sin margenes
ax.set_xlim(W, E); ax.set_ylim(S, N)
ax.set_aspect("auto")                    # Leaflet estira al bounds -> plate-carree
ax.axis("off")

ax.add_collection(PathCollection(susc, facecolors=C_SUSC, edgecolors="none",
                                 alpha=A_SUSC, antialiased=True))
ax.add_collection(PathCollection(imp,  facecolors=C_IMP,
                                 edgecolors="#7F1D1D", linewidths=0.4,
                                 alpha=A_IMP, antialiased=True))

png = os.path.join(OUT, "caida_rocas_maipo.png")
fig.savefig(png, transparent=True, dpi=DPI)
plt.close(fig)

img = Image.open(png).convert("RGBA")
webp = os.path.join(OUT, "caida_rocas_maipo.webp")
img.save(webp, "WEBP", quality=82, method=6)
print(f"overlay  {img.size[0]}x{img.size[1]}  ->  {webp}  "
      f"({os.path.getsize(webp)/1024:.0f} KB)")

# ---------- Leyenda ----------
figL = plt.figure(figsize=(4.2, 1.5), dpi=200)
figL.patch.set_facecolor("white")
axL = figL.add_axes([0, 0, 1, 1]); axL.axis("off")
axL.text(0.04, 0.86, "Caida de rocas", fontsize=13, weight="bold",
         transform=axL.transAxes)
def swatch(y, color, alpha, label):
    axL.add_patch(plt.Rectangle((0.05, y), 0.10, 0.14, facecolor=color,
                  alpha=alpha, edgecolor="#333", linewidth=0.6,
                  transform=axL.transAxes))
    axL.text(0.19, y + 0.02, label, fontsize=9.5, transform=axL.transAxes)
swatch(0.52, C_SUSC, A_SUSC, "Susceptibilidad (generacion / transporte /\ndepositacion)")
swatch(0.20, C_IMP,  A_IMP,  "Area de impacto")
axL.text(0.04, 0.03, "Fuente: Plataforma SIGMA - CIGIDEN", fontsize=6.5,
         color="#666", transform=axL.transAxes)
legpng = os.path.join(OUT, "caida_rocas_maipo_leyenda.png")
figL.savefig(legpng, dpi=200); plt.close(figL)
Image.open(legpng).convert("RGB").save(
    os.path.join(OUT, "caida_rocas_maipo_leyenda.webp"), "WEBP",
    quality=85, method=6)
print("leyenda ->", os.path.join(OUT, "caida_rocas_maipo_leyenda.webp"))
print("\nMANIFEST bounds:", json.dumps(
    {"n": round(N, 6), "s": round(S, 6), "e": round(E, 6), "w": round(W, 6)}))
