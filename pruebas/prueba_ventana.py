"""Prueba la ventana sin mostrarla (QT_QPA_PLATFORM=offscreen) y guarda capturas."""
import os, sys, tempfile, time
tmp = tempfile.mkdtemp(prefix='killsound-ui-')
for v in ('XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_STATE_HOME'):
    os.environ[v] = os.path.join(tmp, v)
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from killsound import app as ui, audio, config, idiomas
idiomas.poner('es')

SALIDA = sys.argv[1]
os.makedirs(SALIDA, exist_ok=True)
VIDEO = os.path.expanduser('~/Downloads/MU HEHEHEHE #cat #memes #hehe #shorts.mp4')
tocados = []
audio.reproducir = lambda ruta, vol=1.0: tocados.append((ruta, vol)) or type('P', (), {'poll': lambda s: 0, 'terminate': lambda s: None})()

qa = QApplication([])
qa.setStyleSheet(ui.ESTILO)
f = QFont(qa.font()); f.setPointSizeF(10.5); qa.setFont(f)
ok = 0
def check(c, t):
    global ok
    print(('OK   ' if c else 'FALLA'), t)
    if not c: sys.exit(1)
    ok += 1
def esperar(cond, seg=20):
    t0 = time.time()
    while not cond() and time.time() - t0 < seg:
        qa.processEvents(); time.sleep(0.02)
    return cond()

# biblioteca vacía
w = ui.Ventana(); w.show(); qa.processEvents()
check(w.lista.count() == 1 and 'MU HEHEHEHE (gato)' in w.lista.item(0).text() and '★' in w.lista.item(0).text(),
      'instalación nueva: viene con el muheeheheh en uso')
check(w.btn_usar.text() == 'Ya suena en tus kills', 'y el botón dice que ya suena')
w.servicio_activo = lambda: True; w.refrescar_estado()
check(w.txt_nick.text() == '' and not w.lbl_falta_nick.isHidden() and 'Falta tu nick' in w.lbl_estado.text(),
      'nick vacío: aviso en rojo y «Falta tu nick» arriba')
w.grab().save(f'{SALIDA}/0_sin_nick.png')
w.txt_nick.setText('Shikimori-san'); w.txt_nick.editingFinished.emit(); qa.processEvents()
check(w.lbl_falta_nick.isHidden() and 'Falta tu nick' not in w.lbl_estado.text() and config.leer_config()['nick'] == 'Shikimori-san',
      'al escribirlo se guarda y el aviso desaparece')
w.grab().save(f'{SALIDA}/1_vacia.png')

# subir el video (como si lo eligiera en el diálogo)
w.importar(VIDEO)
check(esperar(lambda: w.lista.count() == 2), 'subir video: aparece en la lista')
check(w.meta is not None and len(w.partes) == 6, f'detecta {len(w.partes)} partes')
check(w.botones_partes[0][0].isChecked(), 'la parte 1 viene elegida (el primer muheeheheh)')
check(w.btn_usar.isEnabled() and w.btn_usar.text() == 'Usar para las kills', 'listo para usar')

# elegir la parte 2 con su botón
w.botones_partes[1][0].click(); qa.processEvents()
check(abs(w.sp_ini.value() - w.partes[1][0]) < 0.01 and w.cambios, 'botón «2» selecciona la parte 2 y marca cambios')
check(w.btn_usar.text() == 'Guardar y usar para las kills', 'el botón avisa que va a guardar')

# volver a la 1 con un clic sobre la onda
a, b = w.partes[0]
QTest.mouseClick(w.onda, Qt.MouseButton.LeftButton, pos=QPoint(int(w.onda._x((a + b) / 2)), 70)); qa.processEvents()
check(abs(w.onda.ini - a) < 0.01 and abs(w.onda.fin - b) < 0.01, 'clic sobre la onda elige esa parte')
check(not w.cambios, 'volver al recorte guardado quita el aviso de cambios')

