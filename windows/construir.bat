@echo off
rem Compila Sonido de Kill para Windows. Uso (Win+R): cmd /k \\VBoxSvr\ks\construir.bat
setlocal
set KS=\\VBoxSvr\ks
set LOG=%KS%\salida\construir.log
set PY=C:\ks\python\python.exe
echo === inicio %date% %time% > "%LOG%"
if not exist "%PY%" (
  echo instalando Python... >> "%LOG%"
  "%KS%\descargas\python-3.12.10-amd64.exe" /quiet InstallAllUsers=0 PrependPath=0 Include_launcher=0 Include_test=0 Include_doc=0 TargetDir=C:\ks\python >> "%LOG%" 2>&1
)
"%PY%" --version >> "%LOG%" 2>&1 || goto error
echo instalando librerias... >> "%LOG%"
"%PY%" -m pip install --no-index --find-links "%KS%\wheels" pyside6-essentials pyside6-addons numpy pyinstaller >> "%LOG%" 2>&1 || goto error
if not exist "C:\ks\inno\ISCC.exe" (
  echo instalando Inno Setup... >> "%LOG%"
  "%KS%\descargas\innosetup-7.1.1-x64.exe" /VERYSILENT /SUPPRESSMSGBOXES /CURRENTUSER /NORESTART /DIR=C:\ks\inno >> "%LOG%" 2>&1
)
echo copiando fuentes... >> "%LOG%"
if exist C:\ks\build rmdir /s /q C:\ks\build
xcopy /e /i /q /y "%KS%\src" C:\ks\build >> "%LOG%" 2>&1
xcopy /e /i /q /y "%KS%\ffmpeg" C:\ks\build\ffmpeg >> "%LOG%" 2>&1
pushd C:\ks\build
echo pyinstaller... >> "%LOG%"
"%PY%" -m PyInstaller --noconfirm --clean SonidoDeKill.spec >> "%LOG%" 2>&1 || goto error
echo instalador... >> "%LOG%"
"C:\ks\inno\ISCC.exe" /Q instalador.iss >> "%LOG%" 2>&1 || goto error
copy /y salida\*.exe "%KS%\salida\" >> "%LOG%" 2>&1
popd
echo === FIN OK %date% %time% >> "%LOG%"
exit /b 0
:error
echo === ERROR %errorlevel% >> "%LOG%"
exit /b 1
