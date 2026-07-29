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

**31 mapas** en 7 regiones (manifest `version: 3`, actualizado 2026-07-28c).

| id | Región | Escala | Año | Informe |
|----|--------|--------|-----|---------|
| `cruz_de_cana_contexto` | Coquimbo | 1:20.000 aprox. | 2025 | Plano de evacuación Cruz de Caña, Comuna de Coquimbo |
| `cruz_de_cana_detalle` | Coquimbo | 1:5.000 aprox. | 2025 | Plano de evacuación Cruz de Caña, Comuna de Coquimbo |
| `islon_flujos_inundacion` | Coquimbo | 1:10.000 | 2026 | Fig |
| `el_romero_flujos_inundacion` | Coquimbo | 1:5.000 aprox. | 2026 | Zonificacion |
| `atacama_copiapo_hoja1` | Atacama | 1:100.000 | 2022 | IR-22-99 |
| `atacama_copiapo_hoja2` | Atacama | 1:100.000 | 2022 | IR-22-99 |
| `atacama_copiapo_hoja3` | Atacama | 1:100.000 | 2022 | IR-22-99 |
| `atacama_copiapo_hoja4` | Atacama | 1:100.000 | 2022 | IR-22-99 |
| `caida_rocas_maipo` | Metropolitana | — | 2021 | Susceptibilidad y propagación de caídas de rocas |
| `coquimbo_norte` | Coquimbo | 1:250.000 | 2018 | IR-COQ-02 |
| `coquimbo_sur` | Coquimbo | 1:250.000 | 2021 | IR-COQ-03 |
| `valpo_concon` | Valparaíso | 1:10.000 | 2005 | IR-05-29 |
| `valpo_vina_del_mar` | Valparaíso | 1:10.000 | 2005 | IR-05-29 |
| `valpo_valparaiso` | Valparaíso | 1:10.000 | 2005 | IR-05-29 |
| `ohiggins_rancagua` | O'Higgins | 1:100.000 | 2017 | Carta Geológica de Chile - Geología Ambiental Nº29 |
| `flujos_aluvionales_maipo` | Metropolitana | 1:100.000 | 2021 | Susceptibilidad de Flujos Aluvionales |
| `deslizamientos_laderas_maipo` | Metropolitana | 1:100.000 | 2021 | Susceptibilidad de Deslizamientos de Laderas |
| `flujos_sjmaipo_peligro` | Metropolitana | 1:25.000 aprox. | 2026 | Mapa de peligro de flujos de la cuenca alta del río Maipo, … |
| `flujos_lobar_alcance` | Metropolitana | 1:20.000 aprox. | 2026 | Mapa de grado de peligro por alcance de flujos de la cuenca… |
| `flujos_lobar_generacion` | Metropolitana | 1:20.000 aprox. | 2026 | Mapa de grado de peligro por generación de flujos de la cue… |
| `flujos_biobio_tirua` | Bío-Bío | 1:10.000 | 2011 | Evaluación preliminar de peligros geológicos: Área de Tirúa… |
| `flujos_biobio_curanilahue` | Bío-Bío | 1:25.000 | 2011 | Evaluación preliminar de peligros geológicos: Área de Curan… |
| `flujos_biobio_arauco` | Bío-Bío | 1:10.000 | 2011 | Evaluación preliminar de peligros geológicos: Área de la Ci… |
| `flujos_biobio_tubul` | Bío-Bío | 1:25.000 | 2011 | Evaluación preliminar de peligros geológicos: Área Caletas … |
| `flujos_biobio_puntalavapie` | Bío-Bío | 1:10.000 | 2011 | Evaluación preliminar de peligros geológicos: Área de Calet… |
| `flujos_biobio_penco` | Bío-Bío | 1:10.000 | 2011 | Evaluación preliminar de peligros geológicos: Área de Penco… |
| `flujos_biobio_concepcion_a` | Bío-Bío | 1:25.000 | 2012 | Evaluación preliminar de peligros geológicos: Área de Conce… |
| `flujos_biobio_concepcion_b` | Bío-Bío | 1:25.000 | 2012 | Evaluación preliminar de peligros geológicos: Área de Conce… |
| `maule_constitucion` | Maule | 1:10.000 | 2010 | Evaluación preliminar de peligros geológicos: Área de Const… |
| `maule_curico` | Maule | 1:10.000 | 2010 | Evaluación preliminar de peligros geológicos: Área de Curic… |
| `maule_duaoiloca` | Maule | 1:10.000 | 2010 | Evaluación preliminar de peligros geológicos: Área de Duao-… |

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

`deslizamientos_laderas_maipo` usa el mismo pipeline (mismo servicio SIGMA, mismo tipo
`TilesOnly`, misma cuenca del Maipo), con 6 categorías en vez de 5 (agrega "Muy Bajo"). El color
de "No Susceptible" varía entre capas SIGMA (gris (204,204,204) en flujos aluvionales, gris
(178,178,178) aquí), así que el script lo toma dinámicamente desde `/legend?f=json` en vez de
asumirlo fijo. Ver `georef_deslizamientos_laderas.py`.
