"""
Georreferencia el "Mapa 4: Peligro de Remociones en Masa" de la publicacion
"Geologia para el Ordenamiento Territorial: Area de Rancagua" (Region del
Libertador General Bernardo O'Higgins), Carta Geologica de Chile, Serie
Geologia Ambiental N 29 (Alfaro, A.; Arenas, M. et al., SERNAGEOMIN, 2017),
escala 1:100.000.

- PDF vectorial 1 pagina que trae VARIOS elementos en la misma hoja: el mapa
  principal (Mapa 4, arriba-izquierda, el que se georreferencia aca), un mapa
  SECUNDARIO distinto ("Densidad de Remociones en Masa", 1:250.000, arriba-
  derecha, NO se usa), y LEYENDA + SIMBOLOGIA debajo del mapa principal
  (se recortan como leyenda propia).
- El Mapa 4 tiene marco doble (como los mapas de Coquimbo): se usa el
  neat-line INTERIOR para el recorte limpio.
- Proyeccion: UTM huso 19S, referencia geodesica SIRGAS (declarado en el
  propio mapa: "Referencia geodesica: Proyeccion Universal Transversal de
  Mercator (UTM), Zona 19S, SIRGAS") -> equivalente a WGS84 para estos
  efectos, se usa EPSG:32719 (a diferencia de las hojas de Valparaiso del
  mismo lote, que declaran PSAD56 y usan EPSG:24879).
- Grilla UTM AZUL con paso de 5 km (etiquetas "320 km"..."360 km" en E,
  "6 210 km".."6 235 km" en N), y con una ROTACION real de ~1 grado (igual
  fenomeno que georef_coquimbo_sur.py: la fila de ticks de abajo esta
  corrida ~38 px respecto a la de arriba en un alto de mapa de ~2180 px).
  Por eso se usa el mismo modelo AFIN COMPLETO de 6 parametros (E=a*px+b*py+c
  ; N=d*px+e*py+f) en vez del modelo desacoplado.
- Salida: overlay WebP RGBA (alpha=0 fuera del neat-line) + leyenda WebP
  propia (LEYENDA + SIMBOLOGIA, no compartida con otros mapas del repo).
"""
import fitz, numpy as np, cv2, json
from PIL import Image
from pyproj import Transformer
from pathlib import Path

PDF = r"C:\Users\carlos.venegas\.claude\uploads\9e1a9035-2071-4dd6-9bb5-c9f650628f73\c0ee3863-CGCH_GAMB_29_TextoyMapas_187.pdf"
OUT = Path(r"C:\Users\carlos.venegas\Documents\mapas-peligros-overlays\overlays")
NAME = "ohiggins_rancagua"
EPSG_UTM = "EPSG:32719"   # UTM 19S, SIRGAS ~ WGS84 (ver docstring)
DPI = 200
MAX_PX = 3000


