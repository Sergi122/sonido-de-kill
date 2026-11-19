"""Ventana de Sonido de Kill (PySide6)."""
import os
import subprocess
import sys
import time

import threading

from PySide6.QtCore import QObject, QPointF, QRectF, QRunnable, Qt, QThreadPool, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QColor, QDesktopServices, QFont, QIcon, QPainter, QPen
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPushButton, QSlider, QSizePolicy,
    QSystemTrayIcon, QVBoxLayout, QWidget,
)

from . import audio, config, detector, idiomas
from .idiomas import t as T

WINDOWS = os.name == 'nt'
AQUI = os.path.dirname(os.path.abspath(__file__))
NOMBRE_INSTANCIA = f"SonidoDeKill-{os.environ.get('USERNAME') or os.environ.get('USER', '')}"
CLAVE_INICIO = r'Software\Microsoft\Windows\CurrentVersion\Run'
URL_APOYAR = 'https://github.com/sponsors/Sergi122'
ICONO = os.path.join(AQUI, 'icono.svg')
SERVICIO = 'killsound.service'
EXTENSIONES = ('*.mp3 *.ogg *.oga *.wav *.flac *.m4a *.aac *.opus *.webm *.mp4 *.mkv *.mov')

C_FONDO = '#14161c'
C_PANEL = '#1d2029'
C_BORDE = '#2c3140'
C_TEXTO = '#e8eaf0'
C_TENUE = '#8a91a5'
C_ACENTO = '#ff8a3d'
C_OK = '#3ecf8e'
C_MAL = '#ff5d6c'

ESTILO = f"""
QWidget {{ background: {C_FONDO}; color: {C_TEXTO}; font-size: 13px; }}
QFrame#panel {{ background: {C_PANEL}; border: 1px solid {C_BORDE}; border-radius: 12px; }}
QFrame#panel QLabel, QFrame#panel QCheckBox, QFrame#panel QListWidget {{ background: transparent; }}
QLabel#titulo {{ font-size: 20px; font-weight: 700; }}
QLabel#seccion {{ color: {C_TENUE}; font-size: 11px; font-weight: 700; letter-spacing: 1px; }}
QLabel#tenue {{ color: {C_TENUE}; }}
QLineEdit, QDoubleSpinBox, QComboBox {{ background: {C_FONDO}; border: 1px solid {C_BORDE}; border-radius: 8px;
    padding: 6px 8px; selection-background-color: {C_ACENTO}; }}
QLineEdit:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border-color: {C_ACENTO}; }}
QComboBox QAbstractItemView {{ background: {C_PANEL}; border: 1px solid {C_BORDE}; selection-background-color: #2e3446; }}
QPushButton {{ background: #2a2f3d; border: 1px solid {C_BORDE}; border-radius: 8px; padding: 7px 14px; }}
QPushButton:hover {{ background: #343a4b; }}
QPushButton:disabled {{ color: #5b6172; background: #20232c; }}
QPushButton#primario {{ background: {C_ACENTO}; color: #1a1208; border: none; font-weight: 700; }}
QPushButton#primario:hover {{ background: #ff9d5c; }}
QPushButton#primario:disabled {{ background: #5a4232; color: #2a1d12; }}
QPushButton#apoyar {{ background: transparent; border: 1px solid #e0557a; color: #ff7a9c; font-weight: 700; }}
QPushButton#apoyar:hover {{ background: #3a1f2a; }}
QPushButton#parte {{ padding: 4px 10px; border-radius: 12px; font-size: 12px; }}
QPushButton#parte:checked {{ background: {C_ACENTO}; color: #1a1208; border: none; font-weight: 700; }}
QListWidget {{ background: transparent; border: none; outline: none; }}
QListWidget::item {{ padding: 9px 8px; border-radius: 8px; margin: 1px 0; }}
QListWidget::item:selected {{ background: #2e3446; color: {C_TEXTO}; }}
QListWidget::item:hover {{ background: #262b39; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px; border: 1px solid {C_BORDE}; background: {C_FONDO}; }}
QCheckBox::indicator:checked {{ background: {C_ACENTO}; border-color: {C_ACENTO}; }}
QCheckBox#interruptor::indicator {{ width: 40px; height: 22px; border-radius: 11px; }}
QSlider::groove:horizontal {{ height: 6px; background: {C_BORDE}; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {C_ACENTO}; border-radius: 3px; }}
QSlider::handle:horizontal {{ background: {C_TEXTO}; width: 16px; margin: -6px 0; border-radius: 8px; }}
"""


def seg(s):
    return idiomas.decimal(s) + ' s'


def panel():
    f = QFrame()
    f.setObjectName('panel')
    return f


def etiqueta(texto, nombre=None):
    l = QLabel(texto)
    if nombre:
        l.setObjectName(nombre)
    return l


