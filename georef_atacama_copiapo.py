"""
Georreferencia el mapa "Susceptibilidad de Remociones en Masa en la Cuenca del
Rio Copiapo, Region de Atacama" (SERNAGEOMIN, Informe Registrado IR-22-99,
Fernandez & Espinoza 2022, escala 1:100.000, 4 hojas que calzan de oeste a
este siguiendo el rio Copiapo).

- PDF de 4 paginas (1 por hoja), vectorial, proyeccion UTM 19S / SIRGAS
  (declarada en el propio mapa) = EPSG:32719.
- Grilla UTM azul (RGB ~ 79,108,207), paso 10 km. A diferencia de Coquimbo,
  la grilla queda TAPADA por los rellenos de color de las poligonos de
  susceptibilidad en gran parte del mapa (colores solidos por encima),
  ademas de que el mismo tono de azul se usa para hidrografia -> la deteccion
  robusta NO puede barrer toda la grilla por color; en cambio se usan 4
  BANDAS ANGOSTAS pegadas a los 4 bordes del neat-line (10 px hacia adentro),
  zona que esta libre de rellenos e hidrografia densa, igual que
  georef_coquimbo_sur.py. Hay una ligera ROTACION (~0.47 grados) consistente
  en las 4 hojas -> se usa el afin completo de 6 parametros (igual que
  coquimbo_sur), NO el desacoplado simple.
- Cada hoja trae su propia tabla LEYENDA (identica en las 4). En la Hoja 1
  la leyenda va en un bloque APARTE, debajo del neat-line del mapa (no se
  traslapa) -> se usa esa como leyenda UNICA compartida por las 4 hojas
  (igual patron que georef_valparaiso.py). En las hojas 2-4 la leyenda es un
  recuadro INSERTO dentro de la extension del mapa (esquina, sobre zona sin
  datos/Argentina) -> no se recorta aparte, queda tal cual en el overlay
  (fiel al mapa impreso).
- Salida: overlay WebP RGBA (alpha=0 fuera del neat-line) x4 hojas +
  1 leyenda WebP compartida.
"""
import fitz, numpy as np, cv2, json
from PIL import Image
from pyproj import Transformer
from pathlib import Path

PDF = r"C:\Users\carlos.venegas\Documents\Sernageomin_Emergencia 2026\Atacama\16120_IR_99_MapasATACAMA.pdf"
OUT = Path(r"C:\Users\carlos.venegas\Documents\mapas-peligros-overlays\overlays")
OUT.mkdir(parents=True, exist_ok=True)
EPSG_UTM = "EPSG:32719"
DPI = 150
MAX_PX = 3000

to_wgs = Transformer.from_crs(EPSG_UTM, "EPSG:4326", always_xy=True)
to_utm = Transformer.from_crs("EPSG:4326", EPSG_UTM, always_xy=True)


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


def render(page_idx, dpi=DPI):
    pg = fitz.open(PDF)[page_idx]
    sc = dpi / 72
    pix = pg.get_pixmap(matrix=fitz.Matrix(sc, sc))
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        img = img[:, :, :3]
    return np.ascontiguousarray(img)


def blue_mask(img):
    R, G, B = img[:, :, 0].astype(int), img[:, :, 1].astype(int), img[:, :, 2].astype(int)
    return (B > 140) & ((B - R) > 30) & ((B - G) > 10)


def detect_edge_lines(blue, x0, x1, y0, y1, band=10, thr_frac=0.5,
                       top_x=None, bot_x=None, lft_y=None, rgt_y=None):
    """Lineas verticales (top/bottom) y horizontales (left/right) en bandas
    angostas pegadas a los 4 bordes del neat-line [x0:x1, y0:y1]. Cada lado
    admite un sub-rango propio (top_x/bot_x/lft_y/rgt_y) para esquivar
    hidrografia que cruza cerca del borde (rios/tranques con el mismo azul
    de la grilla) en zonas puntuales de una hoja."""
    tx0, tx1 = top_x or (x0, x1)
    bx0, bx1 = bot_x or (x0, x1)
    ly0, ly1 = lft_y or (y0, y1)
    ry0, ry1 = rgt_y or (y0, y1)
    thr = max(1, int(band * thr_frac))
    top = blue[y0:y0 + band, tx0:tx1]
    bot = blue[y1 - band:y1, bx0:bx1]
    lft = blue[ly0:ly1, x0:x0 + band]
    rgt = blue[ry0:ry1, x1 - band:x1]
    vx_top = [v + tx0 for v in group(np.where(top.sum(0) >= thr)[0], 8)]
    vx_bot = [v + bx0 for v in group(np.where(bot.sum(0) >= thr)[0], 8)]
    hy_lft = [v + ly0 for v in group(np.where(lft.sum(1) >= thr)[0], 8)]
    hy_rgt = [v + ry0 for v in group(np.where(rgt.sum(1) >= thr)[0], 8)]
    return vx_top, vx_bot, hy_lft, hy_rgt


