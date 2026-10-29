import math
import random
import time
from array import array
import pygame
from config import find_asset

MASTER_VOLUME = 0.6      
import sys
ENABLED = (sys.platform != "emscripten")
VOLUMES = {
    "star": 0.55, "hit": 0.8, "bump": 0.55, "boom": 0.9, "scratch": 0.8,
    "heal": 0.7, "super": 0.8, "dash": 0.7, "sword": 0.9, "win": 0.8, "click": 0.5,
}
MIN_GAP = {"boom": 0.06, "hit": 0.05, "bump": 0.1, "star": 0.05}

TAU = math.pi * 2
_sounds = {}
_last = {}
_ready = False

def _buf(sr, dur):
    return [0.0] * int(sr * dur)

def _tone(buf, sr, f0, f1, dur, decay=6.0, shape="sine", vol=1.0, start=0.0, bell=False):
    n, s0, phase = int(sr * dur), int(sr * start), 0.0
    for i in range(n):
        j = s0 + i
        if j >= len(buf):
            break
        t = i / sr
        phase += TAU * (f0 + (f1 - f0) * i / n) / sr
        if shape == "sine":
            v = math.sin(phase)
        elif shape == "square":
            v = math.tanh(4 * math.sin(phase))
        else:
            v = 2 * ((phase / TAU) % 1.0) - 1
        env = (math.sin(math.pi * i / n) ** 1.2) if bell else math.exp(-decay * t) * min(1.0, t / 0.003)
        buf[j] += v * vol * env

def _noise(buf, sr, dur, decay=6.0, smooth=1.0, vol=1.0, start=0.0, highpass=False, bell=False):
    n, s0, state = int(sr * dur), int(sr * start), 0.0
    gain = 1.0 if (highpass or smooth >= 1.0) else 1.0 / math.sqrt(smooth / (2.0 - smooth))
    for i in range(n):
        j = s0 + i
        if j >= len(buf):
            break
        t = i / sr
        x = random.uniform(-1, 1)
        state += smooth * (x - state)
        v = (x - state) if highpass else state * gain
        env = (math.sin(math.pi * i / n) ** 1.5) if bell else math.exp(-decay * t) * min(1.0, t / 0.002)
        buf[j] += v * vol * env

def _to_sound(buf, freq, channels):
    peak = max(max(buf), -min(buf), 1e-9)
    scale = 0.9 * 32767 / peak if peak > 0.9 else 32767
    out = array("h")
    for v in buf:
        iv = int(max(-32767, min(32767, v * scale)))
        for _ in range(channels):
            out.append(iv)
    return pygame.mixer.Sound(buffer=out.tobytes())

def _make_all(sr):
    random.seed(11)
    S = {}

    b = _buf(sr, .16)                                   
    _tone(b, sr, 1500, 600, .14, 14, vol=.8)
    _tone(b, sr, 3000, 1200, .08, 30, vol=.25)
    S["star"] = b

    b = _buf(sr, .15)                                   
    _noise(b, sr, .1, 35, smooth=.3, vol=.9)
    _tone(b, sr, 180, 60, .12, 28, vol=.9)
    S["hit"] = b

    b = _buf(sr, .1)                                    
    _tone(b, sr, 260, 120, .08, 45)
    _noise(b, sr, .04, 60, smooth=.5, vol=.4)
    S["bump"] = b

    b = _buf(sr, .75)                                   
    _noise(b, sr, .7, 6, smooth=.1, vol=1.0)
    _tone(b, sr, 120, 30, .7, 4.5, vol=1.2)
    _noise(b, sr, .12, 40, smooth=1.0, vol=.5)
    S["boom"] = b

    b = _buf(sr, .3)                                    
    for k in range(3):
        _noise(b, sr, .1, 22, smooth=.45, vol=.7, start=k * .055, highpass=True)
    S["scratch"] = b

    b = _buf(sr, .7)                                    
    for k, f in enumerate((523, 659, 784, 1047)):
        _tone(b, sr, f, f, .3, 7, vol=.6, start=k * .09)
        _tone(b, sr, f * 2, f * 2, .2, 9, vol=.2, start=k * .09)
    S["heal"] = b

    b = _buf(sr, .75)                                   
    _tone(b, sr, 180, 900, .5, shape="saw", vol=.5, bell=True)
    _tone(b, sr, 360, 1800, .5, vol=.4, bell=True)
    _noise(b, sr, .5, smooth=.3, vol=.3, highpass=True, bell=True)
    _tone(b, sr, 1760, 1760, .25, 9, vol=.5, start=.45)
    S["super"] = b

    b = _buf(sr, .35)                                   
    _noise(b, sr, .32, smooth=.25, vol=.8, highpass=True, bell=True)
    _tone(b, sr, 300, 1400, .3, shape="saw", vol=.25, bell=True)
    S["dash"] = b

    b = _buf(sr, .6)                                    
    _noise(b, sr, .2, smooth=.3, vol=.8, highpass=True, bell=True)
    _tone(b, sr, 150, 80, .12, 20, vol=.5, start=.12)
    _tone(b, sr, 2000, 2000, .45, 9, vol=.35, start=.12)
    _tone(b, sr, 3010, 3010, .4, 11, vol=.25, start=.12)
    S["sword"] = b

    b = _buf(sr, 1.1)                                   
    for k, f in enumerate((523, 659, 784, 1047)):
        _tone(b, sr, f, f, .6 if k == 3 else .25, 3.5, shape="square", vol=.3, start=k * .14)
        _tone(b, sr, f, f, .6 if k == 3 else .25, 3.5, vol=.4, start=k * .14)
    S["win"] = b

    b = _buf(sr, .06)                                   
    _tone(b, sr, 1400, 1000, .04, 50, vol=.7)
    S["click"] = b

    return S

def init():
    global _ready
    if not ENABLED:
        return
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init(44100, -16, 2, 512)
        freq, fmt, channels = pygame.mixer.get_init()
        if fmt != -16:
            print("[sound] unsupported audio format, sounds are off")
            return
        for name, samples in _make_all(freq).items():
            custom = None
            for ext in (".wav", ".ogg", ".mp3"):
                custom = find_asset(f"sfx_{name}{ext}")
                if custom:
                    break
            _sounds[name] = pygame.mixer.Sound(custom) if custom else _to_sound(samples, freq, channels)
        _ready = True
    except Exception as e:
        print(f"[sound] could not start audio ({e}); the game will be silent")

def play(name, volume=1.0):
    if not _ready:
        return
    snd = _sounds.get(name)
    if snd is None:
        return
    now = time.time()
    if now - _last.get(name, 0.0) < MIN_GAP.get(name, 0.03):
        return
    _last[name] = now
    try:
        snd.set_volume(min(1.0, VOLUMES.get(name, 1.0) * MASTER_VOLUME * volume))
        snd.play()
    except Exception:
        pass

init()