def main():
    pg = fitz.open(PDF)[0]
    sc = DPI / 72
    pix = pg.get_pixmap(matrix=fitz.Matrix(sc, sc))
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        img = img[:, :, :3]
    img = np.ascontiguousarray(img)
    H, W = img.shape[:2]
    print(f"Render {W}x{H} @ {DPI}dpi")

    # --- 1) neat-line del Mapa 4 (marco doble, se detecto restringiendo la
    #        busqueda a la region superior-izquierda de la hoja para no
    #        enganchar el mapa secundario de Densidad ni el marco de la hoja
    #        completa) ---
    x0, x1, y0, y1 = 109, 3740, 179, 2362   # interior (detectado con fitz+numpy)
    print(f"  neat-line interior px: x[{x0}:{x1}] y[{y0}:{y1}]")

    # --- 2) grilla UTM azul: paso 5 km, leida y verificada visualmente en
    #        los 4 crops de esquina (tl/tr/bl/br), detectada por color en
    #        bandas angostas pegadas a los 4 bordes del neat-line ---
    STEP_PX, STEP_M = 393.9, 5000
    E_ANCHOR_PX, E_ANCHOR_M = 477, 320000
    N_ANCHOR_PX, N_ANCHOR_M = 261, 6235000

    vx_top = [477, 871, 1264, 1658, 2052, 2446, 2839, 3233, 3627]
    vx_bot = [439, 833, 1227, 1621, 2015, 2408, 2802, 3196, 3590]
    hy_lft = [261, 655, 1049, 1443, 1836, 2230]
    hy_rgt = [324, 718, 1111, 1505, 1899, 2293]
    BAND = 35
    y_top_mid = y0 + BAND / 2
    y_bot_mid = y1 - BAND / 2
    x_lft_mid = x0 + BAND / 2
    x_rgt_mid = x1 - BAND / 2

    def label(vals, anchor_px, anchor_m, sign):
        vals = np.array(vals, float)
        return anchor_m + sign * np.round((vals - anchor_px) / STEP_PX) * STEP_M

    e_top = label(vx_top, E_ANCHOR_PX, E_ANCHOR_M, +1)
    e_bot = label(vx_bot, E_ANCHOR_PX, E_ANCHOR_M, +1)
    n_lft = label(hy_lft, N_ANCHOR_PX, N_ANCHOR_M, -1)
    n_rgt = label(hy_rgt, N_ANCHOR_PX, N_ANCHOR_M, -1)
    print(f"  e_top={e_top}\n  e_bot={e_bot}\n  n_lft={n_lft}\n  n_rgt={n_rgt}")

    # --- 3) ajuste afin completo (con rotacion), igual patron que
    #        georef_coquimbo_sur.py ---
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

    M = np.array([[a, b], [d, e]])
    c_vec = np.array([c, f])
    Minv = np.linalg.inv(M)

    to_wgs = Transformer.from_crs(EPSG_UTM, "EPSG:4326", always_xy=True)
    to_utm = Transformer.from_crs("EPSG:4326", EPSG_UTM, always_xy=True)

    def px2geo(x, y):
        E, N = M @ [x, y] + c_vec
        return to_wgs.transform(E, N)

    cor = [px2geo(x0, y0), px2geo(x1, y0), px2geo(x1, y1), px2geo(x0, y1)]
    lons = [p[0] for p in cor]; lats = [p[1] for p in cor]
    west, east = min(lons), max(lons)
    south, north = min(lats), max(lats)
    print(f"  bbox geo: N={north:.6f} S={south:.6f} E={east:.6f} W={west:.6f}")

    # --- 4) warp plate-carree del recorte ---
    OW = min(x1 - x0, MAX_PX)
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
    webp = OUT / f"{NAME}.webp"
    Image.fromarray(rgba).save(webp, "WEBP", quality=80, method=6)
    print(f"  overlay -> {webp.name}  {OW}x{OH}  {webp.stat().st_size/1024/1024:.2f} MB")

    # --- 5) leyenda propia: LEYENDA + SIMBOLOGIA, debajo del Mapa 4 (todo el
    #        ancho de la hoja hasta antes del mapa secundario de Densidad) ---
    leg = img[2450:H, 0:3750]
    leg_img = Image.fromarray(leg)
    if leg_img.width > 1400:
        h = int(leg_img.height * 1400 / leg_img.width)
        leg_img = leg_img.resize((1400, h), Image.LANCZOS)
    leg_path = OUT / f"{NAME}_leyenda.webp"
    leg_img.save(leg_path, "WEBP", quality=82, method=6)
    print(f"  leyenda -> {leg_path.name}  {leg_img.width}x{leg_img.height}  "
          f"{leg_path.stat().st_size/1024:.0f} KB")

    # --- 6) verificacion: puntos conocidos dentro del bbox ---
    puntos = {"Rancagua": (-70.7444, -34.1708), "Doñihue": (-70.9750, -34.1922),
              "Machali": (-70.6467, -34.1811), "Graneros": (-70.7300, -34.0678)}
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
