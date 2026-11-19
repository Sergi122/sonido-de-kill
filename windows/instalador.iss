; Instalador de Sonido de Kill (Inno Setup). Sin permisos de administrador.
#define Version "1.1.0"
[Setup]
AppId={{6D1F3A52-7C1B-4F0E-9A3D-5B2C8E4F1A77}
AppName=Sonido de Kill
AppVersion={#Version}
AppPublisher=Sergi122
AppPublisherURL=https://github.com/Sergi122
DefaultDirName={localappdata}\Programs\SonidoDeKill
DefaultGroupName=Sonido de Kill
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=salida
OutputBaseFilename=SonidoDeKill-{#Version}-Setup
SetupIconFile=icono.ico
UninstallDisplayIcon={app}\SonidoDeKill.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=force

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "escritorio"; Description: "Crear un acceso directo en el escritorio"
Name: "inicio"; Description: "Iniciar con Windows (escucha tus kills sin abrir la ventana)"

[Files]
Source: "dist\SonidoDeKill\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\Sonido de Kill"; Filename: "{app}\SonidoDeKill.exe"
Name: "{autodesktop}\Sonido de Kill"; Filename: "{app}\SonidoDeKill.exe"; Tasks: escritorio

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "SonidoDeKill"; ValueData: """{app}\SonidoDeKill.exe"" --bandeja"; Tasks: inicio; Flags: uninsdeletevalue

[Run]
Filename: "{app}\SonidoDeKill.exe"; Description: "Abrir Sonido de Kill"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "taskkill.exe"; Parameters: "/IM SonidoDeKill.exe /F"; Flags: runhidden; RunOnceId: "cerrar"