# ---------------------------------------------------------------- sonido (Windows)
class ReproductorQt(QObject):
    """Reproduce con QtMultimedia. Cada sonido usa su propio reproductor, así
    dos kills seguidas suenan las dos."""

    def __init__(self, padre=None):
        super().__init__(padre)
        self.vivos = []

    def tocar(self, ruta, volumen=1.0):
        from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
        try:
            ruta, volumen = audio.con_volumen(ruta, volumen)
        except audio.ErrorAudio:
            volumen = min(volumen, 1.0)
        rep, salida = QMediaPlayer(self), QAudioOutput(self)
        salida.setVolume(volumen)
        rep.setAudioOutput(salida)
        rep.setSource(QUrl.fromLocalFile(ruta))
        par = (rep, salida, time.monotonic())
        self.vivos.append(par)

        def fin(estado):
            if estado == QMediaPlayer.PlaybackState.StoppedState and par in self.vivos:
                self.vivos.remove(par)
                rep.deleteLater()
                salida.deleteLater()
        rep.playbackStateChanged.connect(fin)
        rep.play()
        return _Sonando(rep, par[2])


class EfectosKill(QObject):
    """Sonido de las kills en Windows: QSoundEffect con el WAV ya cargado en
    memoria, que arranca casi al instante. Tres copias por si caen varias
    kills seguidas."""

    def __init__(self, padre=None):
        super().__init__(padre)
        self.clave = None
        self.efectos = []

    def preparar(self, ruta, volumen):
        from PySide6.QtMultimedia import QSoundEffect
        if not ruta or not os.path.exists(ruta):
            return
        try:
            wav, vol = audio.con_volumen(ruta, volumen, wav=True)
        except audio.ErrorAudio:
            return
        if self.clave == (wav, vol):
            return
        self.clave = (wav, vol)
        self.efectos = []
        for _ in range(3):
            e = QSoundEffect(self)
            e.setSource(QUrl.fromLocalFile(wav))
            e.setVolume(vol)
            self.efectos.append(e)

    def tocar(self, ruta, volumen):
        self.preparar(ruta, volumen)
        libres = [e for e in self.efectos if not e.isPlaying()]
        e = (libres or self.efectos or [None])[0]
        if e is not None:
            e.play()
            detector.log('efecto play')


class _Sonando:
    """Imita a un proceso (poll/terminate) para la vista previa."""

    def __init__(self, rep, t0):
        self.rep, self.t0 = rep, t0

    def poll(self):
        from PySide6.QtMultimedia import QMediaPlayer
        try:
            sonando = self.rep.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        except RuntimeError:     # el reproductor ya se borró
            return 0
        return None if sonando or time.monotonic() - self.t0 < 0.4 else 0

    def terminate(self):
        try:
            self.rep.stop()
        except RuntimeError:
            pass


class _Puente(QObject):
    kill = Signal(str, float)     # del hilo del detector a la ventana


def inicio_con_windows(activar=None):
    """Lee o cambia «Iniciar con Windows» (registro HKCU\\...\\Run)."""
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CLAVE_INICIO, 0,
                        winreg.KEY_READ | winreg.KEY_SET_VALUE) as k:
        if activar is None:
            try:
                winreg.QueryValueEx(k, 'SonidoDeKill')
                return True
            except FileNotFoundError:
                return False
        if activar:
            winreg.SetValueEx(k, 'SonidoDeKill', 0, winreg.REG_SZ, f'"{sys.executable}" --bandeja')
        else:
            try:
                winreg.DeleteValue(k, 'SonidoDeKill')
            except FileNotFoundError:
                pass
        return activar


# ---------------------------------------------------------------- trabajos
class _Senales(QObject):
    listo = Signal(object)
    error = Signal(str)


class Trabajo(QRunnable):
    """Corre una función fuera de la ventana (importar o recortar no la congela)."""

    def __init__(self, fn, *args):
        super().__init__()
        self.fn, self.args, self.senales = fn, args, _Senales()

    def run(self):
        try:
            self.senales.listo.emit(self.fn(*self.args))
        except Exception as e:
            self.senales.error.emit(str(e))


