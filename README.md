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
| coquimbo_sur | Coquimbo (Sector Sur) | 1:250.000 | 2021 | IR-COQ-03 (IR-21-88) |
| valpo_concon | Valparaíso — Concón (Hoja 1 de 3) | 1:10.000 | 2005 | IR-05-29 |
| valpo_vina_del_mar | Valparaíso — Viña del Mar (Hoja 2 de 3) | 1:10.000 | 2005 | IR-05-29 |
| valpo_valparaiso | Valparaíso — Valparaíso (Hoja 3 de 3) | 1:10.000 | 2005 | IR-05-29 |
| ohiggins_rancagua | O'Higgins — Área de Rancagua | 1:100.000 | 2017 | Geología Ambiental Nº29 |
| flujos_aluvionales_maipo | Metropolitana — Cuenca del Río Maipo | 1:100.000 | 2021 | Susceptibilidad de Flujos Aluvionales (SIGMA) |

Las 3 hojas de Valparaíso comparten una única leyenda (`overlays/valpo_leyenda.webp`, recortada
de la Hoja 2, la única que la trae completa) y usan datum **PSAD56** (no WGS84): el propio
informe declara "Datum Provisorio Sudamericano (PSAD), La Canoa, Venezuela, 1956", por lo que
se georreferenciaron con EPSG:24879 en vez de EPSG:32719. Ver `georef_valparaiso.py`.

`ohiggins_rancagua` es el "Mapa 4: Peligro de Remociones en Masa" de la Carta Geológica de
Chile, Serie Geología Ambiental Nº29 (Área de Rancagua). La hoja original trae además un mapa
secundario distinto ("Densidad de Remociones en Masa", 1:250.000) que **no** se incluyó. Grilla
UTM con rotación real de ~1° (mismo caso que `coquimbo_sur`): se usó el modelo afín completo de
6 parámetros. Datum SIRGAS (≈ WGS84, EPSG:32719), a diferencia de las hojas de Valparaíso. Ver
`georef_ohiggins_rancagua.py`.

`flujos_aluvionales_maipo` es distinto a los anteriores: no viene de un PDF escaneado sino de un
**raster ya pre-teselado** (ArcGIS MapServer `singleFusedMapCache`, capabilities `TilesOnly`) de
la Plataforma SIGMA (CIGIDEN). El endpoint `/export` dinámico **no** está disponible en este tipo
de servicio (devuelve 404); el pipeline descarga el mosaico de tiles cacheadas (nivel de zoom
máximo del servicio) que cubre el bbox, lo recorta exacto y lo reproyecta (warp vertical) de Web
Mercator (EPSG:3857, proyección nativa de las tiles) a WGS84 plate-carrée. La categoría "No
Susceptible" viene con opacidad fija ~80% en el tile original (gris sólido); se le redujo el
alpha en post-proceso para no tapar el satélite en las zonas sin peligro, dejando las demás
categorías con su opacidad original. Ver `georef_flujos_aluvionales.py`.
