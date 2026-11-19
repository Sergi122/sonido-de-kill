"""Pruebas sin ventana: importar, partes, recorte y detección de kills.
Usa carpetas temporales (no toca la configuración real)."""
import json, os, sys, tempfile
tmp = tempfile.mkdtemp(prefix='killsound-prueba-')
for v in ('XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_STATE_HOME'):
    os.environ[v] = os.path.join(tmp, v)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from killsound import audio, config, detector, idiomas
idiomas.poner('es')

VIDEO = os.path.expanduser('~/Downloads/MU HEHEHEHE #cat #memes #hehe #shorts.mp4')
ok = 0
def check(cond, texto):
    global ok
    print(('OK   ' if cond else 'FALLA'), texto)
    if not cond: sys.exit(1)
    ok += 1

# 1. importar un VIDEO y detectar partes
sid = audio.importar(VIDEO, 'Muhehehe')
m = config.leer_meta(sid)
check(abs(m['duracion_original'] - 10.5) < 0.2, f"duración del original {m['duracion_original']:.2f}s")
partes = audio.detectar_partes(audio.forma_de_onda(config.ruta_original(sid)))
print('     partes:', [(round(a,2), round(b,2)) for a,b in partes])
check(len(partes) >= 3, f'detecta varias partes ({len(partes)})')
a, b = partes[0]
check(0.3 < a < 0.5 and 2.5 < b < 2.8, f'la 1.ª parte es el primer muheeheheh ({a:.2f}–{b:.2f}s)')
check(abs(audio.duracion(config.ruta_clip(sid)) - (b - a)) < 0.1, 'el recorte inicial es la 1.ª parte')

# 2. cambiar el recorte
m.update(inicio=3.6, fin=6.0); config.guardar_meta(sid, m); audio.renderizar(sid)
check(abs(audio.duracion(config.ruta_clip(sid)) - 2.4) < 0.1, 'recortar a mano (3.6–6.0 s)')
try:
    audio.recortar(config.ruta_original(sid), '/dev/null', 1.0, 1.01); check(False, 'recorte mínimo')
except audio.ErrorAudio:
    check(True, 'rechaza recortes de menos de 0,05 s')

# 3. archivo sin audio
txt = os.path.join(tmp, 'no_es_audio.txt'); open(txt, 'w').write('hola')
try:
    audio.importar(txt); check(False, 'archivo sin audio')
except audio.ErrorAudio as e:
    check('no tiene audio' in str(e), 'archivo sin audio: mensaje claro')
check(len(config.listar_sonidos()) == 1, 'el archivo malo no queda en la biblioteca')

# 4. detección de kills
N = 'Shikimori-san'
casos = [
 ('=FRDBR= Shikimori-san (◌Hunter F) ha derribado a ^RZSEN^ nikolas_bicca19 (Su-25K)', True),
 ('=FRDBR= Shikimori-san (◌Hunter F) ha destruido a [ai]\xa0A-4B', True),
 ('Shikimori-san (T-80BVM) ha destruido a Leopard 2A4', True),
 ('=FRDBR= Shikimori-san (◌Hunter F) ha incendiado a A-4B', False),
 ('=FRDBR= Shikimori-san (◌Hunter F) críticamente dañado A-4B', False),
 ('^RZSEN^ nikolas_bicca19 (Su-25K) ha derribado a =FRDBR= Shikimori-san (◌Hunter F)', False),
 ('xShikimori-san (F-4) ha derribado a pepe (MiG-21)', False),
 ('=FRDBR= Shikimori-san (◌Hunter F) has conseguido "Vengador"', False),
 ('Shikimori-san (F-4C) shot down Pilot (MiG-21)', True),
]
for msg, esperado in casos:
    check(detector.es_kill(msg, N) == esperado, f'{"kill" if esperado else "no  "} ← {msg[:70]}')
check(detector.es_kill(casos[3][0], N, tambien_incendio=True), 'incendio cuenta si se activa la opción')
check(not detector.es_kill(casos[0][0], ''), 'sin nick no cuenta nada')

# 5. el detector completo, con mensajes que llegan de a poco
d = detector.Detector()
cfg = config.leer_config(); cfg['sonido'] = sid; cfg['nick'] = N; config.guardar_config(cfg)
todos = [{'id': i, 'msg': msg} for i, (msg, _) in enumerate(casos, start=100)]
visibles = [102]
d.leer = lambda desde: [x for x in todos if desde < x['id'] <= visibles[0]]
sonados = []
d.sonar = lambda mid: sonados.append(mid)
d.paso()                                 # arranque: no suenan las viejas
for _ in range(10):
    visibles[0] += 1; d.paso()
check(sonados == [108], f'en vivo solo suena la kill nueva (ids {sonados})')
cfg['activo'] = False; config.guardar_config(cfg); os.utime(config.CONFIG, (1, 1))
todos.append({'id': 120, 'msg': casos[0][0]}); visibles[0] = 120; d.paso()
check(sonados == [108], 'apagado: detecta pero no suena')
e = config.leer_estado()
check(e['kills_sesion'] == 2 and e['conectado'], f"estado para la app: {e['kills_sesion']} kills, conectado")
print(f'\n{ok} pruebas OK')

