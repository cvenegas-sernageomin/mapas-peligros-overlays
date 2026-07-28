#!/usr/bin/env python3
"""
Procesar mapas de flujos de la RM: San José de Maipo + Lo Barnechea.
Convierte PNG → WebP, genera metadata.
"""
import json
from pathlib import Path
from PIL import Image

# Rutas
TMPDIR = Path(r"C:\Users\carlos.venegas\AppData\Local\Temp\claude\C--Users-carlos-venegas-Documents-Claude\85a1ee73-b51b-44ed-99de-5d6154f39e09\scratchpad")
OVERLAYS_DIR = Path(__file__).parent / "overlays"

# Datos de los mapas (extraído de los KML)
MAPAS = [
    {
        "id": "flujos_sjmaipo_peligro",
        "titulo": "Peligro por Flujos — Cuenca Alta Río Maipo (San José de Maipo)",
        "region": "Metropolitana",
        "fuente": "SERNAGEOMIN",
        "anio": 2026,
        "escala": "1:25.000 aprox.",
        "informe": "Mapa de peligro de flujos de la cuenca alta del río Maipo, Comuna de San José de Maipo",
        "proyeccion_original": "WGS84 geográfico (lat/lon)",
        "bounds": {"n": -32.92233425710519, "s": -34.41656692456429, "e": -69.68926470585771, "w": -70.62618632977818},
        "png_fuente": TMPDIR / "maipo" / "files" / "Layer0.png",
        "opacidad": 0.8,
    },
    {
        "id": "flujos_lobar_alcance",
        "titulo": "Grado de Peligro por Alcance de Flujos — Cuenca Río Mapocho (Lo Barnechea)",
        "region": "Metropolitana",
        "fuente": "SERNAGEOMIN",
        "anio": 2026,
        "escala": "1:20.000 aprox.",
        "informe": "Mapa de grado de peligro por alcance de flujos de la cuenca alta del río Mapocho, Comuna de Lo Barnechea",
        "proyeccion_original": "WGS84 geográfico (lat/lon)",
        "bounds": {"n": -33.0538833218287, "s": -33.53291001155171, "e": -70.1287109778595, "w": -70.65112849954863},
        "png_fuente": TMPDIR / "mapocho" / "files" / "Layer3.png",
        "opacidad": 0.8,
    },
    {
        "id": "flujos_lobar_generacion",
        "titulo": "Grado de Peligro por Generación de Flujos — Cuenca Río Mapocho (Lo Barnechea)",
        "region": "Metropolitana",
        "fuente": "SERNAGEOMIN",
        "anio": 2026,
        "escala": "1:20.000 aprox.",
        "informe": "Mapa de grado de peligro por generación de flujos de la cuenca alta del río Mapocho, Comuna de Lo Barnechea",
        "proyeccion_original": "WGS84 geográfico (lat/lon)",
        "bounds": {"n": -33.05388332188512, "s": -33.53291001160818, "e": -70.12871097786802, "w": -70.65112849955756},
        "png_fuente": TMPDIR / "mapocho" / "files" / "Layer4.png",
        "opacidad": 0.8,
    },
]

def convertir_png_a_webp(png_path: Path, webp_path: Path, quality=82):
    """Convierte PNG a WebP."""
    if not png_path.exists():
        raise FileNotFoundError(f"PNG no encontrado: {png_path}")

    img = Image.open(png_path)
    # Convertir a RGB si es RGBA (para mejor compresión)
    if img.mode == "RGBA":
        # Fondo blanco para transparencia
        rgb_img = Image.new("RGB", img.size, (255, 255, 255))
        rgb_img.paste(img, mask=img.split()[3] if len(img.split()) == 4 else None)
        img = rgb_img

    img.save(webp_path, "WEBP", quality=quality)
    size_kb = webp_path.stat().st_size / 1024
    print(f"OK {png_path.name} -> {webp_path.name} ({size_kb:.1f} KB)")

def main():
    OVERLAYS_DIR.mkdir(exist_ok=True)

    nuevos_mapas = []

    for mapa in MAPAS:
        # Convertir imagen
        png_src = mapa["png_fuente"]
        webp_dst = OVERLAYS_DIR / f"{mapa['id']}.webp"

        convertir_png_a_webp(png_src, webp_dst)

        # Construir entrada de manifest (sin PNG fuente)
        entrada = {k: v for k, v in mapa.items() if k != "png_fuente"}
        entrada["overlay"] = f"overlays/{mapa['id']}.webp"
        entrada["leyenda"] = None  # No hay leyenda disponible

        nuevos_mapas.append(entrada)

    print(f"\nOK {len(nuevos_mapas)} mapas procesados")
    print("\n=== AGREGAR AL manifest.json ===")
    print(json.dumps(nuevos_mapas, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
