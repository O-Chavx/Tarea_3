# Metodología

## Unidad de análisis

El **distrito**: 1,873 distritos con estimación de pobreza del INEI (Mapa de pobreza monetaria 2018).

## Variables

| Variable | Archivo | Definición |
|---|---|---|
| `pobreza` | `distritos.csv` | Pobreza monetaria 2018 (%). Punto medio del intervalo de confianza al 95 % que publica el INEI para cada distrito. |
| `pobreza_alta` | `distritos.csv` | `pobreza ≥ 40` (umbral que el INEI usa al describir el mapa: 713 distritos). |
| `minero` | `distritos.csv` | El distrito alberga al menos una unidad minera del registro MINEM, según su **UBIGEO oficial**. |
| `n_minas` | `distritos.csv` | Número de unidades mineras en el distrito. |
| `lon_c`, `lat_c` | `distritos.csv` | Centroide del polígono del distrito (fórmula del área, anillo exterior de cada parte). |
| `dist_mina_km` | `distritos.csv` | Distancia haversine (radio 6,371 km) del centroide a la unidad minera más cercana; 0 si el distrito es minero. |
| `banda_distancia` | `distritos.csv` | Distrito minero, < 25 km, 25–50 km, 50–100 km, > 100 km. |
| `metodo`, `tipo`, `productos` | `minas.csv` | Método de explotación, metálica / no metálica y minerales (Au, Ag, Cu, Zn, Pb, Mo…). |
| `dentro_de_su_distrito` | `minas.csv` | Control de calidad: la coordenada cae dentro del polígono del distrito declarado. |

## Limpieza

- UBIGEO a 6 dígitos (texto) en las tres bases; espacios y mayúsculas inconsistentes normalizados («MINERíA» → «Minería», «APURIMAC» → «APURÍMAC»).
- Controles: UBIGEO único, pobreza en [0, 100], sin faltantes, sin unidades duplicadas, toda mina con UBIGEO existente.
- `PBI_PC` e `IDH` del archivo del curso **no se usan**: son departamentales, sin año ni fuente documentados y con `#N/D` en Callao.
- El geojson del curso tiene 1,834 polígonos (8 sin geometría): 50 distritos creados después quedan sin polígono. Siguen en los KPI y la tabla, pero no tienen distancia.

## Indicadores

- **Brecha bruta** = media(pobreza | minero) − media(pobreza | no minero).
- **Brecha dentro del departamento** = para cada departamento con distritos mineros y no mineros, la misma resta; luego el promedio ponderado por el número de distritos mineros del departamento. Compara cada distrito minero con sus vecinos del mismo departamento y quita el efecto de que las minas estén en ciertas regiones.
- **Pobreza por banda de distancia** = promedio simple de pobreza de los distritos en cada banda.
- **Pobreza por mineral** = promedio, entre unidades mineras, de la pobreza del distrito donde opera cada una.

Todos los promedios son **simples entre distritos** (no ponderados por población): la pregunta es sobre distritos, no sobre personas.

## Pruebas estadísticas

- **Mann–Whitney** para comparar la distribución de pobreza de distritos mineros y no mineros (p = 1.0 × 10⁻⁶).
- **Permutación dentro de cada departamento** (10,000 sorteos): se baraja la etiqueta «minero» entre los distritos de un mismo departamento y se recalcula la brecha ponderada. Ningún sorteo alcanzó una brecha tan grande como la observada (p < 0.0001).
- **Spearman** entre número de unidades y pobreza en distritos mineros (ρ = −0.13, p = 0.19: no significativo).

## Verificación

`scripts/verificar_datos.py` hace 32 comprobaciones (todas OK, ver `datos/procesados/verificacion.txt`):

- integridad de las bases y del cruce;
- contraste con lo que publicó el INEI: los 3 distritos más pobres (Uchuraccay, Oxamarca, Anguía), 16 de los 20 más pobres en Cajamarca y 713 distritos con pobreza ≥ 40 %;
- cada cifra del README, del dashboard y del reel, recalculada desde los CSV;
- los datos del dashboard idénticos a los procesados.
