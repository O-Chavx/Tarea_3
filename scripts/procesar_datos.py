"""
Paso 2 · Limpieza y transformación.

Entradas (datos/originales/):
  - Poverty.csv                      Mapa de pobreza monetaria distrital 2018 (INEI), 1,873 distritos
  - MINING.csv                       Unidades mineras en producción (MINEM), 142 unidades
  - peru_distrital_simple.geojson    Límites distritales (INEI/MINAM), 1,834 polígonos
  - peru_departamental_simple.geojson

Salidas (datos/procesados/):
  - distritos.csv        un registro por distrito con pobreza, minería y distancia a la mina más cercana
  - minas.csv            unidades mineras limpias, con su pobreza distrital y control de ubicación
  - departamentos.csv    resumen por departamento
  - distritos_mapa.geojson  geometría simplificada + atributos (para el dashboard)

Solo usa pandas, numpy y matplotlib (sin geopandas) para que corra en cualquier entorno del curso.
Uso:  python scripts/procesar_datos.py
"""
from __future__ import annotations

import json
import math
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.path import Path as MplPath

RAIZ = Path(__file__).resolve().parents[1]
ORIG = RAIZ / "datos" / "originales"
PROC = RAIZ / "datos" / "procesados"
PROC.mkdir(parents=True, exist_ok=True)

UMBRAL_POBRE = 40.0  # % de pobreza monetaria que usa INEI para hablar de distritos con alta pobreza


def sin_tildes(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in s if not unicodedata.combining(c)).upper().strip()


def limpiar_texto(s: pd.Series) -> pd.Series:
    return s.astype(str).str.replace(r"\s+", " ", regex=True).str.strip()


# ───────────────────────── 1. Pobreza distrital (INEI 2018) ─────────────────────────
pob = pd.read_csv(ORIG / "Poverty.csv", encoding="utf-8-sig", dtype={"UBIGEO1": str, "UBIGEO2": str})
pob = pob.rename(columns={"UBIGEO1": "ubigeo", "DEPARTAMENTO": "departamento", "PROVINCIA": "provincia",
                          "DISTRITO": "distrito", "POVERTY_RATE": "pobreza"})
pob["ubigeo"] = pob["ubigeo"].str.zfill(6)
for c in ["departamento", "provincia", "distrito"]:
    pob[c] = limpiar_texto(pob[c])
# PBI_PC e IDH vienen a nivel departamental, sin año ni fuente documentados y con "#N/D" en Callao:
# no se usan en el análisis (ver Limitaciones en el README).
pob = pob[["ubigeo", "departamento", "provincia", "distrito", "pobreza"]]
assert pob["ubigeo"].is_unique, "ubigeo duplicado"
assert pob["pobreza"].between(0, 100).all(), "pobreza fuera de rango"
pob["dep_key"] = pob["departamento"].map(sin_tildes)

# ───────────────────────── 2. Unidades mineras (MINEM) ─────────────────────────
min_ = pd.read_csv(ORIG / "MINING.csv", encoding="utf-8-sig", dtype={"UBIGEO": str})
min_.columns = min_.columns.str.strip()
min_ = min_.rename(columns={"UBIGEO": "ubigeo", "MÉTODO DE EXPLOTACIÓN": "metodo", "TITULAR": "titular",
                            "UNIDAD": "unidad", "REGION": "region", "PROVINCIA": "provincia_m",
                            "DISTRITO": "distrito_m", "PRODUCTO": "producto", "LONGITUD": "lon", "LATITUD": "lat"})
min_["ubigeo"] = min_["ubigeo"].str.zfill(6)
for c in ["metodo", "titular", "unidad", "region", "provincia_m", "distrito_m", "producto"]:
    min_[c] = limpiar_texto(min_[c])
# Unificar mayúsculas inconsistentes ("MINERíA" / "MINERÍA") y región con/sin tilde ("APURIMAC"/"APURÍMAC")
min_["metodo"] = min_["metodo"].map(sin_tildes).str.title().str.replace("Mineria", "Minería")
min_["metodo"] = min_["metodo"].replace({"Refineria": "Refinería", "Fundicion": "Fundición",
                                         "Minería No Metalica": "Minería no metálica",
                                         "Minería Subterranea": "Minería subterránea",
                                         "Minería Superficial": "Minería superficial"})
min_["region"] = min_["region"].map(sin_tildes)
dup = min_.duplicated(subset=["unidad", "titular", "ubigeo"]).sum()
min_ = min_.drop_duplicates(subset=["unidad", "titular", "ubigeo"])

