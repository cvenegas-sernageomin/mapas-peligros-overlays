"""
Georreferencia las 3 hojas del mapa "Peligro de Remociones en Masa e Inundaciones
de las Ciudades de Valparaiso, Vina del Mar y Concon" (SERNAGEOMIN, Informe
Registrado IR-05-29 / Inscripcion 11.543, "Mapa 2 de 2", escala 1:10.000,
publicado en 6 hojas de las cuales estas son Hoja 1/3, 2/3 y 3/3 del mapa de
peligro; referencia bibliografica: Lopez L., Wall R., Prat M. 2005).

- 3 PDFs vectoriales de 1 pagina c/u, proyeccion UTM huso 19 (segun el propio
  mapa: "Datos cartograficos: Proyeccion Universal Transversal de Mercator,
  referidas al huso 19"), pero a diferencia de los mapas de Coquimbo (que usan
  WGS84 = EPSG:32719), este informe declara explicitamente en "Datos geodesicos":
  "Elipsoide de referencia Internacional de 1924 / Datum Provisorio Sudamericano
  (PSAD), La Canoa, Venezuela, 1956" -> el CRS correcto es PSAD56 / UTM zone 19S
  = EPSG:24879 (NO 32719). Usar 32719 aqui introduce un corrimiento sistematico
  de ~190 m E / ~370 m N (~415 m total) hacia el SW. Verificado con pyproj.
- Grilla UTM: NO es azul como en Coquimbo, son lineas grises finas (casi
  acromaticas, R=G=B) con tics y etiquetas negras en los bordes, paso de
  1000 m (mucho mas fino que los 20 km de Coquimbo, consistente con la escala
  urbana 1:10.000). Detectada por contraste local (linea mas oscura que sus
  vecinos a +/-3px), no por umbral de color de matiz, porque el gris se mezcla
  con rellenos de color muy variados (amarillo-verde, naranjo, rojo).
- Sin rotacion apreciable (residuales del modelo afin desacoplado E=f(x),
  N=f(y) < 3.5 m en las 3 hojas) -> no hace falta el modelo de 6 parametros de
  coquimbo_sur.
- Hoja 1 (v4) = "Concon" (sector norte, incluye parte norte de Vina del Mar).
- Hoja 2 (v5) = "Vina del Mar" (sector centro) y ADEMAS trae, dentro del mismo
  marco/hoja pero en la mitad derecha (zona sin datos de peligro, terreno alto/
  fuera del area de estudio), la tabla LEYENDA completa + notas + paneles
  auxiliares (simbologia, trabajos anteriores, mapa de ubicacion, datos
  cartograficos/geodesicos, rotulo). Esa mitad derecha NO es parte del mapa de
  peligro y se recorta aparte como leyenda; el mapa util (poligonos de peligro)
  ocupa solo hasta aprox. E=482..6570 px @200dpi (mucho menos que el marco
  completo 482..7300).
- Hoja 3 (v6) = "Valparaiso" (sector sur/costero, incluye tambien el borde sur
  de Vina del Mar).
- Las 3 hojas comparten la MISMA leyenda (confirmado visualmente: solo la
  Hoja 2 la trae completa; se recorta una sola vez desde ahi).
- Salida: overlay WebP RGBA (alpha=0 fuera del neat-line / fuera del area con
  datos) + UNA sola leyenda WebP RGB compartida por las 3 hojas.
"""
import fitz, numpy as np, cv2, json
from PIL import Image
from pyproj import Transformer
from pathlib import Path

OUT = Path(__file__).parent / "overlays"
OUT.mkdir(parents=True, exist_ok=True)
EPSG_UTM = "EPSG:24879"   # PSAD56 / UTM zone 19S (NO 32719, ver docstring)
DPI = 200
MAX_PX = 3000

UP = r"C:\Users\carlos.venegas\.claude\uploads\9e1a9035-2071-4dd6-9bb5-c9f650628f73"

to_wgs = Transformer.from_crs(EPSG_UTM, "EPSG:4326", always_xy=True)
to_utm = Transformer.from_crs("EPSG:4326", EPSG_UTM, always_xy=True)


def render(pdf_path, dpi=DPI):
    pg = fitz.open(pdf_path)[0]
    sc = dpi / 72
    pix = pg.get_pixmap(matrix=fitz.Matrix(sc, sc))
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        img = img[:, :, :3]
    return np.ascontiguousarray(img)


def fit_affine(x, E, y, N):
    x = np.array(x, float); E = np.array(E, float)
    y = np.array(y, float); N = np.array(N, float)
    ae, be = np.polyfit(x, E, 1)
    an, bn = np.polyfit(y, N, 1)
    res_e = float(np.max(np.abs(np.polyval([ae, be], x) - E)))
    res_n = float(np.max(np.abs(np.polyval([an, bn], y) - N)))
    return (ae, be, an, bn, res_e, res_n)


def warp_and_save(img, affine, x0, x1, y0, y1, name, max_px=MAX_PX):
    ae, be, an, bn = affine[:4]

    def px2geo(x, y):
        return to_wgs.transform(ae * x + be, an * y + bn)

    cor = [px2geo(x0, y0), px2geo(x1, y0), px2geo(x1, y1), px2geo(x0, y1)]
    lons = [c[0] for c in cor]; lats = [c[1] for c in cor]
    west, east = min(lons), max(lons)
    south, north = min(lats), max(lats)

    OW = min(x1 - x0, max_px)
    OH = int(round(OW * (north - south) / (east - west)))
    lon_g = west + (np.arange(OW) / (OW - 1)) * (east - west)
    lat_g = north - (np.arange(OH) / (OH - 1)) * (north - south)
    LON, LAT = np.meshgrid(lon_g, lat_g)
    E, N = to_utm.transform(LON.ravel(), LAT.ravel())
    mx = ((E.reshape(LAT.shape) - be) / ae).astype(np.float32)
    my = ((N.reshape(LAT.shape) - bn) / an).astype(np.float32)
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


