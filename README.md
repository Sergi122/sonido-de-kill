# Sonido de Kill

Suena el audio que tú elijas cada vez que haces una kill en **War Thunder**. Para Windows y Linux, en los 20 idiomas del juego.

**Página:** https://sonido-de-kill.web.app · **Descargas:** [Releases](https://github.com/Sergi122/sonido-de-kill/releases/latest)

- Sube cualquier audio o video (mp3, ogg, wav, mp4, mkv…), recorta la parte que quieres sobre la forma de onda y úsala para tus kills.
- «Partes detectadas» corta solo por silencios; «Igualar volumen» hace que se oiga sobre el ruido del juego.
- Volumen hasta 150 %, opción de que suene también al incendiar, historial de tus últimas kills.
- Reconoce las kills con el juego en **cualquier idioma** (usa los textos oficiales del juego en los 20 idiomas).
- La app misma está en los 20 idiomas de War Thunder; se cambia en los ajustes.

## Cómo funciona

War Thunder publica los mensajes de la partida en `http://localhost:8111/hudmsg` (el mismo servidor del mapa en el navegador). La app los lee y, cuando un mensaje dice que **tu nick** derribó o destruyó a alguien, reproduce tu sonido. **No toca ningún archivo del juego** ni inyecta nada.

Escribe tu nick tal como sale en la partida, sin el tag del escuadrón.

## Instalar

**Windows:** descarga `SonidoDeKill-x.y.z-Setup.exe` de [Releases](https://github.com/Sergi122/sonido-de-kill/releases/latest) y ábrelo (no pide administrador). La app queda junto al reloj escuchando tus kills; puede iniciar con Windows.

**Linux:** descarga `SonidoDeKill-x.y.z-linux.tar.gz`, descomprime y ejecuta `./instalar.sh` (sin sudo). Aparece «Sonido de Kill» en el menú y el detector corre como servicio de usuario (`killsound.service`). Quitar: `./instalar.sh --quitar`.
Requiere: python3, PySide6, numpy, ffmpeg y PipeWire (`pw-play`). En Arch: `sudo pacman -S pyside6 python-numpy ffmpeg pipewire`.

## Desarrollo

- Pruebas sin abrir ventanas: `python3 -s pruebas/prueba_logica.py` y `python3 -s pruebas/prueba_ventana.py /tmp/capturas`.
- Traducciones: `killsound/idiomas.py` (las pruebas comprueban que los 20 idiomas tengan todos los textos).
- Windows: `windows/` tiene el `.spec` de PyInstaller, el instalador de Inno Setup y el script de compilación (necesita `ffmpeg\ffmpeg.exe` junto a las fuentes).

## Licencia

Código bajo licencia MIT (ver `LICENSE`). El sonido predeterminado (`killsound/predeterminado/muhehehe.ogg`) es un fragmento de un video de internet y **no** está cubierto por la licencia MIT; pertenece a su autor.

Si te gusta, puedes apoyar el proyecto en [GitHub Sponsors](https://github.com/sponsors/Sergi122) ❤

---

# Kill Sound (English)

Plays the audio you choose every time you get a kill in **War Thunder**. Windows and Linux, in all 20 game languages.

- Upload any audio or video, trim the part you want on the waveform and use it for your kills.
- Detects kills with the game set to **any language** (it uses the game's own kill texts in all 20 languages).
- The app itself is translated into the 20 War Thunder languages; change it in the settings.
- It only reads the game's local `http://localhost:8111/hudmsg` page — it does **not** modify game files or inject anything.

**Windows:** run `SonidoDeKill-x.y.z-Setup.exe` from [Releases](https://github.com/Sergi122/sonido-de-kill/releases/latest) (no admin needed).
**Linux:** extract `SonidoDeKill-x.y.z-linux.tar.gz` and run `./instalar.sh` (needs python3, PySide6, numpy, ffmpeg, PipeWire).

Code: MIT. The default sound clip is not covered by the MIT license.
