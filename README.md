# Minería y pobreza en el Perú

**Tarea 3 · Python Intermedio · Oscar Andres Chavez Inocente**

**Pregunta de investigación:** ¿Los distritos que albergan unidades mineras tienen menos pobreza monetaria que el resto del Perú, y esa diferencia se mantiene al comparar dentro del mismo departamento?

| | |
|---|---|
| Repositorio | https://github.com/O-Chavx/Tarea_3 |
| Dashboard público | https://o-chavx.github.io/Tarea_3/web/ |
| Publicación de LinkedIn | https://www.linkedin.com/… *(reemplazar)* |
| Reel | [`reel/reel.mp4`](reel/reel.mp4) (51 s, 1080 × 1920) · subtítulos en [`reel/subtitulos.srt`](reel/subtitulos.srt) |

![Dashboard: cabecera, filtros y KPIs](docs/captura_dashboard_1.png)

## Descripción

El proyecto cruza la pobreza monetaria estimada por el INEI para **1,873 distritos** (2018) con la ubicación de **142 unidades mineras** registradas por el MINEM. Con Python se limpian y unen las bases, se calcula para cada distrito si alberga minas y a qué distancia está la mina más cercana, y se comparan los niveles de pobreza. Los resultados se publican en un dashboard interactivo (D3.js) y se resumen en un reel vertical de unos 60 segundos narrado con mi voz clonada por IA.

**Cobertura:** Perú, 25 departamentos, 1,873 distritos. **Periodo:** pobreza monetaria 2018 (Mapa de Pobreza publicado por INEI en 2020); unidades mineras del registro MINEM del curso.

## Fuentes de datos