def main():
    # ---------------- Hoja 1/3 : Concon ----------------
    print("=== v4 / Hoja 1 de 3 / Concon ===")
    pdf4 = f"{UP}\\379e8689-11543_IR_29_MapasVALPO_4.pdf"
    img4 = render(pdf4)
    x0_4, x1_4, y0_4, y1_4 = 293, 6384, 547, 9101   # neat-line interior (detectado)
    aff4 = fit_affine(
        [579, 1364, 2151, 2936, 3721, 4510, 5295, 6080],
        [261500, 262500, 263500, 264500, 265500, 266500, 267500, 268500],
        [1772, 2560, 3347, 4130, 4918, 5702, 6489, 7278, 8063, 8852],
        [6354000, 6353000, 6352000, 6351000, 6350000, 6349000, 6348000, 6347000, 6346000, 6345000])
    print(f"  res_e={aff4[4]:.1f}m res_n={aff4[5]:.1f}m")
    r4 = warp_and_save(img4, aff4, x0_4, x1_4, y0_4, y1_4, "valpo_concon")
    print(f"  bbox: N={r4['north']:.6f} S={r4['south']:.6f} E={r4['east']:.6f} W={r4['west']:.6f}")
    check_points(r4['west'], r4['east'], r4['south'], r4['north'],
                 {"Concon": (-71.5217, -32.9264), "Reñaca": (-71.5322, -32.9764)})

    # ---------------- Hoja 2/3 : Vina del Mar (+ leyenda compartida) ----------
    print("\n=== v5 / Hoja 2 de 3 / Vina del Mar ===")
    pdf5 = f"{UP}\\228a9151-11543_IR_29_MapasVALPO_5.pdf"
    img5 = render(pdf5)
    # el marco completo de la hoja es 482..7300 x 567..6041, pero la mitad
    # derecha (desde ~x=6570) es leyenda/paneles sin datos de peligro -> se
    # recorta el mapa util hasta ahi (ver docstring).
    x0_5, x1_5, y0_5, y1_5 = 482, 6570, 567, 6041
    aff5 = fit_affine(
        [1177, 1960, 2743, 3525, 4311, 5093, 5872, 6656],
        [262500, 263500, 264500, 265500, 266500, 267500, 268500, 269500],
        [1343, 2128, 2910, 3691, 4472, 5258],
        [6344000, 6343000, 6342000, 6341000, 6340000, 6339000])
    print(f"  res_e={aff5[4]:.1f}m res_n={aff5[5]:.1f}m")
    r5 = warp_and_save(img5, aff5, x0_5, x1_5, y0_5, y1_5, "valpo_vina_del_mar")
    print(f"  bbox: N={r5['north']:.6f} S={r5['south']:.6f} E={r5['east']:.6f} W={r5['west']:.6f}")
    check_points(r5['west'], r5['east'], r5['south'], r5['north'],
                 {"Vina del Mar centro": (-71.5500, -33.0244), "Reñaca": (-71.5322, -32.9764)})

    # leyenda compartida: recortada de v5 (Hoja 2), la unica con tabla completa
    leg = img5[845:3155, 6800:10764]
    leg_img = Image.fromarray(leg)
    if leg_img.width > 1400:
        h = int(leg_img.height * 1400 / leg_img.width)
        leg_img = leg_img.resize((1400, h), Image.LANCZOS)
    leg_path = OUT / "valpo_leyenda.webp"
    leg_img.save(leg_path, "WEBP", quality=82, method=6)
    print(f"  leyenda compartida -> {leg_path.name}  {leg_img.width}x{leg_img.height}  "
          f"{leg_path.stat().st_size/1024:.0f} KB")

    # ---------------- Hoja 3/3 : Valparaiso ----------------
    print("\n=== v6 / Hoja 3 de 3 / Valparaiso ===")
    pdf6 = f"{UP}\\86c939c8-11543_IR_29_MapasVALPO_6.pdf"
    img6 = render(pdf6)
    x0_6, x1_6, y0_6, y1_6 = 378, 8545, 469, 6063
    aff6 = fit_affine(
        [1177, 1967, 2752, 3541, 4327, 5113, 5901, 6687, 7473],
        [252500, 253500, 254500, 255500, 256500, 257500, 258500, 259500, 260500],
        [626, 1410, 2199, 2984, 3771, 4559, 5345],
        [6344000, 6343000, 6342000, 6341000, 6340000, 6339000, 6338000])
    print(f"  res_e={aff6[4]:.1f}m res_n={aff6[5]:.1f}m")
    r6 = warp_and_save(img6, aff6, x0_6, x1_6, y0_6, y1_6, "valpo_valparaiso")
    print(f"  bbox: N={r6['north']:.6f} S={r6['south']:.6f} E={r6['east']:.6f} W={r6['west']:.6f}")
    check_points(r6['west'], r6['east'], r6['south'], r6['north'],
                 {"Valparaiso centro": (-71.6273, -33.0472), "Vina del Mar centro": (-71.5500, -33.0244)})

    meta = {"valpo_concon": r4, "valpo_vina_del_mar": r5, "valpo_valparaiso": r6}
    (OUT / "valparaiso_meta.json").write_text(json.dumps(meta, indent=2))
    print("\nMETA guardada en valparaiso_meta.json")


if __name__ == "__main__":
    main()
