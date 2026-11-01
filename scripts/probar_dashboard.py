"""
Prueba automática del dashboard en un navegador sin interfaz (Playwright + Chromium).

Cambia los filtros como lo haría una persona y compara lo que muestra la página con lo que se
calcula en pandas a partir de datos/procesados/. Falla ante cualquier error de JavaScript.

Uso:
  pip install playwright && playwright install chromium
  python scripts/probar_dashboard.py                 # prueba web/index.html (D3 desde el CDN)
  python scripts/probar_dashboard.py --d3 ruta/d3.min.js   # sin internet: D3 local
Escribe web/prueba_dashboard.txt.
"""
import argparse
import re
import sys
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument("--d3", help="ruta a d3.min.js v7.9.0 para correr sin internet")
a = p.parse_args()

d = pd.read_csv(RAIZ / "datos" / "procesados" / "distritos.csv", dtype={"ubigeo": str})
m = pd.read_csv(RAIZ / "datos" / "procesados" / "minas.csv", dtype={"ubigeo": str})
filas, fallas, errores = [], 0, []


def ok(nombre, cond, detalle=""):
    global fallas
    fallas += not cond
    filas.append(f"{'OK   ' if cond else 'FALLA'}  {nombre}{'  · ' + detalle if detalle else ''}")


def esperado(dep, met, mineral):
    ms = m.copy()
    if met != "TODOS":
        ms = ms[ms.metodo == met]
    if mineral == "nometal":
        ms = ms[ms.tipo == "No metálica"]
    elif mineral != "TODOS":
        ms = ms[ms[mineral]]
    mineros = set(ms.ubigeo)
    sc = d if dep == "TODOS" else d[d.departamento == dep]
    msc = ms if dep == "TODOS" else ms[ms.departamento == dep]
    es = sc.ubigeo.isin(mineros)
    return {"n": len(sc), "nmin": int(es.sum()), "unid": len(msc), "unid_pais": len(ms),
            "pm": sc[es].pobreza.mean() if es.any() else None, "pn": sc[~es].pobreza.mean() if (~es).any() else None}


def num(t):
    return float(re.sub(r"[^\d.\-−]", "", t.split()[0]).replace("−", "-").replace(",", ""))


