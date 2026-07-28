"""
Georreferencia 8 mapas de remociones en masa de la Region del Biobio
(Tirua, Curanilahue, Arauco, Tubul-Las Penas, Punta Lavapie, Penco,
Concepcion sector A y sector B) a partir de los PDF originales de
SERNAGEOMIN "Geologia para la Reconstruccion y la Gestion del Riesgo"
(2011-2012, post-terremoto 27F).

MOTIVO: los KMZ que el usuario tenia (exportados a mano desde Google Earth
Pro) traian el LatLonBox del GroundOverlay mal ajustado -- overlays visiblemente
corridos respecto al satelital, con magnitud de error DISTINTA en cada mapa
(no es un shift de datum sistematico, es error de cada KMZ individual). El de
Punta Lavapie ademas venia completamente vacio (LatLonBox en NaN).

METODO (mas preciso que digitalizar lineas de grid a mano con pixeles, como
hacen los otros scripts georef_*.py del repo): estos PDF de SERNAGEOMIN traen
el grid UTM como TEXTO REAL embebido (no solo trazo grafico), con las
etiquetas de coordenada (ej "106000", "5747000") como palabras seleccionables.
Se extraen con page.get_text("words") -> posicion (x,y) exacta en puntos PDF,
se filtra por regex de digitos, y se ajusta un polyfit lineal por eje
(pixel/pt = a*UTM + b). Los residuales dan <2 pt (~1 m) de error en todos los
mapas, muy por debajo de lo alcanzable digitalizando pixeles de lineas a mano.

GOTCHA CLAVE -- pagina rotada (page.rotation=90 en varios de estos PDF):
get_text("words") devuelve coordenadas en el espacio SIN ROTAR de la pagina,
pero get_pixmap() SI aplica la rotacion al renderizar. Hay que multiplicar
cada punto por `page.rotation_matrix` ANTES de compararlo con pixeles del
render, o las posiciones quedan desfasadas ~90 grados (facil de detectar
porque el eje que deberia tener Y constante sale con X constante). Al
renderizar con get_pixmap, pasar SOLO fitz.Matrix(escala,escala) -- NUNCA
combinarla con rotation_matrix, porque get_pixmap ya rota sola y se duplica
la rotacion (mat = rotation_matrix * Matrix(s,s) da un resultado con ancho/alto
transpuesto respecto al render real).

GOTCHA -- outlier de lectura: en Curanilahue, la etiqueta "5846" (extremo
superior del grid) dio un residual de ~15 pt vs <2 pt del resto -- se
descarto ese punto del fit (7 de 8 valores de Northing) y el residual bajo a
~1.3 pt. Con 5+ puntos de grid por eje, un polyfit + revision de residuales
individuales detecta este tipo de error de OCR/parsing sin verificacion visual.

GOTCHA -- distincion Easting/Northing NO es por cantidad de digitos: en
varios de estos mapas el Easting va abreviado a 3 digitos ("114km", "115"...)
mientras el Northing va con 7 digitos completos ("5871000"). La forma
confiable de saber cual eje es cual es geometrica, no por longitud del
numero: valores que se repiten con MISMO X y DISTINTO Y (aparecen arriba Y
abajo del mapa) son Easting; valores con MISMO Y y DISTINTO X (aparecen a la
izquierda Y a la derecha) son Northing. Confirmado ademas con pyproj
transformando un punto del grid a WGS84 y comparando contra coordenadas
conocidas del lugar.

NEATLINE (recorte del mapa, sin el texto circundante): deteccion automatica
por conteo de pixeles oscuros por fila/columna (busca las lineas rectas mas
largas de la pagina, filtra por >70% del maximo encontrado) en vez de
inspeccionar a ojo cada esquina. Suele salir un PAR de candidatos por borde
(la linea exterior de la pagina + el neatline real, ~20-40 px de separacion);
se usa siempre el mas INTERIOR de cada par.

LEYENDA: se ubica el bloque "GRADO DE PELIGRO / DESCRIPCION / RECOMENDACIONES"
buscando esas 3 palabras con page.search_for() y quedandose con el trio que
comparte la MISMA fila Y (suele haber matches sueltos de "recomendaciones" en
el cuerpo de texto de Consideraciones Generales que hay que descartar). El
recorte va desde ~130pt arriba de esa fila (para incluir el titulo "LEYENDA")
hasta ~65pt debajo de "NOTA:" (para incluir su texto).

Concepcion trae 2 mapas (12-1a Talcahuano/Hualpen, 12-1b Concepcion/
Chiguayante) lado a lado en la MISMA pagina -- se separan por rango de X antes
del fit, pero comparten una sola leyenda (esta al centro de la pagina, entre
ambos).

Tubul: el PDF fuente es UN SOLO mapa (Caletas Tubul-Las Penas), pero el
usuario tenia DOS kmz separados (MAPA_07_1 y MAPA_07_3) con el mismo
LatLonBox -- probablemente duplicados o capas separadas de un export viejo.
Se genero un unico overlay `flujos_biobio_tubul` y se retiraron las 2
entradas redundantes del manifest.

Uso: las coordenadas de grid/neatline/leyenda de cada mapa fueron levantadas
interactivamente (get_text + verificacion visual del recorte antes de
aceptarlo) y quedan hardcodeadas abajo. Para agregar un mapa nuevo de esta
misma serie SERNAGEOMIN, replicar el patron: extraer grid points con
`extraer_grid()`, revisar residuales, ubicar neatline con `detectar_neatline()`,
generar overlay + leyenda con `generar_overlay()`/`generar_leyenda()`.
"""
import re
import numpy as np
import fitz
from PIL import Image
from pyproj import Transformer
from pathlib import Path