# ---------------------------------------------------------------- onda
class Onda(QWidget):
    """Forma de onda con la selección (arrastrable) y las partes detectadas."""
    seleccion = Signal(float, float)
    AGARRE = 8

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self.picos = None
        self.dur = 0.0
        self.ini = self.fin = 0.0
        self.partes = []
        self.cabezal = None
        self._arrastre = None

    def cargar(self, picos, dur, ini, fin, partes):
        self.picos, self.dur, self.partes = picos, max(dur, 0.01), partes
        self.ini, self.fin = ini, fin
        self.update()

    def poner(self, ini, fin):
        self.ini, self.fin = ini, fin
        self.update()

    def _x(self, t):
        return 10 + (self.width() - 20) * t / self.dur

    def _t(self, x):
        return min(self.dur, max(0.0, (x - 10) / max(1, self.width() - 20) * self.dur))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(0, 0, self.width(), self.height())
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(C_FONDO))
        p.drawRoundedRect(r, 10, 10)
        if self.picos is None or len(self.picos) == 0:
            p.setPen(QColor(C_TENUE))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, T('onda_vacia'))
            return
        medio = self.height() / 2
        alto = self.height() / 2 - 14
        # partes detectadas (franja tenue abajo)
        for a, b in self.partes:
            p.setBrush(QColor(255, 138, 61, 40))
            p.drawRoundedRect(QRectF(self._x(a), self.height() - 7, self._x(b) - self._x(a), 4), 2, 2)
        # selección
        xa, xb = self._x(self.ini), self._x(self.fin)
        p.setBrush(QColor(255, 138, 61, 38))
        p.drawRect(QRectF(xa, 4, xb - xa, self.height() - 8))
        # onda: una barra por píxel
        ancho = self.width() - 20
        n = len(self.picos)
        maximo = float(self.picos.max()) or 1.0
        for i in range(int(ancho)):
            j0 = int(i * n / ancho)
            j1 = max(j0 + 1, int((i + 1) * n / ancho))
            v = float(self.picos[j0:j1].max()) / maximo
            x = 10 + i
            dentro = xa <= x <= xb
            p.setPen(QPen(QColor(C_ACENTO if dentro else '#4a5166'), 1))
            h = max(1.0, v * alto)
            p.drawLine(QPointF(x, medio - h), QPointF(x, medio + h))
        # bordes de la selección con agarraderas
        for x in (xa, xb):
            p.setPen(QPen(QColor(C_TEXTO), 2))
            p.drawLine(QPointF(x, 4), QPointF(x, self.height() - 4))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(C_TEXTO))
            p.drawRoundedRect(QRectF(x - 4, medio - 12, 8, 24), 3, 3)
        if self.cabezal is not None:
            x = self._x(self.cabezal)
            p.setPen(QPen(QColor('#ffffff'), 1.5))
            p.drawLine(QPointF(x, 2), QPointF(x, self.height() - 2))

    def mousePressEvent(self, e):
        if self.picos is None:
            return
        x = e.position().x()
        if abs(x - self._x(self.ini)) <= self.AGARRE:
            self._arrastre = 'ini'
        elif abs(x - self._x(self.fin)) <= self.AGARRE:
            self._arrastre = 'fin'
        else:
            self._arrastre = 'nuevo'
            self._ancla = self._t(x)
            self.ini = self.fin = self._ancla

    def mouseMoveEvent(self, e):
        x = e.position().x()
        if self._arrastre is None:
            cerca = self.picos is not None and min(abs(x - self._x(self.ini)), abs(x - self._x(self.fin))) <= self.AGARRE
            self.setCursor(Qt.CursorShape.SizeHorCursor if cerca else Qt.CursorShape.IBeamCursor)
            return
        t = self._t(x)
        if self._arrastre == 'ini':
            self.ini = min(t, self.fin - 0.05)
        elif self._arrastre == 'fin':
            self.fin = max(t, self.ini + 0.05)
        else:
            self.ini, self.fin = min(self._ancla, t), max(self._ancla, t)
        self.update()
        self.seleccion.emit(self.ini, self.fin)

    def mouseReleaseEvent(self, _):
        if self._arrastre == 'nuevo' and self.fin - self.ini < 0.05:
            # un clic suelto selecciona la parte que está debajo
            for a, b in self.partes:
                if a <= self._ancla <= b:
                    self.ini, self.fin = a, b
                    break
            else:
                self.fin = min(self.dur, self.ini + 0.5)
            self.update()
        if self._arrastre:
            self.seleccion.emit(self.ini, self.fin)
        self._arrastre = None


