# PyInstaller: carpeta con SonidoDeKill.exe (sin consola) + ffmpeg.
a = Analysis(
    ['entrada.py'],
    pathex=['.'],
    binaries=[('ffmpeg\\ffmpeg.exe', 'ffmpeg')],
    datas=[('killsound\\icono.svg', 'killsound'), ('killsound\\predeterminado\\muhehehe.ogg', 'killsound\\predeterminado'), ('killsound\\predeterminado\\info.json', 'killsound\\predeterminado')],
    hiddenimports=['PySide6.QtMultimedia', 'PySide6.QtNetwork'],
    excludes=['tkinter', 'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtQml',
              'PySide6.QtQuick', 'PySide6.Qt3DCore', 'PySide6.QtCharts', 'PySide6.QtDataVisualization',
              'PySide6.QtPdf', 'PySide6.QtSql', 'PySide6.QtBluetooth', 'PySide6.QtPositioning'],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='SonidoDeKill', console=False,
          icon='icono.ico', version=None, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name='SonidoDeKill', upx=False)
