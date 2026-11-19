"""Servicio en segundo plano: lee los mensajes de la partida que publica War
Thunder en http://localhost:8111/hudmsg y reproduce el sonido elegido cada vez
que tu nick hace una kill. No toca ningún archivo del juego."""
import json
import os
import re
import subprocess
import sys
import threading
import time
import unicodedata
import urllib.request

from . import config

# Textos oficiales del juego (lang/*.csv, claves NET_UNIT_KILLED_FM / _GM y
# NET_UNIT_CRITICAL_HIT_BURN). El juego escribe «Autor (vehículo) <verbo>
# Víctima (vehículo)» en el idioma que tenga puesto cada jugador, así que se
# buscan los de todos los idiomas a la vez.
VERBOS_KILL = {
    'en': ['shot down', 'destroyed'],
    'fr': ['abattu', 'détruit'],
    'it': ['ha abbattuto', 'ha distrutto'],
    'de': ['abgeschossen', 'zerstört'],
    'es': ['ha derribado a', 'ha destruido a', 'ha derribado', 'ha destruido'],
    'ru': ['сбил', 'уничтожил'],
    'pl': ['zestrzelił', 'zniszczył'],
    'cs': ['sestřelil', 'zničil'],
    'tr': ['düşürdü:', 'imha etti:'],
    'zh_CN': ['击落了', '击毁了'],
    'ja': ['によって 撃破されました', 'によって 撃墜されました', '撃墜されました'],
    'pt_BR': ['abateu', 'destruiu'],
    'uk': ['збив', 'знищив'],
    'sr': ['oborio', 'uništio'],
    'hu': ['lelőtte:', 'megsemmisítette:'],
    'ko': ['격추 >', '격파 >'],
    'be': ['збіў', 'знішчыў'],
    'ro': ['l-a doborât pe', 'l-a distrus pe'],
    'zh_TW': ['擊落了', '擊毀了'],
    'vi': ['bắn hạ', 'đã phá huỷ', 'đã phá hủy'],
}
VERBOS_FUEGO = {
    'en': ['set afire'], 'fr': ['mis en feu'], 'it': ['ha mandato in fiamme'], 'de': ['in Brand gesetzt'],
    'es': ['ha incendiado a', 'ha incendiado'], 'ru': ['поджёг', 'поджег'], 'pl': ['podpalił'], 'cs': ['zapálil'],
    'tr': ['yaktı:'], 'zh_CN': ['的攻击引燃了'], 'ja': ['火が 着きました'], 'pt_BR': ['incendiou'],
    'uk': ['підпалив'], 'sr': ['zapalio'], 'hu': ['kigyújtotta:'], 'ko': ['화재 >'], 'be': ['падпаліў'],
    'ro': ['l-a incendiat pe'], 'zh_TW': ['攻擊引燃'], 'vi': ['làm cháy'],
}


def limpiar(texto):
    """Quita los espacios invisibles que mete el juego (chino, japonés) y
    deja un solo espacio normal entre palabras."""
    texto = unicodedata.normalize('NFC', texto).replace('\u200b', '').replace('\\t', ' ').replace('\xa0', ' ')
    return re.sub(r'\s+', ' ', texto).strip()


def _patron(verbos):
    todos = sorted({unicodedata.normalize('NFC', v) for lista in verbos.values() for v in lista}, key=len, reverse=True)
    # donde el verbo tiene un espacio, el juego a veces no lo pone (japonés)
    alt = '|'.join(r'\s*'.join(re.escape(p) for p in v.split(' ')) for v in todos)
    # «destroyed by» / «abattu par» es cuando TE matan: no cuenta
    return re.compile(r'\)\s*(?:' + alt + r')(?!\s+(?:by|par)\b)')


KILL = _patron(VERBOS_KILL)
INCENDIO = _patron(VERBOS_FUEGO)


def _verbo(msg, tambien_incendio=False):
    m = KILL.search(msg)
    if tambien_incendio:
        f = INCENDIO.search(msg)
        if f and (not m or f.start() < m.start()):
            m = f
    return m


def es_kill(msg, nick, tambien_incendio=False):
    """True si el mensaje dice que `nick` mató (o incendió, si se pide) a
    alguien, en cualquiera de los idiomas del juego."""
    nick = limpiar(nick or '')
    if not nick:
        return False
    msg = limpiar(msg)
    m = _verbo(msg, tambien_incendio)
    if not m:
        return False
    autor = msg[:m.start() + 1]
    # «=TAG= Nick (Vehículo)»: el nick va justo antes del paréntesis del vehículo
    return re.search(r'(^|\s)' + re.escape(nick) + r' \(', autor) is not None


def victima(msg):
    """Lo que va después del verbo (para mostrar «→ víctima» en la app)."""
    msg = limpiar(msg)
    m = _verbo(msg, True)
    return msg[m.end():].strip() if m else None


