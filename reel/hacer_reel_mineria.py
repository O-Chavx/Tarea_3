"""
Reel vertical 1080 × 1920 de «Minería y pobreza en el Perú».

Extiende el flujo de la Sesión 15 (reel.py del curso, copiado sin cambios en esta carpeta):
  - Voz:        Qwen3-TTS (o VoxCPM2) clona TU voz a partir de 15–25 s de audio y narra guion.json
  - Subtítulos: Whisper con marcas de tiempo por palabra → subtitulos.srt
  - Video:      cada escena muestra su gráfico o mapa (con un acercamiento lento), la cifra clave,
                subtítulos, aviso «voz generada con IA», fuente y créditos
  - Música:     recursos/musica_fondo.wav (original, CC0) a −20 dB bajo la voz

Uso (en el entorno de la sesión 15, ver README):
  python hacer_reel_mineria.py --voz mi_voz.m4a
  python hacer_reel_mineria.py --voz mi_voz.m4a --motor voxcpm --velocidad 1.05
  python hacer_reel_mineria.py --vista-previa        # sin voz: revisa diseño y tiempos (solo música)

Salidas: reel.mp4, subtitulos.srt, narracion.wav, portada.png
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

AQUI = Path(__file__).resolve().parent
REC = AQUI / "recursos"
FNT = REC / "fuentes"

ANCHO, ALTO, FPS = 1080, 1920, 30
M = 72                                   # margen lateral
FONDO, PANEL, TEXTO, SUAVE, ACENTO, CAJA = "#0e141a", "#151d25", "#e7edf2", "#a3afba", "#f07a48", "#1d2833"
AUTOR = "Oscar Andres Chavez Inocente"
CREDITOS = "Música original (CC0) · Gráficos propios con Python"
VOL_MUSICA = 0.10                        # ≈ −20 dB respecto de la voz
PALABRAS_POR_SEG = 2.6                   # solo para --vista-previa
PAUSA, INICIO, FINAL = 0.35, 0.3, 1.2


def ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


def fuente(nombre, tam):
    return ImageFont.truetype(str(FNT / f"{nombre}.otf"), tam)


def envolver(d, texto, f, ancho):
    lineas, actual = [], ""
    for p in texto.split():
        prueba = f"{actual} {p}".strip()
        if d.textlength(prueba, font=f) <= ancho:
            actual = prueba
        else:
            lineas.append(actual)
            actual = p
    return lineas + [actual]


# ───────────────────────── Narración ─────────────────────────
class Narr:
    def __init__(self, audio, sr, escenas, palabras):
        self.audio, self.sr, self.escenas, self.palabras = audio, sr, escenas, palabras

    @property
    def duracion(self):
        return len(self.audio) / self.sr


def narracion_simulada(guion, sr=24000):
    """Sin voz: estima la duración de cada escena por número de palabras y reparte los subtítulos."""
    escenas, palabras, t = [], [], INICIO
    for e in guion["escenas"]:
        ws = e["frase"].split()
        dur = len(ws) / PALABRAS_POR_SEG
        escenas.append((t, t + dur))
        paso = dur / len(ws)
        palabras += [(t + i * paso, t + (i + 1) * paso, w) for i, w in enumerate(ws)]
        t += dur + PAUSA
    t += FINAL
    return Narr(np.zeros(int(t * sr), np.float32), sr, escenas, palabras)


def narracion_con_voz(guion, a):
    import reel  # módulo de la sesión 15
    if a.motor == "voxcpm":
        voz = reel.VozExpresiva(a.voz, device=a.device)
    else:
        voz = reel.Voz(a.voz, modelo=a.tts, device=a.device)
    print("Referencia transcrita:", voz.texto_ref)
    n = reel.narrar(voz, guion, velocidad=a.velocidad)
    print("WER por escena:", ", ".join(f"{e['wer']:.2f}" for e in guion["escenas"]))
    reel.subtitulos(n, guion)
    reel.a_srt(n, AQUI / "subtitulos.srt")
    # se añade el silencio final más largo para el cierre
    audio = np.concatenate([n.audio, np.zeros(int((FINAL - reel.FINAL) * n.sr), np.float32)]) if FINAL > reel.FINAL else n.audio
    return Narr(audio, n.sr, n.escenas, n.palabras)


def bloques(palabras, max_palabras=4, max_letras=26):
    out, actual = [], []
    for p in palabras:
        actual.append(p)
        if len(actual) >= max_palabras or sum(len(x[2]) + 1 for x in actual) >= max_letras or p[2][-1] in ".,;:?!":
            out.append(actual)
            actual = []
    return out + ([actual] if actual else [])


def a_srt(palabras, ruta):
    def hms(t):
        return f"{int(t // 3600):02}:{int(t % 3600 // 60):02}:{int(t % 60):02},{int(t % 1 * 1000):03}"
    lineas = []
    for i, b in enumerate(bloques(palabras), 1):
        lineas += [str(i), f"{hms(b[0][0])} --> {hms(b[-1][1])}", " ".join(p[2] for p in b), ""]
    Path(ruta).write_text("\n".join(lineas), encoding="utf-8")


# ───────────────────────── Diseño ─────────────────────────
IMG_CAJA = (M, 700, ANCHO - M, 1460)     # x0, y0, x1, y1 del panel de imagen
SUB_Y = 1530


def base(guion):
    img = Image.new("RGB", (ANCHO, ALTO), FONDO)
    d = ImageDraw.Draw(img)
    d.text((M, 150), guion["titulo"].upper(), font=fuente("InterDisplay-ExtraBold", 40), fill=ACENTO)
    aviso, f = "VOZ GENERADA CON IA A PARTIR DE MI VOZ", fuente("Inter-SemiBold", 24)
    x1 = M + d.textlength(aviso, font=f) + 36
    d.rounded_rectangle((M, 212, x1, 256), radius=22, outline=SUAVE, width=2)
    d.text((M + 18, 234), aviso, font=f, fill=SUAVE, anchor="lm")
    pie = fuente("Inter-Regular", 26)
    y = 1715
    for linea in envolver(d, f"{AUTOR} · Datos: {guion['fuente']}", pie, ANCHO - 2 * M) + [CREDITOS]:
        d.text((M, y), linea, font=pie, fill=SUAVE)
        y += 36
    x0, y0, x1, y1 = IMG_CAJA
    d.rounded_rectangle((x0, y0, x1, y1), radius=24, fill=PANEL)
    return img


def capa_texto(e):
    capa = Image.new("RGBA", (ANCHO, 420), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    ancho, y = ANCHO - 2 * M, 0
    if e.get("cifra"):
        for tam in range(190, 70, -10):
            f = fuente("InterDisplay-ExtraBold", tam)
            if d.textlength(e["cifra"], font=f) <= ancho:
                break
        bb = d.textbbox((0, 0), e["cifra"], font=f, anchor="ls")
        y = -bb[1]
        d.text((M, y), e["cifra"], font=f, fill=TEXTO, anchor="ls")
        y += 26
        fe, color = fuente("Inter-SemiBold", 44), SUAVE
    else:
        fe, color = fuente("InterDisplay-Bold", 78), TEXTO
    for linea in envolver(d, e["etiqueta"], fe, ancho):
        y += int(fe.size * 1.1)
        d.text((M, y), linea, font=fe, fill=color, anchor="ls")
    return capa


def preparar_imagen(ruta):
    x0, y0, x1, y1 = IMG_CAJA
    w, h = x1 - x0 - 24, y1 - y0 - 24
    im = Image.open(AQUI / ruta).convert("RGB")
    s = min(w / im.width, h / im.height)
    return im.resize((int(im.width * s * 1.08), int(im.height * s * 1.08)), Image.LANCZOS), (w, h)


def cuadro(fondo, capas, imgs, n, t, bls, fsub):
    img = fondo.copy()
    i = max([k for k, (ini, _) in enumerate(n.escenas) if ini - PAUSA <= t] or [0])
    ini, fin = n.escenas[i]
    a = min(1.0, max(0.0, (t - ini + PAUSA) / 0.4))          # entrada suave
    prog = min(1.0, max(0.0, (t - ini) / max(0.1, fin - ini + PAUSA)))
    # imagen con acercamiento lento (de 1.0 a 1.08)
    grande, (w, h) = imgs[i]
    z = 1 / 1.08 + (1 - 1 / 1.08) * prog
    iw, ih = int(grande.width * z), int(grande.height * z)
    im = grande.resize((iw, ih), Image.BILINEAR)
    cx, cy = (iw - min(iw, w)) // 2, (ih - min(ih, h)) // 2
    im = im.crop((cx, cy, cx + min(iw, w), cy + min(ih, h)))
    x0, y0, x1, y1 = IMG_CAJA
    px, py = x0 + (x1 - x0 - im.width) // 2, y0 + (y1 - y0 - im.height) // 2
    if a < 1:
        img.paste(Image.blend(Image.new("RGB", im.size, PANEL), im, a), (px, py))
    else:
        img.paste(im, (px, py))
    capa = capas[i]
    if a < 1:
        capa = capa.copy()
        capa.putalpha(capa.getchannel("A").point(lambda v: int(v * a)))
    img.paste(capa, (0, 300 + int(30 * (1 - a))), capa)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((M, 100, ANCHO - M, 106), radius=3, fill=CAJA)
    d.rounded_rectangle((M, 100, M + (ANCHO - 2 * M) * min(1, t / n.duracion), 106), radius=3, fill=ACENTO)
    b = next((b for b in bls if b[0][0] - 0.1 <= t <= b[-1][1] + 0.25), None)
    if b:
        texto = " ".join(p[2] for p in b)
        w = d.textlength(texto, font=fsub)
        x, y = (ANCHO - w) / 2, SUB_Y
        d.rounded_rectangle((x - 30, y - 22, x + w + 30, y + fsub.size + 30), radius=26, fill=CAJA)
        for ini_p, fin_p, pal in b:
            d.text((x, y), pal, font=fsub, fill=ACENTO if ini_p <= t <= fin_p + 0.05 else TEXTO)
            x += d.textlength(pal + " ", font=fsub)
    return img


def video(guion, n, salida, preset="veryfast", con_voz=True):
    wav = AQUI / "narracion.wav"
    import wave
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(n.sr)
        w.writeframes((np.clip(n.audio, -1, 1) * 32767).astype("<i2").tobytes())
    fondo = base(guion)
    capas = [capa_texto(e) for e in guion["escenas"]]
    imgs = [preparar_imagen(e["imagen"]) for e in guion["escenas"]]
    bls = bloques(n.palabras)
    fsub = fuente("Inter-Bold", 54)
    D = n.duracion
    voz = "loudnorm=I=-16:TP=-1.5:LRA=11" if con_voz else "volume=0"   # loudnorm no admite silencio puro
    filtro = (f"[1:a]aformat=channel_layouts=mono,{voz}[v];"
              f"[2:a]aformat=channel_layouts=mono,atrim=0:{D:.2f},volume={VOL_MUSICA},"
              f"afade=t=in:d=1.5,afade=t=out:st={max(0, D - 2.5):.2f}:d=2.5[m];"
              f"[v][m]amix=inputs=2:duration=first:normalize=0[a]")
    cmd = [ffmpeg(), "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{ANCHO}x{ALTO}",
           "-r", str(FPS), "-i", "-", "-i", str(wav), "-i", str(REC / "musica_fondo.wav"),
           "-filter_complex", filtro, "-map", "0:v", "-map", "[a]",
           "-c:v", "libx264", "-preset", preset, "-crf", "21", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-t", f"{D:.2f}", "-movflags", "+faststart", str(salida)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for k in range(int(D * FPS)):
        proc.stdin.write(cuadro(fondo, capas, imgs, n, k / FPS, bls, fsub).tobytes())
    proc.stdin.close()
    proc.wait()
    t = n.escenas[1][0] + 1.5
    cuadro(fondo, capas, imgs, n, t, bls, fsub).save(AQUI / "portada.png")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--voz", help="15–25 s de tu voz (m4a, opus, wav, mp3)")
    p.add_argument("--vista-previa", action="store_true", help="sin voz clonada: tiempos estimados, solo música")
    p.add_argument("--motor", default="qwen", choices=["qwen", "voxcpm"])
    p.add_argument("--tts", default="Qwen/Qwen3-TTS-12Hz-0.6B-Base")
    p.add_argument("--device", default="cpu", help="cpu, mps (Mac) o cuda")
    p.add_argument("--velocidad", type=float, default=1.0)
    p.add_argument("--salida", default=str(AQUI / "reel.mp4"))
    a = p.parse_args()
    if not a.vista_previa and not a.voz:
        p.error("usa --voz mi_voz.m4a, o --vista-previa para probar sin voz")

    t0 = time.time()
    guion = json.loads((AQUI / "guion.json").read_text(encoding="utf-8"))
    if a.vista_previa:
        n = narracion_simulada(guion)
        a_srt(n.palabras, AQUI / "subtitulos_vista_previa.srt")
    else:
        n = narracion_con_voz(guion, a)
        (AQUI / "guion.json").write_text(json.dumps(guion, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Duración: {n.duracion:.1f} s (objetivo 45–75 s)")
    video(guion, n, a.salida, con_voz=not a.vista_previa)
    print(f"Listo en {time.time() - t0:.0f} s → {a.salida}")
