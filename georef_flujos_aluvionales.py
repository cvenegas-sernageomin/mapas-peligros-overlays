# -*- coding: utf-8 -*-
"""
Genera el overlay WebP georreferenciado de "Susceptibilidad de Flujos
Aluvionales" (Plataforma SIGMA / CIGIDEN) para la cuenca del rio Maipo.

A diferencia de caida_rocas_maipo (vectores ya en WGS84), esta capa es un
RASTER pre-teselado: MapServer con singleFusedMapCache=true y capabilities
"Map,TilesOnly,Tilemap" -> el endpoint /export dinamico NO esta disponible
(devuelve 404) aunque el servicio lo anuncie. Hay que:
  1. Descargar el mosaico de tiles cacheadas (nivel de zoom maximo del
     servicio) que cubre el bbox deseado.
  2. Recortar exacto al bbox (en Web Mercator, EPSG:3857 - proyeccion nativa
     de las tiles).
  3. Reproyectar (warp vertical, ya que x es lineal en ambas proyecciones)
     de Web Mercator a WGS84 plate-carree para que Leaflet L.imageOverlay
     (que asume mapeo lineal lat/lon) lo dibuje sin deformacion.
  4. Ajustar la opacidad de la categoria "No Susceptible" (gris opaco en el
     tile original) para no tapar el satelite.
  5. Construir la leyenda aparte con PIL desde /legend?f=json.

Requiere Python 3.12 (numpy, opencv-python, pyproj, Pillow, requests no
hace falta - se usa urllib). Correr con -X utf8.
"""
import os
import io
import json
import math
import time
import base64
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
from pyproj import Transformer

# ---------------------------------------------------------------------
# Configuracion especifica de esta capa (Flujos Aluvionales)
# ---------------------------------------------------------------------
SERVICE = ("https://tiles.arcgis.com/tiles/UeyripQFTg6pfUe5/arcgis/rest/"
           "services/Susceptibilidad_Flujos_detritos_29092021/MapServer")
ID = "flujos_aluvionales"
TITULO_LEYENDA = "Susceptibilidad de Flujos Aluvionales"

# bbox objetivo en WGS84 (calculado a partir del fullExtent del servicio)
N, S, E, W = -32.907483, -34.292426, -69.766117, -71.651594

MAX_PX = 3000
GRAY_ALPHA_FACTOR = 0.88  # cuanto se reduce el alpha de "No Susceptible"
GRAY_TOL = 60.0           # tolerancia de distancia de color al gris puro

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "overlays")
os.makedirs(OUT, exist_ok=True)


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.load(urllib.request.urlopen(req, timeout=30))


def fetch_bytes(url, tries=4, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for i in range(tries):
        try:
            return urllib.request.urlopen(req, timeout=timeout).read()
        except Exception:
            if i == tries - 1:
                return None
            time.sleep(0.3)


def download_mosaic(service, level, col0, col1, row0, row1, ts=256, workers=16):
    ncols, nrows = col1 - col0 + 1, row1 - row0 + 1
    mosaic = Image.new("RGBA", (ncols * ts, nrows * ts), (0, 0, 0, 0))
    jobs = [(r, c) for r in range(row0, row1 + 1) for c in range(col0, col1 + 1)]
    missing = 0

    def _one(row, col):
        data = fetch_bytes(f"{service}/tile/{level}/{row}/{col}")
        return row, col, data

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_one, r, c) for r, c in jobs]
        for fut in as_completed(futs):
            row, col, data = fut.result()
            if data is None:
                missing += 1
                continue
            try:
                im = Image.open(io.BytesIO(data)).convert("RGBA")
                mosaic.paste(im, ((col - col0) * ts, (row - row0) * ts))
            except Exception:
                missing += 1
    print(f"mosaico {ncols}x{nrows} tiles, faltantes={missing}")
    return mosaic


def tile_range_for_bbox(xmin, ymin, xmax, ymax, res, ts=256,
                         origin_x=-20037508.342787, origin_y=20037508.342787):
    def colrow(x, y):
        return (x - origin_x) / (res * ts), (origin_y - y) / (res * ts)
    c0, r0 = colrow(xmin, ymax)
    c1, r1 = colrow(xmax, ymin)
    return math.floor(c0), math.floor(c1), math.floor(r0), math.floor(r1)