def label_by_step(vals, anchor_px, anchor_m, step_px, step_m, sign):
    vals = np.array(vals, float)
    return anchor_m + sign * np.round((vals - anchor_px) / step_px) * step_m


def fit_affine6(px_e, py_e, E_v, px_n, py_n, N_v):
    Ae = np.column_stack([px_e, py_e, np.ones_like(px_e)])
    (a, b, c), *_ = np.linalg.lstsq(Ae, E_v, rcond=None)
    res_e = float(np.max(np.abs(Ae @ [a, b, c] - E_v)))
    An = np.column_stack([px_n, py_n, np.ones_like(px_n)])
    (d, e, f), *_ = np.linalg.lstsq(An, N_v, rcond=None)
    res_n = float(np.max(np.abs(An @ [d, e, f] - N_v)))
    return a, b, c, d, e, f, res_e, res_n


def warp_and_save(img, M, c_vec, x0, x1, y0, y1, name, max_px=MAX_PX):
    Minv = np.linalg.inv(M)

    def px2geo(x, y):
        E, N = M @ [x, y] + c_vec
        return to_wgs.transform(E, N)

    cor = [px2geo(x0, y0), px2geo(x1, y0), px2geo(x1, y1), px2geo(x0, y1)]
    lons = [p[0] for p in cor]; lats = [p[1] for p in cor]
    west, east = min(lons), max(lons)
    south, north = min(lats), max(lats)

    OW = min(x1 - x0, max_px)
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
    webp = OUT / f"{name}.webp"
    Image.fromarray(rgba).save(webp, "WEBP", quality=80, method=6)
    size_mb = webp.stat().st_size / 1024 / 1024
    print(f"  overlay -> {webp.name}  {OW}x{OH}  {size_mb:.2f} MB")
    return dict(west=west, east=east, south=south, north=north, size=[OW, OH])


def check_points(west, east, south, north, puntos):
    for k, (lo, la) in puntos.items():
        dentro = west <= lo <= east and south <= la <= north
        print(f"    {k}: {lo},{la}  dentro={dentro}")


STEP_PX, STEP_M = 590.6, 10000

# neat-line interior de cada hoja (detectado con deteccion de marco negro +
# inspeccion visual): x0,x1,y0,y1 @ 150dpi
SHEETS = {
    0: dict(x0=117, x1=2893, y0=216, y1=3387,
            e_anchor_px=497, e_anchor_m=310000,
            n_anchor_px=257, n_anchor_m=7010000,
            rgt_y=(216, 1550)),  # evita rio que cruza el borde derecho mas abajo
    1: dict(x0=117, x1=9034, y0=188, y1=4639,
            e_anchor_px=272, e_anchor_m=380000,
            n_anchor_px=243, n_anchor_m=7050000),
    2: dict(x0=117, x1=9181, y0=214, y1=4665,
            e_anchor_px=6644, e_anchor_m=490000,
            n_anchor_px=4342, n_anchor_m=6910000),
    3: dict(x0=117, x1=7049, y0=212, y1=4659,
            e_anchor_px=398, e_anchor_m=390000,
            n_anchor_px=587, n_anchor_m=6900000),
}