def log(*a):
    ahora = time.time()
    linea = ' '.join([time.strftime('%H:%M:%S', time.localtime(ahora)) + f'.{int(ahora % 1 * 1000):03d}', *map(str, a)])
    if os.name == 'nt':
        # en Windows la app no tiene consola: registro en un archivo chico
        ruta = os.path.join(config.ESTADO_DIR, 'registro.txt')
        try:
            os.makedirs(config.ESTADO_DIR, exist_ok=True)
            modo = 'w' if os.path.exists(ruta) and os.path.getsize(ruta) > 200_000 else 'a'
            with open(ruta, modo, encoding='utf-8') as f:
                f.write(linea + '\n')
        except OSError:
            pass
    else:
        print(linea, flush=True)


class Detector:
    def __init__(self, tocar=None):
        # tocar(ruta, volumen): en Windows lo pone la app (reproductor de Qt);
        # en Linux, si no se da, se usa pw-play.
        self.tocar = tocar
        self.parar = False
        self.ultimo = None
        self.cfg = config.leer_config()
        self.cfg_mtime = 0
        self.estado = {'conectado': False, 'kills_sesion': 0, 'ultimas': []}

    def recargar_config(self):
        try:
            mt = os.path.getmtime(config.CONFIG)
        except OSError:
            mt = 0
        if mt != self.cfg_mtime:
            self.cfg_mtime = mt
            self.cfg = config.leer_config()

    def leer(self, desde):
        url = self.cfg['url'].rstrip('/') + f'/hudmsg?lastEvt=0&lastDmg={desde}'
        with urllib.request.urlopen(url, timeout=2) as r:
            return json.load(r).get('damage', [])

    def sonar(self, mid):
        sid = self.cfg.get('sonido')
        ruta = config.ruta_clip(sid) if sid else None
        if not ruta or not os.path.exists(ruta):
            log('sin sonido elegido')
            return

        vol = self.cfg.get('volumen', 1.0)
        if self.tocar:
            self.tocar(ruta, vol)
            log(f'sonido id={mid}')
            return

        def tocar():
            r = subprocess.run(['pw-play', '--volume', f'{vol:.2f}', ruta], capture_output=True, text=True)
            log(f'sonido id={mid} rc={r.returncode} {r.stderr.strip()[:200]}')
        threading.Thread(target=tocar, daemon=True).start()

    def publicar(self, **cambios):
        self.estado.update(cambios)
        self.estado['actualizado'] = time.time()
        config.guardar_estado(self.estado)

    def paso(self):
        self.recargar_config()
        msgs = self.leer(0 if self.ultimo is None else self.ultimo)
        if not self.estado['conectado']:
            self.publicar(conectado=True)
            log('conectado al juego')
        ids = [m['id'] for m in msgs]
        if self.ultimo is None:
            self.ultimo = max(ids, default=0)   # las kills viejas no suenan
            return
        if ids and max(ids) < self.ultimo:      # el juego se reinició
            self.ultimo = 0
        for m in msgs:
            if m['id'] <= self.ultimo:
                continue
            self.ultimo = m['id']
            if es_kill(m['msg'], self.cfg.get('nick', ''), self.cfg.get('tambien_incendio', False)):
                log(f"KILL id={m['id']} {m['msg']}")
                ultimas = ([{'hora': time.strftime('%H:%M:%S'), 'msg': m['msg']}] + self.estado['ultimas'])[:20]
                self.publicar(kills_sesion=self.estado['kills_sesion'] + 1, ultimas=ultimas)
                if self.cfg.get('activo', True):
                    self.sonar(m['id'])

    def correr(self):
        log('detector iniciado')
        self.publicar(conectado=False)
        while not self.parar:
            try:
                self.paso()
                time.sleep(0.3)
            except (OSError, ValueError):
                if self.estado['conectado']:
                    self.publicar(conectado=False)
                    log('juego desconectado')
                time.sleep(3)   # juego cerrado o cargando: esperar sin gastar CPU
            except Exception as e:   # nunca morir por un mensaje raro
                log('error:', repr(e)[:200])
                time.sleep(3)


def main():
    if '--probar' in sys.argv:
        d = Detector()
        msgs = d.leer(0)
        mias = [m['msg'] for m in msgs if es_kill(m['msg'], d.cfg['nick'], d.cfg['tambien_incendio'])]
        print(f"{len(msgs)} mensajes, {len(mias)} kills de {d.cfg['nick']}:")
        for t in mias:
            print('  ', t)
        return
    try:
        from . import audio
        audio.asegurar_predeterminado()
    except Exception as e:
        log('no se pudo poner el sonido predeterminado:', repr(e)[:200])
    Detector().correr()


if __name__ == '__main__':
    main()
