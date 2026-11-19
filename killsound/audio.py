"""Audio con ffmpeg: importar cualquier audio o video, forma de onda, detectar
partes separadas por silencio, recortar y reproducir."""
import os
import subprocess
import tempfile
import time

import numpy as np

from . import config
from .idiomas import t

TASA_ONDA = 100          # puntos de la forma de onda por segundo
FILTRO_IGUALAR = ('acompressor=threshold=-30dB:ratio=6:attack=5:release=60:makeup=6,'
                  'volume=4dB,alimiter=limit=0.8:level=false')   # techo -2 dB: el ogg no se pasa de 1.0


class ErrorAudio(Exception):
    pass


def _programa(nombre):
    """ffmpeg/ffprobe: el que viene junto a la app (Windows) o el del sistema."""
    import sys
    exe = nombre + ('.exe' if os.name == 'nt' else '')
    for base in (getattr(sys, '_MEIPASS', None), os.path.dirname(sys.executable)):
        if base:
            for sub in ('ffmpeg', ''):
                ruta = os.path.join(base, sub, exe)
                if os.path.isfile(ruta):
                    return ruta
    return nombre


# en Windows, que ffmpeg no abra ventanas negras
_SIN_VENTANA = {'creationflags': 0x08000000} if os.name == 'nt' else {}


def _correr(args, **kw):
    return subprocess.run(args, **_SIN_VENTANA, **kw)


def _ffmpeg(*args):
    r = _correr([_programa('ffmpeg'), '-v', 'error', '-y', *args], capture_output=True, text=True,
                encoding='utf-8', errors='replace')
    if r.returncode != 0:
        raise ErrorAudio(r.stderr.strip().splitlines()[-1] if r.stderr.strip() else 'ffmpeg falló')


def duracion(ruta):
    """Duración en segundos (solo con ffmpeg, así no hace falta ffprobe)."""
    import re
    r = _correr([_programa('ffmpeg'), '-hide_banner', '-i', ruta], capture_output=True, text=True,
                encoding='utf-8', errors='replace')
    m = re.search(r'Duration: (\d+):(\d+):(\d+(?:\.\d+)?)', r.stderr)
    if not m:
        raise ErrorAudio(t('err_duracion'))
    h, mi, se = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(se)


def importar(archivo, nombre=None):
    """Copia el audio de cualquier archivo (también videos) a la biblioteca.
    Devuelve el id. El recorte inicial es la primera parte con sonido."""
    sid = config.nuevo_id()
    os.makedirs(config.carpeta(sid), exist_ok=True)
    try:
        _ffmpeg('-i', archivo, '-vn', '-ac', '2', '-ar', '48000', '-c:a', 'libvorbis', '-q:a', '6',
                config.ruta_original(sid))
    except ErrorAudio:
        config.borrar_sonido(sid)
        raise ErrorAudio(t('err_sin_audio'))
    dur = duracion(config.ruta_original(sid))
    partes = detectar_partes(forma_de_onda(config.ruta_original(sid)))
    ini, fin = partes[0] if partes else (0.0, min(dur, 3.0))
    meta = {
        'nombre': nombre or nombre_limpio(archivo),
        'archivo': os.path.basename(archivo),
        'duracion_original': dur,
        'inicio': ini, 'fin': fin,
        'igualar': True,
        'creado': time.time(),
    }
    config.guardar_meta(sid, meta)
    renderizar(sid)
    return sid


def nombre_limpio(archivo):
    """«MU HEHEHEHE #cat #memes #shorts.mp4» → «MU HEHEHEHE»."""
    import re
    base = os.path.splitext(os.path.basename(archivo))[0]
    limpio = re.sub(r'\s+', ' ', re.sub(r'#\S+', '', base)).strip(' -_|')
    return (limpio or base)[:60]


CARPETA_PREDETERMINADO = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'predeterminado')


def predeterminado():
    """(archivo, nombre) del sonido que trae esta versión de la app, según
    predeterminado/info.json (versión personal: el muheeheheh; pública: uno libre)."""
    import json
    try:
        with open(os.path.join(CARPETA_PREDETERMINADO, 'info.json'), encoding='utf-8') as f:
            info = json.load(f)
    except (OSError, ValueError):
        return None, None
    ruta = os.path.join(CARPETA_PREDETERMINADO, info.get('archivo', ''))
    return (ruta if os.path.isfile(ruta) else None), info.get('nombre') or 'Sonido de kill'


