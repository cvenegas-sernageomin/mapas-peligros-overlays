"""
Georreferencia "CRUZ DE CANA (2).pdf" (SENAPRED / SERNAGEOMIN, "Plano de
Evacuacion ante Amenaza de Remocion en Masa", Region de Coquimbo, Comuna de
Coquimbo, sector Cruz de Cana, Edicion julio 2025, COD 225041021).

PDF de 1 pagina con DOS mapas apilados (contexto arriba, zoom urbano abajo),
cada uno con su propia grilla geografica lat/lon (grados/min/seg, WGS84).

=== CORRECCION (v2): AMBOS MAPAS ESTAN ROTADOS ~1.12 grados ===
La version anterior asumia "sin rotacion" y hacia un fit lineal por ejes
separados, ademas de leer las etiquetas de longitud del Mapa 1 en el pie de
pagina (posiciones ~[400,1665,2930]) tratandolas como verticales. Medido con
los ticks reales: la MISMA linea de longitud del Mapa 1 esta en x=316 en el
borde superior (py=393) y en x=398 en el pie (py=4590) -> los meridianos estan
inclinados ~1.12 grados. Igual el Mapa 2 (tick de latitud izq py=3361, der
py=3303). Como Leaflet imageOverlay NO soporta rotacion, cada mapa se
**warpea** a plate-carree (norte arriba) con cv2.remap, igual que la variante A
de los PDF SERNAGEOMIN con grilla UTM.

Puntos de control MEDIDOS (deteccion de ticks/grilla, ver historial de la
sesion de auditoria):
  MAPA 1 (grilla de la pagina completa):
    Longitud (W->E: -71.25, -71.20, -71.15):
      borde superior py=393 : x = [316, 1583, 2849]
      pie de pagina  py=4590: x = [398, 1663, 2928]   (misma linea, +82px = rotacion)
    Latitud (N->S: -30.00, -30.05, -30.10):
      margen izq x=79: py = [539, 1994, 3449]
  MAPA 2 (grilla propia, zoom):
    Longitud (W->E: -71.2167, -71.20, -71.1833) borde inferior py~4540: x=[242,1508,2775]
    Latitud (linea unica -30.0167 = 30d1'0"S): (142,3361) izq y (3165,3303) der
      -> escala vertical por isotropia (m/px iguales en ambos ejes).

Cada affine (px,py)->(lon,lat) se construye por gradientes (rotacion + escala +
ancla) y se VERIFICA contra todos los ticks antes de warpear (residual < 1 px).
"""
import numpy as np, json
from PIL import Image
from pathlib import Path
import fitz, cv2

PDF = r"C:\Users\carlos.venegas\Downloads\CRUZ DE CAÑA (2).pdf"
OUT = Path(__file__).parent / "overlays"
OUT.mkdir(parents=True, exist_ok=True)
DPI = 200
MAX_PX = 3000

# metros por grado a ~30.03 S
MLAT = 110852.0
MLON = 111320.0 * np.cos(np.radians(30.03))   # ~96366


def render():
    pg = fitz.open(PDF)[0]
    sc = DPI / 72
    pix = pg.get_pixmap(matrix=fitz.Matrix(sc, sc))
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        img = img[:, :, :3]
    return np.ascontiguousarray(img)


def affine_from_lon(al1, al2, cl, lat_anchor):
    """
    Dado el plano de longitud lon=al1*px+al2*py+cl, construye el affine completo
    (px,py)->(lon,lat) asumiendo transformacion ORTOGONAL isotropa en metros con
    EJE Y INVERTIDO (imagen: py hacia abajo = sur) -> rotacion + reflexion:
      aa1 = (MLON/MLAT)*al2 ;  aa2 = -(MLON/MLAT)*al1   (aa2<0: lat baja al bajar py)
    y ca desde un ancla de latitud (px,py,lat).
    """
    k = MLON / MLAT
    aa1 = k * al2
    aa2 = -k * al1
    (pxA, pyA, latA) = lat_anchor
    ca = latA - aa1 * pxA - aa2 * pyA
    return np.array([[al1, al2, cl], [aa1, aa2, ca]])


def lon_plane_lsq(pts):
    """Ajusta lon = al1*px + al2*py + cl por minimos cuadrados. pts: (px,py,lon)."""
    A = np.array([[px, py, 1.0] for px, py, _ in pts])
    b = np.array([lon for *_, lon in pts])
    coef, *_ = np.linalg.lstsq(A, b, rcond=None)
    return coef  # al1, al2, cl


def lon_plane_from_dir(lon_dir, lon_step_deg, lon_perp_px, lon_anchor):
    """Plano de longitud a partir de la direccion de las lineas de lon + paso + ancla."""
    u = np.array(lon_dir, float); u /= np.linalg.norm(u)
    n = np.array([u[1], -u[0]])                 # perp = direccion de +lon (E)
    if n[0] < 0:
        n = -n
    g = (lon_step_deg / lon_perp_px) * n        # (al1, al2)
    (pxA, pyA, lonA) = lon_anchor
    cl = lonA - g[0] * pxA - g[1] * pyA
    return g[0], g[1], cl


def verify(A, lon_pts, lat_pts, tag):
    m = 0.0
    for (px, py, lon) in lon_pts:
        plon = A[0, 0] * px + A[0, 1] * py + A[0, 2]
        m = max(m, abs(plon - lon) / (abs(A[0, 0]) + 1e-12))   # error en px
    for (px, py, lat) in lat_pts:
        plat = A[1, 0] * px + A[1, 1] * py + A[1, 2]
        m = max(m, abs(plat - lat) / (abs(A[1, 1]) + 1e-12))
    print(f"  [{tag}] residual max = {m:.2f} px")
    assert m < 6.0, f"residual demasiado grande en {tag}"


