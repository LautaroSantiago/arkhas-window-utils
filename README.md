# Arkhas

Utilidad de control rápido de ventanas para Linux, activada por un atajo global, con interfaz propia en GTK3. Pensada para Linux Mint MATE, compatible con cualquier entorno GTK3/X11.

## Qué es Arkhas

Arkhas empezó como un divisor de pantalla: un atajo que abre un selector de ventanas y acomoda dos, una al lado de la otra. Con el uso fue creciendo hasta cubrir un puñado de acciones rápidas sobre ventanas que antes requerían salir del teclado — cerrar, maximizar, ver qué está consumiendo recursos — todas disparadas desde el mismo picker.

Arkhas **no es un gestor de ventanas**: no reemplaza a Marco (ni a ningún otro), no dibuja decoraciones ni maneja el foco por su cuenta. Es una utilidad que se apoya en el gestor de ventanas que ya tenés (vía Wnck/EWMH) para ejecutar acciones puntuales bajo demanda. Sin rofi, sin dependencias del gestor de atajos de ningún escritorio en particular, sin configuración manual por `gsettings`.

![Python](https://img.shields.io/badge/python-3-blue)
![GTK](https://img.shields.io/badge/GTK-3-green)
![Platform](https://img.shields.io/badge/platform-Linux-lightgrey)
![License](https://img.shields.io/badge/license-MIT-yellow)
![Status](https://img.shields.io/badge/status-en%20desarrollo-orange)

> **Proyecto en desarrollo activo.** Todavía está en proceso de prueba y revisión. El paquete `.deb` sigue sin publicarse (ver [Limitaciones conocidas](#limitaciones-conocidas)); por ahora se instala desde el código fuente. Usalo sabiendo que puede cambiar de un commit a otro.

## Funcionalidades

- Atajo de teclado global configurable desde la interfaz (click y presionás la combinación) — funciona vía `XGrabKey` directo, no depende del gestor de atajos de ningún escritorio en particular.
- Selector de ventanas propio con la misma paleta visual de la app, sin depender de `rofi` ni de ninguna herramienta externa. Fondo levemente transparente (con compositor activo).
- Lista de ventanas ordenada por uso más reciente primero, igual que un Alt+Tab.
- División configurable con un slider (10%–90%), un solo control para que izquierda y derecha siempre sumen 100%.
- Auto-resolución de la selección: si en un momento dado solo queda una ventana disponible para elegir, Arkhas la toma directo sin mostrar el picker; si no queda ninguna, no abre el picker completo — en la primera selección muestra un aviso breve y liviano (con una carita dibujada en código, no un archivo de imagen) en vez de no hacer nada; en la segunda, la primera ventana ya elegida simplemente pasa a ocupar el porcentaje configurado.
- Si cancelás la segunda selección (Esc), la primera ventana pasa a ocupar el porcentaje configurado (no un 50% fijo).
- La segunda selección excluye automáticamente la ventana que ya elegiste (por instancia, no por aplicación — podés elegir dos ventanas del mismo navegador sin problema).
- Desde el picker, con la ventana resaltada: **X** la cierra (y la saca de la lista sin cerrar el picker), **Espacio** la maximiza (y cierra el picker).
- Monitor de recursos en vivo dentro del picker: % de RAM (pastilla a la izquierda) y % de swap (a la derecha) del sistema, coloreados según severidad (verde → amarillo → naranja → rojo a medida que sube el uso), y el % de RAM+swap combinado que ocupa el proceso de cada ventana (junto con sus procesos hijos) al lado de su título — se usa memoria y no CPU porque CPU cae a 0% en cuanto la app queda inactiva, mientras que la memoria reservada se mantiene estable. Se actualiza cada 1 segundo, y también al instante al cerrar una ventana con X.
- Compensa automáticamente el margen invisible de las apps con decoración del lado del cliente (Chromium/GTK3: Brave, Thorium, etc.), para que no quede un hueco ni una superposición entre las dos ventanas.
- Instancia única: si volvés a abrir la app mientras ya está corriendo, te muestra la ventana existente en vez de duplicar el proceso.
- Arranca en segundo plano sin mostrar ventana (`--hidden`), pensado para autostart.
- Cerrar la ventana de configuración no mata el atajo: se oculta, el proceso sigue escuchando.
- Ícono en la bandeja del sistema (dibujado en código, sin depender de archivos ni de un tema de íconos): click izquierdo abre/muestra la ventana de configuración, click derecho da un menú con esa acción más "Salir" (termina el proceso del todo).

## Requisitos

- Linux con X11 y GTK3 (probado en Linux Mint MATE, no debería depender del escritorio).
- Python 3.8+
- PyGObject (bindings de Python para GTK3) + typelibs de GTK3 y Wnck.
- `python-xlib`.
- `psutil` (para el % de RAM/swap del sistema y de memoria por ventana en el picker).
- `pycairo` (para dibujar el ícono de la bandeja).

## Instalación

Por ahora, solo desde el código fuente (el `.deb` está pausado hasta tener ícono de bandeja):

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-wnck-3.0 python3-xlib python3-psutil python3-cairo
git clone https://github.com/LautaroSantiago/arkhas-window-utils.git
cd arkhas-window-utils
python3 arkhas.py
```

## Uso

1. La primera vez que la abrís, ya tiene un atajo por defecto (**Ctrl+Alt+S**) y una división 50%/50%.
2. Para cambiar el atajo: click en el botón de "Atajo para activar la división" y presioná la combinación que quieras.
3. Ajustá el slider para elegir qué porcentaje ocupa la ventana de la izquierda (el resto va para la derecha).
4. Click en **Guardar** — el atajo queda activo al instante, sin reiniciar la app.
5. Apretá el atajo en cualquier momento: aparece la lista de ventanas abiertas (la más reciente primero), elegís la primera (va a la izquierda), aparece de nuevo la lista sin esa ventana, elegís la segunda (va a la derecha). Esc en la segunda selección deja la primera al porcentaje configurado.
6. Dentro del picker: flechas para navegar, Enter para elegir, **X** para cerrar la ventana resaltada sin salir del picker, **Espacio** para maximizarla y cerrar el picker. Abajo, las pastillas de RAM y swap del sistema se actualizan solas.
7. El ícono de la bandeja siempre está disponible: click izquierdo abre la configuración, click derecho abre un menú (incluye "Salir", que corta el proceso del todo sin necesidad de terminal).

### Arranque automático al iniciar sesión

```bash
mkdir -p ~/.config/autostart
cp arkhas-autostart.desktop ~/.config/autostart/
```

Con esto, Arkhas arranca en segundo plano (sin mostrar ventana) cada vez que iniciás sesión, y el atajo queda disponible sin tocar nada. El autostart no llama a `arkhas.py` directo: pasa por `arkhas-restart.sh`, que primero mata cualquier instancia que haya quedado viva de una sesión anterior y limpia el lockfile antes de relanzar — así cada boot arranca desde cero, sin arrastrar ningún estado raro de la vez anterior. Para abrir la ventana de configuración más tarde, simplemente corré `python3 arkhas.py` de nuevo — como ya hay una instancia corriendo, te va a traer al frente esa misma ventana en vez de abrir una nueva.

Para terminar el proceso del todo (y que el atajo deje de funcionar):

```bash
pkill -f "python3 arkhas.py"
```

### Si el atajo deja de responder

`arkhas-restart.sh` mata cualquier instancia (nueva o vieja), limpia el lockfile, y vuelve a levantar Arkhas desde cero — sin tener que acordarse de la secuencia de comandos a mano cada vez:

```bash
cd ~/arkhas-window-utils
bash arkhas-restart.sh
```

Al final imprime el log y confirma si el proceso quedó corriendo. Si el problema persiste después de esto, revisá también que la tecla configurada siga llegando al servidor X (por ejemplo con `xev`, sobre todo si usás teclas remapeadas con xmodmap/xcape).

## Estructura del proyecto

```
arkhas/
├── arkhas.py                    # Punto de entrada: lock de instancia única, señales, loop principal
├── ui.py                      # Ventana de configuración: atajo, slider, y orquesta el flujo al dispararse
├── theme.py                   # Paleta visual verde compartida por toda la app
├── config.py                  # Persistencia en ~/.config/arkhas/config.json
├── hotkey.py                  # Atajo global vía XGrabKey (python-xlib), corre en un hilo aparte
├── picker.py                  # Selector de ventanas propio (reemplaza rofi), vía Wnck
├── sysstats.py                 # RAM/swap del sistema y memoria por árbol de procesos (psutil)
├── tray.py                     # Ícono de bandeja (dibujado en código), menú abrir/salir
├── placer.py                  # Cálculo de geometría y posicionamiento de ventanas
├── test_picker_flow.py        # Prueba manual: encadena 2 selecciones del picker
├── test_placer_flow.py        # Prueba manual: flujo completo de selección + posicionamiento
├── arkhas-autostart.desktop   # Entrada XDG para arranque automático (instalación desde código fuente)
├── arkhas-restart.sh           # Reinicia Arkhas de cero (mata instancias, limpia lock, relanza)
├── build_deb.sh                # Genera arkhas_<version>_all.deb a partir del código actual (pausado, ver más abajo)
├── packaging/debian/           # Estructura del paquete Debian (control, .desktop, autostart)
└── README.md
```

## Cómo funciona

**Atajo global**: en vez de depender de la configuración de atajos de MATE/GNOME/etc, `hotkey.py` abre su propia conexión X11 y hace un `XGrabKey` sobre la ventana raíz. Esto funciona igual en cualquier escritorio, y corre en un hilo de fondo mientras la app esté viva. Como los callbacks de GTK no son thread-safe, el disparo del atajo se despacha con `GLib.idle_add` hacia el hilo principal.

**Selector de ventanas**: `picker.py` arma la lista con `Wnck`, ordenada por orden de apilamiento invertido (la ventana con foco más reciente aparece primero), filtrando ventanas propias de Arkhas, paneles y ventanas sin interés (`skip_tasklist`). Usa un grab de teclado/mouse propio (`Gdk.Seat.grab`) en vez de depender del foco que le dé el gestor de ventanas, con reintentos por si la ventana todavía no está mapeada en el servidor X en el primer intento. Cuando hay 0 o 1 ventana candidata, `pick_window()` resuelve la selección sin mostrar ningún diálogo.

**Cierre robusto del picker**: cada acción que cierra el picker (Esc, Enter, X con lista vacía, Espacio) pasa por `_finish()`, que suelta el grab de teclado, destruye la ventana, y le avisa a GTK que termine ese ciclo interno (`Gtk.main_quit()`). Estos tres pasos están envueltos en un `try/finally` a propósito: si cualquiera de los dos primeros pasos falla (por ejemplo, un error al maximizar una ventana que ya no existe), `main_quit()` se ejecuta igual. Sin esa garantía, una excepción a mitad de camino dejaba ese ciclo interno de GTK colgado para siempre — el proceso seguía vivo, pero cada disparo nuevo del atajo apilaba un picker más adentro del que había quedado trabado, en vez de abrir uno limpio, dando la impresión de que "el atajo dejó de funcionar".

**Resistencia a caídas del proceso**: `arkhas.py` tiene varias capas pensadas específicamente para que el proceso no muera sin dejar rastro. (1) Todo el arranque —incluida la toma del lock, algo que puede fallar por disco lleno o permisos— está envuelto en un try/except de última instancia que loguea con timestamp y traceback completo antes de salir, en vez de un crash silencioso. (2) Se instala un manejador de bajo nivel para errores fatales de la conexión X principal (`XSetIOErrorHandler`, vía `ctypes`): si el servidor X se corta de golpe, GDK por diseño llama a `exit()` directo en código C, sin pasar por ningún `try/except` de Python — el manejador propio deja constancia clara en el log e intenta auto-relanzarse con `os.execv` hasta 3 veces (el lockfile se libera solo durante el `execv`, gracias a que Python abre archivos con *close-on-exec* por default desde la 3.4, así que el proceso relanzado no compite consigo mismo por el lock). (3) El log se trunca solo si supera 5MB, para que un proceso corriendo semanas sin reiniciar no vaya llenando el disco de a poco. (Se evaluó pedirle al kernel una prioridad más baja frente al OOM killer vía `/proc/self/oom_score_adj`, pero un proceso sin privilegios no puede bajar ese valor en Linux — requiere `CAP_SYS_RESOURCE` — así que se descartó: solo iba a fallar en silencio o generar ruido en el log en cada arranque, sin ningún beneficio real.)

**Monitor de recursos**: `sysstats.py` lee `psutil.virtual_memory()`/`swap_memory()` para las pastillas de RAM/swap, y para el % por ventana arma un `ProcessTreeMemory` por fila que suma la memoria (RSS + porción swappeada) del proceso dueño de la ventana más todos sus hijos (así una compilación lanzada desde una terminal, o un proceso de decodificación de video que un navegador delega aparte, se reflejan igual). A diferencia de una métrica de CPU, la memoria no depende de mantener el mismo objeto entre lecturas — es una lectura instantánea, y se mantiene estable aunque la app esté inactiva, a diferencia del CPU que cae a 0% todo el tiempo. El color de las pastillas (verde/amarillo/naranja/rojo) se recalcula agregando y quitando clases CSS en caliente según el porcentaje.

**Ícono de bandeja**: `tray.py` usa `Gtk.StatusIcon` — una API deprecada en GTK3, pero la que mejor compatibilidad tiene con el applet de bandeja tradicional de MATE, sin sumar una dependencia como `libappindicator3` (pensada más para GNOME/Unity). El ícono se dibuja en código con Cairo (dos rectángulos redondeados en la paleta verde de la app, representando la división de pantalla) en vez de cargarse desde un archivo, así no depende de un tema de íconos instalado ni de soporte para SVG.

**Posicionamiento**: la parte más delicada. Las apps con decoración del lado del cliente (Brave, Thorium, y en general cualquier app GTK3/Chromium moderna) reservan un margen invisible alrededor de la ventana real (`_GTK_FRAME_EXTENTS`) para sombra y área de resize. Pedirle a la ventana que ocupe exactamente el rectángulo deseado sin tener esto en cuenta deja un hueco visible en el borde. `placer.py` compensa ese margen, pero en vez de calcular la corrección una sola vez y confiar en que salga bien, mide la geometría real resultante después de cada pedido (leyendo directo del servidor X, no de la caché de Wnck) y corrige el error observado, hasta 3 intentos — porque el comportamiento real de Marco + la app no sigue una fórmula fija y predecible.

## Limitaciones conocidas

- El paquete `.deb` (`build_deb.sh`, `packaging/`) queda armado y probado, pero todavía no se publica como forma de instalación recomendada — por ahora, código fuente.
- Un atajo global por vez.
- Riesgos que no se pueden eliminar del todo, por ser fallas a nivel del sistema operativo: si el kernel activa el OOM killer en una emergencia real de memoria, puede matar a Arkhas igual que a cualquier otro proceso (bajar la prioridad de ser candidato requiere un privilegio que un proceso normal no tiene en Linux, así que no hay mitigación posible sin pedir permisos elevados); si el servidor X se cae de forma persistente (no un hiccup transitorio), el auto-relanzo agota sus 3 intentos y el proceso queda detenido hasta que el usuario lo reinicie a mano.

## Solución de problemas

| Problema | Causa probable | Solución |
|---|---|---|
| `ModuleNotFoundError: No module named 'gi'` | Faltan bindings de GTK | `sudo apt install python3-gi gir1.2-gtk-3.0` |
| `ModuleNotFoundError: No module named 'Xlib'` | Falta python-xlib | `sudo apt install python3-xlib` |
| Las pastillas dicen "RAM: N/D" / no aparece % de memoria por ventana | Falta psutil | `sudo apt install python3-psutil` |
| `ModuleNotFoundError: No module named 'cairo'` | Falta pycairo | `sudo apt install python3-cairo` |
| No aparece el ícono en la bandeja del sistema | El panel no tiene un applet de "área de notificación" agregado, o no soporta `Gtk.StatusIcon` | En MATE: click derecho en el panel → Añadir al panel → "Área de notificación" |
| El picker no lista ninguna ventana | No hay otras ventanas abiertas, o ya se excluyó la única disponible | Comportamiento esperado — el picker lo indica en pantalla |
| El atajo no responde | Otra instancia ya lo tiene agarrado, el atajo elegido choca con uno del sistema, un remapeo de teclado (xmodmap/xcape) dejó de estar activo, quedó un proceso viejo colgado, o el atajo guardado cambió por accidente (ver fila de abajo) | `bash arkhas-restart.sh`; revisar `cat ~/.config/arkhas/config.json` para confirmar cuál es el atajo realmente guardado; si usás teclas remapeadas (F13/F14, etc.), confirmá con `xev` que la tecla sigue emitiendo el keysym esperado |
| El atajo guardado cambió solo, sin que lo hayas tocado a propósito | Apretar Escape mientras la ventana esperaba una tecla nueva ("Presioná la combinación...") lo guardaba como el atajo literal en vez de cancelar la espera — bug corregido; si tenés una versión anterior, revisá `~/.config/arkhas/config.json` y reconfigurá desde la interfaz | Actualizar a la versión más reciente |
| No me deja asignar X, Espacio o Escape solas como atajo | X, Espacio y Escape sueltas son controles del picker (cerrar, maximizar, cancelar); usarlas como atajo global chocaría con esos controles cada vez que el picker está abierto | Comportamiento esperado — agregá un modificador (ej. Ctrl+Alt+X) o elegí otra tecla |
| El atajo no anda justo al reiniciar la PC, pero sí después de reiniciar Arkhas a mano | Si usás un remapeo de teclado (xmodmap/xcape) que corre por su cuenta al iniciar sesión, puede terminar de aplicarse DESPUÉS de que Arkhas ya arrancó — bug corregido: Arkhas ahora reacciona en vivo al evento `MappingNotify` que manda el servidor X cuando el mapeo cambia, sin importar el orden de arranque | Actualizar a la versión más reciente |
| Click en el ícono de la bandeja (o volver a correr `arkhas`) no abre la ventana si el proceso lleva un rato inactivo | `signal.signal()` de Python solo procesa la señal cuando el intérprete "recupera el control" — con el loop de GLib en reposo total, eso podía tardar indefinidamente o no pasar nunca — bug corregido: ahora se usa `GLib.unix_signal_add()`, que integra la señal directamente en el loop de eventos de GLib | Actualizar a la versión más reciente |
| Queda un hueco o superposición entre las dos ventanas | Alguna app declara `_GTK_FRAME_EXTENTS` de forma poco convencional | Abrí un issue con la salida de `ARKHAS_DEBUG=1 python3 arkhas.py` |

## Licencia

MIT — ver [LICENSE](LICENSE).

## Autor

**Lautaro Subeldia**

- GitHub: https://github.com/LautaroSantiago
- LinkedIn: https://www.linkedin.com/in/lautaro-subeldia