with sync_playwright() as pw:
    nav = pw.chromium.launch()
    pg = nav.new_page(viewport={"width": 1300, "height": 900})
    pg.on("pageerror", lambda e: errores.append(str(e)))
    pg.on("console", lambda c: errores.append(c.text) if c.type == "error" else None)
    if a.d3:
        pg.route("**/cdnjs.cloudflare.com/**", lambda r: r.fulfill(path=a.d3, content_type="application/javascript"))
    pg.route("**/fonts.googleapis.com/**", lambda r: r.fulfill(body="", content_type="text/css"))
    pg.goto((RAIZ / "web" / "index.html").as_uri())
    pg.wait_for_timeout(1500)

    ok("Carga: 6 KPI", pg.locator(".kpi").count() == 6)
    ok("Mapa: 1,823 polígonos de distritos", pg.locator("#map g >> nth=0").locator("path").count() >= 1823)
    ok("Mapa: 142 unidades mineras", pg.locator("#map g g:nth-child(2) path").count() == 142)
    ok("Cuatro gráficos dibujados", all(pg.locator(f"#{c} *").count() > 5 for c in ["c-bandas", "c-intra", "c-strip", "c-mineral"]))
    ok("Tres hallazgos visibles", pg.locator(".finding").count() == 3)

    combos = [("TODOS", "TODOS", "TODOS"), ("CAJAMARCA", "TODOS", "TODOS"), ("JUNÍN", "TODOS", "TODOS"),
              ("TODOS", "TODOS", "oro"), ("TODOS", "TODOS", "cobre"), ("TODOS", "Minería subterránea", "TODOS"),
              ("AREQUIPA", "Minería superficial", "TODOS"), ("PUNO", "TODOS", "nometal"), ("LIMA", "TODOS", "plata"),
              ("CUSCO", "TODOS", "TODOS"), ("LORETO", "TODOS", "TODOS")]
    for dep, met, mineral in combos:
        pg.select_option("#f-dep", dep); pg.select_option("#f-met", met); pg.select_option("#f-min", mineral)
        pg.wait_for_timeout(250)
        e = esperado(dep, met, mineral)
        k = pg.locator(".kpi .v").all_inner_texts()
        sub0 = pg.locator(".kpi .s").first.inner_text()
        etiqueta = f"{dep.title()} · {met.lower()} · {mineral}"
        ok(f"{etiqueta}: distritos analizados = {e['n']}", num(k[0]) == e["n"] and sub0.startswith(f"{e['nmin']:,}"),
           f"pantalla {k[0]} / {sub0.split()[0]} mineros")
        ok(f"{etiqueta}: unidades mineras = {e['unid']}", num(k[1]) == e["unid"])
        if e["pm"] is not None and e["pn"] is not None:
            vals = [float(x) for x in re.findall(r"\d+\.\d", k[2])]
            ok(f"{etiqueta}: pobreza media {e['pm']:.1f} vs {e['pn']:.1f} %",
               abs(vals[0] - e["pm"]) < 0.051 and abs(vals[1] - e["pn"]) < 0.051, k[2].replace("\n", " "))
        else:
            ok(f"{etiqueta}: sin distritos mineros → KPI sin cifra", k[2].startswith("—"))
        ok(f"{etiqueta}: triángulos del mapa = {e['unid_pais']}", pg.locator("#map g g:nth-child(2) path").count() == e["unid_pais"])

    pg.click("#f-reset"); pg.wait_for_timeout(300)
    ok("Restablecer vuelve a todo el Perú", pg.locator("#f-dep").input_value() == "TODOS" and num(pg.locator(".kpi .v").first.inner_text()) == 1873)
    pg.fill("#f-q", "yauli"); pg.wait_for_timeout(400)
    filas_tbl = pg.locator("#tbl tbody tr").all_inner_texts()
    ok("Buscador: «yauli» encuentra los distritos y la provincia Yauli", len(filas_tbl) > 0 and all("Yauli" in f for f in filas_tbl), f"{len(filas_tbl)} filas")
    pg.fill("#f-q", ""); pg.wait_for_timeout(300)
    pg.locator("#tbl tbody tr").first.click(); pg.wait_for_timeout(900)
    ok("Clic en la tabla abre la ficha del distrito", "UBIGEO" in pg.locator("#ficha").inner_text())
    pg.click(".seg button[data-var=dist]"); pg.wait_for_timeout(300)
    ok("Mapa cambia a distancia a la mina", "Distancia" in pg.locator("#map-legend").inner_text())
    pg.click(".seg button[data-var=pobreza]")
    pg.evaluate("document.documentElement.setAttribute('data-theme','dark')"); pg.wait_for_timeout(300)
    bg = pg.evaluate("getComputedStyle(document.body).backgroundColor")
    ok("Modo oscuro cambia el fondo", bg != "rgb(243, 245, 247)", bg)
    cel = nav.new_page(viewport={"width": 390, "height": 844})
    if a.d3:
        cel.route("**/cdnjs.cloudflare.com/**", lambda r: r.fulfill(path=a.d3, content_type="application/javascript"))
    cel.goto((RAIZ / "web" / "index.html").as_uri()); cel.wait_for_timeout(1500)
    ancho = cel.evaluate("[document.documentElement.scrollWidth, innerWidth]")
    ok("Celular (390 px): sin desplazamiento horizontal", ancho[0] <= ancho[1], f"{ancho}")
    nav.close()

ok("Sin errores de JavaScript", not errores, "; ".join(errores[:3]))
texto = f"Prueba del dashboard · {len(filas)} comprobaciones · {'todas OK' if not fallas else f'{fallas} FALLAS'}\n\n" + "\n".join(filas) + "\n"
(RAIZ / "web" / "prueba_dashboard.txt").write_text(texto, encoding="utf-8")
print(texto)
sys.exit(1 if fallas else 0)
