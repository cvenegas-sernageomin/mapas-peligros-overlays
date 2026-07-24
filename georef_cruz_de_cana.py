"""
Georreferencia "CRUZ DE CANA (2).pdf" (SENAPRED / SERNAGEOMIN, "Plano de
Evacuacion ante Amenaza de Remocion en Masa", Region de Coquimbo, Comuna de
Coquimbo, sector Cruz de Cana, Edicion julio 2025, COD 225041021).

- PDF de 1 pagina que en realidad contiene DOS mapas apilados verticalmente,
  cada uno con su PROPIA grilla geografica (grados/minutos/segundos, WGS84
  lat/lon, NO UTM):
  - Mapa 1 (arriba): vista de CONTEXTO de toda la quebrada/cuenca (area de
    evacuacion en rosado sobre el patron dendritico completo), con un
    rectangulo rojo que delimita el area que se amplia abajo.
  - Mapa 2 (abajo): ZOOM del sector urbano (calles, vias de evacuacion,
    puntos de encuentro PE).
  Cada mapa tiene su propio marco/grilla, a ESCALA DISTINTA -> se georreferencian
  por separado, cada uno con su propio fit.
- Grillas NEGRAS (no azules como los mapas SERNAGEOMIN de PDF con grilla UTM),
  con marca de tick + etiqueta grados/min/seg fuera del marco:
  - Mapa 1: 3 lineas de latitud (30d0'S, 30d3'S, 30d6'S, paso 3') detectadas en
    el margen izquierdo de TODA la pagina (un marco "decorativo" exterior que
    en realidad lleva la escala del Mapa 1 continuada mas alla de su propio
    borde inferior); longitud leida en la FILA INFERIOR de etiquetas al pie de
    la pagina (71d15'W, 71d12'W, 71d9'W, paso 3').
  - Mapa 2: su propio marco INTERIOR (mas angosto que el exterior) con solo
    UNA linea de latitud visible (30d1'0"S, el area es chica) y 3 de longitud
    (71d13'W, 71d12'W, 71d11'W, paso 1') en la FILA SUPERIOR de etiquetas al
    pie (justo bajo el borde del propio Mapa 2).
- GOTCHA (confirmado numericamente con el Mapa 1, que tiene grilla completa en
  ambos ejes): la imagen base es un mosaico satelital en una proyeccion donde
  los PIXELES son proporcionales a METROS reales (no a grados) -> pixeles por
  grado de longitud / pixeles por grado de latitud = cos(latitud) (Mapa 1 dio
  1.150 vs cos^-1(30 deg)=1.155, error <0.5%). Como el Mapa 2 solo trae UNA
  linea de latitud (no alcanza a haber una segunda dentro del area tan chica),
  se usa esta relacion para derivar su escala vertical (grados lat/pixel) a
  partir de su escala horizontal (grados lon/pixel, con 3 puntos limpios) mas
  la constante 111320 m/grado, en vez de asumir (incorrecto) que
  grados/pixel es igual en ambos ejes.
- Verificado componiendo ambos bbox sobre satelital Esri real: el pueblo/valle
  encaja exactamente (Mapa 1) y la trama de calles encaja exactamente (Mapa 2).
- Salida: 2 overlays WebP (recorte directo, sin warp: no hay rotacion en
  ninguno de los dos mapas) + 1 leyenda compartida (recortada del recuadro
  LEYENDA que trae el Mapa 1, valida para ambos: mismos simbolos).
"""
import numpy as np, json
from PIL import Image
from pathlib import Path
import fitz

PDF = r"C:\Users\carlos.venegas\Downloads\CRUZ DE CAÑA (2).pdf"
OUT = Path(r"C:\Users\carlos.venegas\Documents\mapas-peligros-overlays\overlays")
OUT.mkdir(parents=True, exist_ok=True)
DPI = 200
MAX_PX = 3000

# --- anclas de grilla leidas por deteccion automatica (ver docstring) ---
# Mapa 1 (contexto): marco propio x=[79,3229] y=[393,2666]
M1_X0, M1_X1, M1_Y0, M1_Y1 = 79, 3229, 393, 2666
M1_PX_LON = [400, 1665, 2930]
M1_LON = [-71 - 15 / 60, -71 - 12 / 60, -71 - 9 / 60]
M1_PY_LAT = [539, 1994, 3449]
M1_LAT = [-30 - 0 / 60, -30 - 3 / 60, -30 - 6 / 60]

# Mapa 2 (zoom urbano): marco propio x=[142,3165] y=[2666,4536]
M2_X0, M2_X1, M2_Y0, M2_Y1 = 142, 3165, 2666, 4536
M2_PX_LON = [252, 1519, 2750]
M2_LON = [-71 - 13 / 60, -71 - 12 / 60, -71 - 11 / 60]
M2_PY_LAT_ANCHOR = 3360.0
M2_LAT_ANCHOR = -30 - 1 / 60

