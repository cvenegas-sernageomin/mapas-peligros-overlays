#!/usr/bin/env python3
"""
Procesar 9 mapas de remociones en masa del Bío-Bío.
Extrae PNG de KMZ, convierte a WebP, genera metadata.
"""
import json
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image

BIOBIO_DIR = Path(r"C:\Users\carlos.venegas\Documents\Sernageomin_Emergencia 2026\Bio-Bio")
OVERLAYS_DIR = Path(__file__).parent / "overlays"
TMPDIR = Path(r"C:\Users\CARLOS~1.VEN\AppData\Local\Temp\claude\C--Users-carlos-venegas-Documents-Claude\85a1ee73-b51b-44ed-99de-5d6154f39e09\scratchpad\biobio")

# Mapeos de archivos KMZ a IDs y títulos
MAPAS_CONFIG = {
    "IR_48_14140_MAPA_02_1_Tirua_Remocion_Masa.kmz": {
        "id": "flujos_biobio_tirua",
        "titulo": "Remociones en Masa — Tirúa (Bío-Bío)",
        "comuna": "Tirúa",
    },
    "IR_48_14140_MAPA_03_1_Curanilahue_Remocion_Masa.kmz": {
        "id": "flujos_biobio_curanilahue",
        "titulo": "Remociones en Masa — Curanilahue (Bío-Bío)",
        "comuna": "Curanilahue",
    },
    "IR_48_14140_MAPA_05_1_Arauco_Remocion_Masa.kmz": {
        "id": "flujos_biobio_arauco",
        "titulo": "Remociones en Masa — Arauco (Bío-Bío)",
        "comuna": "Arauco",
    },
    "IR_48_14140_MAPA_06_1_Puntalavapie_Remocion_Masa.kmz": {
        "id": "flujos_biobio_puntalavapie",
        "titulo": "Remociones en Masa — Punta Lavapié (Bío-Bío)",
        "comuna": "Arauco",
    },
    "IR_48_14140_MAPA_07_1_Tubul_Remocion_Masa.kmz": {
        "id": "flujos_biobio_tubul_1",
        "titulo": "Remociones en Masa — Tubul (Bío-Bío) — Sector 1",
        "comuna": "Arauco",
    },
    "IR_48_14140_MAPA_07_3_Tubul_Remocion_Masa.kmz": {
        "id": "flujos_biobio_tubul_3",
        "titulo": "Remociones en Masa — Tubul (Bío-Bío) — Sector 3",
        "comuna": "Arauco",
    },
    "IR_48_14140_MAPA_10_1_Penco_Remocion_Masa.kmz": {
        "id": "flujos_biobio_penco",
        "titulo": "Remociones en Masa — Penco (Bío-Bío)",
        "comuna": "Penco",
    },
    "IR_48_14140_MAPA_12_1_Concepcion_Remocion_Masa_A.kmz": {
        "id": "flujos_biobio_concepcion_a",
        "titulo": "Remociones en Masa — Concepción (Bío-Bío) — Sector A",
        "comuna": "Concepción",
    },
    "IR_48_14140_MAPA_12_1_Concepcion_Remocion_Masa_B.kmz": {
        "id": "flujos_biobio_concepcion_b",
        "titulo": "Remociones en Masa — Concepción (Bío-Bío) — Sector B",
        "comuna": "Concepción",
    },
}

def extraer_kmz(kmz_path: Path, dest_dir: Path):
    """Extrae un KMZ a una carpeta temporal."""
    with zipfile.ZipFile(kmz_path, 'r') as z:
        z.extractall(dest_dir)

def parsear_bounds_kml(kml_path: Path) -> dict:
    """Extrae bounds {n, s, e, w} del KML."""
    # Leer y limpiar el XML de atributos xsi mal declarados
    with open(kml_path, 'r', encoding='utf-8') as f:
        xml_str = f.read()

    # Reemplazar xsi:schemaLocation con atributo limpio
    xml_str = xml_str.replace('xsi:schemaLocation=', 'schemaLocation=')

    # Parsear
    root = ET.fromstring(xml_str)
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    bounds = None

    # Buscar el primer LatLonBox
    for box in root.findall('.//kml:LatLonBox', ns):
        n = box.find('kml:north', ns)
        s = box.find('kml:south', ns)
        e = box.find('kml:east', ns)
        w = box.find('kml:west', ns)

        if all([n is not None, s is not None, e is not None, w is not None]):
            bounds = {
                "n": float(n.text),
                "s": float(s.text),
                "e": float(e.text),
                "w": float(w.text),
            }
            break

    return bounds

def encontrar_png(dir_path: Path) -> Path:
    """Encuentra el primer PNG en la carpeta."""
    for png in dir_path.rglob('*.png'):
        return png
    return None

def convertir_png_a_webp(png_path: Path, webp_path: Path, quality=82):
    """Convierte PNG a WebP."""
    img = Image.open(png_path)

    if img.mode == "RGBA":
        rgb_img = Image.new("RGB", img.size, (255, 255, 255))
        rgb_img.paste(img, mask=img.split()[3] if len(img.split()) == 4 else None)
        img = rgb_img

    img.save(webp_path, "WEBP", quality=quality)
    size_kb = webp_path.stat().st_size / 1024
    return size_kb

def main():
    TMPDIR.mkdir(exist_ok=True, parents=True)
    OVERLAYS_DIR.mkdir(exist_ok=True)

    mapas_procesados = []

    for kmz_filename, config in MAPAS_CONFIG.items():
        kmz_path = BIOBIO_DIR / kmz_filename

        if not kmz_path.exists():
            print(f"ERROR: {kmz_filename} no encontrado")
            continue

        print(f"Procesando {config['id']}...")

        # Extraer KMZ
        extract_dir = TMPDIR / config['id']
        extract_dir.mkdir(exist_ok=True)
        extraer_kmz(kmz_path, extract_dir)

        # Parsear KML y PNG
        kml_file = extract_dir / "doc.kml"
        png_file = encontrar_png(extract_dir)

        if not png_file:
            print(f"  ERROR: No PNG encontrado en {kmz_filename}")
            continue

        bounds = parsear_bounds_kml(kml_file)
        if not bounds:
            print(f"  ERROR: No bounds encontrado en KML")
            continue

        # Convertir a WebP
        webp_dst = OVERLAYS_DIR / f"{config['id']}.webp"
        size_kb = convertir_png_a_webp(png_file, webp_dst)
        print(f"  OK: {size_kb:.1f} KB")

        # Construir entrada manifest
        entrada = {
            "id": config['id'],
            "titulo": config['titulo'],
            "region": "Bío-Bío",
            "fuente": "SERNAGEOMIN",
            "anio": 2026,
            "escala": "variable",
            "informe": f"Mapa de remociones en masa — {config['comuna']} (IR-48-14140)",
            "proyeccion_original": "WGS84 geográfico (lat/lon)",
            "bounds": bounds,
            "overlay": f"overlays/{config['id']}.webp",
            "leyenda": None,
            "opacidad": 0.8,
        }
        mapas_procesados.append(entrada)

    print(f"\nOK {len(mapas_procesados)} mapas procesados")
    print("\n=== AGREGAR AL manifest.json (antes de la llave cierre) ===")
    print(json.dumps(mapas_procesados, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
