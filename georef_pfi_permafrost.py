# -*- coding: utf-8 -*-
"""
Georeferencia el raster PFI (Permafrost Favorability Index, Azocar/Brenning/Bodin 2017,
andespermafrost.com) a WebP alpha + bounds WGS84, siguiendo el patron del repo
(overlay recortado a la mascara real, sin relleno blanco).

Fuente: pfi.sdat (SAGA GIS grid), EPSG:32719, 30 m, 5412x19293 px, ~4.3% pixeles validos
(mascara de terreno montanoso). Rango de valores 0.03-0.999 (0=desfavorable, 1=muy favorable).

Uso: python georef_pfi_permafrost.py <ruta_a_pfi.sdat>
"""
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from PIL import Image

HERE = Path(__file__).parent
OUT_DIR = HERE / "overlays"
CAP_PX = 3000  # misma convencion del repo (variante A paso 4)

# Rampa verde->amarillo->naranja->rojo, igual convencion que zonificacion morfoclimatica
# (Baja/Moderada/Alta/Muy Alta) para que el usuario lea "mas rojo = mas favorable" de forma
# consistente con el resto de la app.
STOPS = [
    (0.00, (26, 152, 80)),    # verde
    (0.35, (166, 217, 106)),  # verde claro
    (0.55, (255, 255, 191)),  # amarillo
    (0.75, (253, 174, 97)),   # naranja
    (1.00, (215, 25, 28)),    # rojo
]


def ramp(v):
    """v en [0,1] -> (r,g,b) interpolando STOPS."""
    for i in range(len(STOPS) - 1):
        v0, c0 = STOPS[i]
        v1, c1 = STOPS[i + 1]
        if v0 <= v <= v1:
            t = 0 if v1 == v0 else (v - v0) / (v1 - v0)
            return tuple(int(c0[k] + t * (c1[k] - c0[k])) for k in range(3))
    return STOPS[-1][1]


LUT = np.array([ramp(i / 255) for i in range(256)], dtype=np.uint8)


def main(src_path):
    src_path = Path(src_path)
    with rasterio.open(src_path) as src:
        print("origen:", src.crs, src.bounds, src.shape, "nodata=", src.nodata)

        dst_crs = "EPSG:4326"
        transform0, width0, height0 = calculate_default_transform(
            src.crs, dst_crs, src.width, src.height, *src.bounds
        )

        # downsample para no pasar el cap de pixeles (mantiene aspecto)
        scale = min(1.0, CAP_PX / max(width0, height0))
        width = max(1, int(width0 * scale))
        height = max(1, int(height0 * scale))
        transform, width, height = calculate_default_transform(
            src.crs, dst_crs, src.width, src.height, *src.bounds,
            dst_width=width, dst_height=height,
        )

        dst = np.full((height, width), np.nan, dtype=np.float32)
        reproject(
            source=rasterio.band(src, 1),
            destination=dst,
            src_transform=src.transform,
            src_crs=src.crs,
            src_nodata=src.nodata,
            dst_transform=transform,
            dst_crs=dst_crs,
            dst_nodata=np.nan,
            resampling=Resampling.bilinear,
        )

        # bounds WGS84 del raster de salida
        left = transform.c
        top = transform.f
        right = left + transform.a * width
        bottom = top + transform.e * height
        bounds = {"n": round(top, 6), "s": round(bottom, 6), "e": round(right, 6), "w": round(left, 6)}
        print("bounds WGS84 salida:", bounds, "size:", width, "x", height)

    valid = ~np.isnan(dst)
    idx = np.clip((np.nan_to_num(dst, nan=0.0) * 255).astype(np.int32), 0, 255)
    rgb = LUT[idx]
    alpha = np.where(valid, 255, 0).astype(np.uint8)
    rgba = np.dstack([rgb, alpha])

    OUT_DIR.mkdir(exist_ok=True)
    out_path = OUT_DIR / "pfi_permafrost.webp"
    Image.fromarray(rgba, "RGBA").save(out_path, "WEBP", lossless=False, quality=90)
    print("guardado:", out_path, out_path.stat().st_size / 1024, "KB")

    return bounds, width, height


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else r"pfi.sdat"
    main(src)
