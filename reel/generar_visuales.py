"""
Genera las imágenes de cada escena del reel (900 × 780 px, tema oscuro) a partir de los datos procesados.

Uso:  python reel/generar_visuales.py
Requiere haber corrido antes scripts/procesar_datos.py y scripts/analizar_datos.py.
La escena 6 usa una captura del dashboard (reel/recursos/escena6_dashboard.png), que se toma aparte.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager
from matplotlib.collections import PolyCollection
from matplotlib.colors import BoundaryNorm, ListedColormap

RAIZ = Path(__file__).resolve().parents[1]
PROC = RAIZ / "datos" / "procesados"
OUT = RAIZ / "reel" / "recursos"
OUT.mkdir(parents=True, exist_ok=True)

FONDO, PANEL, TEXTO, SUAVE, LINEA = "#0e141a", "#151d25", "#e7edf2", "#a3afba", "#26313b"
MINERO, NOMINERO = "#f07a48", "#4b95ea"
RAMPA = ["#162333", "#173a63", "#1c5cab", "#2a78d6", "#4b95ea", "#7cb2f0", "#acd0f7", "#dbeafc"]
CORTES = [0, 10, 20, 30, 40, 50, 60, 70, 100]

for f in ["Inter", "Inter Display"]:
    if any(f == x.name for x in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = f
        break
plt.rcParams.update({"text.color": TEXTO, "axes.labelcolor": SUAVE, "xtick.color": SUAVE, "ytick.color": SUAVE,
                     "axes.edgecolor": LINEA, "font.size": 15, "axes.facecolor": PANEL, "figure.facecolor": PANEL,
                     "savefig.facecolor": PANEL})

d = pd.read_csv(PROC / "distritos.csv", dtype={"ubigeo": str})
m = pd.read_csv(PROC / "minas.csv", dtype={"ubigeo": str})
R = json.loads((PROC / "resultados.json").read_text(encoding="utf-8"))
geo = json.loads((PROC / "distritos_mapa.geojson").read_text(encoding="utf-8"))
pob = d.set_index("ubigeo")["pobreza"]
dep_de = d.set_index("ubigeo")["departamento"]
mineros = set(d.loc[d.minero, "ubigeo"])


def poligonos(filtro=lambda u: True):
    polys, vals, ubs = [], [], []
    for f in geo["features"]:
        u = f["properties"]["u"]
        if not filtro(u):
            continue
        g = f["geometry"]
        partes = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        for p in partes:
            polys.append(np.asarray(p[0]))
            vals.append(pob[u])
            ubs.append(u)
    return polys, np.asarray(vals), ubs


cmap, norm = ListedColormap(RAMPA), BoundaryNorm(CORTES, len(RAMPA))


def figura():
    fig = plt.figure(figsize=(9, 7.8), dpi=100)
    return fig


def guardar(fig, nombre):
    fig.savefig(OUT / nombre, dpi=100)
    plt.close(fig)
    print("✓", nombre)


def leyenda_rampa(fig, x=0.06, y=0.05):
    ax = fig.add_axes([x, y, 0.4, 0.025])
    ax.imshow([np.arange(len(RAMPA))], cmap=cmap, aspect="auto")
    ax.set_yticks([])
    ax.set_xticks(np.arange(len(RAMPA) + 1) - 0.5, [f"{c}" for c in CORTES[:-1]] + ["%"], fontsize=11)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    fig.text(x, y + 0.04, "Pobreza monetaria 2018", fontsize=12, color=SUAVE)


# ── Escena 1: mapa nacional ──
fig = figura()
ax = fig.add_axes([0, 0, 1, 1])
polys, vals, _ = poligonos()
ax.add_collection(PolyCollection(polys, array=vals, cmap=cmap, norm=norm, edgecolors=PANEL, linewidths=0.15))
ax.scatter(m.lon, m.lat, marker="^", s=46, c=MINERO, edgecolors=PANEL, linewidths=0.8, zorder=3)
ax.set_xlim(-81.6, -68.4); ax.set_ylim(-18.6, 0.4); ax.set_aspect("equal"); ax.axis("off")
leyenda_rampa(fig)
fig.text(0.06, 0.15, "▲", color=MINERO, fontsize=16)
fig.text(0.1, 0.15, "Unidad minera (MINEM)", color=SUAVE, fontsize=13)
fig.text(0.94, 0.93, "1,873 distritos\n142 unidades mineras", ha="right", va="top", fontsize=17, color=TEXTO, weight="bold")
guardar(fig, "escena1_mapa.png")

# ── Escena 2: distribución con / sin minas ──
fig = figura()
ax = fig.add_axes([0.2, 0.14, 0.75, 0.72])
rng = np.random.default_rng(3)
ax.axvspan(40, 85, color=LINEA, alpha=0.6, lw=0)
ax.text(41, 1.62, "40 % o más", color=SUAVE, fontsize=12)
for i, (lab, g, col) in enumerate([("Con minas", d[d.minero], MINERO), ("Sin minas", d[~d.minero], NOMINERO)]):
    y = 1 - i
    ax.scatter(g.pobreza, y + rng.uniform(-0.3, 0.3, len(g)), s=16 if i else 40, c=col, alpha=0.45 if i else 0.85, lw=0)
    med = g.pobreza.mean()
    ax.plot([med, med], [y - 0.4, y + 0.4], color=TEXTO, lw=3)
    ax.text(med + 1, y + 0.45, f"promedio {med:.1f} %", fontsize=15, color=TEXTO, weight="bold")
    ax.text(-2, y, f"{lab}\n", ha="right", va="center", fontsize=17, color=TEXTO, weight="bold")
    ax.text(-2, y - 0.12, f"n = {len(g):,}", ha="right", va="center", fontsize=12, color=SUAVE)
ax.set_xlim(0, 85); ax.set_ylim(-0.6, 1.75); ax.set_yticks([])
ax.set_xticks(range(0, 90, 20), [f"{x} %" for x in range(0, 90, 20)])
for s in ["top", "right", "left"]:
    ax.spines[s].set_visible(False)
ax.tick_params(length=0)
fig.text(0.05, 0.92, "Cada punto es un distrito", fontsize=18, weight="bold")
fig.text(0.05, 0.03, "Pobreza monetaria 2018 · INEI", fontsize=12, color=SUAVE)
guardar(fig, "escena2_distribucion.png")

# ── Escena 3: brecha dentro de cada departamento ──
intra = pd.read_csv(PROC / "brecha_intra_departamento.csv").sort_values("brecha_pp", ascending=False)
fig = figura()
ax = fig.add_axes([0.24, 0.08, 0.66, 0.78])
y = np.arange(len(intra))
ax.hlines(y, intra.pob_mineros, intra.pob_no_mineros, color=SUAVE, lw=2, alpha=0.7)
ax.scatter(intra.pob_no_mineros, y, s=70, c=NOMINERO, edgecolors=PANEL, lw=1.5, zorder=3, label="Sin minas")
ax.scatter(intra.pob_mineros, y, s=70, c=MINERO, edgecolors=PANEL, lw=1.5, zorder=3, label="Con minas")
for yi, (_, r) in zip(y, intra.iterrows()):
    ax.text(max(r.pob_mineros, r.pob_no_mineros) + 1.5, yi, f"{r.brecha_pp:+.1f}".replace("-", "−"), va="center", fontsize=11, color=SUAVE)
ax.set_yticks(y, [x.title() for x in intra.departamento], fontsize=12)
ax.set_xlim(0, 65); ax.set_xticks(range(0, 70, 20), [f"{x} %" for x in range(0, 70, 20)])
ax.tick_params(length=0)
for s in ["top", "right", "left"]:
    ax.spines[s].set_visible(False)
ax.grid(axis="x", color=LINEA, lw=0.8); ax.set_axisbelow(True)
ax.legend(loc="lower left", bbox_to_anchor=(0.0, 1.0), ncol=2, frameon=False, fontsize=13, labelcolor=TEXTO)
fig.text(0.05, 0.94, f"Brecha ponderada: {R['brecha_intra_departamento_pp']:+.1f} pp".replace("-", "−")
         + f"  ·  {R['deps_mineros_menos_pobres']} de {R['deps_comparados']} departamentos", fontsize=17, weight="bold")
guardar(fig, "escena3_departamentos.png")

# ── Escena 4: bandas de distancia ──
b = pd.DataFrame(R["bandas"])
fig = figura()
ax = fig.add_axes([0.27, 0.14, 0.62, 0.72])
yy = np.arange(len(b))[::-1]
cols = [MINERO] + [NOMINERO] * (len(b) - 1)
ax.barh(yy, b.pobreza_media, color=cols, height=0.62)
for yi, v, n in zip(yy, b.pobreza_media, b.distritos):
    ax.text(v + 0.8, yi, f"{v:.1f} %", va="center", fontsize=18, weight="bold", color=TEXTO)
    ax.text(v + 0.8, yi - 0.3, f"{n} distritos", va="center", fontsize=11, color=SUAVE)
ax.set_yticks(yy, b.banda_distancia, fontsize=16)
ax.set_xlim(0, 45); ax.set_xticks([0, 10, 20, 30, 40], ["0", "10 %", "20 %", "30 %", "40 %"])
ax.tick_params(length=0)
for s in ["top", "right", "left"]:
    ax.spines[s].set_visible(False)
ax.grid(axis="x", color=LINEA, lw=0.8); ax.set_axisbelow(True)
fig.text(0.05, 0.92, "Distancia del distrito a la mina más cercana", fontsize=18, weight="bold")
fig.text(0.05, 0.03, "Promedio simple de pobreza por distrito · INEI 2018, MINEM", fontsize=12, color=SUAVE)
guardar(fig, "escena4_distancia.png")

# ── Escena 5: Cajamarca ──
fig = figura()
ax = fig.add_axes([0.02, 0.1, 0.6, 0.7])
es_caj = lambda u: dep_de.get(u) == "CAJAMARCA"
polys, vals, ubs = poligonos(es_caj)
ax.add_collection(PolyCollection(polys, array=vals, cmap=cmap, norm=norm, edgecolors=PANEL, linewidths=0.4))
pm = [p for p, u in zip(polys, ubs) if u in mineros]
ax.add_collection(PolyCollection(pm, facecolors="none", edgecolors=MINERO, linewidths=2.6))
mc = m[m.departamento == "CAJAMARCA"]
ax.scatter(mc.lon, mc.lat, marker="^", s=90, c=MINERO, edgecolors=PANEL, lw=1, zorder=3)
dc = d[(d.departamento == "CAJAMARCA") & d.minero].sort_values("pobreza", ascending=False)
fig.text(0.66, 0.8, "Distritos mineros", fontsize=14, color=SUAVE)
for k, (_, r) in enumerate(dc.iterrows()):
    fig.text(0.66, 0.74 - k * 0.055, f"{r.distrito.title()}", fontsize=15, color=TEXTO)
    fig.text(0.95, 0.74 - k * 0.055, f"{r.pobreza:.1f} %", fontsize=15, color=TEXTO, weight="bold", ha="right")
allp = np.vstack(polys)
ax.set_xlim(allp[:, 0].min() - 0.05, allp[:, 0].max() + 0.05); ax.set_ylim(allp[:, 1].min() - 0.05, allp[:, 1].max() + 0.05)
ax.set_aspect("equal"); ax.axis("off")
leyenda_rampa(fig, y=0.04)
fig.text(0.05, 0.93, f"Cajamarca: sus distritos mineros (borde naranja)\npromedian {R['cajamarca']['pob_mineros']:.1f} % de pobreza", fontsize=17, weight="bold", va="top")
guardar(fig, "escena5_cajamarca.png")