def warp(img, A, x0, x1, y0, y1, name, max_px=MAX_PX):
    """Warpea el recorte [x0:x1,y0:y1] a plate-carree usando el affine px->geo."""
    M = A[:, :2]
    c = A[:, 2]
    Minv = np.linalg.inv(M)
    # bbox geo de las 4 esquinas del recorte
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    geos = [M @ np.array([cx, cy]) + c for (cx, cy) in corners]
    lons = [g[0] for g in geos]; lats = [g[1] for g in geos]
    w, e = min(lons), max(lons)
    s, n = min(lats), max(lats)
    # resolucion de salida ~ preservando px
    aspect_m = ((e - w) * MLON) / ((n - s) * MLAT)
    W = min(max_px, x1 - x0)
    H = int(round(W / aspect_m))
    # mapas de muestreo: para cada pixel de salida (i,j) -> lon,lat -> px,py fuente
    ii, jj = np.meshgrid(np.arange(W), np.arange(H))
    lon = w + (ii + 0.5) / W * (e - w)
    lat = n - (jj + 0.5) / H * (n - s)
    d = np.stack([lon - c[0], lat - c[1]], axis=-1)      # (H,W,2)
    src = d @ Minv.T                                     # (H,W,2) -> px,py
    map_x = src[:, :, 0].astype(np.float32)
    map_y = src[:, :, 1].astype(np.float32)
    warped = cv2.remap(img, map_x, map_y, interpolation=cv2.INTER_LINEAR,
                       borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))
    # alpha: dentro del recorte fuente
    inside = ((map_x >= x0) & (map_x < x1) & (map_y >= y0) & (map_y < y1)).astype(np.uint8) * 255
    rgba = np.dstack([warped, inside])
    Image.fromarray(rgba, "RGBA").save(OUT / f"{name}.webp", "WEBP", quality=88, method=6)
    b = dict(n=round(n, 6), s=round(s, 6), e=round(e, 6), w=round(w, 6))
    print(f"  {name}.webp  {W}x{H}  bounds={b}")
    return b


def main():
    img = render()
    H, W = img.shape[:2]
    print(f"Render {W}x{H} @ {DPI}dpi")

    # ================= MAPA 1 (contexto) =================
    # Longitud: 6 puntos MEDIDOS en 2 alturas (borde superior py393 y pie py4590)
    # -> el ajuste LSQ captura la rotacion (al2 != 0). Latitud: por isotropia.
    al1, al2, cl = lon_plane_lsq([
        (316, 393, -71.25), (1583, 393, -71.20), (2849, 393, -71.15),
        (398, 4590, -71.25), (1663, 4590, -71.20), (2928, 4590, -71.15)])
    A1 = affine_from_lon(al1, al2, cl, (79, 539, -30.00))
    print(f"  Mapa1 rotacion ~ {np.degrees(np.arctan2(-al2, al1)):.3f} deg")
    verify(A1,
        [(316, 393, -71.25), (1583, 393, -71.20), (2849, 393, -71.15),
         (398, 4590, -71.25), (1663, 4590, -71.20), (2928, 4590, -71.15)],
        [(79, 539, -30.00), (79, 1994, -30.05), (79, 3449, -30.10)],
        "MAPA1")

    # ================= MAPA 2 (zoom urbano) =================
    # Longitud solo con ticks al pie (una altura) -> la rotacion se toma de la
    # linea de LATITUD (izq py3361, der py3303). Latitud: por isotropia.
    m2_lat_dir = (3165 - 142, 3303 - 3361)          # direccion de la linea de lat
    m2_lon_dir = (m2_lat_dir[1], -m2_lat_dir[0])     # lineas de lon perpendiculares
    al1b, al2b, clb = lon_plane_from_dir(m2_lon_dir, 1.0 / 60.0, 1266.5, (1508, 4540, -71.20))
    A2 = affine_from_lon(al1b, al2b, clb, (142, 3361, -30.0 - 1 / 60))
    print(f"  Mapa2 rotacion ~ {np.degrees(np.arctan2(-al2b, al1b)):.3f} deg")
    verify(A2,
        [(242, 4540, -71.2167), (1508, 4540, -71.20), (2775, 4540, -71.1833)],
        [(142, 3361, -30.01667), (3165, 3303, -30.01667)],
        "MAPA2")

    # ---- warp + recortes ----
    b1 = warp(img, A1, 79, 3229, 393, 2666, "cruz_de_cana_contexto")
    b2 = warp(img, A2, 142, 3165, 2666, 4536, "cruz_de_cana_detalle")

    # leyenda: recuadro dentro del Mapa 1 (esquina inferior izquierda), sin warp (es texto)
    leg = img[1983:2350, 101:641]
    Image.fromarray(leg).save(OUT / "cruz_de_cana_leyenda.webp", "WEBP", quality=90, method=6)
    print(f"  leyenda -> cruz_de_cana_leyenda.webp  {leg.shape[1]}x{leg.shape[0]}")

    (OUT / "cruz_de_cana_meta.json").write_text(json.dumps(
        {"cruz_de_cana_contexto": b1, "cruz_de_cana_detalle": b2}, indent=2))
    print("META:", b1, b2)


if __name__ == "__main__":
    main()