# ---------------------------------------------------------------- ventana
class Ventana(QMainWindow):
    def __init__(self):
        super().__init__()
        self.saliendo = False
        self.aviso_bandeja = False
        self.bandeja = None
        if os.path.exists(ICONO):
            self.setWindowIcon(QIcon(ICONO))
        pantalla = QApplication.primaryScreen()
        libre = pantalla.availableGeometry() if pantalla else None
        if libre:   # que entre en pantallas chicas (laptops, VM)
            self.resize(min(1060, libre.width() - 20), min(720, libre.height() - 40))
        else:
            self.resize(1060, 720)
        self.setAcceptDrops(True)
        try:
            audio.asegurar_predeterminado()
        except audio.ErrorAudio:
            pass
        self.cfg = config.leer_config()
        self.sid = None          # sonido abierto en el editor
        self.meta = None
        self.cambios = False
        self.proceso = None
        self.pool = QThreadPool.globalInstance()
        self._trabajos = set()   # referencias vivas hasta que el trabajo avise
        self.reproductor = ReproductorQt(self) if WINDOWS else None
        self.efectos = EfectosKill(self) if WINDOWS else None
        self.hilo = None
        if WINDOWS:
            # en Windows el detector vive dentro de la app (ícono junto al reloj)
            self.puente = _Puente()
            self.puente.kill.connect(self._sonar_kill)
            self.detector = detector.Detector(tocar=lambda r, v: self.puente.kill.emit(r, v))
            self.hilo = threading.Thread(target=self.detector.correr, daemon=True, name='detector')
            self.hilo.start()

        self._construir()
        self.recargar_lista()
        self._precargar()
        self.reloj = QTimer(self, interval=1000, timeout=self.refrescar_estado)
        self.reloj.start()
        self.refrescar_estado()
        self.cabezal = QTimer(self, interval=30, timeout=self._mover_cabezal)
        if WINDOWS and QSystemTrayIcon.isSystemTrayAvailable():
            self._crear_bandeja()

    # ----- construcción
    def _construir(self):
        """Arma toda la ventana con los textos del idioma elegido (se vuelve a
        llamar al cambiar de idioma)."""
        self.setWindowTitle(T('app'))
        raiz = QWidget()
        self.setCentralWidget(raiz)
        v = QVBoxLayout(raiz)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(14)
        v.addLayout(self._barra())
        h = QHBoxLayout()
        h.setSpacing(14)
        h.addWidget(self._biblioteca(), 0)
        h.addWidget(self._editor(), 1)
        v.addLayout(h, 1)
        v.addWidget(self._ajustes())

    def _barra(self):
        h = QHBoxLayout()
        t = etiqueta(T('app'), 'titulo')
        sub = etiqueta(T('subtitulo'), 'tenue')
        col = QVBoxLayout()
        col.setSpacing(0)
        col.addWidget(t)
        col.addWidget(sub)
        h.addLayout(col)
        h.addStretch(1)
        self.lbl_estado = QLabel()
        self.lbl_estado.setTextFormat(Qt.TextFormat.RichText)
        h.addWidget(self.lbl_estado)
        h.addSpacing(18)
        apoyar = QPushButton(T('apoyar'))
        apoyar.setObjectName('apoyar')
        apoyar.setToolTip(T('apoyar_tip'))
        apoyar.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(URL_APOYAR)))
        h.addWidget(apoyar)
        h.addSpacing(18)
        self.chk_activo = QCheckBox(T('sonar_cada_kill'))
        self.chk_activo.setObjectName('interruptor')
        self.chk_activo.setChecked(self.cfg.get('activo', True))
        self.chk_activo.toggled.connect(self._activo)
        h.addWidget(self.chk_activo)
        return h

    def _biblioteca(self):
        f = panel()
        f.setFixedWidth(290)
        v = QVBoxLayout(f)
        v.setContentsMargins(14, 14, 14, 14)
        v.addWidget(etiqueta(T('tus_sonidos'), 'seccion'))
        self.lista = QListWidget()
        self.lista.setWordWrap(True)
        self.lista.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.lista.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.lista.currentItemChanged.connect(self._elegido)
        v.addWidget(self.lista, 1)
        self.btn_subir = QPushButton(T('subir'))
        self.btn_subir.setObjectName('primario')
        self.btn_subir.clicked.connect(self.subir)
        v.addWidget(self.btn_subir)
        ayuda = etiqueta(T('arrastrar'), 'tenue')
        ayuda.setWordWrap(True)
        v.addWidget(ayuda)
        self.btn_borrar = QPushButton(T('eliminar'))
        self.btn_borrar.clicked.connect(self.borrar)
        v.addWidget(self.btn_borrar)
        return f

    def _editor(self):
        f = panel()
        v = QVBoxLayout(f)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(10)
        fila = QHBoxLayout()
        fila.addWidget(etiqueta(T('recorte'), 'seccion'))
        fila.addStretch(1)
        self.lbl_en_uso = etiqueta('')
        fila.addWidget(self.lbl_en_uso)
        v.addLayout(fila)
        fila = QHBoxLayout()
        self.txt_nombre = QLineEdit()
        self.txt_nombre.setPlaceholderText(T('nombre_ph'))
        self.txt_nombre.editingFinished.connect(self._renombrar)
        fila.addWidget(self.txt_nombre, 1)
        self.lbl_archivo = etiqueta('', 'tenue')
        fila.addWidget(self.lbl_archivo)
        v.addLayout(fila)

        self.onda = Onda()
        self.onda.seleccion.connect(self._sel_desde_onda)
        v.addWidget(self.onda)

        fila = QHBoxLayout()
        fila.addWidget(etiqueta(T('partes'), 'tenue'))
        self.caja_partes = QHBoxLayout()
        self.caja_partes.setSpacing(6)
        fila.addLayout(self.caja_partes)
        fila.addStretch(1)
        v.addLayout(fila)
        ayuda = etiqueta(T('ayuda_recorte'), 'tenue')
        ayuda.setWordWrap(True)
        v.addWidget(ayuda)

        fila = QHBoxLayout()
        fila.addWidget(QLabel(T('desde')))
        self.sp_ini = self._spin()
        fila.addWidget(self.sp_ini)
        fila.addWidget(QLabel(T('hasta')))
        self.sp_fin = self._spin()
        fila.addWidget(self.sp_fin)
        self.lbl_largo = etiqueta('', 'tenue')
        fila.addWidget(self.lbl_largo)
        fila.addStretch(1)
        v.addLayout(fila)
        self.chk_igualar = QCheckBox(T('igualar'))
        self.chk_igualar.toggled.connect(lambda _: self._marcar_cambio())
        v.addWidget(self.chk_igualar)

        fila = QHBoxLayout()
        self.btn_escuchar = QPushButton(T('escuchar'))
        self.btn_escuchar.clicked.connect(self.escuchar)
        fila.addWidget(self.btn_escuchar)
        self.btn_guardar = QPushButton(T('guardar_recorte'))
        self.btn_guardar.clicked.connect(lambda: self.guardar())
        fila.addWidget(self.btn_guardar)
        fila.addStretch(1)
        self.lbl_aviso = etiqueta('', 'tenue')
        fila.addWidget(self.lbl_aviso)
        self.btn_usar = QPushButton(T('usar'))
        self.btn_usar.setObjectName('primario')
        self.btn_usar.clicked.connect(self.usar)
        fila.addWidget(self.btn_usar)
        v.addLayout(fila)
        v.addStretch(1)
        return f

    def _spin(self):
        s = QDoubleSpinBox()
        s.setDecimals(2)
        s.setSingleStep(0.05)
        s.setSuffix(' s')
        s.setFixedWidth(100)
        s.valueChanged.connect(self._sel_desde_spin)
        return s

    def _ajustes(self):
        f = panel()
        h = QHBoxLayout(f)
        h.setContentsMargins(16, 12, 16, 12)
        h.setSpacing(22)

        col = QVBoxLayout()
        col.addWidget(etiqueta(T('volumen'), 'seccion'))
        fila = QHBoxLayout()
        self.sl_vol = QSlider(Qt.Orientation.Horizontal)
        self.sl_vol.setRange(0, 150)
        self.sl_vol.setValue(int(round(self.cfg.get('volumen', 1.0) * 100)))
        self.sl_vol.setFixedWidth(180)
        self.lbl_vol = QLabel()
        self.sl_vol.valueChanged.connect(self._vol)
        self._vol(self.sl_vol.value(), guardar=False)
        fila.addWidget(self.sl_vol)
        fila.addWidget(self.lbl_vol)
        b = QPushButton(T('probar'))
        b.clicked.connect(self.probar_activo)
        fila.addWidget(b)
        col.addLayout(fila)
        col.addSpacing(6)
        col.addWidget(etiqueta(T('idioma'), 'seccion'))
        self.cmb_idioma = QComboBox()
        for codigo, nombre in idiomas.IDIOMAS:
            self.cmb_idioma.addItem(nombre, codigo)
        self.cmb_idioma.setCurrentIndex(idiomas.CODIGOS.index(idiomas.elegido()))
        self.cmb_idioma.setMaxVisibleItems(20)
        self.cmb_idioma.setFixedWidth(180)
        self.cmb_idioma.currentIndexChanged.connect(self._cambiar_idioma)
        col.addWidget(self.cmb_idioma)
        h.addLayout(col)

        col = QVBoxLayout()
        col.addWidget(etiqueta(T('nick_titulo'), 'seccion'))
        self.txt_nick = QLineEdit(self.cfg.get('nick', ''))
        self.txt_nick.setFixedWidth(200)
        self.txt_nick.setPlaceholderText(T('nick_ph'))
        self.txt_nick.setToolTip(T('nick_tip'))
        self.txt_nick.editingFinished.connect(self._guardar_nick)
        col.addWidget(self.txt_nick)
        self.lbl_falta_nick = etiqueta(T('falta_nick_aviso'))
        self.lbl_falta_nick.setWordWrap(True)
        self.lbl_falta_nick.setMaximumWidth(220)
        self.lbl_falta_nick.setStyleSheet(f'color: {C_MAL}; font-weight: 600;')
        col.addWidget(self.lbl_falta_nick)
        self._marcar_nick()
        col.addStretch(1)
        h.addLayout(col)

        col = QVBoxLayout()
        col.addWidget(etiqueta(T('cuando'), 'seccion'))
        col.addWidget(etiqueta(T('al_derribar'), 'tenue'))
        self.chk_incendio = QCheckBox(T('incendiar'))
        self.chk_incendio.setChecked(self.cfg.get('tambien_incendio', False))
        self.chk_incendio.toggled.connect(lambda v: self._cfg(tambien_incendio=v))
        col.addWidget(self.chk_incendio)
        if WINDOWS:
            self.chk_inicio = QCheckBox(T('iniciar_windows'))
            try:
                self.chk_inicio.setChecked(inicio_con_windows())
            except OSError:
                self.chk_inicio.setEnabled(False)
            self.chk_inicio.toggled.connect(lambda v: inicio_con_windows(v))
            col.addWidget(self.chk_inicio)
        col.addStretch(1)
        h.addLayout(col)

        col = QVBoxLayout()
        col.addWidget(etiqueta(T('ultimas'), 'seccion'))
        self.lbl_kills = etiqueta(T('ninguna'), 'tenue')
        self.lbl_kills.setWordWrap(True)
        self.lbl_kills.setTextFormat(Qt.TextFormat.RichText)
        col.addWidget(self.lbl_kills)
        col.addStretch(1)
        h.addLayout(col, 1)
        return f

    def _lanzar(self, fn, args, listo, error):
        t = Trabajo(fn, *args)
        t.setAutoDelete(False)
        self._trabajos.add(t)

        def fin_ok(r):
            self._trabajos.discard(t)
            listo(r)

        def fin_mal(txt):
            self._trabajos.discard(t)
            error(txt)
        t.senales.listo.connect(fin_ok, Qt.ConnectionType.QueuedConnection)
        t.senales.error.connect(fin_mal, Qt.ConnectionType.QueuedConnection)
        self.pool.start(t)

    # ----- configuración y estado
    def _cfg(self, **cambios):
        self.cfg = config.leer_config()
        self.cfg.update(cambios)
        config.guardar_config(self.cfg)
        self.recargar_lista()
        self._precargar()

    def _cambiar_idioma(self, i):
        codigo = self.cmb_idioma.itemData(i)
        if not codigo or codigo == idiomas.elegido():
            return
        idiomas.poner(codigo)
        idiomas.traducir_qt(QApplication.instance(), codigo)
        self._cfg(idioma=codigo)
        # el combo que avisó es parte de lo que se rehace: esperar a salir de su señal
        QTimer.singleShot(0, self._reconstruir)

    def _reconstruir(self):
        sid = self.sid
        self._parar()
        self.sid = self.meta = None
        self._construir()
        self.recargar_lista(seleccionar=sid)
        self._precargar()
        self.refrescar_estado()
        if self.bandeja:
            self._menu_bandeja()

    def _guardar_nick(self):
        self._cfg(nick=self.txt_nick.text().strip())
        self._marcar_nick()
        self.refrescar_estado()

    def _marcar_nick(self):
        falta = not self.txt_nick.text().strip()
        self.lbl_falta_nick.setVisible(falta)
        self.txt_nick.setStyleSheet(f'border-color: {C_MAL};' if falta else '')

    def _vol(self, valor, guardar=True):
        self.lbl_vol.setText(f'{valor} %')
        if guardar:
            self._cfg(volumen=valor / 100)

    def servicio_activo(self):
        if WINDOWS:
            return self.hilo is not None and self.hilo.is_alive()
        r = subprocess.run(['systemctl', '--user', 'is-active', SERVICIO], capture_output=True, text=True)
        return r.stdout.strip() == 'active'

    def _activo(self, v):
        self._cfg(activo=v)
        if self.bandeja:
            self.accion_activo.blockSignals(True)
            self.accion_activo.setChecked(v)
            self.accion_activo.blockSignals(False)

    # ----- Windows: sonido de las kills e ícono junto al reloj
    def _sonar_kill(self, ruta, volumen):
        self.efectos.tocar(ruta, volumen)

    def _precargar(self):
        sid = self.cfg.get('sonido')
        if self.efectos and sid:
            self.efectos.preparar(config.ruta_clip(sid), self.cfg.get('volumen', 1.0))

    def _reproducir(self, ruta, volumen):
        if WINDOWS:
            return self.reproductor.tocar(ruta, volumen)
        return audio.reproducir(ruta, volumen)

    def _crear_bandeja(self):
        self.bandeja = QSystemTrayIcon(self.windowIcon(), self)
        self.bandeja.setToolTip(T('app'))
        self._menu_bandeja()
        self.bandeja.activated.connect(
            lambda r: self.mostrar() if r in (QSystemTrayIcon.ActivationReason.Trigger,
                                              QSystemTrayIcon.ActivationReason.DoubleClick) else None)
        self.bandeja.show()

    def _menu_bandeja(self):
        menu = QMenu()
        abrir = QAction(T('abrir_app'), menu)
        abrir.triggered.connect(self.mostrar)
        menu.addAction(abrir)
        self.accion_activo = QAction(T('sonar_cada_kill'), menu, checkable=True)
        self.accion_activo.setChecked(self.cfg.get('activo', True))
        self.accion_activo.toggled.connect(lambda v: self.chk_activo.setChecked(v))
        menu.addAction(self.accion_activo)
        apoyar = QAction(T('apoyar_proyecto'), menu)
        apoyar.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(URL_APOYAR)))
        menu.addAction(apoyar)
        menu.addSeparator()
        salir = QAction(T('salir'), menu)
        salir.triggered.connect(self.salir)
        menu.addAction(salir)
        self.menu_bandeja = menu
        self.bandeja.setContextMenu(menu)

    def mostrar(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def salir(self):
        self.saliendo = True
        if WINDOWS and self.hilo:
            self.detector.parar = True
        self.close()
        QApplication.quit()

    def refrescar_estado(self):
        e = config.leer_estado()
        if not self.servicio_activo():
            texto, color = T('detector_apagado'), C_MAL
        elif not config.leer_config().get('nick'):
            texto, color = T('falta_nick'), C_MAL
        elif e.get('conectado') and time.time() - e.get('actualizado', 0) < 3600:
            texto, color = T('conectado'), C_OK
        else:
            texto, color = T('esperando'), C_TENUE
        self.lbl_estado.setText(f'<span style="color:{color}">●</span>&nbsp; {texto}')
        if self.bandeja:
            self.bandeja.setToolTip(f"{T('app')} — {texto}")
        ultimas = e.get('ultimas', [])[:3]
        if ultimas:
            filas = [f"<b>{u['hora']}</b> &nbsp;{self._corto(u['msg'])}" for u in ultimas]
            self.lbl_kills.setText(T('en_sesion', n=e.get('kills_sesion', 0)) + '<br>' + '<br>'.join(filas))

    @staticmethod
    def _corto(msg):
        v = detector.victima(msg)
        return '→ ' + v[:48] if v else msg[:48]

    # ----- biblioteca
    def recargar_lista(self, seleccionar=None):
        actual = seleccionar or self.sid
        activo = self.cfg.get('sonido')
        self.lista.blockSignals(True)
        self.lista.clear()
        for m in config.listar_sonidos():
            largo = m['fin'] - m['inicio']
            marca = '★  ' if m['id'] == activo else ''
            it = QListWidgetItem(f"{marca}{m['nombre']}\n{seg(largo)}" + (f"  ·  {T('en_uso_lista')}" if m['id'] == activo else ''))
            it.setData(Qt.ItemDataRole.UserRole, m['id'])
            self.lista.addItem(it)
            if m['id'] == actual:
                self.lista.setCurrentItem(it)
        if self.lista.currentItem() is None and self.lista.count():
            self.lista.setCurrentRow(0)
        self.lista.blockSignals(False)
        item = self.lista.currentItem()
        if item is None:
            if self.sid is not None or self.meta is not None:
                self._abrir(None)
        elif item.data(Qt.ItemDataRole.UserRole) != self.sid:
            self._abrir(item.data(Qt.ItemDataRole.UserRole))
        self._actualizar_botones()

    def _elegido(self, item, _anterior):
        if item is None:
            return
        sid = item.data(Qt.ItemDataRole.UserRole)
        if sid != self.sid:
            self._abrir(sid)

    def _abrir(self, sid):
        self._parar()
        self.sid, self.meta, self.cambios = sid, (config.leer_meta(sid) if sid else None), False
        while self.caja_partes.count():
            w = self.caja_partes.takeAt(0).widget()
            if w:
                w.deleteLater()
        if not self.meta:
            self.onda.cargar(None, 0, 0, 0, [])
            self.txt_nombre.clear()
            self.lbl_archivo.clear()
            self._actualizar_botones()
            return
        m = self.meta
        self.txt_nombre.setText(m['nombre'])
        arch = m.get('archivo', '')
        self.lbl_archivo.setText(arch if len(arch) <= 34 else arch[:31] + '…')
        self.lbl_archivo.setToolTip(arch)
        picos = audio.forma_de_onda(config.ruta_original(sid))
        self.partes = audio.detectar_partes(picos)
        dur = m['duracion_original']
        self.onda.cargar(picos, dur, m['inicio'], m['fin'], self.partes)
        self.botones_partes = []
        for i, (a, b) in enumerate(self.partes[:8]):
            btn = QPushButton(f'{i + 1}')
            btn.setObjectName('parte')
            btn.setCheckable(True)
            btn.setToolTip(f'{seg(a)} – {seg(b)}')
            btn.clicked.connect(lambda _=False, a=a, b=b: self._poner_sel(a, b))
            self.caja_partes.addWidget(btn)
            self.botones_partes.append((btn, a, b))
        for s in (self.sp_ini, self.sp_fin):
            s.blockSignals(True)
            s.setRange(0, dur)
        self.sp_ini.setValue(m['inicio'])
        self.sp_fin.setValue(m['fin'])
        for s in (self.sp_ini, self.sp_fin):
            s.blockSignals(False)
        self.chk_igualar.blockSignals(True)
        self.chk_igualar.setChecked(m.get('igualar', True))
        self.chk_igualar.blockSignals(False)
        self._refrescar_sel()
        self.cambios = False
        self._actualizar_botones()

    def _actualizar_botones(self):
        hay = self.meta is not None
        for w in (self.btn_escuchar, self.btn_borrar, self.txt_nombre, self.sp_ini, self.sp_fin, self.chk_igualar):
            w.setEnabled(hay)
        self.btn_guardar.setEnabled(hay and self.cambios)
        en_uso = hay and self.cfg.get('sonido') == self.sid
        self.btn_usar.setEnabled(hay and (self.cambios or not en_uso))
        self.btn_usar.setText(T('guardar_usar') if self.cambios else
                              (T('ya_suena') if en_uso else T('usar')))
        self.lbl_en_uso.setText(f'<span style="color:{C_OK}">{T("en_uso")}</span>' if en_uso else '')
        self.lbl_aviso.setText(T('sin_guardar') if self.cambios else '')

    # ----- selección
    def _poner_sel(self, a, b):
        self.onda.poner(a, b)
        self._sel_desde_onda(a, b)

    def _sel_desde_onda(self, a, b):
        for s, v in ((self.sp_ini, a), (self.sp_fin, b)):
            s.blockSignals(True)
            s.setValue(v)
            s.blockSignals(False)
        self._marcar_cambio()

    def _sel_desde_spin(self, _):
        a, b = self.sp_ini.value(), self.sp_fin.value()
        if b - a < 0.05:
            return
        self.onda.poner(a, b)
        self._marcar_cambio()

    def _refrescar_sel(self):
        a, b = self.onda.ini, self.onda.fin
        self.lbl_largo.setText(T('dura', t=seg(b - a)))
        for btn, pa, pb in getattr(self, 'botones_partes', []):
            btn.setChecked(abs(pa - a) < 0.02 and abs(pb - b) < 0.02)

    def _marcar_cambio(self):
        if not self.meta:
            return
        self._refrescar_sel()
        m = self.meta
        self.cambios = (abs(self.onda.ini - m['inicio']) > 1e-3 or abs(self.onda.fin - m['fin']) > 1e-3
                        or self.chk_igualar.isChecked() != m.get('igualar', True))
        self._actualizar_botones()

    # ----- acciones
    def subir(self):
        ruta, _ = QFileDialog.getOpenFileName(self, T('elegir_archivo'), os.path.expanduser('~/Downloads'),
                                              f"{T('filtro_audio')} ({EXTENSIONES});;{T('filtro_todos')} (*)")
        if ruta:
            self.importar(ruta)

    def importar(self, ruta):
        self.btn_subir.setEnabled(False)
        self.btn_subir.setText(T('cargando'))
        self._lanzar(audio.importar, (ruta,), self._importado, self._error_import)

    def _importado(self, sid):
        self._fin_import()
        self.sid = None
        self.recargar_lista(seleccionar=sid)

    def _error_import(self, texto):
        self._fin_import()
        QMessageBox.warning(self, T('no_subir'), texto)

    def _fin_import(self):
        self.btn_subir.setEnabled(True)
        self.btn_subir.setText(T('subir'))

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        for u in e.mimeData().urls():
            if u.isLocalFile():
                self.importar(u.toLocalFile())
                break

    def _renombrar(self):
        if self.meta and self.txt_nombre.text().strip() and self.txt_nombre.text().strip() != self.meta['nombre']:
            self.meta['nombre'] = self.txt_nombre.text().strip()[:60]
            config.guardar_meta(self.sid, self.meta)
            self.recargar_lista()

    def guardar(self, despues=None):
        if not self.meta:
            return
        self.meta.update(inicio=self.onda.ini, fin=self.onda.fin, igualar=self.chk_igualar.isChecked())
        config.guardar_meta(self.sid, self.meta)
        self.btn_guardar.setEnabled(False)
        self.lbl_aviso.setText(T('guardando'))
        def listo(_):
            self.cambios = False
            self.recargar_lista()
            self._actualizar_botones()
            if despues:
                despues()
        def mal(txt):
            self._actualizar_botones()
            QMessageBox.warning(self, T('no_guardar'), txt)
        self._lanzar(audio.renderizar, (self.sid,), listo, mal)

    def usar(self):
        def activar():
            self._cfg(sonido=self.sid)
            self._actualizar_botones()
        if self.cambios:
            self.guardar(despues=activar)
        else:
            activar()

    def borrar(self):
        if not self.meta:
            return
        r = QMessageBox.question(self, T('eliminar'), T('eliminar_pregunta', n=self.meta['nombre']))
        if r != QMessageBox.StandardButton.Yes:
            return
        sid = self.sid
        config.borrar_sonido(sid)
        if self.cfg.get('sonido') == sid:
            self._cfg(sonido=None)
        self.sid = None
        self.recargar_lista()

    def escuchar(self):
        if not self.meta:
            return
        if self.proceso and self.proceso.poll() is None:
            self._parar()
            return
        a, b = self.onda.ini, self.onda.fin
        try:
            ruta = audio.vista_previa(self.sid, a, b, self.chk_igualar.isChecked())
        except audio.ErrorAudio as e:
            QMessageBox.warning(self, T('no_escuchar'), str(e))
            return
        self.proceso = self._reproducir(ruta, self.sl_vol.value() / 100)
        self._t0, self._ta, self._tb = time.monotonic(), a, b
        self.btn_escuchar.setText(T('detener'))
        self.cabezal.start()

    def _mover_cabezal(self):
        t = self._ta + time.monotonic() - self._t0
        if t > self._tb or (self.proceso and self.proceso.poll() is not None):
            self._parar()
            return
        self.onda.cabezal = t
        self.onda.update()

    def _parar(self):
        self.cabezal.stop() if hasattr(self, 'cabezal') else None
        if self.proceso and self.proceso.poll() is None:
            self.proceso.terminate()
        self.proceso = None
        self.onda.cabezal = None
        self.onda.update()
        self.btn_escuchar.setText(T('escuchar'))

    def probar_activo(self):
        sid = self.cfg.get('sonido')
        if not sid or not os.path.exists(config.ruta_clip(sid)):
            QMessageBox.information(self, T('sin_sonido'), T('sin_sonido_txt', usar=T('usar')))
            return
        self._reproducir(config.ruta_clip(sid), self.sl_vol.value() / 100)

    def closeEvent(self, e):
        self._parar()
        if self.bandeja and not self.saliendo:
            # en Windows cerrar la ventana no apaga el detector
            e.ignore()
            self.hide()
            if not self.aviso_bandeja:
                self.aviso_bandeja = True
                self.bandeja.showMessage(T('sigue_activo'), T('sigue_activo_txt'),
                                         QSystemTrayIcon.MessageIcon.Information, 4000)
            return
        super().closeEvent(e)


def _ya_abierta():
    """Si la app ya corre, le pide que se muestre y devuelve True."""
    s = QLocalSocket()
    s.connectToServer(NOMBRE_INSTANCIA)
    if s.waitForConnected(300):
        s.write(b'mostrar')
        s.waitForBytesWritten(300)
        return True
    return False


def main():
    app = QApplication(sys.argv)
    idiomas.elegido()
    app.setApplicationName(T('app'))
    idiomas.traducir_qt(app, idiomas.elegido())
    app.setDesktopFileName('killsound')
    if os.path.exists(ICONO):
        app.setWindowIcon(QIcon(ICONO))
    bandeja = '--bandeja' in sys.argv
    servidor = None
    if WINDOWS:
        if _ya_abierta():
            return
        QApplication.setQuitOnLastWindowClosed(False)
        servidor = QLocalServer()
        QLocalServer.removeServer(NOMBRE_INSTANCIA)
        servidor.listen(NOMBRE_INSTANCIA)
    app.setStyleSheet(ESTILO)
    f = QFont(app.font())
    f.setPointSizeF(10.5)
    app.setFont(f)
    w = Ventana()
    if servidor:
        servidor.newConnection.connect(lambda: (servidor.nextPendingConnection(), w.mostrar()))
    if not (bandeja and w.bandeja):
        w.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