def build_overlay():
    info = fetch_json(f"{SERVICE}?f=json")
    assert info.get("singleFusedMapCache"), "este script asume un MapServer TilesOnly"
    lods = {l["level"]: l["resolution"] for l in info["tileInfo"]["lods"]}
    level = info["maxLOD"]
    res = lods[level]
    ts = info["tileInfo"]["cols"]
    origin_x = info["tileInfo"]["origin"]["x"]
    origin_y = info["tileInfo"]["origin"]["y"]

    tr = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    xmin, ymin = tr.transform(W, S)
    xmax, ymax = tr.transform(E, N)

    col0, col1, row0, row1 = tile_range_for_bbox(xmin, ymin, xmax, ymax, res, ts,
                                                  origin_x, origin_y)
    print(f"nivel {level} (res={res:.3f} m/px), cols {col0}-{col1}, rows {row0}-{row1}")

    mosaic = download_mosaic(SERVICE, level, col0, col1, row0, row1, ts)
    mw, mh = mosaic.size

    left = (xmin - origin_x) / res - col0 * ts
    right = (xmax - origin_x) / res - col0 * ts
    top = (origin_y - ymax) / res - row0 * ts
    bottom = (origin_y - ymin) / res - row0 * ts

    crop_box = (int(round(left)), int(round(top)), int(round(right)), int(round(bottom)))
    crop = mosaic.crop(crop_box)
    cw, ch = crop.size
    crop_arr = np.array(crop)

    lon_span, lat_span = E - W, N - S
    Wpx = MAX_PX
    Hpx = int(round(MAX_PX * lat_span / lon_span))

    xmin_a = origin_x + (col0 * ts + crop_box[0]) * res
    xmax_a = origin_x + (col0 * ts + crop_box[2]) * res
    ymax_a = origin_y - (row0 * ts + crop_box[1]) * res
    ymin_a = origin_y - (row0 * ts + crop_box[3]) * res

    lats = N - (np.arange(Hpx) + 0.5) / Hpx * lat_span
    _, ys = tr.transform(np.zeros_like(lats), lats)
    src_row = (ymax_a - ys) / (ymax_a - ymin_a) * ch

    map_y = np.tile(src_row.astype(np.float32).reshape(-1, 1), (1, Wpx))
    cols_src = (np.arange(Wpx) + 0.5) / Wpx * cw
    map_x = np.tile(cols_src.astype(np.float32).reshape(1, -1), (Hpx, 1))

    warped = cv2.remap(crop_arr, map_x, map_y, interpolation=cv2.INTER_LINEAR,
                        borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))

    # ajuste de opacidad de "No Susceptible" (gris) para no tapar el satelite
    arr = warped.astype(np.float32)
    rgb = arr[:, :, :3]
    alpha = arr[:, :, 3]
    gray = np.array([204, 204, 204], dtype=np.float32)
    dist = np.linalg.norm(rgb - gray, axis=2)
    grayness = np.clip(1.0 - dist / GRAY_TOL, 0.0, 1.0)
    alpha_new = alpha * (1.0 - grayness * GRAY_ALPHA_FACTOR)
    arr[:, :, 3] = alpha_new
    final = np.clip(arr, 0, 255).astype(np.uint8)

    out_img = Image.fromarray(final, mode="RGBA")
    overlay_path = os.path.join(OUT, f"{ID}.webp")
    out_img.save(overlay_path, "WEBP", quality=80, method=6)
    print(f"overlay {out_img.size} -> {overlay_path} "
          f"({os.path.getsize(overlay_path)/1024/1024:.2f} MB)")
    print("MANIFEST bounds:", json.dumps({"n": N, "s": S, "e": E, "w": W}))
    return out_img


def build_legend():
    d = fetch_json(f"{SERVICE}/legend?f=json")
    cats = []
    for item in d["layers"][0]["legend"]:
        b = base64.b64decode(item["imageData"])
        im = Image.open(io.BytesIO(b)).convert("RGBA")
        px = im.getpixel((im.width // 2, im.height // 2))
        cats.append((item["label"], px[:3]))
    print("categorias:", cats)

    Wl, Hl = 480, 56 + 38 * len(cats) + 30
    img = Image.new("RGB", (Wl, Hl), "white")
    dr = ImageDraw.Draw(img)
    try:
        font_title = ImageFont.truetype("arialbd.ttf", 20)
        font_label = ImageFont.truetype("arial.ttf", 17)
        font_small = ImageFont.truetype("arial.ttf", 12)
    except Exception:
        font_title = font_label = font_small = ImageFont.load_default()

    dr.text((16, 14), TITULO_LEYENDA, fill="black", font=font_title)
    y = 56
    sw = 34
    for label, color in cats:
        dr.rectangle([16, y, 16 + sw, y + 24], fill=tuple(color), outline=(80, 80, 80))
        dr.text((16 + sw + 12, y + 2), label, fill="black", font=font_label)
        y += 38
    dr.text((16, Hl - 24), "Fuente: Plataforma SIGMA - CIGIDEN",
            fill=(100, 100, 100), font=font_small)

    leg_path = os.path.join(OUT, f"{ID}_leyenda.webp")
    img.save(leg_path, "WEBP", quality=85, method=6)
    print(f"leyenda {img.size} -> {leg_path} ({os.path.getsize(leg_path)/1024:.1f} KB)")


if __name__ == "__main__":
    build_overlay()
    build_legend()
