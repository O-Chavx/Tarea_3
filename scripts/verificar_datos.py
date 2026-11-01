"""
Paso 4 · Verificación de datos y cifras.

Recalcula desde datos/procesados/*.csv cada cifra que usan el dashboard, el README y el reel,
la compara con resultados.json y la contrasta con lo que publicó el INEI.
Escribe datos/procesados/verificacion.txt y termina con error si alguna comprobación falla.

Uso:  python scripts/verificar_datos.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
PROC = RAIZ / "datos" / "procesados"
d = pd.read_csv(PROC / "distritos.csv", dtype={"ubigeo": str})
m = pd.read_csv(PROC / "minas.csv", dtype={"ubigeo": str})
dep = pd.read_csv(PROC / "departamentos.csv")
R = json.loads((PROC / "resultados.json").read_text(encoding="utf-8"))
geo = json.loads((PROC / "distritos_mapa.geojson").read_text(encoding="utf-8"))
web = (RAIZ / "web" / "data" / "datos.js").read_text(encoding="utf-8")
W = json.loads(web[web.index("{"):web.rindex("}") + 1].replace("NaN", "null"))

filas, fallas = [], 0


def ok(nombre, cond, detalle=""):
    global fallas
    fallas += not cond
    filas.append(f"{'OK   ' if cond else 'FALLA'}  {nombre}{'  · ' + detalle if detalle else ''}")


def cerca(a, b, tol=0.05):
    return abs(float(a) - float(b)) <= tol


# 1. Integridad
ok("1,873 distritos con pobreza", len(d) == 1873, f"{len(d)}")
ok("UBIGEO único y de 6 dígitos", d.ubigeo.is_unique and d.ubigeo.str.fullmatch(r"\d{6}").all())
ok("Pobreza entre 0 y 100 %", d.pobreza.between(0, 100).all(), f"{d.pobreza.min():.2f}–{d.pobreza.max():.2f}")
ok("Sin valores faltantes en pobreza", d.pobreza.notna().all())
ok("25 departamentos", d.departamento.nunique() == 25)
ok("142 unidades mineras", len(m) == 142)
ok("Unidades sin duplicados (unidad, titular, UBIGEO)", not m.duplicated(["unidad", "titular", "ubigeo"]).any())
ok("Todo UBIGEO minero existe en la base de pobreza", m.ubigeo.isin(d.ubigeo).all())
ok("109 distritos mineros", d.minero.sum() == 109 == m.ubigeo.nunique())
ok("Suma de unidades por distrito = 142", d.n_minas.sum() == 142)
ok("Coordenadas de minas dentro del Perú", m.lon.between(-81.5, -68.5).all() and m.lat.between(-18.5, 0).all())
ok("1,823 polígonos en el mapa (50 distritos nuevos sin polígono)", len(geo["features"]) == 1823 and (~d.con_mapa).sum() == 50)
ok("Departamentos suman 1,873 distritos", dep.distritos.sum() == 1873)

# 2. Contraste con lo que publicó el INEI (Mapa de pobreza 2018)
top = d.nlargest(3, "pobreza").distrito.str.upper().tolist()
ok("3 distritos más pobres = Uchuraccay, Oxamarca, Anguía (INEI)", top == ["UCHURACCAY", "OXAMARCA", "ANGUIA"] or
   [t.replace("Í", "I") for t in top] == ["UCHURACCAY", "OXAMARCA", "ANGUIA"], ", ".join(top))
ok("16 de los 20 más pobres en Cajamarca (INEI)", (d.nlargest(20, "pobreza").departamento == "CAJAMARCA").sum() == 16)
ok("713 distritos con pobreza ≥ 40 % (INEI)", (d.pobreza >= 40).sum() == 713, f"{(d.pobreza >= 40).sum()}")

# 3. Cifras del análisis recalculadas
M, N = d[d.minero], d[~d.minero]
ok("Pobreza media distritos mineros = 26.8 %", cerca(M.pobreza.mean(), R["pobreza_media_minero"]) and cerca(M.pobreza.mean(), 26.84, .01))
ok("Pobreza media resto = 34.6 %", cerca(N.pobreza.mean(), R["pobreza_media_no_minero"]) and cerca(N.pobreza.mean(), 34.60, .01))
ok("Medianas 24.5 % y 35.0 %", cerca(M.pobreza.median(), 24.5) and cerca(N.pobreza.median(), 35.0))
ok("Brecha bruta = −7.8 pp", cerca(M.pobreza.mean() - N.pobreza.mean(), -7.76, .01))
ok("Pobreza ≥ 40 %: 22.0 % mineros vs 39.1 % resto",
   cerca(100 * M.pobreza_alta.mean(), 22.0, .1) and cerca(100 * N.pobreza_alta.mean(), 39.1, .1))
ok("24 distritos mineros con pobreza ≥ 40 %", M.pobreza_alta.sum() == 24 == R["mineros_pobreza_alta"])
intra = []
for _, g in d.groupby("departamento"):
    k = g.minero.sum()
    if 0 < k < len(g):
        intra.append((g[g.minero].pobreza.mean() - g[~g.minero].pobreza.mean(), k))
gap = np.average([a for a, _ in intra], weights=[k for _, k in intra])
ok("Brecha dentro del departamento = −4.4 pp", cerca(gap, R["brecha_intra_departamento_pp"]) and cerca(gap, -4.4, .05), f"{gap:.3f}")
ok("18 de 21 departamentos con distritos mineros menos pobres", sum(a < 0 for a, _ in intra) == 18 and len(intra) == 21)
b = d.dropna(subset=["banda_distancia"]).groupby("banda_distancia").pobreza.mean()
ok("Bandas: 26.8 / 31.2 / 34.7 / 36.4 / 36.9 %", all(cerca(b[k], v, .05) for k, v in
   {"Distrito minero": 26.84, "< 25 km": 31.18, "25–50 km": 34.74, "50–100 km": 36.42, "> 100 km": 36.90}.items()))
ok("Bandas crecen con la distancia", b.reindex(["Distrito minero", "< 25 km", "25–50 km", "50–100 km", "> 100 km"]).is_monotonic_increasing)
caj = d[(d.departamento == "CAJAMARCA") & d.minero]
ok("Cajamarca: 8 distritos mineros, 52.9 % de pobreza media", len(caj) == 8 and cerca(caj.pobreza.mean(), 52.9, .05))
ok("Cobre 21.0 % y oro 32.0 % (por unidad)", cerca(m[m.cobre].pobreza.mean(), 20.95, .01) and cerca(m[m.oro].pobreza.mean(), 32.0, .01))
ok("Junín es el departamento con más unidades (22)", R["dep_mas_minas"] == {"departamento": "JUNÍN", "unidades": 22})

# 4. Datos del dashboard idénticos a los procesados
wd = pd.DataFrame(W["distritos"])
ok("Dashboard: 1,873 distritos y 142 minas", len(wd) == 1873 and len(W["minas"]) == 142)
ok("Dashboard: pobreza igual a la base procesada",
   np.allclose(wd.sort_values("ubigeo").pobreza.to_numpy(), d.sort_values("ubigeo").pobreza.round(2).to_numpy()))
ok("Dashboard: mismo resultados.json", W["resultados"]["brecha_intra_departamento_pp"] == R["brecha_intra_departamento_pp"])

texto = (f"Verificación de datos · {len(filas)} comprobaciones · "
         f"{'todas OK' if not fallas else f'{fallas} FALLAS'}\n\n" + "\n".join(filas) + "\n")
(PROC / "verificacion.txt").write_text(texto, encoding="utf-8")
print(texto)
sys.exit(1 if fallas else 0)