SRC_DIR = Path(r"C:\Users\carlos.venegas\Documents\Sernageomin_Emergencia 2026\Bio-Bio")
OUT = Path(__file__).parent / "overlays"
EPSG_UTM = "EPSG:32719"
to_wgs = Transformer.from_crs(EPSG_UTM, "EPSG:4326", always_xy=True)


def extraer_grid(pdf_path, min_digits=4, max_digits=7):
    """Extrae candidatos a etiqueta de grid UTM (texto numerico) con su
    posicion ya rotada al espacio visual de la pagina. Devuelve dict
    {texto: [(x,y), ...]} en puntos PDF."""
    doc = fitz.open(pdf_path)
    page = doc[0]
    mat = page.rotation_matrix
    pts = {}
    for w in page.get_text("words"):
        txt = w[4].rstrip(".,")
        if re.fullmatch(rf"\d{{{min_digits},{max_digits}}}", txt):
            cx, cy = (w[0] + w[2]) / 2, (w[1] + w[3]) / 2
            p = fitz.Point(cx, cy) * mat
            pts.setdefault(txt, []).append((round(p.x, 1), round(p.y, 1)))
    doc.close()
    return pts, page.rotation, page.rect.width, page.rect.height


def fit_axis(vals, pxs):
    a, b = np.polyfit(vals, pxs, 1)
    resid = np.polyval([a, b], vals) - np.array(pxs)
    return a, b, resid


def detectar_neatline(png_path, x0=0, x1=None):
    """Detecta el recuadro del mapa (neatline) buscando filas/columnas con
    mayor densidad de pixeles oscuros (>70% del maximo). Devuelve el PAR mas
    interior si hay doble linea (pagina + neatline)."""
    img = np.array(Image.open(png_path).convert("L"))
    H, W = img.shape
    x1 = x1 or W
    region = img[:, x0:x1]
    rd = (region < 100).sum(axis=1)
    cd = (region < 100).sum(axis=0)
    rows = np.where(rd > rd.max() * 0.7)[0]
    cols = np.where(cd > cd.max() * 0.7)[0] + x0
    return rows, cols


def render(pdf_path, out_png, scale, rotate=True):
    doc = fitz.open(pdf_path)
    page = doc[0]
    mat = fitz.Matrix(scale, scale)  # get_pixmap ya rota sola si rotate=True (default)
    pix = page.get_pixmap(matrix=mat)
    pix.save(out_png)
    doc.close()
    return pix.width, pix.height