| Archivo | Fuente | Contenido |
|---|---|---|
| `datos/originales/Poverty.csv` | INEI (2020), [Mapa de pobreza monetaria provincial y distrital 2018](https://www.inei.gob.pe/media/MenuRecursivo/publicaciones_digitales/Est/Lib1718/Libro.pdf) | Pobreza monetaria por distrito (punto medio del IC 95 %) |
| `datos/originales/MINING.csv` | MINEM, [unidades mineras en producción](http://www.minem.gob.pe/_publicaSector.php?idSector=1&idCategoria=24) | 142 unidades: titular, método, productos, UBIGEO y coordenadas |
| `datos/originales/peru_distrital_simple.geojson` | Límites distritales INEI (simplificados) | 1,834 polígonos |

Las cuatro bases vienen del repositorio del curso ([d2cml-ai/Data-Science-Python](https://github.com/d2cml-ai/Data-Science-Python/tree/main/sessions/06-geoespacial/lab/Data), sesión 06) y se descargaron el 30 de octubre de 2026. `scripts/obtener_datos.py` las vuelve a bajar y muestra su huella sha256 (Poverty `b54a657567b7`, MINING `19a493f05066`, distrital `1eba0da33464`).

**Verificación de la fuente de pobreza:** los tres distritos más pobres de la base (Uchuraccay, Oxamarca y Anguía) son los mismos que reportó el INEI al publicar el mapa, y en ambos casos 16 de los 20 distritos más pobres están en Cajamarca ([Peru Support Group, 2020](https://perusupportgroup.org.uk/2020/02/poverty-map-published/)).

## Metodología

1. **Limpieza** (`scripts/procesar_datos.py`): UBIGEO a 6 dígitos; espacios y mayúsculas inconsistentes en nombres («MINERíA» / «MINERÍA», «APURIMAC» / «APURÍMAC»); control de rango de pobreza (0–100) y de duplicados; separación de los productos de cada unidad (Au, Ag, Cu, Zn, Pb…) en metálicos y no metálicos. Las columnas `PBI_PC` e `IDH` se descartan: son departamentales, no documentan año ni fuente y tienen `#N/D` en Callao.
2. **Cruce espacial sin geopandas:** centroide de cada polígono (fórmula de área), distancia haversine del centroide a la unidad minera más cercana, y control de que cada mina caiga dentro de su distrito declarado (`matplotlib.path`).
3. **Indicadores** (`scripts/analizar_datos.py`):
   - Distrito minero = alberga al menos una unidad (por UBIGEO oficial).
   - Brecha bruta = pobreza media de distritos mineros − pobreza media del resto.
   - Brecha dentro del departamento = la misma resta en cada departamento, promediada según su número de distritos mineros.
   - Porcentaje de distritos con pobreza ≥ 40 %; pobreza media por banda de distancia (0, < 25, 25–50, 50–100, > 100 km); pobreza media por mineral y método.
   - Significancia: Mann–Whitney (brecha bruta) y prueba de permutación con 10,000 sorteos de la etiqueta «minero» dentro de cada departamento.
4. Todas las cifras quedan en `datos/procesados/resultados.json`, de donde las toman el dashboard, el guion del reel y este README.

## Hallazgos principales

1. **Los distritos con minas son menos pobres en promedio: −7.8 puntos.** Su pobreza media es 26.8 % frente a 34.6 % del resto (mediana 24.5 % vs 35.0 %). Solo el 22.0 % de los 109 distritos mineros supera el 40 % de pobreza, frente al 39.1 % de los demás (Mann–Whitney, p < 0.001).
2. **Al comparar dentro de cada departamento, la ventaja se reduce casi a la mitad: −4.4 puntos.** Parte de la brecha bruta se explica por *dónde* están las minas. Aun así, la diferencia se mantiene en 18 de 21 departamentos y no aparece por azar (permutación, p < 0.0001). En Cusco (+5.7) y Huánuco (+5.6) los distritos mineros son más pobres que el resto de su departamento.
3. **La pobreza aumenta con la distancia a una mina, pero la mina no garantiza bienestar.** La pobreza media pasa de 26.8 % en distritos mineros a 31.2 % a menos de 25 km, 34.7 % entre 25 y 50 km, 36.4 % entre 50 y 100 km y 36.9 % a más de 100 km. Sin embargo, 24 distritos mineros superan el 40 %: los 8 de Cajamarca promedian 52.9 %, y Cachachi (76.9 %) y Encañada (74.9 %) están entre los más pobres del país.

Además: los distritos con unidades de cobre promedian 21.0 % de pobreza y los de oro 32.0 %; entre distritos mineros, tener más unidades no se asocia con menos pobreza (Spearman ρ = −0.13, p = 0.19).

![Dashboard: comparación por departamento, distribución y mineral](docs/captura_dashboard_2.png)

## Limitaciones

- **Asociación, no causalidad.** Las minas no se ubican al azar; los distritos mineros pueden diferir en altitud, urbanización o conectividad. Además, algunas «unidades» son refinerías o fundiciones en zonas urbanas (Lima, Ica, Arequipa).
- **Un solo corte (2018).** No permite ver si la pobreza cambió después de la llegada de la mina.
- **Promedios simples por distrito**, sin ponderar por población: un distrito de 500 habitantes pesa igual que uno de 500,000.
- **Registro minero incompleto:** 142 unidades formales; no incluye minería artesanal ni informal ni proyectos en exploración. En 33 unidades la coordenada cae fuera del distrito declarado; para clasificar distritos se usa el UBIGEO oficial y las coordenadas solo para mapas y distancias.
- **Mapa desactualizado:** el geojson tiene 1,834 polígonos; 50 distritos creados después (p. ej. Uchuraccay) no tienen polígono ni distancia, pero sí entran en los KPIs y la tabla.
- La pobreza distrital es una estimación en áreas pequeñas con intervalo de confianza; aquí se usa el punto medio.

## Estructura

```
Tarea_3/
├── README.md · requirements.txt · index.html (redirige a web/)
├── datos/originales/        bases tal como vienen del curso
├── datos/procesados/        distritos.csv, minas.csv, departamentos.csv, resultados.json, geojson liviano
├── scripts/                 obtener_datos.py → procesar_datos.py → analizar_datos.py
├── web/                     index.html (dashboard D3.js) + data/datos.js
├── reel/                    guion.json, hacer_reel_mineria.py, generar_visuales.py, reel.py (sesión 15),
│                            recursos/ (imágenes por escena, música CC0, fuentes Inter OFL), reel.mp4, subtitulos.srt
└── docs/                    capturas del dashboard y texto de LinkedIn
```

## Cómo reproducir

```bash
cd Tarea_3
pip install -r requirements.txt
python scripts/obtener_datos.py     # descarga las bases (si no están)
python scripts/procesar_datos.py    # limpieza y cruce
python scripts/analizar_datos.py    # indicadores, resultados.json y web/data/datos.js
python -m http.server -d web 8000   # abrir http://localhost:8000
```

**Publicar el dashboard (GitHub Pages):** Settings → Pages → *Deploy from a branch* → `main` / `/ (root)`. El dashboard queda en https://o-chavx.github.io/Tarea_3/web/ (la raíz redirige ahí).

**Reel** (en el entorno de la sesión 15: `qwen-tts faster-whisper imageio-ffmpeg soundfile jiwer num2words pillow`):

```bash
cd reel
python generar_visuales.py                       # imágenes de las escenas
python recursos/generar_musica.py                # pista de fondo original
python hacer_reel_mineria.py --vista-previa      # prueba sin voz
python hacer_reel_mineria.py --voz mi_voz.ogg --tts Qwen/Qwen3-TTS-12Hz-1.7B-Base --velocidad 1.05   # reel final
```

La grabación de referencia (24.7 s) no se sube al repositorio. `reel/reel.mp4` es la versión final (modelo Qwen3-TTS 1.7B); `reel/reel_v1.mp4` es la primera prueba con el modelo 0.6B.

## Uso de inteligencia artificial

Usé Claude (Anthropic) para proponer el enfoque, escribir y depurar los scripts de Python, construir el dashboard y redactar el guion del reel. La narración del reel se generó con Qwen3-TTS 1.7B (Alibaba, Apache 2.0) a partir de una grabación de mi propia voz, y Whisper produjo los subtítulos. Revisé que cada cifra del dashboard, el guion y este README coincida con `datos/procesados/resultados.json` y contrasté la fuente de pobreza con publicaciones del INEI. La música de fondo es original, generada con código (CC0).
