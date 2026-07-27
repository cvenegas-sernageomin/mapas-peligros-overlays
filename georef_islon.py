"""
Georreferencia "imagen.png" (Fig. 19: Areas expuestas ante la amenaza de
remociones en masa tipo flujo -aluviones- e inundaciones en el sector El
Islon, Comuna de Coquimbo, Region de Coquimbo, escala 1:10.000).

- Imagen raster suelta (PNG, sin metadata de georreferenciacion) pero con
  grilla UTM AZUL rotulada (5 lineas E cada 500 m, 4 lineas N cada 500 m) y
  Norte hacia arriba (rosa de los vientos vertical) -> igual que el_romero,
  fit afin simple por eje (a*px+c) y recorte rectangular directo, sin warp.
  Grilla detectada por umbral de color en la franja blanca de margen, fuera
  del marco: residuales <1 m en ambos ejes, escala ~3.06 m/px identica en
  E y N (confirma ausencia de rotacion).
- Datum: no declarado en la imagen; se asume EPSG:32719 (UTM19S/WGS84-SIRGAS)
  igual que el resto de mapas de Coquimbo del repo -- confirmado ademas por
  los shapefiles fuente (Islon.7z: inundacion_santa_gracia.shp,
  flujos_quebradas_laterales.shp, puente_obra.shp), que declaran ese mismo
  EPSG en su .prj y cuyo bbox cae dentro del recorte calculado aqui.
- El marco (X0,X1,Y0,Y1) es la hoja COMPLETA (foto + norte + titulo + leyenda
  + escala), porque la foto base tiene un contorno irregular/rotado que no
  coincide con un rectangulo mas chico -- recortar mas angosto perderia mapa
  real. Los rincones sin foto (fondo blanco de esos widgets) se vuelven
  transparentes (umbral casi-blanco) para no tapar el basemap de Leaflet con
  un rectangulo opaco; el texto/simbolos oscuros de esos widgets quedan
  flotando fieles al impreso (mismo criterio "tal cual" usado en
  atacama_copiapo hoja2-4 para la leyenda inserta).
- GOTCHA de la sesion: la capa "Area de alcance de remociones en masa tipo
  flujo" (simbolo de leyenda con trama/hachurado) NO viene en ningun
  shapefile de Islon.7z -- inundacion_santa_gracia.shp trae SOLO "Rio Santa
  Gracia" + "Llanura de inundacion" (llanura = area de inundacion, calza
  geometricamente con el area celeste de la figura) y flujos_quebradas_
  laterales.shp calza con las lineas rojas ("areas de generacion"). No se
  reconstruyo el poligono de "alcance" a mano (no inventar poligonos
  institucionales, ver gotcha el_romero) -- al rasterizar la HOJA COMPLETA
  como imagen (no como capas vectoriales separadas), ese poligono igual
  queda incluido tal como lo publico SERNAGEOMIN, solo que sin poder
  aislarlo como dato propio.
"""
import numpy as np, json
from PIL import Image
from pyproj import Transformer
from pathlib import Path

SRC = r"C:\Users\carlos.venegas\Documents\Sernageomin_Emergencia 2026\imagen.png"
OUT = Path(r"C:\Users\carlos.venegas\Documents\mapas-peligros-overlays\overlays")
OUT.mkdir(parents=True, exist_ok=True)
NAME = "islon_flujos_inundacion"
EPSG_UTM = "EPSG:32719"

# marco exterior (deteccion automatica: fila/columna >400 px < RGB 100 en el
# rango completo de ancho/alto) con 2 px hacia adentro para no incluir el
# propio trazo negro del marco en el overlay.
X0, X1 = 29, 885
Y0, Y1 = 31, 716

# anclas de grilla (deteccion automatica: columnas/filas no-blancas en la
# franja de margen blanco, fuera del marco, justo bajo/al lado de cada label)
COLS_PX = [165.5, 328.5, 492, 655.5, 818.5]
E_VALS = [288000, 288500, 289000, 289500, 290000]
ROWS_PX = [190, 354, 517, 681]
N_VALS = [6691000, 6690500, 6690000, 6689500]

WHITE_THRESH = 248  # RGB >= esto en los 3 canales -> fondo de papel, alpha 0


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

    # --- recorte directo (sin warp: no hay rotacion) + alpha casi-blanco ---
    crop = img[Y0:Y1, X0:X1]
    rgba = np.dstack([crop, np.full(crop.shape[:2], 255, dtype=np.uint8)])
    near_white = np.all(crop >= WHITE_THRESH, axis=-1)
    rgba[near_white, 3] = 0
    Image.fromarray(rgba, "RGBA").save(OUT / f"{NAME}.webp", "WEBP", quality=90, method=6)
    print(f"  overlay -> {NAME}.webp  {rgba.shape[1]}x{rgba.shape[0]}  ({near_white.mean()*100:.1f}% transparente)")

    # --- leyenda: recorte del bloque "Leyenda" (bottom-left, dentro del marco) ---
    leg = img[571:666, 8:400]
    Image.fromarray(leg).save(OUT / f"{NAME}_leyenda.webp", "WEBP", quality=90, method=6)
    print(f"  leyenda -> {NAME}_leyenda.webp  {leg.shape[1]}x{leg.shape[0]}")

    # --- verificacion: bbox de los shapefiles fuente (mismo EPSG) debe caer DENTRO del bbox de la imagen ---
    import geopandas as gpd
    islon_dir = r"C:\Users\carlos.venegas\Documents\Sernageomin_Emergencia 2026\Islon_extracted\Islon"
    for shp in ["inundacion_santa_gracia", "flujos_quebradas_laterales", "puente_obra"]:
        gdf = gpd.read_file(f"{islon_dir}\\{shp}.shp")
        minx, miny, maxx, maxy = gdf.total_bounds
        dentro = (west <= minx <= east and west <= maxx <= east and
                  south <= miny <= north and south <= maxy <= north)
        print(f"  check {shp}: bounds={gdf.total_bounds.round(1).tolist()} dentro_de_imagen={dentro}")

    meta = dict(id=NAME, bounds=dict(n=round(lat_n, 6), s=round(lat_s, 6),
                e=round(lon_e, 6), w=round(lon_w, 6)),
                res_e_m=round(res_e, 2), res_n_m=round(res_n, 2),
                size=[int(X1 - X0), int(Y1 - Y0)])
    print("META", json.dumps(meta))
    (OUT / f"{NAME}_meta.json").write_text(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