def asegurar_predeterminado():
    """La primera vez (biblioteca vacía) agrega el sonido que trae la app y lo
    deja en uso. Si el usuario lo borra después, no vuelve."""
    cfg = config.leer_config()
    ruta, nombre = predeterminado()
    if cfg.get('predeterminado_hecho') or config.listar_sonidos() or not ruta:
        return None
    sid = importar(ruta, nombre)
    m = config.leer_meta(sid)
    m.update(inicio=0.0, fin=m['duracion_original'], igualar=False)   # ya viene recortado e igualado
    config.guardar_meta(sid, m)
    renderizar(sid)
    cfg = config.leer_config()
    cfg['predeterminado_hecho'] = True
    if not cfg.get('sonido'):
        cfg['sonido'] = sid
    config.guardar_config(cfg)
    return sid


def forma_de_onda(ruta):
    """Picos (0–1) a TASA_ONDA puntos por segundo."""
    r = _correr([_programa('ffmpeg'), '-v', 'error', '-i', ruta, '-ac', '1', '-ar', '8000',
                 '-f', 'f32le', '-'], capture_output=True)
    datos = np.frombuffer(r.stdout, dtype=np.float32)
    if datos.size == 0:
        return np.zeros(1, dtype=np.float32)
    paso = 8000 // TASA_ONDA
    n = datos.size // paso
    if n == 0:
        return np.array([float(np.abs(datos).max())], dtype=np.float32)
    bloques = np.abs(datos[:n * paso]).reshape(n, paso)
    return bloques.max(axis=1)


def detectar_partes(onda, umbral_db=-35.0, silencio_min=0.15, sonido_min=0.12):
    """Tramos con sonido separados por al menos `silencio_min` s de silencio.
    Devuelve [(inicio, fin), ...] en segundos, con un pequeño margen."""
    if onda.size == 0:
        return []
    umbral = 10 ** (umbral_db / 20)
    activo = onda > umbral
    partes, i, n = [], 0, onda.size
    hueco = int(silencio_min * TASA_ONDA)
    while i < n:
        if not activo[i]:
            i += 1
            continue
        ini = i
        ult = i
        j = i
        while j < n and j - ult <= hueco:
            if activo[j]:
                ult = j
            j += 1
        if (ult - ini + 1) / TASA_ONDA >= sonido_min:
            partes.append((max(0.0, ini / TASA_ONDA - 0.03), min(n / TASA_ONDA, (ult + 1) / TASA_ONDA + 0.04)))
        i = ult + 1
    return partes


def _filtro(inicio, fin, igualar):
    largo = fin - inicio
    fade = min(0.08, largo / 4)
    f = [FILTRO_IGUALAR] if igualar else []
    f.append(f'afade=t=out:st={max(0.0, largo - fade):.3f}:d={fade:.3f}')
    return ','.join(f)


def recortar(origen, destino, inicio, fin, igualar=True):
    if fin - inicio < 0.05:
        raise ErrorAudio(t('err_corto'))
    _ffmpeg('-ss', f'{inicio:.3f}', '-to', f'{fin:.3f}', '-i', origen, '-vn',
            '-af', _filtro(inicio, fin, igualar), '-ar', '48000', '-c:a', 'libvorbis', '-q:a', '6', destino)


def renderizar(sid):
    m = config.leer_meta(sid)
    recortar(config.ruta_original(sid), config.ruta_clip(sid), m['inicio'], m['fin'], m.get('igualar', True))


def vista_previa(sid, inicio, fin, igualar):
    """Recorte temporal para escuchar antes de guardar."""
    tmp = os.path.join(tempfile.gettempdir(), f'killsound-previa-{os.getuid()}.ogg')
    recortar(config.ruta_original(sid), tmp, inicio, fin, igualar)
    return tmp


def con_volumen(ruta, volumen, wav=False):
    """Windows no sube el volumen por encima de 100 % y su reproductor de
    efectos (el más rápido) solo lee WAV: se prepara una copia (una vez, queda
    guardada) y se devuelve (archivo, volumen 0–1)."""
    vol = max(0.0, volumen)
    if vol <= 1.0 and not wav:
        return ruta, vol
    pct = int(round(vol * 100)) if vol > 1.0 else 100
    destino = f'{os.path.splitext(ruta)[0]}.vol{pct}.{"wav" if wav else "ogg"}'
    if not os.path.exists(destino) or os.path.getmtime(destino) < os.path.getmtime(ruta):
        filtro = f'volume={vol:.2f},alimiter=limit=0.89:level=false' if vol > 1.0 else 'anull'
        codec = ['-c:a', 'pcm_s16le'] if wav else ['-c:a', 'libvorbis', '-q:a', '6']
        _ffmpeg('-i', ruta, '-af', filtro, '-ar', '48000', '-ac', '2', *codec, destino)
    return destino, min(vol, 1.0)


def reproducir(ruta, volumen=1.0):
    """Linux: pw-play (sirve sin ventana, también desde el servicio)."""
    return subprocess.Popen(['pw-play', '--volume', f'{max(0.0, volumen):.2f}', ruta],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
