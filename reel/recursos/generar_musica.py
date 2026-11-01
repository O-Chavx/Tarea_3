"""Pista de fondo original (ambiental, 72 s) generada con numpy: sin derechos de terceros.
Autor: Oscar Andres Chavez Inocente. Licencia: CC0 (dominio público).
Uso:  python reel/recursos/generar_musica.py   ->  reel/recursos/musica_fondo.wav
"""
import wave
from pathlib import Path

import numpy as np

SR, DUR, BPM = 44100, 72.0, 84
t = np.arange(int(SR * DUR)) / SR
beat = 60 / BPM
compas = 4 * beat

def nota(n):  # número MIDI -> Hz
    return 440 * 2 ** ((n - 69) / 12)

# La menor - Fa - Do - Sol (i-VI-III-VII), un acorde por compás
acordes = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]
pad = np.zeros_like(t)
arp = np.zeros_like(t)
bajo = np.zeros_like(t)
for k in range(int(DUR / compas) + 1):
    ac = acordes[k % 4]
    t0 = k * compas
    m = (t >= t0) & (t < t0 + compas + 0.5)
    tt = t[m] - t0
    env = np.minimum(1, tt / 0.8) * np.exp(-np.maximum(0, tt - compas) * 4)
    for n in ac:
        f = nota(n)
        pad[m] += env * (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * 2.003 * f * tt)) / 3
    bajo[m] += env * np.sin(2 * np.pi * nota(ac[0] - 12) * tt) * 0.5
    for j in range(8):  # arpegio en corcheas
        n = ac[[0, 1, 2, 1][j % 4]] + 12
        ts = t0 + j * beat / 2
        mm = (t >= ts) & (t < ts + 1.2)
        tt = t[mm] - ts
        arp[mm] += np.sin(2 * np.pi * nota(n) * tt) * np.exp(-tt * 4.5) * 0.35

mix = 0.55 * pad + 0.5 * bajo + arp
# eco sencillo y fundidos de entrada y salida
d = int(SR * beat * 0.75)
eco = np.zeros_like(mix); eco[d:] = mix[:-d] * 0.3
mix = mix + eco
mix *= np.minimum(1, t / 2.5) * np.minimum(1, (DUR - t) / 3)
mix = mix / np.abs(mix).max() * 0.8
out = Path(__file__).with_name("musica_fondo.wav")
with wave.open(str(out), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((mix * 32767).astype("<i2").tobytes())
print("✓", out)
