"""
Georreferencia el mapa "Peligro de Remociones en Masa - Region de Coquimbo, Sector Norte"
(IR-COQ-02, 15633_IR_68, 1:250.000, SERNAGEOMIN 2018).

- PDF vectorial 1 pagina, proyeccion UTM 19S (EPSG:32719), grilla azul en km.
- Detecta la grilla UTM azul por color -> ajuste afin pixel->UTM (sin OCR).
- Recorta al neat-line (marco negro del mapa) y WARP UTM->WGS84 plate-carree
  (norte-arriba, rotacion 0) para que calce exacto en Leaflet (imageOverlay).
- Salida: overlay PNG RGBA (transparente fuera del marco) + leyenda recortada aparte.

Reutiliza el patron de georef_ir114.py / to_latlonbox.py de sernageomin_maule.
"""
import fitz, numpy as np, cv2, json
from PIL import Image
from pyproj import Transformer
from pathlib import Path

PDF = r"C:\Users\carlos.venegas\Documents\Sernageomin_Emergencia 2026\5. COQUIMBO\IR-COQ-02\15633_IR_68_MapaCOQUIMBO.pdf"
OUT = Path(r"C:\Users\carlos.venegas\Documents\mapas-peligros-overlays\overlays")
NAME = "coquimbo_norte"
EPSG_UTM = "EPSG:32719"
DPI = 150
sc = DPI / 72


def group(idx, gap):
    if len(idx) == 0:
        return []
    g = []; s = idx[0]; pv = idx[0]
    for i in idx[1:]:
        if i - pv > gap:
            g.append((s + pv) // 2); s = i
        pv = i
    g.append((s + pv) // 2)
    return g


def main():
    pg = fitz.open(PDF)[0]
    pix = pg.get_pixmap(matrix=fitz.Matrix(sc, sc))
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        img = img[:, :, :3]
    img = np.ascontiguousarray(img)
    H, W = img.shape[:2]
    print(f"Render {W}x{H} @ {DPI}dpi")
    R, G, B = img[:, :, 0].astype(int), img[:, :, 1].astype(int), img[:, :, 2].astype(int)

    # --- 1) grilla UTM azul (lineas saturadas de azul) ---
    blue = (B > 110) & (R < 90) & (G < 90) & ((B - R) > 60) & ((B - G) > 60)
    vx = group(np.where(blue.sum(0) > 0.5 * blue.sum(0).max())[0], 5)
    hy = group(np.where(blue.sum(1) > 0.5 * blue.sum(1).max())[0], 5)
    # anclas leidas visualmente en los crops de esquina:
    #   vertical x=227 -> E=240000 ; horizontal y=324 -> N=6.780.000 ; paso 20 km ~= 472.5 px
    STEP_PX, STEP_M = 472.5, 20000
    ex = np.array(vx, float)
    ev = 240000 + np.round((ex - 227) / STEP_PX) * STEP_M
    ny = np.array(hy, float)
    nv = 6780000 - np.round((ny - 324) / STEP_PX) * STEP_M
    ae, be = np.polyfit(ex, ev, 1)   # E = ae*x + be
    an, bn = np.polyfit(ny, nv, 1)   # N = an*y + bn
    res_e = np.max(np.abs(np.polyval([ae, be], ex) - ev))
    res_n = np.max(np.abs(np.polyval([an, bn], ny) - nv))
    print(f"  vert lines {len(vx)}  slope_E={ae:.4f} m/px (res {res_e:.0f} m)")
    print(f"  horz lines {len(hy)}  slope_N={an:.4f} m/px (res {res_n:.0f} m)")

    # --- 2) neat-line negro (marco del mapa) ---
    black = (R < 70) & (G < 70) & (B < 70)
    rows = sorted(group(np.where(black.sum(1) > 0.35 * W)[0], 8))
    cols = sorted(group(np.where(black.sum(0) > 0.35 * H)[0], 8))
    # marco doble: usar el INTERIOR para un recorte limpio del mapa (sin titulo ni margenes)
    x0, x1 = cols[1], cols[-2]          # 117 .. 4601 (neat-line interior)
    y0, y1 = rows[1], rows[-2]          # 158 .. 4708
    x_leg = cols[-1] + 8               # leyenda empieza tras el marco exterior derecho
    print(f"  neat-line px: x[{x0}:{x1}] y[{y0}:{y1}]  (cols={cols} rows={rows})")

    to_wgs = Transformer.from_crs(EPSG_UTM, "EPSG:4326", always_xy=True)
    to_utm = Transformer.from_crs("EPSG:4326", EPSG_UTM, always_xy=True)

    def px2geo(x, y):
        return to_wgs.transform(ae * x + be, an * y + bn)

    # geo bbox del neat-line
    cor = [px2geo(x0, y0), px2geo(x1, y0), px2geo(x1, y1), px2geo(x0, y1)]
    lons = [c[0] for c in cor]; lats = [c[1] for c in cor]
    west, east = min(lons), max(lons)
    south, north = min(lats), max(lats)
    print(f"  bbox geo: N={north:.5f} S={south:.5f} E={east:.5f} W={west:.5f}")

    # --- 3) warp plate-carree del recorte ---
    OW = x1 - x0
    OH = int(round(OW * (north - south) / (east - west)))
    lon_g = west + (np.arange(OW) / (OW - 1)) * (east - west)
    lat_g = north - (np.arange(OH) / (OH - 1)) * (north - south)
    LON, LAT = np.meshgrid(lon_g, lat_g)
    E, N = to_utm.transform(LON.ravel(), LAT.ravel())
    mx = ((E.reshape(LAT.shape) - be) / ae).astype(np.float32)
    my = ((N.reshape(LAT.shape) - bn) / an).astype(np.float32)
    warped = cv2.remap(img, mx, my, cv2.INTER_LINEAR,
                       borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))
    # alpha=0 fuera del neat-line (donde el pixel fuente cae fuera del marco)
    inside = (mx >= x0) & (mx <= x1) & (my >= y0) & (my <= y1)
    rgba = np.dstack([warped, (inside * 255).astype(np.uint8)])
    OUT.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba).save(OUT / f"{NAME}.png")
    print(f"  overlay -> {NAME}.png  {OW}x{OH}")

    # --- 4) leyenda recortada (a la derecha del neat-line) ---
    leg = img[y0:y1, x_leg:W]
    Image.fromarray(leg).save(OUT / f"{NAME}_leyenda.png")
    print(f"  leyenda -> {NAME}_leyenda.png  {leg.shape[1]}x{leg.shape[0]}")

    # --- 5) verificacion: puntos conocidos ---
    puntos = {"La Serena": (-71.2500, -29.9078), "Vicuna": (-70.7100, -30.0319),
              "Ovalle": (-71.2000, -30.6017)}
    print("  check (esperado deben caer dentro del bbox):")
    for k, (lo, la) in puntos.items():
        dentro = west <= lo <= east and south <= la <= north
        print(f"    {k}: {lo},{la}  dentro={dentro}")

    meta = dict(id=NAME, bounds=dict(n=round(north, 6), s=round(south, 6),
                e=round(east, 6), w=round(west, 6)), res_e_m=int(round(res_e)),
                res_n_m=int(round(res_n)), size=[int(OW), int(OH)])
    print("META", json.dumps(meta))
    (OUT / f"{NAME}_meta.json").write_text(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
