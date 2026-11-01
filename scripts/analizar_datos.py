"""
Paso 3 · Indicadores y hallazgos.

Pregunta: ¿Los distritos que albergan unidades mineras tienen menos pobreza monetaria
que el resto del Perú, y esa diferencia se mantiene al comparar dentro del mismo departamento?

Entradas: datos/procesados/{distritos,minas,departamentos}.csv
Salidas:  datos/procesados/resultados.json   (todas las cifras que usan el dashboard, el README y el reel)
          web/data/datos.js                  (datos embebidos para el dashboard)
          reel/recursos/graficos/*.png        (gráficos verticales para el reel)
Uso:  python scripts/analizar_datos.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

RAIZ = Path(__file__).resolve().parents[1]
PROC = RAIZ / "datos" / "procesados"
WEB = RAIZ / "web" / "data"
WEB.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(2026)

d = pd.read_csv(PROC / "distritos.csv", dtype={"ubigeo": str})
m = pd.read_csv(PROC / "minas.csv", dtype={"ubigeo": str})
dep = pd.read_csv(PROC / "departamentos.csv")

R: dict = {}

# ── KPIs generales ──
R["n_distritos"] = int(len(d))
R["n_minas"] = int(len(m))
R["n_distritos_mineros"] = int(d.minero.sum())
R["n_departamentos_con_minas"] = int(d.loc[d.minero, "departamento"].nunique())
R["pobreza_media_nacional_distrital"] = round(d.pobreza.mean(), 2)
R["pobreza_media_minero"] = round(d.loc[d.minero, "pobreza"].mean(), 2)
R["pobreza_media_no_minero"] = round(d.loc[~d.minero, "pobreza"].mean(), 2)
R["pobreza_mediana_minero"] = round(d.loc[d.minero, "pobreza"].median(), 2)
R["pobreza_mediana_no_minero"] = round(d.loc[~d.minero, "pobreza"].median(), 2)
R["brecha_bruta_pp"] = round(R["pobreza_media_minero"] - R["pobreza_media_no_minero"], 2)
R["pct_pobreza_alta_minero"] = round(100 * d.loc[d.minero, "pobreza_alta"].mean(), 1)
R["pct_pobreza_alta_no_minero"] = round(100 * d.loc[~d.minero, "pobreza_alta"].mean(), 1)
R["n_distritos_pobreza_alta"] = int(d.pobreza_alta.sum())
t = stats.mannwhitneyu(d.loc[d.minero, "pobreza"], d.loc[~d.minero, "pobreza"])
R["mannwhitney_p"] = float(f"{t.pvalue:.3g}")

# ── Hallazgo 2: comparación dentro del mismo departamento ──
# Para cada departamento con minas: media(mineros) − media(no mineros). Promedio ponderado por n.º de distritos mineros.
filas = []
for dp, g in d.groupby("departamento"):
    if g.minero.sum() == 0 or (~g.minero).sum() == 0:
        continue
    filas.append({"departamento": dp, "n_mineros": int(g.minero.sum()), "n_no_mineros": int((~g.minero).sum()),
                  "pob_mineros": g.loc[g.minero, "pobreza"].mean(), "pob_no_mineros": g.loc[~g.minero, "pobreza"].mean()})
intra = pd.DataFrame(filas)
intra["brecha_pp"] = intra.pob_mineros - intra.pob_no_mineros
w = intra.n_mineros
R["brecha_intra_departamento_pp"] = round(float(np.average(intra.brecha_pp, weights=w)), 2)
R["deps_mineros_menos_pobres"] = int((intra.brecha_pp < 0).sum())
R["deps_comparados"] = int(len(intra))


# Prueba de permutación: se baraja la etiqueta "minero" dentro de cada departamento (10,000 veces)
def brecha_intra(df):
    out, ws = [], []
    for _, g in df.groupby("departamento"):
        k = g.minero.sum()
        if k == 0 or k == len(g):
            continue
        out.append(g.loc[g.minero, "pobreza"].mean() - g.loc[~g.minero, "pobreza"].mean())
        ws.append(k)
    return np.average(out, weights=ws)


obs = brecha_intra(d)
grupos = [(g.pobreza.to_numpy(), int(g.minero.sum())) for _, g in d.groupby("departamento")
          if 0 < g.minero.sum() < len(g)]
sims = np.empty(10_000)
for i in range(len(sims)):
    vals, ws = [], []
    for x, k in grupos:
        idx = rng.permutation(len(x))
        vals.append(x[idx[:k]].mean() - x[idx[k:]].mean())
        ws.append(k)
    sims[i] = np.average(vals, weights=ws)
n_ext = int((np.abs(sims) >= abs(obs)).sum())
R["permutacion_p_bilateral"] = f"< {1/len(sims):.4f}" if n_ext == 0 else round(n_ext / len(sims), 4)

# ── Hallazgo 3: cercanía a una mina (bandas de distancia desde el centroide del distrito) ──
orden = ["Distrito minero", "< 25 km", "25–50 km", "50–100 km", "> 100 km"]
band = (d.dropna(subset=["banda_distancia"]).groupby("banda_distancia")
        .agg(distritos=("ubigeo", "size"), pobreza_media=("pobreza", "mean"),
             pct_pobreza_alta=("pobreza_alta", "mean")).reindex(orden).reset_index())
band["pct_pobreza_alta"] *= 100
R["bandas"] = band.round(2).to_dict(orient="records")

# ── Por tipo de minería / mineral (a nivel de unidad minera, pobreza de su distrito) ──
R["por_metodo"] = (m.groupby("metodo").agg(unidades=("unidad", "size"), pobreza_media=("pobreza", "mean"))
                   .sort_values("unidades", ascending=False).round(2).reset_index().to_dict(orient="records"))
mins = {"Oro (Au)": m.oro, "Cobre (Cu)": m.cobre, "Plata (Ag)": m.plata, "Zinc o plomo": m.zinc_plomo,
        "No metálica": m.tipo.eq("No metálica")}
R["por_mineral"] = [{"mineral": k, "unidades": int(v.sum()), "pobreza_media": round(m.loc[v, "pobreza"].mean(), 2)}
                    for k, v in mins.items()]

# Departamentos: ranking
dep = dep.merge(intra[["departamento", "brecha_pp", "pob_mineros", "pob_no_mineros"]], on="departamento", how="left")
R["departamentos"] = dep.round(2).to_dict(orient="records")
top_dep_minas = dep.sort_values("unidades_mineras", ascending=False).iloc[0]
R["dep_mas_minas"] = {"departamento": top_dep_minas.departamento, "unidades": int(top_dep_minas.unidades_mineras)}
R["dep_mayor_pobreza_media"] = dep.sort_values("pobreza_media", ascending=False).iloc[0][["departamento", "pobreza_media"]].to_dict()

# Distritos mineros extremos
dm = d[d.minero].sort_values("pobreza")
R["mineros_mas_pobres"] = dm.tail(5)[["departamento", "distrito", "pobreza", "n_minas", "minerales"]].iloc[::-1].round(1).to_dict(orient="records")
R["mineros_menos_pobres"] = dm.head(5)[["departamento", "distrito", "pobreza", "n_minas", "minerales"]].round(1).to_dict(orient="records")
R["mineros_pobreza_alta"] = int(dm.pobreza_alta.sum())

# Cajamarca: el caso de contraste
caj = d[d.departamento == "CAJAMARCA"]
R["cajamarca"] = {"distritos": int(len(caj)), "pobreza_media": round(caj.pobreza.mean(), 1),
                  "mineros": int(caj.minero.sum()), "pob_mineros": round(caj.loc[caj.minero, "pobreza"].mean(), 1),
                  "en_top20_pobres": int((d.nlargest(20, "pobreza").departamento == "CAJAMARCA").sum())}

# Calidad de datos
R["minas_fuera_de_su_distrito"] = int((~m.dentro_de_su_distrito).sum())
R["distritos_sin_poligono"] = int((~d.con_mapa).sum())

# Correlación n.º de unidades vs pobreza entre distritos mineros
rho = stats.spearmanr(dm.n_minas, dm.pobreza)
R["spearman_nminas_pobreza"] = {"rho": round(float(rho.statistic), 3), "p": float(f"{rho.pvalue:.3g}")}

(PROC / "resultados.json").write_text(json.dumps(R, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
intra.round(3).to_csv(PROC / "brecha_intra_departamento.csv", index=False)

# ── Datos para la web ──
geo = json.loads((PROC / "distritos_mapa.geojson").read_text(encoding="utf-8"))
dist_cols = ["ubigeo", "departamento", "provincia", "distrito", "pobreza", "minero", "n_minas", "minerales",
             "unidades", "dist_mina_km", "banda_distancia", "con_mapa", "lon_c", "lat_c"]
dw = d[dist_cols].copy()
dw["pobreza"] = dw.pobreza.round(2)
dw["dist_mina_km"] = dw.dist_mina_km.round(1)
dw["lon_c"] = dw.lon_c.round(4)
dw["lat_c"] = dw.lat_c.round(4)
mw = m[["ubigeo", "departamento", "distrito", "unidad", "titular", "metodo", "tipo", "mineral_principal",
        "productos", "oro", "cobre", "plata", "zinc_plomo", "lon", "lat", "pobreza"]].round(4)
payload = {"distritos": json.loads(dw.to_json(orient="records", force_ascii=False)),
           "minas": json.loads(mw.to_json(orient="records", force_ascii=False)),
           "resultados": R, "geo": geo}
(WEB / "datos.js").write_text("window.DATOS = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":"),
                                                              default=str) + ";", encoding="utf-8")

print(json.dumps({k: v for k, v in R.items() if not isinstance(v, list)}, ensure_ascii=False, indent=1, default=str))
print(band.round(1).to_string())
print(pd.DataFrame(R["por_metodo"]).to_string())
print(pd.DataFrame(R["por_mineral"]).to_string())
print(intra.round(1).sort_values("brecha_pp").to_string())
