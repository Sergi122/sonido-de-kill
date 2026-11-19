"""Rutas, configuración y biblioteca de sonidos (todo en JSON, sin base de datos)."""
import json
import os
import shutil
import time
import uuid

WINDOWS = os.name == 'nt'
INICIO = os.path.expanduser('~')
if WINDOWS:
    # %APPDATA%\SonidoDeKill\{config.json, sonidos\, estado.json}
    _base = os.path.join(os.environ.get('APPDATA', INICIO), 'SonidoDeKill')
    CONFIG_DIR = DATOS_DIR = ESTADO_DIR = os.environ.get('KILLSOUND_DIR', _base)
else:
    CONFIG_DIR = os.path.join(os.environ.get('XDG_CONFIG_HOME', os.path.join(INICIO, '.config')), 'killsound')
    DATOS_DIR = os.path.join(os.environ.get('XDG_DATA_HOME', os.path.join(INICIO, '.local/share')), 'killsound')
    ESTADO_DIR = os.path.join(os.environ.get('XDG_STATE_HOME', os.path.join(INICIO, '.local/state')), 'killsound')
SONIDOS_DIR = os.path.join(DATOS_DIR, 'sonidos')
CONFIG = os.path.join(CONFIG_DIR, 'config.json')
ESTADO = os.path.join(ESTADO_DIR, 'estado.json')

PREDETERMINADA = {
    'activo': True,
    'nick': '',              # cada uno escribe el suyo en la app
    'sonido': None,          # id del sonido de la biblioteca
    'volumen': 1.0,          # 0.0 – 1.5
    'tambien_incendio': False,
    'url': 'http://localhost:8111',
}


def _guardar_json(ruta, datos):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    tmp = ruta + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    os.replace(tmp, ruta)      # escritura atómica: el detector nunca lee a medias


def _leer_json(ruta, defecto):
    try:
        with open(ruta, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return defecto


def leer_config():
    c = dict(PREDETERMINADA)
    c.update(_leer_json(CONFIG, {}))
    return c


def guardar_config(c):
    _guardar_json(CONFIG, c)


def leer_estado():
    return _leer_json(ESTADO, {})


def guardar_estado(e):
    _guardar_json(ESTADO, e)


# ------------------------------------------------------------ biblioteca
# Cada sonido vive en SONIDOS_DIR/<id>/: original.ogg (audio completo del
# archivo subido), clip.ogg (el recorte que suena) y meta.json.

def carpeta(sid):
    return os.path.join(SONIDOS_DIR, sid)


def ruta_clip(sid):
    return os.path.join(carpeta(sid), 'clip.ogg')


def ruta_original(sid):
    return os.path.join(carpeta(sid), 'original.ogg')


def leer_meta(sid):
    return _leer_json(os.path.join(carpeta(sid), 'meta.json'), None)


def guardar_meta(sid, meta):
    _guardar_json(os.path.join(carpeta(sid), 'meta.json'), meta)


def listar_sonidos():
    out = []
    if os.path.isdir(SONIDOS_DIR):
        for sid in os.listdir(SONIDOS_DIR):
            m = leer_meta(sid)
            if m and os.path.exists(ruta_clip(sid)):
                m['id'] = sid
                out.append(m)
    return sorted(out, key=lambda m: m.get('creado', 0))


def nuevo_id():
    return time.strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:6]


def borrar_sonido(sid):
    shutil.rmtree(carpeta(sid), ignore_errors=True)
