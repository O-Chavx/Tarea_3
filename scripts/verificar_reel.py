"""
Verificación del guion y del reel.

Guion:  cada cifra que dice la narración (en palabras) y la que aparece en pantalla corresponde a resultados.json.
Reel:   formato 1080 × 1920 H.264 + AAC, duración 45–75 s, 5–7 escenas, sonoridad, música bajo la voz,
        subtítulos (lo que Whisper oyó en el audio final) frente al guion, aviso de IA, fuente y créditos.

Uso:  python scripts/verificar_reel.py      → escribe reel/verificacion_reel.txt
"""
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
REEL = RAIZ / "reel"
R = json.loads((RAIZ / "datos" / "procesados" / "resultados.json").read_text(encoding="utf-8"))
G = json.loads((REEL / "guion.json").read_text(encoding="utf-8"))
E = G["escenas"]
filas, fallas = [], 0


def ok(nombre, cond, detalle=""):
    global fallas
    fallas += not cond
    filas.append(f"{'OK   ' if cond else 'FALLA'}  {nombre}{'  · ' + detalle if detalle else ''}")


def ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


def norm(s):
    s = unicodedata.normalize("NFD", s.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^\w\s]", " ", s).split()


def wer(ref, hyp):
    r, h = norm(ref), norm(hyp)
    dp = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, dp[0] = dp[0], i
        for j in range(1, len(h) + 1):
            prev, dp[j] = dp[j], min(dp[j] + 1, dp[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
    return dp[-1] / max(1, len(r))


# ── Guion frente a los datos ──
b = {x["banda_distancia"]: x["pobreza_media"] for x in R["bandas"]}
cifras = [
    (0, "mil ochocientos setenta y tres", R["n_distritos"] == 1873),
    (0, "ciento cuarenta y dos unidades", R["n_minas"] == 142),
    (1, "veintiséis punto ocho", round(R["pobreza_media_minero"], 1) == 26.8),
    (1, "treinta y cuatro punto seis", round(R["pobreza_media_no_minero"], 1) == 34.6),
    (2, "siete punto ocho", round(R["brecha_bruta_pp"], 1) == -7.8),
    (2, "cuatro punto cuatro", round(R["brecha_intra_departamento_pp"], 1) == -4.4),
    (3, "treinta y uno por ciento a menos de veinticinco", round(b["< 25 km"]) == 31),
    (3, "casi treinta y siete por ciento a más de cien", 36.5 <= b["> 100 km"] < 37),
    (3, "la pobreza sube cuando nos alejamos", b["Distrito minero"] < b["< 25 km"] < b["25–50 km"] < b["50–100 km"] < b["> 100 km"]),
    (4, "Veinticuatro distritos mineros", R["mineros_pobreza_alta"] == 24),
    (4, "sus ocho distritos mineros", R["cajamarca"]["mineros"] == 8),
    (4, "casi cincuenta y tres por ciento", 52.5 <= R["cajamarca"]["pob_mineros"] < 53),
]
for i, frase, cond in cifras:
    ok(f"Guion escena {i + 1}: «{frase}»", frase in E[i]["frase"] and cond)
pantalla = {0: "1,873", 1: "26.8 % vs 34.6 %", 2: "−4.4 pp", 3: "31 % → 37 %", 4: "24"}
for i, c in pantalla.items():
    ok(f"Cifra en pantalla escena {i + 1} = {c}", E[i]["cifra"] == c)
ok("Cierre aclara que es asociación, no causa", "asociación, no una prueba de causa" in E[-1]["frase"])

# ── Video ──
mp4 = REEL / "reel.mp4"
info = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(mp4)], capture_output=True, text=True).stderr
dur = re.search(r"Duration: (\d+):(\d+):([\d.]+)", info)
dur = int(dur[1]) * 3600 + int(dur[2]) * 60 + float(dur[3])
ok("Duración entre 45 y 75 s", 45 <= dur <= 75, f"{dur:.1f} s")
ok("5 a 7 escenas", 5 <= len(E) <= 7, f"{len(E)} escenas")
ok("Video vertical 1080 × 1920 en H.264", "h264" in info and "1080x1920" in info)
ok("Audio AAC", "Audio: aac" in info)
ok("Tamaño < 50 MB (sube a LinkedIn y GitHub)", mp4.stat().st_size < 50e6, f"{mp4.stat().st_size / 1e6:.1f} MB")
ln = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(mp4), "-af", "loudnorm=print_format=json", "-f", "null", "-"],
                    capture_output=True, text=True).stderr
lufs = float(json.loads(ln[ln.rindex("{"):ln.rindex("}") + 1])["input_i"])
ok("Sonoridad entre −20 y −12 LUFS", -20 <= lufs <= -12, f"{lufs:.1f} LUFS")
# Música bajo la voz: se mide en las pausas entre escenas (solo música) frente al promedio con voz
srt_txt = (REEL / "subtitulos.srt").read_text(encoding="utf-8")
def seg(t):
    h, m_, s_ = t.replace(",", ".").split(":")
    return int(h) * 3600 + int(m_) * 60 + float(s_)
tiempos = [tuple(map(seg, l.split(" --> "))) for l in srt_txt.splitlines() if " --> " in l]
pausas = [(a[1], b[0]) for a, b in zip(tiempos, tiempos[1:]) if b[0] - a[1] >= 0.3 and 3 < a[1] < dur - 4]
def vol(ss, t):
    o = subprocess.run([ffmpeg(), "-hide_banner", "-ss", f"{ss:.2f}", "-t", f"{t:.2f}", "-i", str(mp4), "-af", "volumedetect",
                        "-vn", "-f", "null", "-"], capture_output=True, text=True).stderr
    return float(re.search(r"mean_volume: ([-\d.]+)", o)[1])
musica = sum(vol(a + 0.05, b - a - 0.1) for a, b in pausas) / max(1, len(pausas))
total = vol(0, dur)
ok("Música al menos 12 dB por debajo de la voz", total - musica >= 12,
   f"mezcla {total:.1f} dB, música sola en {len(pausas)} pausas {musica:.1f} dB")

# ── Subtítulos (lo que Whisper oyó en el audio final) frente al guion ──
srt = srt_txt
oido = " ".join(l for l in srt.splitlines() if l and not l[0].isdigit())
w = wer(" ".join(e["frase"] for e in E), oido)
ok("Subtítulos frente al guion: error de palabras < 5 %", w < 0.05, f"WER {w:.3f}")
ok("WER por escena ≤ 0.25 (control de Whisper al narrar)", all(e.get("wer", 0) <= 0.25 for e in E),
   ", ".join(f"{e.get('wer', 0):.2f}" for e in E))
# ── Transparencia (lo dibuja hacer_reel_mineria.py en todos los cuadros) ──
src = (REEL / "hacer_reel_mineria.py").read_text(encoding="utf-8")
ok("Aviso «VOZ GENERADA CON IA» en pantalla", "VOZ GENERADA CON IA" in src)
ok("Fuente de datos en pantalla", "Datos: {guion['fuente']}" in src and "INEI" in G["fuente"])
ok("Créditos de música y gráficos", "Música original (CC0)" in src and (REEL / "recursos" / "CREDITOS.md").exists())

texto = f"Verificación del guion y del reel · {len(filas)} comprobaciones · {'todas OK' if not fallas else f'{fallas} FALLAS'}\n\n" + "\n".join(filas) + "\n"
(REEL / "verificacion_reel.txt").write_text(texto, encoding="utf-8")
print(texto)
sys.exit(1 if fallas else 0)