METALES = {"Au": "Oro", "Ag": "Plata", "Cu": "Cobre", "Zn": "Zinc", "Pb": "Plomo", "Mo": "Molibdeno",
           "Sn": "Estaño", "Fe": "Hierro", "As": "Arsénico", "Bi": "Bismuto", "Mn": "Manganeso",
           "Cd": "Cadmio", "W": "Tungsteno", "Sb": "Antimonio", "In": "Indio", "Te": "Telurio", "Se": "Selenio"}
min_["productos"] = min_["producto"].str.split(",").apply(lambda xs: [x.strip() for x in xs if x.strip()])
min_["es_metalica"] = min_["productos"].apply(lambda xs: any(x in METALES for x in xs))
min_["oro"] = min_["productos"].apply(lambda xs: "Au" in xs)
min_["cobre"] = min_["productos"].apply(lambda xs: "Cu" in xs)
min_["plata"] = min_["productos"].apply(lambda xs: "Ag" in xs)
min_["zinc_plomo"] = min_["productos"].apply(lambda xs: "Zn" in xs or "Pb" in xs)


def mineral_principal(xs: list[str]) -> str:
    for k in ["Cu", "Au", "Zn", "Ag", "Pb", "Fe", "Sn", "Mo"]:
        if k in xs:
            return METALES[k]
    return "No metálico"


min_["mineral_principal"] = min_["productos"].apply(mineral_principal)
min_["tipo"] = np.where(min_["es_metalica"], "Metálica", "No metálica")

# ───────────────────────── 3. Geometría distrital ─────────────────────────
geo = json.loads((ORIG / "peru_distrital_simple.geojson").read_text(encoding="utf-8"))
geo_sin_geom = [f["properties"]["IDDIST"] for f in geo["features"] if not f.get("geometry")]


def anillos(geom):
    if geom["type"] == "Polygon":
        return [geom["coordinates"]]
    return geom["coordinates"]  # MultiPolygon


def centroide(geom):
    """Centroide ponderado por área (fórmula del polígono / shoelace) del anillo exterior de cada parte."""
    A = Cx = Cy = 0.0
    for poly in anillos(geom):
        x, y = np.asarray(poly[0]).T[:2]
        cross = x[:-1] * y[1:] - x[1:] * y[:-1]
        a = cross.sum() / 2
        if abs(a) < 1e-14:
            continue
        A += a
        Cx += ((x[:-1] + x[1:]) * cross).sum() / 6
        Cy += ((y[:-1] + y[1:]) * cross).sum() / 6
    return (Cx / A, Cy / A) if A else (np.nan, np.nan)


paths: dict[str, list[MplPath]] = {}
cent = {}
for f in geo["features"]:
    if not f.get("geometry"):
        continue
    ub = f["properties"]["IDDIST"]
    cent[ub] = centroide(f["geometry"])
    paths[ub] = [MplPath(np.asarray(poly[0])[:, :2]) for poly in anillos(f["geometry"])]

cent_df = pd.DataFrame([(k, v[0], v[1]) for k, v in cent.items()], columns=["ubigeo", "lon_c", "lat_c"])


def contiene(ub: str, lon: float, lat: float) -> bool:
    return any(p.contains_point((lon, lat)) for p in paths.get(ub, []))


# Control de calidad: ¿cada mina cae dentro del polígono del distrito que declara?
min_["dentro_de_su_distrito"] = [contiene(u, lo, la) for u, lo, la in zip(min_.ubigeo, min_.lon, min_.lat)]