# 6. sonido predeterminado (instalación nueva)
import shutil
for d in (config.CONFIG_DIR, config.DATOS_DIR, config.ESTADO_DIR):
    shutil.rmtree(d, ignore_errors=True)
sid = audio.asegurar_predeterminado()
lista = config.listar_sonidos()
check(sid and len(lista) == 1 and lista[0]['nombre'] == 'MU HEHEHEHE (gato)', 'instalación nueva: trae el muheeheheh')
check(config.leer_config()['nick'] == '', 'el nick viene vacío de fábrica')
check(config.leer_config()['sonido'] == sid, 'y queda en uso')
check(abs(audio.duracion(config.ruta_clip(sid)) - 2.26) < 0.1, 'dura lo mismo que el recorte (2,26 s)')
check(audio.asegurar_predeterminado() is None and len(config.listar_sonidos()) == 1, 'no se duplica al abrir otra vez')
config.borrar_sonido(sid)
check(audio.asegurar_predeterminado() is None and not config.listar_sonidos(), 'si lo borras, no vuelve solo')
print(f'\n{ok} pruebas OK (con predeterminado)')

# 7. kills en TODOS los idiomas del juego, con los textos sacados de sus archivos
import csv, glob, re
LANG = '/mnt/storage/SteamLibrary/steamapps/common/War Thunder/lang'
def prueba_idiomas_del_juego():
    global ok
    filas = {}
    for f in glob.glob(LANG + '/*.csv'):
        with open(f, encoding='utf-8') as fh:
            r = csv.reader(fh, delimiter=';'); cab = next(r)
            for row in r:
                if row and row[0] in ('NET_UNIT_KILLED_FM', 'NET_UNIT_KILLED_GM', 'NET_UNIT_CRITICAL_HIT_BURN'):
                    filas[row[0]] = {c.strip('<>'): v for c, v in zip(cab, row)}
    check(len(filas) == 3, 'textos de kill leídos del juego')
    COLS = [c for c in filas['NET_UNIT_KILLED_FM'] if c not in ('ID|readonly|noverify', 'Comments', 'max_chars')]
    check(len(COLS) >= 20, f'{len(COLS)} idiomas en el juego')

    def variantes(v):
        """Como puede llegar al hudmsg: el \\t del CSV como tabulador, espacio o nada."""
        return {v.replace('\\t', x) for x in ('\t', ' ', '')}

    malos = []
    for col in COLS:
        for clave in ('NET_UNIT_KILLED_FM', 'NET_UNIT_KILLED_GM', 'NET_UNIT_CRITICAL_HIT_BURN'):
            fuego = clave.endswith('BURN')
            for v in variantes(filas[clave][col]):
                mio = f'=FRDBR= {N} (Tiger II (H)) {v} =ABC=\xa0pepe_99 (T-34-85)'
                contra = f'=ABC= pepe_99 (T-34-85) {v} =FRDBR= {N} (Tiger II (H))'
                pegado = f'{N} (F-4C){v}pepe (MiG-21)'      # chino/japonés sin espacios
                if fuego:
                    ok_ = (not detector.es_kill(mio, N) and detector.es_kill(mio, N, True)
                           and not detector.es_kill(contra, N, True))
                else:
                    ok_ = (detector.es_kill(mio, N) and not detector.es_kill(contra, N, True)
                           and detector.es_kill(pegado, N)
                           and detector.victima(mio).startswith('=ABC= pepe_99'))
                if not ok_:
                    malos.append((col, clave, v))
    check(not malos, f'kill/incendio reconocidos en {len(COLS)} idiomas ({len(COLS) * 3 * 2} casos) {malos[:3]}')


if os.path.isdir(LANG):
    prueba_idiomas_del_juego()
else:
    print('(War Thunder no está instalado aquí: se salta la prueba con sus textos de kill)')

# 8. traducciones de la app completas
claves = set(idiomas.TEXTOS['es'])
for c in idiomas.CODIGOS:
    falta = claves - set(idiomas.TEXTOS[c]); sobra = set(idiomas.TEXTOS[c]) - claves
    huecos = [k for k in claves & set(idiomas.TEXTOS[c])
              if set(re.findall(r'{(\w+)}', idiomas.TEXTOS[c][k])) != set(re.findall(r'{(\w+)}', idiomas.TEXTOS['es'][k]))]
    check(not falta and not sobra and not huecos, f'{c}: {len(claves)} textos, mismos datos {falta or ""}{sobra or ""}{huecos or ""}')
check(len(idiomas.CODIGOS) == 20 and len(set(idiomas.CODIGOS)) == 20, '20 idiomas como el juego')
idiomas.poner('ja')
try:
    audio.importar(txt)
except audio.ErrorAudio as e:
    check('使える音声' in str(e), f'errores también traducidos: {e}')
idiomas.poner('en'); check(idiomas.decimal(2.5) == '2.50', 'inglés: 2.50')
idiomas.poner('de'); check(idiomas.decimal(2.5) == '2,50', 'alemán: 2,50')
for pasiva in ('destroyed by', 'shot down by', 'détruit par', 'abattu par'):
    check(not detector.es_kill(f'{N} (F-4C) {pasiva} pepe (MiG-21)', N), f'pasiva «{pasiva}» no cuenta')
idiomas.poner('es')
print(f'\n{ok} pruebas OK (con idiomas)')