def main():
    meta = {}

    # ---------------- Hoja 1: fit completo (6 parametros) ----------------
    print("=== Hoja 1 de 4 ===")
    img0 = render(0)
    blue0 = blue_mask(img0)
    s0 = SHEETS[0]
    vx_top, vx_bot, hy_lft, hy_rgt = detect_edge_lines(
        blue0, s0['x0'], s0['x1'], s0['y0'], s0['y1'], rgt_y=s0.get('rgt_y'))

    e_top = label_by_step(vx_top, s0['e_anchor_px'], s0['e_anchor_m'], STEP_PX, STEP_M, +1)
    e_bot = label_by_step(vx_bot, s0['e_anchor_px'], s0['e_anchor_m'], STEP_PX, STEP_M, +1)
    n_lft = label_by_step(hy_lft, s0['n_anchor_px'], s0['n_anchor_m'], STEP_PX, STEP_M, -1)
    n_rgt = label_by_step(hy_rgt, s0['n_anchor_px'], s0['n_anchor_m'], STEP_PX, STEP_M, -1)

    px_e = np.concatenate([vx_top, vx_bot]).astype(float)
    py_e = np.concatenate([np.full(len(vx_top), s0['y0'] + 5.0), np.full(len(vx_bot), s0['y1'] - 5.0)])
    E_v = np.concatenate([e_top, e_bot])
    px_n = np.concatenate([np.full(len(hy_lft), s0['x0'] + 5.0), np.full(len(hy_rgt), s0['x1'] - 5.0)])
    py_n = np.concatenate([hy_lft, hy_rgt]).astype(float)
    N_v = np.concatenate([n_lft, n_rgt])

    a, b, c, d, e, f, res_e, res_n = fit_affine6(px_e, py_e, E_v, px_n, py_n, N_v)
    print(f"  E = {a:.5f}*px + {b:.5f}*py + {c:.2f}   (res {res_e:.1f} m)")
    print(f"  N = {d:.5f}*px + {e:.5f}*py + {f:.2f}   (res {res_n:.1f} m)")
    rot_deg = np.degrees(np.arctan2(-b, a))
    print(f"  rotacion aparente ~ {rot_deg:.3f} deg (reusada en hojas 2-4)")

    M = np.array([[a, b], [d, e]])
    c_vec = np.array([c, f])

    r0 = warp_and_save(img0, M, c_vec, s0['x0'], s0['x1'], s0['y0'], s0['y1'], "atacama_copiapo_hoja1")
    print(f"  bbox: N={r0['north']:.6f} S={r0['south']:.6f} E={r0['east']:.6f} W={r0['west']:.6f}")
    check_points(r0['west'], r0['east'], r0['south'], r0['north'],
                 {"Caldera": (-70.8228, -27.0675)})
    meta["atacama_copiapo_hoja1"] = dict(bounds=r0, res_e_m=res_e, res_n_m=res_n,
                                          rot_deg=round(float(rot_deg), 3))

    # leyenda: bloque aparte debajo del neat-line de la Hoja 1 (unica, compartida)
    leg = img0[3448:6383, 0:img0.shape[1]]
    leg_img = Image.fromarray(leg)
    if leg_img.width > 1600:
        h = int(leg_img.height * 1600 / leg_img.width)
        leg_img = leg_img.resize((1600, h), Image.LANCZOS)
    leg_path = OUT / "atacama_copiapo_leyenda.webp"
    leg_img.save(leg_path, "WEBP", quality=82, method=6)
    print(f"  leyenda -> {leg_path.name}  {leg_img.width}x{leg_img.height}  "
          f"{leg_path.stat().st_size/1024:.0f} KB")

    # ------- Hojas 2-4: mismo giro (a,b,d,e) de la Hoja 1, offset (c,f) -------
    # por un unico anclaje limpio por hoja (grilla muy contaminada por rios/
    # curvas de nivel cerca del margen en estas hojas -> el fit de 6 parametros
    # con muchos puntos no es confiable; la rotacion es del mismo producto
    # cartografico impreso igual en las 4 hojas, ~590.6 px/10km @ 150dpi).
    names = {1: "atacama_copiapo_hoja2", 2: "atacama_copiapo_hoja3", 3: "atacama_copiapo_hoja4"}
    check_pts = {
        1: {"Copiapo": (-70.3323, -27.3668)},
        2: {"Los Loros": (-70.0964, -27.9058)},
        3: {},
    }
    for idx in (1, 2, 3):
        print(f"\n=== Hoja {idx+1} de 4 ===")
        s = SHEETS[idx]
        img = render(idx)
        px, py = s['e_anchor_px'], s['y0'] + 5.0
        c_i = s['e_anchor_m'] - a * px - b * py
        px2, py2 = s['x0'] + 5.0, s['n_anchor_px']
        f_i = s['n_anchor_m'] - d * px2 - e * py2
        c_vec_i = np.array([c_i, f_i])
        print(f"  offset por anclaje: c={c_i:.2f} f={f_i:.2f}")

        r = warp_and_save(img, M, c_vec_i, s['x0'], s['x1'], s['y0'], s['y1'], names[idx])
        print(f"  bbox: N={r['north']:.6f} S={r['south']:.6f} E={r['east']:.6f} W={r['west']:.6f}")
        check_points(r['west'], r['east'], r['south'], r['north'], check_pts[idx])
        meta[names[idx]] = dict(bounds=r, rot_deg=round(float(rot_deg), 3), anchored=True)

    (OUT / "atacama_copiapo_meta.json").write_text(json.dumps(meta, indent=2))
    print("\nMETA guardada en atacama_copiapo_meta.json")


if __name__ == "__main__":
    main()
