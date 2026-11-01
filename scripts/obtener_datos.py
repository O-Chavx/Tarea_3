"""
Paso 1 · Obtención de datos.

Descarga las bases originales desde el repositorio público del curso (sesión 06, geoespacial)
y las guarda en datos/originales/. Si ya existen, no las vuelve a bajar.

Origen de cada archivo:
  Poverty.csv          INEI (2020), Mapa de pobreza monetaria provincial y distrital 2018.
                       https://www.inei.gob.pe/media/MenuRecursivo/publicaciones_digitales/Est/Lib1718/Libro.pdf
                       POVERTY_RATE = punto medio del intervalo de confianza al 95 % de cada distrito.
  MINING.csv           MINEM, unidades mineras en producción.
                       http://www.minem.gob.pe/_publicaSector.php?idSector=1&idCategoria=24
  peru_*_simple.geojson  Límites distritales y departamentales (INEI), simplificados.

Uso:  python scripts/obtener_datos.py
"""
import hashlib
import urllib.request
from pathlib import Path

BASE = "https://raw.githubusercontent.com/d2cml-ai/Data-Science-Python/main/sessions/06-geoespacial/lab/Data/"
ARCHIVOS = ["Poverty.csv", "MINING.csv", "peru_distrital_simple.geojson", "peru_departamental_simple.geojson"]
DESTINO = Path(__file__).resolve().parents[1] / "datos" / "originales"
DESTINO.mkdir(parents=True, exist_ok=True)

for nombre in ARCHIVOS:
    ruta = DESTINO / nombre
    if not ruta.exists():
        print("Descargando", nombre)
        urllib.request.urlretrieve(BASE + nombre, ruta)
    h = hashlib.sha256(ruta.read_bytes()).hexdigest()[:12]
    print(f"✓ {nombre:36s} {ruta.stat().st_size / 1024:8.0f} KB  sha256:{h}")
