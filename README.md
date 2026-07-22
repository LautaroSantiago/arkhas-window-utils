# Arkhas

Utilidad de control rápido de ventanas para Linux, activada por un atajo global, con interfaz propia en GTK3. Pensada para Linux Mint MATE, compatible con cualquier entorno GTK3/X11.

## Qué es Arkhas

Arkhas empezó como un divisor de pantalla: un atajo que abre un selector de ventanas y acomoda dos, una al lado de la otra. Con el uso fue creciendo hasta cubrir un puñado de acciones rápidas sobre ventanas que antes requerían salir del teclado — cerrar, maximizar, ver qué está consumiendo recursos — todas disparadas desde el mismo picker.

Arkhas **no es un gestor de ventanas**: no reemplaza a Marco (ni a ningún otro), no dibuja decoraciones ni maneja el foco por su cuenta. Es una utilidad que se apoya en el gestor de ventanas que ya tenés (vía Wnck/EWMH) para ejecutar acciones puntuales bajo demanda. Sin rofi, sin dependencias del gestor de atajos de ningún escritorio en particular, sin configuración manual por `gsettings`.

![Python](https://img.shields.io/badge/python-3-blue)
![GTK](https://img.shields.io/badge/GTK-3-green)
![Platform](https://img.shields.io/badge/platform-Linux-lightgrey)
![License](https://img.shields.io/badge/license-MIT-yellow)
![Status](https://img.shields.io/badge/status-activo-brightgreen)

> Proyecto de mantenimiento activo, desarrollado y usado día a día por su autor. No tiene garantías formales ni suite de tests automatizada — los cambios se validan a mano contra el uso real — así que las versiones pueden traer ajustes de comportamiento de un commit a otro. Los issues y sugerencias son bienvenidos.

## Funcionalidades

**Atajo global**
- Configurable desde la interfaz (click y presionás la combinación) — funciona vía `XGrabKey` directo, no depende del gestor de atajos de ningún escritorio en particular.
- Reacciona en vivo a cambios en el mapeo de teclado (remapeos con xmodmap, cambios de layout) sin necesidad de reiniciar.

**Selector de ventanas**
- Interfaz propia con la misma paleta visual de la app, sin depender de `rofi` ni de ninguna herramienta externa. Fondo levemente transparente (con compositor activo).
- Lista ordenada por uso más reciente primero, igual que un Alt+Tab.
- División configurable con un slider (10%–90%), un solo control para que izquierda y derecha siempre sumen 100%.
- Auto-resolución de la selección: con una sola ventana candidata, Arkhas la toma directo sin mostrar el picker; con ninguna, avisa con un mensaje breve en vez de no hacer nada.
- La segunda selección excluye automáticamente la ventana ya elegida (por instancia, no por aplicación — se pueden elegir dos ventanas del mismo navegador sin problema). Si se cancela con Esc, la primera pasa a ocupar el porcentaje configurado.
- Compensa automáticamente el margen invisible de las apps con decoración del lado del cliente (Chromium/GTK3: Brave, Thorium, etc.), para que no quede un hueco ni una superposición entre las dos ventanas.

**Acciones rápidas desde el picker**
- **X** cierra la ventana resaltada sin salir del picker.
- **Espacio** la maximiza y cierra el picker.

**Monitor de recursos**
- % de RAM y de swap del sistema, coloreados según severidad (verde → amarillo → naranja → rojo a medida que sube el uso).
- % de RAM+swap combinado por ventana (proceso dueño más sus hijos), junto al título de cada una — se usa memoria y no CPU porque CPU cae a 0% en cuanto la app queda inactiva.
- Todo se actualiza cada 1 segundo, y al instante al cerrar una ventana con X.

**Arranque y confiabilidad**
- Instancia única: reabrir la app mientras ya está corriendo muestra la ventana existente en vez de duplicar el proceso.
- Arranca en segundo plano sin mostrar ventana (`--hidden`), pensado para autostart.
- Ícono en la bandeja del sistema (dibujado en código, sin depender de archivos ni de un tema de íconos): click izquierdo abre/muestra la configuración, click derecho da un menú con esa acción más "Salir".
- Cerrar la ventana de configuración no mata el atajo: se oculta, el proceso sigue escuchando.
- Resistente a fallas a nivel de sistema (conexión X perdida, log sin límite, excepciones no manejadas) — ver [Cómo funciona](#cómo-funciona) para el detalle.

## Requisitos

- Linux con X11 y GTK3 (probado en Linux Mint MATE, no debería depender del escritorio).
- Python 3.8+
- PyGObject (bindings de Python para GTK3) + typelibs de GTK3 y Wnck.
- `python-xlib`.
- `psutil` (para el % de RAM/swap del sistema y de memoria por ventana en el picker).
- `pycairo` (para dibujar el ícono de la bandeja).

## Instalación

### Opción A — Código fuente (recomendada)

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-wnck-3.0 python3-xlib python3-psutil python3-cairo
git clone https://github.com/LautaroSantiago/arkhas-window-utils.git
cd arkhas-window-utils
python3 arkhas.py
```

### Opción B — Armar tu propio paquete `.deb`

La estructura de empaquetado (`build_deb.sh`, `packaging/`) está incluida en el repo y probada; no hay un paquete pre-armado publicado en Releases todavía, pero se genera en un paso a partir del código fuente:

```bash
cd arkhas-window-utils
bash build_deb.sh
sudo apt install ./arkhas_<version>_all.deb
```

Esto instala el comando `arkhas` en el PATH del sistema, el lanzador de menú, y el arranque automático a nivel sistema (`/etc/xdg/autostart/`), resolviendo las dependencias de Python/GTK automáticamente. Para desinstalar: `sudo apt remove arkhas`.

## Uso

1. La primera vez que la abrís, ya tiene un atajo por defecto (**Ctrl+Alt+S**) y una división 50%/50%.
2. Para cambiar el atajo: click en el botón de "Atajo para activar la división" y presioná la combinación que quieras.
3. Ajustá el slider para elegir qué porcentaje ocupa la ventana de la izquierda (el resto va para la derecha).
4. Click en **Guardar** — el atajo queda activo al instante, sin reiniciar la app.
5. Apretá el atajo en cualquier momento: aparece la lista de ventanas abiertas (la más reciente primero), elegís la primera (va a la izquierda), aparece de nuevo la lista sin esa ventana, elegís la segunda (va a la derecha). Esc en la segunda selección deja la primera al porcentaje configurado.
6. Dentro del picker: flechas para navegar, Enter para elegir, **X** para cerrar la ventana resaltada sin salir del picker, **Espacio** para maximizarla y cerrar el picker.
7. El ícono de la bandeja siempre está disponible: click izquierdo abre la configuración, click derecho abre un menú (incluye "Salir", que corta el proceso del todo sin necesidad de terminal).

### Arranque automático al iniciar sesión

Si instalaste el `.deb`, esto ya está resuelto (autostart a nivel sistema). Si corrés desde el código fuente:

```bash
mkdir -p ~/.config/autostart
cp arkhas-autostart.desktop ~/.config/autostart/
```

Con esto, Arkhas arranca en segundo plano (sin mostrar ventana) cada vez que iniciás sesión, y el atajo queda disponible sin tocar nada. El autostart no llama a `arkhas.py` directo: pasa por `arkhas-restart.sh`, que primero mata cualquier instancia que haya quedado viva de una sesión anterior y limpia el lockfile antes de relanzar — así cada boot arranca desde cero, sin arrastrar ningún estado raro de la vez anterior.

Para abrir la ventana de configuración más tarde, corré `arkhas` (si instalaste el `.deb`) o `python3 arkhas.py` (desde el código fuente) de nuevo — como ya hay una instancia corriendo, te va a traer al frente esa misma ventana en vez de abrir una nueva. Para terminar el proceso del todo (y que el atajo deje de funcionar):

```bash
pkill -f "arkhas.py"
```

### Atajo del sistema para abrir la configuración (opcional)

Además del ícono de bandeja, se puede armar un atajo de teclado del *sistema* (vía MATE, separado del atajo interno de Arkhas que dispara el picker) para abrir/traer al frente la ventana de configuración sin usar el mouse.

Primero, revisá qué atajos personalizados ya tenés cargados, para no pisar ninguno:

```bash
dconf list /org/mate/desktop/keybindings/
```

Elegí un índice `customN` libre (por ejemplo `custom1`) y corré:

```bash
gsettings set org.mate.control-center.keybinding:/org/mate/desktop/keybindings/customN/ action "arkhas"
gsettings set org.mate.control-center.keybinding:/org/mate/desktop/keybindings/customN/ name 'Abrir opciones de Arkhas'
gsettings set org.mate.control-center.keybinding:/org/mate/desktop/keybindings/customN/ binding '<Control><Alt>o'
```

Esto asume que Arkhas está instalado vía el `.deb` (el comando `arkhas` en el PATH). Si en cambio corrés desde el código fuente, **no uses `cd` suelto** en el `action` del atajo — un atajo de teclado se ejecuta sin ningún working directory garantizado, así que `cd ruta && comando` puede fallar de forma intermitente según el gestor de atajos. Envolvé todo en `bash -c` con la ruta absoluta del proyecto en vez de `~` (algunos gestores de atajos no expanden `~` correctamente):

```bash
gsettings set org.mate.control-center.keybinding:/org/mate/desktop/keybindings/customN/ action "bash -c 'cd /ruta/absoluta/a/arkhas-window-utils && python3 arkhas.py'"
```

### Si el atajo deja de responder

`arkhas-restart.sh` mata cualquier instancia (nueva o vieja), limpia el lockfile, y vuelve a levantar Arkhas desde cero, sin tener que acordarse de la secuencia de comandos a mano cada vez:

```bash
cd ~/arkhas-window-utils
bash arkhas-restart.sh
```

Al final imprime el log y confirma si el proceso quedó corriendo. Si el problema persiste, revisá también que la tecla configurada siga llegando al servidor X (por ejemplo con `xev`, sobre todo si usás teclas remapeadas con xmodmap/xcape).

## Estructura del proyecto

```
arkhas-window-utils/
├── arkhas.py                   # Punto de entrada: lock de instancia única, señales, loop principal
├── ui.py                       # Ventana de configuración: atajo, slider, y orquesta el flujo al dispararse
├── theme.py                    # Paleta visual verde compartida por toda la app
├── config.py                   # Persistencia en ~/.config/arkhas/config.json
├── hotkey.py                   # Atajo global vía XGrabKey (python-xlib), corre en un hilo aparte
├── picker.py                   # Selector de ventanas propio (reemplaza rofi), vía Wnck
├── sysstats.py                 # RAM/swap del sistema y memoria por árbol de procesos (psutil)
├── tray.py                     # Ícono de bandeja (dibujado en código), menú abrir/salir
├── placer.py                   # Cálculo de geometría y posicionamiento de ventanas
├── test_picker_flow.py         # Prueba manual: encadena 2 selecciones del picker
├── test_placer_flow.py         # Prueba manual: flujo completo de selección + posicionamiento
├── arkhas-autostart.desktop    # Entrada XDG para arranque automático (instalación desde código fuente)
├── arkhas-restart.sh           # Reinicia Arkhas de cero (mata instancias, limpia lock, relanza)
├── build_deb.sh                # Genera arkhas_<version>_all.deb a partir del código actual
├── packaging/debian/           # Estructura del paquete Debian (control, .desktop, autostart)
└── README.md
```

## Cómo funciona

**Atajo global**: en vez de depender de la configuración de atajos de MATE/GNOME/etc, `hotkey.py` abre su propia conexión X11 y hace un `XGrabKey` sobre la ventana raíz. Esto funciona igual en cualquier escritorio, y corre en un hilo de fondo mientras la app esté viva. Reacciona en vivo al evento `MappingNotify` que el servidor X manda cuando el mapeo de teclado cambia (xmodmap, cambio de layout), así que no importa el orden en que arranquen Arkhas y un eventual script de remapeo. Como los callbacks de GTK no son thread-safe, el disparo del atajo se despacha con `GLib.idle_add` hacia el hilo principal.

**Selector de ventanas**: `picker.py` arma la lista con `Wnck`, ordenada por orden de apilamiento invertido (la ventana con foco más reciente aparece primero), filtrando ventanas propias de Arkhas, paneles y ventanas sin interés (`skip_tasklist`). Usa un grab de teclado/mouse propio (`Gdk.Seat.grab`) en vez de depender del foco que le dé el gestor de ventanas, con reintentos por si la ventana todavía no está mapeada en el servidor X en el primer intento. Cuando hay 0 o 1 ventana candidata, `pick_window()` resuelve la selección sin mostrar ningún diálogo.

**Cierre robusto del picker**: cada acción que cierra el picker (Esc, Enter, X con lista vacía, Espacio) pasa por `_finish()`, que suelta el grab de teclado, destruye la ventana, y le avisa a GTK que termine ese ciclo interno (`Gtk.main_quit()`). Estos tres pasos están envueltos en un `try/finally` a propósito: si cualquiera de los dos primeros falla, `main_quit()` se ejecuta igual. Sin esa garantía, una excepción a mitad de camino dejaba ese ciclo interno de GTK colgado para siempre — el proceso seguía vivo, pero cada disparo nuevo del atajo apilaba un picker más adentro del que había quedado trabado, dando la impresión de que "el atajo dejó de funcionar".

**Monitor de recursos**: `sysstats.py` lee `psutil.virtual_memory()`/`swap_memory()` para las pastillas de RAM/swap, y para el % por ventana arma un `ProcessTreeMemory` por fila que suma la memoria (RSS + porción swappeada) del proceso dueño de la ventana más todos sus hijos (así una compilación lanzada desde una terminal, o un proceso de decodificación de video que un navegador delega aparte, se reflejan igual). A diferencia de una métrica de CPU, la memoria no depende de mantener el mismo objeto entre lecturas — es una lectura instantánea, y se mantiene estable aunque la app esté inactiva. El color de las pastillas se recalcula agregando y quitando clases CSS en caliente según el porcentaje.

**Ícono de bandeja**: `tray.py` usa `Gtk.StatusIcon` — una API deprecada en GTK3, pero la que mejor compatibilidad tiene con el applet de bandeja tradicional de MATE, sin sumar una dependencia como `libappindicator3` (pensada más para GNOME/Unity). El ícono se dibuja en código con Cairo (dos rectángulos redondeados en la paleta verde de la app) en vez de cargarse desde un archivo, así no depende de un tema de íconos instalado ni de soporte para SVG.

**Posicionamiento**: la parte más delicada. Las apps con decoración del lado del cliente (Brave, Thorium, y en general cualquier app GTK3/Chromium moderna) reservan un margen invisible alrededor de la ventana real (`_GTK_FRAME_EXTENTS`) para sombra y área de resize. Pedirle a la ventana que ocupe exactamente el rectángulo deseado sin tener esto en cuenta deja un hueco visible en el borde. `placer.py` compensa ese margen, pero en vez de calcular la corrección una sola vez y confiar en que salga bien, mide la geometría real resultante después de cada pedido (leyendo directo del servidor X, no de la caché de Wnck) y corrige el error observado, hasta 3 intentos — porque el comportamiento real de Marco + la app no sigue una fórmula fija y predecible.

**Resistencia a caídas del proceso**: `arkhas.py` tiene varias capas pensadas específicamente para que el proceso no muera sin dejar rastro. Todo el arranque —incluida la toma del lock, algo que puede fallar por disco lleno o permisos— está envuelto en un try/except de última instancia que loguea con timestamp y traceback completo antes de salir. Se instala un manejador de bajo nivel para errores fatales de la conexión X principal (`XSetIOErrorHandler`, vía `ctypes`): si el servidor X se corta de golpe, GDK por diseño llama a `exit()` directo en código C, sin pasar por ningún `try/except` de Python — el manejador propio deja constancia clara en el log e intenta auto-relanzarse con `os.execv` hasta 3 veces (el lockfile se libera solo durante el `execv`, gracias a que Python abre archivos con *close-on-exec* por default desde la 3.4). Las señales `SIGUSR1` (mostrar ventana) y `SIGTERM` se manejan vía `GLib.unix_signal_add()` en vez de `signal.signal()` de Python puro — este último solo se procesa cuando el intérprete "recupera el control", lo cual puede tardar indefinidamente con el loop de GLib en reposo total. El log se trunca solo si supera 5MB, para que un proceso corriendo semanas no vaya llenando el disco de a poco.

## Limitaciones conocidas

- Un atajo global por vez.
- Riesgos que no se pueden eliminar del todo, por ser fallas a nivel del sistema operativo: si el kernel activa el OOM killer en una emergencia real de memoria, puede matar a Arkhas igual que a cualquier otro proceso (bajar la prioridad de ser candidato requiere un privilegio que un proceso normal no tiene en Linux, así que no hay mitigación posible sin pedir permisos elevados); si el servidor X se cae de forma persistente (no un hiccup transitorio), el auto-relanzo agota sus 3 intentos y el proceso queda detenido hasta que se reinicie a mano; un `kill -9` externo no deja ningún rastro posible en el log, por diseño del sistema operativo.

## Solución de problemas

| Problema | Causa probable | Solución |
|---|---|---|
| `ModuleNotFoundError: No module named 'gi'` | Faltan bindings de GTK | `sudo apt install python3-gi gir1.2-gtk-3.0` |
| `ModuleNotFoundError: No module named 'Xlib'` | Falta python-xlib | `sudo apt install python3-xlib` |
| `ModuleNotFoundError: No module named 'cairo'` | Falta pycairo | `sudo apt install python3-cairo` |
| Las pastillas dicen "RAM: N/D" / no aparece % de memoria por ventana | Falta psutil | `sudo apt install python3-psutil` |
| No aparece el ícono en la bandeja del sistema | El panel no tiene un applet de "área de notificación" agregado, o no soporta `Gtk.StatusIcon` | En MATE: click derecho en el panel → Añadir al panel → "Área de notificación" |
| El picker no lista ninguna ventana | No hay otras ventanas abiertas, o ya se excluyó la única disponible | Comportamiento esperado — el picker lo indica en pantalla |
| El atajo no responde | Otra instancia ya lo tiene agarrado, el atajo elegido choca con uno del sistema, un remapeo de teclado (xmodmap/xcape) dejó de estar activo, o el atajo guardado cambió por accidente | `bash arkhas-restart.sh`; revisar `cat ~/.config/arkhas/config.json` para confirmar cuál es el atajo realmente guardado; si usás teclas remapeadas, confirmá con `xev` que la tecla sigue emitiendo el keysym esperado |
| No me deja asignar X, Espacio o Escape solas como atajo | X, Espacio y Escape sueltas son controles del picker (cerrar, maximizar, cancelar); usarlas como atajo global chocaría con esos controles cada vez que el picker está abierto | Comportamiento esperado — agregá un modificador (ej. Ctrl+Alt+X) o elegí otra tecla |
| Queda un hueco o superposición entre las dos ventanas | Alguna app declara `_GTK_FRAME_EXTENTS` de forma poco convencional | Abrí un issue con la salida de `ARKHAS_DEBUG=1 python3 arkhas.py` |

## Historial de versiones

Resumen de los hitos más importantes — para el detalle completo, `git log`.

- **v1.0.0** — Versión inicial: divisor de pantalla activado por atajo, picker propio (sin rofi), atajo configurable vía `XGrabKey`.
- **v1.1.0** — Código comentado de punta a punta. Primer empaquetado `.deb`. Auto-resolución de la selección (0/1/2+ ventanas candidatas). Orden de la lista por uso más reciente (MRU). Picker con fondo transparente.
- **v1.2.0** — **X** para cerrar y **Espacio** para maximizar ventanas directo desde el picker.
- *(entre v1.2.0 y v1.7.0)* — Tramo de correcciones sobre el manejo de atajos y el picker, incluyendo un fix para que el atajo no dejara de responder si `maximize()` fallaba a mitad de camino. Se sumó la severidad por color en las pastillas de RAM/swap, y se reencuadró el proyecto como "utilidad de control rápido de ventanas" en vez de solo "divisor de pantallas".
- **v1.7.0** — Fix crítico: un `AttributeError` silencioso rompía el picker apenas había 2 o más ventanas. Fix: Escape ya no se guarda como atajo global al usarse para cancelar la captura de tecla. Bloqueo de X/Espacio/Escape sueltas como atajo global. El % por ventana pasa de CPU a memoria. Logging acumulativo con timestamp, `arkhas-restart.sh`.
- **v1.8.0** — Fix: el atajo podía quedar armado con keycode 0 (`AnyKey` en X11, agarra *todas* las teclas) si el remapeo de teclado no había terminado de aplicarse al arrancar. Ahora reacciona en vivo a `MappingNotify`.
- **v2.0.0** — Ícono de bandeja. Aviso amigable cuando no hay ventanas para dividir. Resistencia a caídas del proceso (try/except de última instancia, `XSetIOErrorHandler` con auto-relanzo, rotación de log). Fix de una condición de carrera en el lockfile.
- *(rename)* — El repositorio y el paquete pasan a llamarse **arkhas-window-utils**; `main.py` se renombra a `arkhas.py`.
- **v2.2.0** — Fix: el click en el ícono de bandeja (y `SIGUSR1` en general) no abría la ventana si el proceso llevaba un rato inactivo — ahora usa `GLib.unix_signal_add()` en vez de `signal.signal()`.
- **v2.3.0** — Manejo explícito de `SIGTERM` con logging, para dejar rastro si el proceso se cierra por una señal externa.

## Licencia

MIT — ver [LICENSE](LICENSE).

## Autor

**Lautaro Subeldia**

- GitHub: https://github.com/LautaroSantiago
- LinkedIn: https://www.linkedin.com/in/lautaro-subeldia
