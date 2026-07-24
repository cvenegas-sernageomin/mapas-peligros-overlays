"""
Georreferencia el mapa "Zonificacion.jpg" (Susceptibilidad de Flujos de Detritos
y de Inundacion, sector Canal El Romero / Canal San Pedro, La Serena, Region de
Coquimbo) a partir de una imagen JPG YA renderizada (no un PDF de SERNAGEOMIN) que
el usuario obtuvo de un informe/estudio de infraestructura de riego (gaviones,
compuertas, obras de arte de los canales El Romero y San Pedro).

- Imagen raster simple (JPG), SIN metadata de georreferenciacion, pero con grilla
  UTM NEGRA rotulada en el borde (no azul como los mapas SERNAGEOMIN de PDF) y
  Norte hacia arriba (rosa de los vientos vertical) -> a diferencia de los mapas
  anteriores del repo, este NO tiene rotacion ni requiere warp: basta un fit
  afin simple (a*px+c) por eje y un recorte rectangular directo de la imagen.
- Grilla: 6 lineas E (298000..299000, paso 200 m) x 6 lineas N (6684600..6683600,
  paso 200 m), detectadas por umbral de negro (filas/columnas con >50% de negro).
  Fit con polyfit: residuales <1 m en ambos ejes, escala ~0.8465 m/px identica en
  E y N (confirma ausencia de rotacion/deformacion).
- Fuente/datum: no declarado en la imagen: se asume EPSG:32719 (UTM 19S,
  WGS84/SIRGAS) igual que el resto de mapas de Coquimbo del repo, coherente con
  las coordenadas (lat ~-29.9, sector El Romero/Canal San Pedro, La Serena).
- Leyenda: bloque "SIMBOLOGIA" debajo del marco (y>=1420 px), se recorta aparte.
"""
import numpy as np, json
from PIL import Image
from pyproj import Transformer
from pathlib import Path

SRC = r"C:\Users\carlos.venegas\Documents\Sernageomin_Emergencia 2026\Zonificacion.jpg"
OUT = Path(r"C:\Users\carlos.venegas\Documents\mapas-peligros-overlays\overlays")
OUT.mkdir(parents=True, exist_ok=True)
NAME = "el_romero_flujos_inundacion"
EPSG_UTM = "EPSG:32719"

# neat-line interior (detectado): frame T/B doblado (outer~58-60/1416-1418,
# inner~69/1408), L/R linea simple (~55/1708). Se usa un margen de 2 px hacia
# adentro para no incluir el propio trazo negro del marco en el overlay.
X0, X1 = 58, 1706
Y0, Y1 = 70, 1407

# anclas de grilla leidas por deteccion automatica (filas/columnas con >50% negro)
COLS_PX = [268, 506, 742, 978, 1214, 1450]
E_VALS  = [298000, 298200, 298400, 298600, 298800, 299000]
ROWS_PX = [197, 433, 669, 905, 1142, 1378]
N_VALS  = [6684600, 6684400, 6684200, 6684000, 6683800, 6683600]


def main():
    img = np.array(Image.open(SRC).convert("RGB"))
    H, W = img.shape[:2]
    print(f"Imagen {W}x{H}")

    aE, cE = np.polyfit(COLS_PX, E_VALS, 1)
    aN, cN = np.polyfit(ROWS_PX, N_VALS, 1)
    res_e = float(np.max(np.abs(np.polyval([aE, cE], COLS_PX) - np.array(E_VALS))))
    res_n = float(np.max(np.abs(np.polyval([aN, cN], ROWS_PX) - np.array(N_VALS))))
    print(f"  E = {aE:.6f}*px + {cE:.3f}   (res {res_e:.2f} m)")
    print(f"  N = {aN:.6f}*py + {cN:.3f}   (res {res_n:.2f} m)")

    def px2e(x): return aE * x + cE
    def py2n(y): return aN * y + cN

    west, east = px2e(X0), px2e(X1)
    north, south = py2n(Y0), py2n(Y1)
    print(f"  bbox UTM: W={west:.1f} E={east:.1f} N={north:.1f} S={south:.1f}")

    to_wgs = Transformer.from_crs(EPSG_UTM, "EPSG:4326", always_xy=True)
    lon_w, lat_n = to_wgs.transform(west, north)
    lon_e, lat_s = to_wgs.transform(east, south)
    print(f"  bbox geo: N={lat_n:.6f} S={lat_s:.6f} E={lon_e:.6f} W={lon_w:.6f}")

    # --- recorte directo (sin warp: no hay rotacion) ---
    overlay = img[Y0:Y1, X0:X1]
    Image.fromarray(overlay).save(OUT / f"{NAME}.webp", "WEBP", quality=88, method=6)
    print(f"  overlay -> {NAME}.webp  {overlay.shape[1]}x{overlay.shape[0]}")

    # --- leyenda: bloque debajo del marco (1450, no 1420, para no incluir la fila de etiquetas UTM residual) ---
    leg = img[1450:H, 0:W]
    Image.fromarray(leg).save(OUT / f"{NAME}_leyenda.webp", "WEBP", quality=88, method=6)
    print(f"  leyenda -> {NAME}_leyenda.webp  {leg.shape[1]}x{leg.shape[0]}")

    # --- verificacion visual: puntos conocidos deben caer dentro del bbox ---
    check = {"Casa anegada (aprox, dentro de la imagen)": ((lon_w + lon_e) / 2, (lat_n + lat_s) / 2)}
    for k, (lo, la) in check.items():
        dentro = lon_w <= lo <= lon_e and lat_s <= la <= lat_n
        print(f"  check {k}: {lo:.5f},{la:.5f} dentro={dentro}")

    meta = dict(id=NAME, bounds=dict(n=round(lat_n, 6), s=round(lat_s, 6),
                e=round(lon_e, 6), w=round(lon_w, 6)),
                res_e_m=round(res_e, 2), res_n_m=round(res_n, 2),
                size=[int(X1 - X0), int(Y1 - Y0)])
    print("META", json.dumps(meta))
    (OUT / f"{NAME}_meta.json").write_text(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