# ───────────────────────── 4. Cruce y distancia a la mina más cercana ─────────────────────────
def haversine_km(lon1, lat1, lon2, lat2):
    R = 6371.0
    lon1, lat1, lon2, lat2 = map(np.radians, (lon1, lat1, lon2, lat2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


por_dist = (min_.groupby("ubigeo")
            .agg(n_minas=("unidad", "size"),
                 n_metalicas=("es_metalica", "sum"),
                 tiene_oro=("oro", "any"), tiene_cobre=("cobre", "any"),
                 metodos=("metodo", lambda s: "; ".join(sorted(set(s)))),
                 minerales=("productos", lambda s: ", ".join(sorted({x for xs in s for x in xs}))),
                 unidades=("unidad", lambda s: "; ".join(s)),
                 titulares=("titular", lambda s: "; ".join(sorted(set(s)))))
            .reset_index())

d = pob.merge(cent_df, on="ubigeo", how="left").merge(por_dist, on="ubigeo", how="left")
d["n_minas"] = d["n_minas"].fillna(0).astype(int)
d["n_metalicas"] = d["n_metalicas"].fillna(0).astype(int)
d["tiene_oro"] = d["tiene_oro"].astype("boolean").fillna(False).astype(bool)
d["tiene_cobre"] = d["tiene_cobre"].astype("boolean").fillna(False).astype(bool)
d["minero"] = d["n_minas"] > 0
d["con_mapa"] = d["lon_c"].notna()
d["pobreza_alta"] = d["pobreza"] >= UMBRAL_POBRE

M = min_[["lon", "lat"]].to_numpy()
dist = np.full(len(d), np.nan)
ok = d["con_mapa"].to_numpy()
C = d.loc[ok, ["lon_c", "lat_c"]].to_numpy()
D = haversine_km(C[:, [0]], C[:, [1]], M[:, 0][None, :], M[:, 1][None, :])
dist[ok] = D.min(axis=1)
d["dist_mina_km"] = np.where(d["minero"], 0.0, dist)

bins = [-0.1, 0.0, 25, 50, 100, 1e9]
labs = ["Distrito minero", "< 25 km", "25–50 km", "50–100 km", "> 100 km"]
d["banda_distancia"] = pd.cut(d["dist_mina_km"], bins=bins, labels=labs)
d.loc[~d["con_mapa"] & ~d["minero"], "banda_distancia"] = np.nan

# Región natural aproximada no disponible → se usa el departamento como control territorial.
d = d.sort_values("ubigeo").reset_index(drop=True)
cols = ["ubigeo", "departamento", "provincia", "distrito", "pobreza", "pobreza_alta", "minero", "n_minas",
        "n_metalicas", "tiene_oro", "tiene_cobre", "metodos", "minerales", "unidades", "titulares",
        "lon_c", "lat_c", "con_mapa", "dist_mina_km", "banda_distancia"]
d[cols].to_csv(PROC / "distritos.csv", index=False, float_format="%.4f")

m_out = min_.merge(pob[["ubigeo", "departamento", "distrito", "pobreza"]], on="ubigeo", how="left")
m_out["productos"] = m_out["productos"].apply(", ".join)
m_out[["ubigeo", "departamento", "distrito", "unidad", "titular", "metodo", "tipo", "mineral_principal",
       "productos", "oro", "cobre", "plata", "zinc_plomo", "lon", "lat", "dentro_de_su_distrito", "pobreza"]
      ].to_csv(PROC / "minas.csv", index=False, float_format="%.4f")

dep = (d.groupby("departamento")
       .agg(distritos=("ubigeo", "size"), pobreza_media=("pobreza", "mean"),
            pobreza_mediana=("pobreza", "median"), pobreza_max=("pobreza", "max"),
            pobreza_min=("pobreza", "min"), distritos_pobreza_alta=("pobreza_alta", "sum"),
            distritos_mineros=("minero", "sum"), unidades_mineras=("n_minas", "sum"))
       .reset_index())
dep["pct_pobreza_alta"] = 100 * dep["distritos_pobreza_alta"] / dep["distritos"]
dep["brecha_max_min"] = dep["pobreza_max"] - dep["pobreza_min"]
dep.to_csv(PROC / "departamentos.csv", index=False, float_format="%.3f")


# ───────────────────────── 5. GeoJSON liviano para la web ─────────────────────────
def redondear(coords, nd=3):
    if isinstance(coords[0], (int, float)):
        return [round(coords[0], nd), round(coords[1], nd)]
    out = [redondear(c, nd) for c in coords]
    if out and isinstance(out[0][0], (int, float)):  # anillo: quitar puntos repetidos consecutivos
        dedup = [out[0]] + [p for i, p in enumerate(out[1:], 1) if p != out[i - 1]]
        out = dedup if len(dedup) >= 4 else out
    return out


attrs = d.set_index("ubigeo")
feats = []
for f in geo["features"]:
    if not f.get("geometry"):
        continue
    ub = f["properties"]["IDDIST"]
    if ub not in attrs.index:
        continue
    r = attrs.loc[ub]
    feats.append({"type": "Feature",
                  "properties": {"u": ub},
                  "geometry": {"type": f["geometry"]["type"], "coordinates": redondear(f["geometry"]["coordinates"])}})
(PROC / "distritos_mapa.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats},
                                                        separators=(",", ":")), encoding="utf-8")

print(f"Distritos con pobreza: {len(d):,} | con polígono en el mapa: {d.con_mapa.sum():,} "
      f"| sin polígono (creados después del shapefile): {(~d.con_mapa).sum()}")
print(f"Polígonos sin geometría en el geojson: {len(geo_sin_geom)} | duplicados de minas eliminados: {dup}")
print(f"Unidades mineras: {len(min_)} en {min_.ubigeo.nunique()} distritos | "
      f"coordenadas dentro de su distrito declarado: {min_.dentro_de_su_distrito.sum()} de {len(min_)}")
print("Listo →", PROC)
