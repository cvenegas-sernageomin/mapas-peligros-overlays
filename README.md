# Mapas de peligro — overlays georreferenciados

Overlays georreferenciados de mapas de **peligros geológicos** de SERNAGEOMIN (Chile),
listos para consumirse como **capa fija** en la PWA
[Ingreso de Remociones en Masa](https://cvenegas-sernageomin.github.io/remociones-en-masa/).

Cada mapa se sirve por CDN (`raw.githubusercontent.com`) y se descarga **on-demand** solo
cuando el usuario activa la capa (no engorda la PWA).

## Estructura

- `manifest.json` — índice que lee la PWA: por mapa da `bounds` (N/S/E/W en WGS84),
  URL del `overlay` (WebP con transparencia), URL de la `leyenda`, `opacidad` por defecto.
- `overlays/<id>.webp` — mapa recortado al neat-line, **warp a plate-carrée** (norte-arriba,
  rotación 0) para calzar exacto en Leaflet `imageOverlay`.
- `overlays/<id>_leyenda.webp` — leyenda/simbología de la hoja, consultable aparte.
- `georef_<id>.py` — script reproducible de georreferenciación (detección de grilla UTM por
  color → afín pixel→UTM → recorte → warp → export WebP).

## Cómo se georreferencia (resumen)

Proyección original UTM (huso según región, ej. 19S = EPSG:32719). Se detecta la grilla UTM
por color, se ajusta la transformación afín pixel→UTM (residuales típicos < 20 m), se recorta
al marco del mapa y se reproyecta a WGS84 plate-carrée. Ver `georef_coquimbo_norte.py`.

## Mapas incluidos

| id | Región | Escala | Año | Informe |
|----|--------|--------|-----|---------|
| coquimbo_norte | Coquimbo (Sector Norte) | 1:250.000 | 2018 | IR-COQ-02 |
