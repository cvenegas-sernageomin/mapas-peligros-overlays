"""
Georreferencia el mapa "Peligro de Remociones en Masa - Region de Coquimbo, Sector Sur"
(IR-COQ-03, 16024_IR_88 / Informe Registrado IR-21-88, 1:250.000, SERNAGEOMIN 2021).

- PDF vectorial 1 pagina, proyeccion UTM 19S (EPSG:32719), grilla azul en km.
- A diferencia de georef_coquimbo_norte.py, esta grilla tiene una ligera ROTACION
  (~1 grado) respecto a los ejes de pixeles del render, y el color de la linea
  azul es mas claro (57,115,210) y se confunde con rios si se usa el mismo
  umbral saturado del script 1. Por eso: (a) se usa un umbral de azul mas laxo,
  (b) SOLO se detectan lineas en bandas angostas pegadas a los 4 bordes del
  neat-line (lejos de rios/rellenos que tapan la grilla en el interior), y
  (c) se ajusta un AFIN COMPLETO de 6 parametros (E = a*px+b*py+c ; N =
  d*px+e*py+f) en vez del modelo desacoplado del script 1, para capturar la
  rotacion correctamente.
- La leyenda de este mapa va DEBAJO del mapa (no a la derecha como en el
  sector norte): se recorta toda la franja inferior fuera del neat-line.
- Salida: overlay PNG RGBA (transparente fuera del marco) + leyenda recortada aparte.
"""
import fitz, numpy as np, cv2, json
from PIL import Image
from pyproj import Transformer
from pathlib import Path