# leyenda: recuadro dentro del marco del Mapa 1 (esquina inferior izquierda)
LEG_X0, LEG_X1, LEG_Y0, LEG_Y1 = 101, 641, 1983, 2350

M_PER_DEG_LAT = 111320.0


def render():
    pg = fitz.open(PDF)[0]
    sc = DPI / 72
    pix = pg.get_pixmap(matrix=fitz.Matrix(sc, sc))
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        img = img[:, :, :3]
    return np.ascontiguousarray(img)


def save_crop(img, x0, x1, y0, y1, name, bounds, max_px=MAX_PX):
    crop = img[y0:y1, x0:x1]
    h, w = crop.shape[:2]
    if w > max_px:
        nh = int(round(h * max_px / w))
        crop = np.array(Image.fromarray(crop).resize((max_px, nh), Image.LANCZOS))
    webp = OUT / f"{name}.webp"
    Image.fromarray(crop).save(webp, "WEBP", quality=88, method=6)
    print(f"  {name}.webp  {crop.shape[1]}x{crop.shape[0]}  bounds={bounds}")


def main():
    img = render()
    H, W = img.shape[:2]
    print(f"Render {W}x{H} @ {DPI}dpi")

    # --- Mapa 1: fit lineal simple en cada eje (sin rotacion) ---
    aE1, cE1 = np.polyfit(M1_PX_LON, M1_LON, 1)
    aN1, cN1 = np.polyfit(M1_PY_LAT, M1_LAT, 1)
    res_e1 = float(np.max(np.abs(np.polyval([aE1, cE1], M1_PX_LON) - np.array(M1_LON))))
    res_n1 = float(np.max(np.abs(np.polyval([aN1, cN1], M1_PY_LAT) - np.array(M1_LAT))))
    print(f"  Mapa1 E={aE1:.10f}*px+{cE1:.6f}  res={res_e1:.7f} deg")
    print(f"  Mapa1 N={aN1:.10f}*py+{cN1:.6f}  res={res_n1:.7f} deg")
    ratio = aE1 / (-aN1)
    print(f"  Mapa1 ratio pxE/pxN = {ratio:.4f}  (1/cos(lat) esperado)")

    west1, east1 = aE1 * M1_X0 + cE1, aE1 * M1_X1 + cE1
    north1, south1 = aN1 * M1_Y0 + cN1, aN1 * M1_Y1 + cN1
    b1 = dict(n=round(north1, 6), s=round(south1, 6), e=round(east1, 6), w=round(west1, 6))

    # --- Mapa 2: longitud con 3 puntos; latitud derivada via cos(lat) ---
    aE2, cE2 = np.polyfit(M2_PX_LON, M2_LON, 1)
    res_e2 = float(np.max(np.abs(np.polyval([aE2, cE2], M2_PX_LON) - np.array(M2_LON))))
    print(f"  Mapa2 E={aE2:.10f}*px+{cE2:.6f}  res={res_e2:.7f} deg")

    lat0 = M2_LAT_ANCHOR
    coslat = np.cos(np.radians(abs(lat0)))
    m_per_deg_lon = M_PER_DEG_LAT * coslat
    m_per_px_x = abs(aE2) * m_per_deg_lon
    lat_per_px = -(m_per_px_x / M_PER_DEG_LAT)
    cN2 = M2_LAT_ANCHOR - lat_per_px * M2_PY_LAT_ANCHOR
    print(f"  Mapa2 N(derivado)={lat_per_px:.10f}*py+{cN2:.6f}")

    west2, east2 = aE2 * M2_X0 + cE2, aE2 * M2_X1 + cE2
    north2, south2 = lat_per_px * M2_Y0 + cN2, lat_per_px * M2_Y1 + cN2
    b2 = dict(n=round(north2, 6), s=round(south2, 6), e=round(east2, 6), w=round(west2, 6))

    print(f"  Mapa1 bbox: {b1}")
    print(f"  Mapa2 bbox: {b2}")
    dentro = b2['w'] >= b1['w'] and b2['e'] <= b1['e'] and b2['s'] >= b1['s'] and b2['n'] <= b1['n']
    print(f"  check: Mapa2 dentro de Mapa1 = {dentro}")

    save_crop(img, M1_X0, M1_X1, M1_Y0, M1_Y1, "cruz_de_cana_contexto", b1)
    save_crop(img, M2_X0, M2_X1, M2_Y0, M2_Y1, "cruz_de_cana_detalle", b2)

    leg = img[LEG_Y0:LEG_Y1, LEG_X0:LEG_X1]
    Image.fromarray(leg).save(OUT / "cruz_de_cana_leyenda.webp", "WEBP", quality=90, method=6)
    print(f"  leyenda -> cruz_de_cana_leyenda.webp  {leg.shape[1]}x{leg.shape[0]}")

    meta = {"cruz_de_cana_contexto": b1, "cruz_de_cana_detalle": b2}
    (OUT / "cruz_de_cana_meta.json").write_text(json.dumps(meta, indent=2))
    print("META guardada en cruz_de_cana_meta.json")


if __name__ == "__main__":
    main()
