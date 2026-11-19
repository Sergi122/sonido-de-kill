#!/usr/bin/env bash
# Instala Sonido de Kill para este usuario (sin sudo): menú de apps, ícono y
# el detector como servicio que arranca solo. Uso: ./instalar.sh  |  ./instalar.sh --quitar
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
DIR="$PWD"
APPS=~/.local/share/applications
ICONOS=~/.local/share/icons/hicolor/scalable/apps
SERV=~/.config/systemd/user
if [ "${1:-}" = "--quitar" ]; then
  systemctl --user disable --now killsound.service 2>/dev/null || true
  rm -f "$SERV/killsound.service" "$APPS/killsound.desktop" "$ICONOS/killsound.svg" ~/.local/bin/sonido-de-kill
  systemctl --user daemon-reload
  echo "Quitado (tus sonidos siguen en ~/.local/share/killsound)."
  exit 0
fi
for dep in python3 ffmpeg ffprobe pw-play; do
  command -v "$dep" >/dev/null || { echo "Falta $dep"; exit 1; }
done
python3 -c 'import PySide6, numpy' 2>/dev/null || { echo "Falta PySide6 o numpy (pacman -S pyside6 python-numpy)"; exit 1; }
mkdir -p "$APPS" "$ICONOS" "$SERV" ~/.local/bin
cp killsound/icono.svg "$ICONOS/killsound.svg"
ln -sf "$DIR/sonido-de-kill" ~/.local/bin/sonido-de-kill
cat > "$APPS/killsound.desktop" <<D
[Desktop Entry]
Type=Application
Name=Sonido de Kill
Comment=Un sonido cada vez que haces una kill en War Thunder
Exec=$DIR/sonido-de-kill
Icon=killsound
Categories=Game;
Keywords=war thunder;kill;sonido;
StartupWMClass=killsound
D
cat > "$SERV/killsound.service" <<S
[Unit]
Description=Sonido de Kill: detector de kills de War Thunder

[Service]
ExecStart=$DIR/sonido-de-kill detector
Restart=always
RestartSec=5
Nice=10

[Install]
WantedBy=default.target
S
systemctl --user daemon-reload
systemctl --user enable --now killsound.service >/dev/null
update-desktop-database "$APPS" 2>/dev/null || true
echo "Instalado. Ábrelo desde el menú: «Sonido de Kill»."