PDF = r"C:\Users\carlos.venegas\Documents\Sernageomin_Emergencia 2026\5. COQUIMBO\IR-COQ-03\16024_IR_88_MapaCOQ.pdf"
OUT = Path(r"C:\Users\carlos.venegas\Documents\mapas-peligros-overlays\overlays")
NAME = "coquimbo_sur"
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

    # --- 1) neat-line negro (marco del mapa) primero, para acotar las bandas ---
    black = (R < 70) & (G < 70) & (B < 70)
    rows = sorted(group(np.where(black.sum(1) > 0.35 * W)[0], 8))
    cols = sorted(group(np.where(black.sum(0) > 0.35 * H)[0], 8))
    x0, x1 = cols[1], cols[-2]          # neat-line interior
    y0, y1 = rows[1], rows[-2]
    x0o, x1o = cols[0], cols[-1]        # neat-line exterior (marco doble)
    y0o, y1o = rows[0], rows[-1]
    print(f"  neat-line px: interior x[{x0}:{x1}] y[{y0}:{y1}]  cols={cols} rows={rows}")

    # --- 2) grilla UTM azul: color mas claro que el script 1, detectada solo en
    #        bandas angostas pegadas a los 4 bordes del neat-line (evita rios) ---
    blue = (B > 180) & (R < 150) & (G < 180) & ((B - R) > 60) & ((B - G) > 40)

    BAND = 40
    y_top0, y_top1 = y0, y0 + BAND
    y_bot0, y_bot1 = y1 - BAND, y1
    x_lft0, x_lft1 = x0, x0 + BAND
    x_rgt0, x_rgt1 = x1 - BAND, x1
    y_top_mid = (y_top0 + y_top1) / 2
    y_bot_mid = (y_bot0 + y_bot1) / 2
    x_lft_mid = (x_lft0 + x_lft1) / 2
    x_rgt_mid = (x_rgt0 + x_rgt1) / 2

    # restringido a x0:x1 / y0:y1 (interior del neat-line) para no enganchar
    # artefactos de anti-aliasing del marco negro doble (zona entre borde
    # exterior e interior) que a veces se detectan como "azules" espurios
    vx_top = [v + x0 for v in group(np.where(blue[y_top0:y_top1, x0:x1].sum(0) > 5)[0], 8)]
    vx_bot = [v + x0 for v in group(np.where(blue[y_bot0:y_bot1, x0:x1].sum(0) > 5)[0], 8)]
    hy_lft = [v + y0 for v in group(np.where(blue[y0:y1, x_lft0:x_lft1].sum(1) > 5)[0], 8)]
    hy_rgt = [v + y0 for v in group(np.where(blue[y0:y1, x_rgt0:x_rgt1].sum(1) > 5)[0], 8)]
    print(f"  vx_top({len(vx_top)})={vx_top}")
    print(f"  vx_bot({len(vx_bot)})={vx_bot}")
    print(f"  hy_lft({len(hy_lft)})={hy_lft}")
    print(f"  hy_rgt({len(hy_rgt)})={hy_rgt}")

    # anclas leidas visualmente en los crops de esquina (ver coq03_tl/tr/br.png):
    #   vertical x=416 -> E=240 000 ... en realidad "220 km" (ver crop tl) ; paso ~472.5 px = 20 km
    #   horizontal borde derecho y=5366 -> N=6.440.000 (ver crop br)
    # Se etiqueta cada linea detectada por REDONDEO al multiplo de 20 km mas
    # cercano desde la ancla (robusto a listas de distinto largo por banda,
    # a diferencia de indexar por posicion en la lista que se desfasa si a
    # algun borde le falta/sobra una linea por la rotacion).
    STEP_PX, STEP_M = 472.5, 20000
    E_ANCHOR_PX, E_ANCHOR_M = 416, 220000
    N_ANCHOR_PX, N_ANCHOR_M = 5366, 6440000

    def label(vals, anchor_px, anchor_m, sign):
        vals = np.array(vals, float)
        return anchor_m + sign * np.round((vals - anchor_px) / STEP_PX) * STEP_M

    e_top = label(vx_top, E_ANCHOR_PX, E_ANCHOR_M, +1)
    e_bot = label(vx_bot, E_ANCHOR_PX, E_ANCHOR_M, +1)
    n_lft = label(hy_lft, N_ANCHOR_PX, N_ANCHOR_M, -1)
    n_rgt = label(hy_rgt, N_ANCHOR_PX, N_ANCHOR_M, -1)
    print(f"  e_top={e_top}\n  e_bot={e_bot}\n  n_lft={n_lft}\n  n_rgt={n_rgt}")

    # --- 3) ajuste afin completo (con rotacion): E=a*px+b*py+c ; N=d*px+e*py+f ---
    px_e = np.concatenate([np.array(vx_top, float), np.array(vx_bot, float)])
    py_e = np.concatenate([np.full(len(vx_top), y_top_mid), np.full(len(vx_bot), y_bot_mid)])
    E_v = np.concatenate([e_top, e_bot])
    Ae = np.column_stack([px_e, py_e, np.ones_like(px_e)])
    (a, b, c), *_ = np.linalg.lstsq(Ae, E_v, rcond=None)
    res_e = np.max(np.abs(Ae @ [a, b, c] - E_v))

    px_n = np.concatenate([np.full(len(hy_lft), x_lft_mid), np.full(len(hy_rgt), x_rgt_mid)])
    py_n = np.concatenate([np.array(hy_lft, float), np.array(hy_rgt, float)])
    N_v = np.concatenate([n_lft, n_rgt])
    An = np.column_stack([px_n, py_n, np.ones_like(px_n)])
    (d, e, f), *_ = np.linalg.lstsq(An, N_v, rcond=None)
    res_n = np.max(np.abs(An @ [d, e, f] - N_v))

    print(f"  E = {a:.5f}*px + {b:.5f}*py + {c:.2f}   (res {res_e:.1f} m)")
    print(f"  N = {d:.5f}*px + {e:.5f}*py + {f:.2f}   (res {res_n:.1f} m)")
    rot_deg = np.degrees(np.arctan2(-b, a))
    print(f"  rotacion aparente ~ {rot_deg:.3f} deg")

    # matriz directa pixel->UTM y su inversa UTM->pixel
    M = np.array([[a, b], [d, e]])
    c_vec = np.array([c, f])
    Minv = np.linalg.inv(M)

    to_wgs = Transformer.from_crs(EPSG_UTM, "EPSG:4326", always_xy=True)
    to_utm = Transformer.from_crs("EPSG:4326", EPSG_UTM, always_xy=True)

    def px2geo(x, y):
        E, N = M @ [x, y] + c_vec
        return to_wgs.transform(E, N)

    # geo bbox del neat-line interior
    cor = [px2geo(x0, y0), px2geo(x1, y0), px2geo(x1, y1), px2geo(x0, y1)]
    lons = [p[0] for p in cor]; lats = [p[1] for p in cor]
    west, east = min(lons), max(lons)
    south, north = min(lats), max(lats)
    print(f"  bbox geo: N={north:.5f} S={south:.5f} E={east:.5f} W={west:.5f}")

    # --- 4) warp plate-carree del recorte ---
    OW = x1 - x0
    OH = int(round(OW * (north - south) / (east - west)))
    lon_g = west + (np.arange(OW) / (OW - 1)) * (east - west)
    lat_g = north - (np.arange(OH) / (OH - 1)) * (north - south)
    LON, LAT = np.meshgrid(lon_g, lat_g)
    E, N = to_utm.transform(LON.ravel(), LAT.ravel())
    EN = np.vstack([E, N])
    PXY = Minv @ (EN - c_vec[:, None])
    mx = PXY[0].reshape(LAT.shape).astype(np.float32)
    my = PXY[1].reshape(LAT.shape).astype(np.float32)
    warped = cv2.remap(img, mx, my, cv2.INTER_LINEAR,
                       borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))
    inside = (mx >= x0) & (mx <= x1) & (my >= y0) & (my <= y1)
    rgba = np.dstack([warped, (inside * 255).astype(np.uint8)])
    OUT.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba).save(OUT / f"{NAME}.png")
    print(f"  overlay -> {NAME}.png  {OW}x{OH}")

    # --- 5) leyenda: en este mapa va DEBAJO del neat-line (no a la derecha) ---
    y_leg = y1o + 8
    leg = img[y_leg:H, 0:W]
    Image.fromarray(leg).save(OUT / f"{NAME}_leyenda.png")
    print(f"  leyenda -> {NAME}_leyenda.png  {leg.shape[1]}x{leg.shape[0]}")

    # --- 6) verificacion: puntos conocidos dentro del bbox ---
    puntos = {"Ovalle": (-71.2000, -30.6017), "Combarbala": (-71.0083, -31.1758),
              "Illapel": (-71.1667, -31.6333), "Los Vilos": (-71.5111, -31.9111)}
    print("  check (esperado deben caer dentro del bbox):")
    for k, (lo, la) in puntos.items():
        dentro = west <= lo <= east and south <= la <= north
        print(f"    {k}: {lo},{la}  dentro={dentro}")

    meta = dict(id=NAME, bounds=dict(n=round(north, 6), s=round(south, 6),
                e=round(east, 6), w=round(west, 6)), res_e_m=float(round(res_e, 1)),
                res_n_m=float(round(res_n, 1)), rot_deg=round(float(rot_deg), 3),
                size=[int(OW), int(OH)])
    print("META", json.dumps(meta))
    (OUT / f"{NAME}_meta.json").write_text(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
