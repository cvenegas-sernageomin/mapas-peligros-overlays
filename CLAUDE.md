# Mapas de peligro (overlays) — notas para Claude

Pipeline + repo de mapas de peligro georreferenciados (PDF/ArcGIS → WebP + bounds) que consumen
Remociones en masa y GeoChile vía `manifest.json`. Repo `cvenegas-sernageomin/mapas-peligros-overlays` (rama `main`).
Ficha en memoria: `proyecto-mapas-peligros-overlays` (métodos A–F según el tipo de fuente).

## Entorno
- Usar `…\Python312\python.exe -X utf8`: el `python` por defecto no tiene cv2/pyproj.
- Hay un checkout viejo en otra ruta; el vigente es **este**.

## Reglas
- Un script `georef_<id>.py` por mapa; el resultado va a `overlays/<id>.webp` + `<id>_leyenda.webp` y una entrada en `manifest.json`.
- Al regenerar un overlay con el mismo nombre, **subir `version` del manifest**: los consumidores cuelgan `?v=` de ahí y el navegador cachea los `<img>`.
- Verificar el datum de la hoja antes de asumir EPSG:32719. Medir cada meridiano a dos alturas (rotación).
- Verificación obligatoria de cada mapa nuevo: superponer calles/cauces OSM o límite administrativo (Esri satelital no basta).
- Las correcciones hechas en GeoChile a mapas de peligro se reflejan también aquí.

## Verificar
Servidor: config `mapas-peligros-overlays` (puerto 8771).