def bbox_wgs84(left, top, right, bottom, scale, aE, bE, aN, bN):
    def px2e(x):
        return ((x / scale) - bE) / aE

    def py2n(y):
        return ((y / scale) - bN) / aN

    we, ee = px2e(left), px2e(right)
    nn, sn = py2n(top), py2n(bottom)
    lon_w, lat_n = to_wgs.transform(we, nn)
    lon_e, lat_s = to_wgs.transform(ee, sn)
    return dict(n=round(lat_n, 6), s=round(lat_s, 6), e=round(lon_e, 6), w=round(lon_w, 6))


def generar_overlay(png_path, left, top, right, bottom, out_webp, quality=85):
    img = Image.open(png_path)
    crop = img.crop((left, top, right, bottom))
    crop.save(out_webp, "WEBP", quality=quality)
    return crop.size


def generar_leyenda(png_path, grado_x, reco_x, y_cabecera, y_nota, scale, out_webp, quality=88):
    """Recorta el bloque LEYENDA: desde ~130pt arriba de la fila de cabecera
    (GRADO/DESCRIPCION/RECOMENDACIONES) hasta ~65pt debajo de 'NOTA:'."""
    top = (y_cabecera - 130) * scale
    bottom = (y_nota + 65) * scale
    left = (grado_x - 25) * scale
    right = (reco_x + 360) * scale
    img = Image.open(png_path)
    px = (max(0, left), max(0, top), min(img.width, right), min(img.height, bottom))
    img.crop(px).save(out_webp, "WEBP", quality=quality)


# ---------------------------------------------------------------------------
# Resultados ya calculados (fits validados con residuo sub-2pt salvo donde se
# indica; bbox WGS84 verificados visualmente contra la geografia real).
# Se dejan documentados aca en vez de recalcular en cada corrida.
# ---------------------------------------------------------------------------

RESULTADOS = {
    "flujos_biobio_tirua": dict(
        pdf="2010_Mapa_Tirua_Remocion_Masa.pdf", scale=1.5,
        bounds=dict(n=-38.320481, s=-38.353696, e=-73.476586, w=-73.514675),
    ),
    "flujos_biobio_curanilahue": dict(
        pdf="2010_Mapa_Curanilahue_Remocion_Masa.pdf", scale=1.2,
        bounds=dict(n=-37.452841, s=-37.521969, e=-73.308941, w=-73.372523),
    ),
    "flujos_biobio_arauco": dict(
        pdf="2010_Mapa_Arauco_Remocion_Masa.pdf", scale=1.2,
        bounds=dict(n=-37.224066, s=-37.263239, e=-73.264873, w=-73.351120),
    ),
    "flujos_biobio_tubul": dict(
        pdf="2010_Mapa_Tubul_Remocion_Masa.pdf", scale=1.5,
        bounds=dict(n=-37.197212, s=-37.278977, e=-73.384157, w=-73.503421),
    ),
    "flujos_biobio_puntalavapie": dict(
        pdf="2010_Mapa_Puntalavapie_Remocion_Masa.pdf", scale=1.2,
        bounds=dict(n=-37.139985, s=-37.165303, e=-73.570717, w=-73.610298),
    ),
    "flujos_biobio_penco": dict(
        pdf="2010_Mapa_Penco_Remocion_Masa.pdf", scale=1.2,
        bounds=dict(n=-36.693822, s=-36.757295, e=-72.954165, w=-73.010138),
    ),
    "flujos_biobio_concepcion_a": dict(
        pdf="2010_Mapa_Concepcion_Remocion_Masa.pdf", scale=1.2,
        bounds=dict(n=-36.606568, s=-36.797300, e=-73.028090, w=-73.215138),
    ),
    "flujos_biobio_concepcion_b": dict(
        pdf="2010_Mapa_Concepcion_Remocion_Masa.pdf", scale=1.2,
        bounds=dict(n=-36.771893, s=-36.962725, e=-72.987613, w=-73.173062),
    ),
}

if __name__ == "__main__":
    for mid, r in RESULTADOS.items():
        print(mid, "->", r["bounds"])