# arrastrar el borde final para acortar
xb = int(w.onda._x(b)); xn = int(w.onda._x(b - 0.5))
QTest.mousePress(w.onda, Qt.MouseButton.LeftButton, pos=QPoint(xb, 70))
ev_move = QTest.mouseMove(w.onda, QPoint(xn, 70))
from PySide6.QtGui import QMouseEvent
from PySide6.QtCore import QPointF, QEvent
w.onda.mouseMoveEvent(QMouseEvent(QEvent.Type.MouseMove, QPointF(xn, 70), QPointF(xn, 70), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
QTest.mouseRelease(w.onda, Qt.MouseButton.LeftButton, pos=QPoint(xn, 70)); qa.processEvents()
check(abs(w.onda.fin - (b - 0.5)) < 0.05 and abs(w.sp_fin.value() - w.onda.fin) < 0.01, f'arrastrar el borde: fin {w.onda.fin:.2f}s')

# escuchar (sin sonar de verdad)
w.escuchar(); qa.processEvents()
check(tocados and tocados[-1][0].endswith('.ogg'), 'Escuchar reproduce la selección')

# guardar y usar
w.usar()
r = esperar(lambda: config.leer_config().get('sonido') == w.sid)
check(r, 'Guardar y usar: queda como sonido de las kills')
check(abs(audio.duracion(config.ruta_clip(w.sid)) - (w.onda.fin - w.onda.ini)) < 0.1, 'el archivo guardado dura lo recortado')
check(w.btn_usar.text() == 'Ya suena en tus kills' and not w.btn_usar.isEnabled(), 'botón: «Ya suena en tus kills»')
check(sum('★' in w.lista.item(i).text() for i in range(w.lista.count())) == 1 and '★' in w.lista.currentItem().text(),
      'solo uno en uso: el nuevo')

# ajustes
w.sl_vol.setValue(80); w.txt_nick.setText('OtroNick'); w.txt_nick.editingFinished.emit()
w.chk_incendio.setChecked(True); w.chk_activo.setChecked(False)
c = config.leer_config()
check(c['volumen'] == 0.8 and c['nick'] == 'OtroNick' and c['tambien_incendio'] and not c['activo'], 'ajustes se guardan')
w.chk_activo.setChecked(True); w.txt_nick.setText('Shikimori-san'); w.txt_nick.editingFinished.emit(); w.sl_vol.setValue(100)

# estado con kills
config.guardar_estado({'conectado': True, 'actualizado': time.time(), 'kills_sesion': 3, 'ultimas': [
    {'hora': '19:58:12', 'msg': '=FRDBR= Shikimori-san (◌Hunter F) ha derribado a ⋇AngyScorp7837 (F-105D)'},
    {'hora': '19:57:20', 'msg': '=FRDBR= Shikimori-san (◌Hunter F) ha derribado a =ACTF= blackonegamer100 (F8U-2)'},
    {'hora': '19:55:02', 'msg': '=FRDBR= Shikimori-san (◌Hunter F) ha destruido a [ai]\xa0A-4B'}]})
w.servicio_activo = lambda: True
w.refrescar_estado(); qa.processEvents()
check('3 en esta sesión' in w.lbl_kills.text() and 'F-105D' in w.lbl_kills.text(), 'muestra las últimas kills')
check('conectado' in w.lbl_estado.text(), 'muestra War Thunder conectado')
w.grab().save(f'{SALIDA}/2_editor.png')

# archivo malo
from PySide6.QtWidgets import QMessageBox
avisos = []
QMessageBox.warning = staticmethod(lambda *a: avisos.append(a[2]))
malo = os.path.join(tmp, 'malo.txt'); open(malo, 'w').write('x')
w.importar(malo)
check(esperar(lambda: avisos), f'archivo sin audio: avisa «{avisos[0] if avisos else ""}»')
check(w.lista.count() == 2 and w.btn_subir.isEnabled(), 'y la app sigue bien')

# eliminar
QMessageBox.question = staticmethod(lambda *a: QMessageBox.StandardButton.Yes)
w.borrar(); qa.processEvents()
check(w.lista.count() == 1 and config.leer_config().get('sonido') is None, 'eliminar el sonido en uso lo desactiva')
print(f'\n{ok} pruebas OK')

# idiomas: cambiar desde el selector de los ajustes
w.importar(VIDEO)
esperar(lambda: w.lista.count() == 2)
sid_antes = w.sid
anchos = {}
for i, (codigo, nombre) in enumerate(idiomas.IDIOMAS):
    w.cmb_idioma.setCurrentIndex(i)
    esperar(lambda: w.cmb_idioma.currentData() == codigo and w.btn_subir.text() == idiomas.TEXTOS[codigo]['subir'], 5)
    qa.processEvents()
    anchos[codigo] = w.centralWidget().minimumSizeHint().width()
    if not (w.windowTitle() == idiomas.TEXTOS[codigo]['app'] and config.leer_config()['idioma'] == codigo
            and w.sid == sid_antes and w.lista.count() == 2 and w.onda.picos is not None):
        check(False, f'cambiar a {nombre}')
    w.grab().save(f'{SALIDA}/idioma_{codigo}.png')
check(True, f'cambia en vivo a los {len(anchos)} idiomas, guarda la elección y conserva el sonido abierto')
ancho_max = max(anchos.values())
check(ancho_max <= 1060, f'ningún idioma ensancha la ventana (máx {ancho_max}px: {max(anchos, key=anchos.get)})')
w.cmb_idioma.setCurrentIndex(idiomas.CODIGOS.index('es')); esperar(lambda: w.windowTitle() == 'Sonido de Kill', 5)
w2 = ui.Ventana()
check(w2.cmb_idioma.currentData() == 'es' and w2.btn_subir.text() == idiomas.TEXTOS['es']['subir'], 'al volver a abrir recuerda el idioma')
print(f'\n{ok} pruebas OK (con idiomas)')
