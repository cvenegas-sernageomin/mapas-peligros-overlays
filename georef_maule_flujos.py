"""Georref 3 mapas de remociones en masa de la Region del Maule (serie SERNAGEOMIN
2010 "Geologia para la Reconstruccion y la Gestion del Riesgo", post-27F):
Constitucion (Mapa 13-1), Curico (14-1), Duao/Iloca/La Pesca (15-1).

Metodo: VARIANTE F de [[proyecto-mapas-peligros-overlays]] (ver georef_biobio_flujos.py)
= grilla UTM como TEXTO REAL embebido en el PDF. Se extraen las etiquetas de
coordenada con page.get_text("words"), se ajusta polyfit lineal por eje
(px_pt = a*UTM + b), se detecta el neatline por densidad de pixeles oscuros y se
recorta. Paginas SIN rotacion (rot=0) -> no hay gotcha de rotation_matrix aca.
Datum WGS84 (declarado en las 3 hojas) -> EPSG:32719 (UTM 19S).

GOTCHA especifico de estos 3: el Easting va abreviado a 3 digitos con sufijo "km"
("187km","188","189"...) y el Northing a 3 digitos ("086"=6086000, "128"=6128000).
Distinguir E de N por geometria (repetido con mismo x = Easting; mismo y = Northing),
NO por nº de digitos. Valor completo: E = int(txt)*1000; N = 6000000 + int(txt)*1000.

Residuales 2-4.5 pt (~7-15 m al peor punto de cada esquina, <2 pt al centro) — algo
mayores que Bio-Bio (sub-2pt) por un leve arqueo sistematico (centro del texto vs
linea), aceptable para overlay de referencia 1:10.000. Verificado con calles OSM
(Overpass) superpuestas: la trama urbana de Constitucion y Curico y el camino
costero Duao-Iloca-La Pesca calzan exacto.

Neatlines (px en el render de cada scale) y bounds WGS84 resultantes hardcodeados
abajo; para regenerar, correr este script (usa los PDF en SRC_DIR).
"""
import fitz, numpy as np, os
from PIL import Image
from pyproj import Transformer

SRC_DIR = r"C:\Users\carlos.venegas\Documents\sernageomin_maule\2010_geologia-para-la-reconstruccion-y-la-gestion-del-riesgo-terremoto-2010-v1"
OUT = "overlays"
to_wgs = Transformer.from_crs("EPSG:32719", "EPSG:4326", always_xy=True)

MAPS = {
  "maule_constitucion": dict(
    pdf="IR_43_14427_MAPA_13_1_Constitucion_Remocion_Masa.pdf", scale=1.5,
    nl=(127, 193, 2293, 1750),  # left, top, right, bottom (px en render)
    E={187000:221.2, 188000:509.9, 189000:793.8, 190000:1078.3, 191000:1356.0},  # UTM -> pt
    N={6086000:283.4, 6085000:570.9, 6084000:853.9, 6083000:1134.2},
    bounds=dict(n=-35.315131, s=-35.349665, e=-72.393547, w=-72.448043)),
  "maule_curico": dict(
    pdf="IR_43_14427_MAPA_14_1_Curico_Remocion_Masa.pdf", scale=1.2,
    nl=(122, 125, 2830, 1999),
    E={293000:282.3, 294000:571.0, 295000:854.4, 296000:1139.1, 297000:1421.3,
       298000:1705.5, 299000:1988.9, 300000:2266.4},
    N={6128000:363.9, 6127000:650.2, 6126000:933.6, 6125000:1218.3, 6124000:1497.6},
    bounds=dict(n=-34.960977, s=-35.012206, e=-71.188501, w=-71.274306)),
  "maule_duaoiloca": dict(
    pdf="IR_43_14427_MAPA_15_1_Duao_Iloca_Remocion_Masa.pdf", scale=1.2,
    nl=(136, 151, 1650, 3903),
    E={208000:173.6, 209000:462.0, 210000:746.4, 211000:1029.2, 212000:1306.8},
    N={6136000:143.8, 6135000:429.7, 6134000:713.1, 6133000:996.0, 6132000:1280.0,
       6131000:1563.2, 6130000:1846.6, 6129000:2130.0, 6128000:2413.5, 6127000:2697.1, 6126000:2976.0},
    bounds=dict(n=-34.875749, s=-34.976381, e=-72.152151, w=-72.196995)),
}

# Leyenda (GRADO DE PELIGRO/DESCRIPCION/RECOMENDACIONES): (grado_x, reco_x, y_header, y_nota, clamp_top_px)
LEYENDA = {
  "maule_constitucion": (757, 1308, 1288, 1593, 1752),
  "maule_curico":       (1286, 1765, 1783, 2145, 2001),
  "maule_duaoiloca":    (1473, 2196, 93, 428, None),
}

def fit(d):
    v = sorted(d); px = [d[k] for k in v]
    a, b = np.polyfit(v, px, 1)
    res = float(np.max(np.abs(np.polyval([a, b], v) - np.array(px))))
    return a, b, res

if __name__ == "__main__":
    for name, m in MAPS.items():
        doc = fitz.open(os.path.join(SRC_DIR, m["pdf"])); page = doc[0]
        s = m["scale"]; left, top, right, bottom = m["nl"]
        pix = page.get_pixmap(matrix=fitz.Matrix(s, s)); png = f"_{name}.png"; pix.save(png)
        aE, bE, rE = fit(m["E"]); aN, bN, rN = fit(m["N"])
        px2e = lambda x: ((x / s) - bE) / aE
        py2n = lambda y: ((y / s) - bN) / aN
        we, ee = px2e(left), px2e(right); nn, sn = py2n(top), py2n(bottom)
        lw, ln = to_wgs.transform(we, nn); le, ls = to_wgs.transform(ee, sn)
        Image.open(png).crop((left, top, right, bottom)).save(f"{OUT}/{name}.webp", "WEBP", quality=85)
        print(f"{name}: resE={rE:.2f}pt resN={rN:.2f}pt bounds N={ln:.6f} S={ls:.6f} E={le:.6f} W={lw:.6f}")
        gx, rx, yh, yn, clamp = LEYENDA[name]
        lt = max((yh - 130) * s, clamp or 0); lb = (yn + 65) * s; ll = (gx - 25) * s; lr = (rx + 360) * s
        img = Image.open(png)
        img.crop((max(0, ll), max(0, lt), min(img.width, lr), min(img.height, lb))).save(f"{OUT}/{name}_leyenda.webp", "WEBP", quality=88)
        os.remove(png); doc.close()
