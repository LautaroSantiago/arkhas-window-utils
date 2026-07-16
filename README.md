# Arkhas

Divisor de pantalla activado por un atajo global, con interfaz en GTK3, pensado para Linux Mint MATE (compatible con cualquier entorno GTK3/X11).

Arkhas no es un gestor de ventanas ni reemplaza al que ya usás: es un disparador puntual. Apretás el atajo, elegís una ventana de una lista, la ubica a la izquierda; elegís otra, la ubica a la derecha. Sin rofi, sin dependencias del gestor de ventanas específicas, sin configuración manual de atajos por `gsettings`.

![Python](https://img.shields.io/badge/python-3-blue)
![GTK](https://img.shields.io/badge/GTK-3-green)
![Platform](https://img.shields.io/badge/platform-Linux-lightgrey)
![License](https://img.shields.io/badge/license-MIT-yellow)
![Status](https://img.shields.io/badge/status-en%20desarrollo-orange)

> **Proyecto en desarrollo activo.** Todavía está en proceso de prueba y revisión — la posición de las ventanas, en particular, puede fallar con algunas combinaciones de aplicaciones mientras se sigue afinando. Todavía no hay paquete `.deb` ni ícono de bandeja. Usalo sabiendo que puede cambiar de un commit a otro.

## Funcionalidades

- Atajo de teclado global configurable desde la interfaz (click y presionás la combinación) — funciona vía `XGrabKey` directo, no depende del gestor de atajos de ningún escritorio en particular.
- Selector de ventanas propio con la misma paleta visual de la app, sin depender de `rofi` ni de ninguna herramienta externa.
- División configurable con un slider (10%–90%), un solo control para que izquierda y derecha siempre sumen 100%.
- Si cancelás la segunda selección (Esc), la primera ventana pasa a ocupar el 50% de la pantalla.
- La segunda selección excluye automáticamente la ventana que ya elegiste (por instancia, no por aplicación — podés elegir dos ventanas del mismo navegador sin problema).
- Compensa automáticamente el margen invisible de las apps con decoración del lado del cliente (Chromium/GTK3: Brave, Thorium, etc.), para que no quede un hueco ni una superposición entre las dos ventanas.
- Instancia única: si volvés a abrir la app mientras ya está corriendo, te muestra la ventana existente en vez de duplicar el proceso.
- Arranca en segundo plano sin mostrar ventana (`--hidden`), pensado para autostart.
- Cerrar la ventana de configuración no mata el atajo: se oculta, el proceso sigue escuchando.

## Requisitos

- Linux con X11 y GTK3 (probado en Linux Mint MATE, no debería depender del escritorio).
- Python 3.8+
- PyGObject (bindings de Python para GTK3) + typelibs de GTK3 y Wnck.
- `python-xlib`.

## Instalación

### Opción A — Paquete `.deb` (próximamente)

Todavía no hay paquete `.deb` publicado. Cuando esté disponible, se va a instalar con:

```bash
sudo apt install ./arkhas_1.0.0_all.deb
```

### Opción B — Desde el código fuente

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-wnck-3.0 python3-xlib
git clone https://github.com/LautaroSantiago/arkhas.git
cd arkhas
python3 main.py
```

## Uso

1. La primera vez que la abrís, ya tiene un atajo por defecto (**Ctrl+Alt+S**) y una división 50%/50%.
2. Para cambiar el atajo: click en el botón de "Atajo para activar la división" y presioná la combinación que quieras.
3. Ajustá el slider para elegir qué porcentaje ocupa la ventana de la izquierda (el resto va para la derecha).
4. Click en **Guardar** — el atajo queda activo al instante, sin reiniciar la app.
5. Apretá el atajo en cualquier momento: aparece la lista de ventanas abiertas, elegís la primera (va a la izquierda), aparece de nuevo la lista sin esa ventana, elegís la segunda (va a la derecha). Esc en la segunda selección deja la primera al 50%.

### Arranque automático al iniciar sesión

```bash
mkdir -p ~/.config/autostart
cp arkhas-autostart.desktop ~/.config/autostart/
```

Con esto, Arkhas arranca en segundo plano (sin mostrar ventana) cada vez que iniciás sesión, y el atajo queda disponible sin tocar nada. Para abrir la ventana de configuración más tarde, simplemente corré `python3 main.py` de nuevo — como ya hay una instancia corriendo, te va a traer al frente esa misma ventana en vez de abrir una nueva.

Para terminar el proceso del todo (y que el atajo deje de funcionar):

```bash
pkill -f "python3 main.py"
```

## Estructura del proyecto

```
arkhas/
├── main.py                    # Punto de entrada: lock de instancia única, señales, loop principal
├── ui.py                      # Ventana de configuración: atajo, slider, y orquesta el flujo al dispararse
├── theme.py                   # Paleta visual verde compartida por toda la app
├── config.py                  # Persistencia en ~/.config/arkhas/config.json
├── hotkey.py                  # Atajo global vía XGrabKey (python-xlib), corre en un hilo aparte
├── picker.py                  # Selector de ventanas propio (reemplaza rofi), vía Wnck
├── placer.py                  # Cálculo de geometría y posicionamiento de ventanas
├── test_picker_flow.py        # Prueba manual: encadena 2 selecciones del picker
├── test_placer_flow.py        # Prueba manual: flujo completo de selección + posicionamiento
├── arkhas-autostart.desktop   # Entrada XDG para arranque automático
└── README.md
```

## Cómo funciona

**Atajo global**: en vez de depender de la configuración de atajos de MATE/GNOME/etc, `hotkey.py` abre su propia conexión X11 y hace un `XGrabKey` sobre la ventana raíz. Esto funciona igual en cualquier escritorio, y corre en un hilo de fondo mientras la app esté viva. Como los callbacks de GTK no son thread-safe, el disparo del atajo se despacha con `GLib.idle_add` hacia el hilo principal.

**Selector de ventanas**: `picker.py` arma la lista con `Wnck`, filtrando ventanas propias de Arkhas, paneles y ventanas sin interés (`skip_tasklist`). Usa un grab de teclado/mouse propio (`Gdk.Seat.grab`) en vez de depender del foco que le dé el gestor de ventanas, con reintentos por si la ventana todavía no está mapeada en el servidor X en el primer intento.

**Posicionamiento**: la parte más delicada. Las apps con decoración del lado del cliente (Brave, Thorium, y en general cualquier app GTK3/Chromium moderna) reservan un margen invisible alrededor de la ventana real (`_GTK_FRAME_EXTENTS`) para sombra y área de resize. Pedirle a la ventana que ocupe exactamente el rectángulo deseado sin tener esto en cuenta deja un hueco visible en el borde. `placer.py` compensa ese margen, pero en vez de calcular la corrección una sola vez y confiar en que salga bien, mide la geometría real resultante después de cada pedido (leyendo directo del servidor X, no de la caché de Wnck) y corrige el error observado, hasta 3 intentos — porque el comportamiento real de Marco + la app no sigue una fórmula fija y predecible.

## Limitaciones conocidas

- No hay ícono en bandeja todavía: la única forma de abrir la ventana de configuración es correr `python3 main.py` de nuevo (te trae la instancia existente al frente).
- Sin el paquete `.deb`, la instalación de dependencias y el autostart hay que hacerlos a mano.
- Un atajo global por vez.

## Solución de problemas

| Problema | Causa probable | Solución |
|---|---|---|
| `ModuleNotFoundError: No module named 'gi'` | Faltan bindings de GTK | `sudo apt install python3-gi gir1.2-gtk-3.0` |
| `ModuleNotFoundError: No module named 'Xlib'` | Falta python-xlib | `sudo apt install python3-xlib` |
| El picker no lista ninguna ventana | No hay otras ventanas abiertas, o ya se excluyó la única disponible | Comportamiento esperado — el picker lo indica en pantalla |
| El atajo no responde | Otra instancia ya lo tiene agarrado, o el atajo elegido choca con uno del sistema | `pgrep -af "python3 main.py"` para ver si hay más de una instancia |
| Queda un hueco o superposición entre las dos ventanas | Alguna app declara `_GTK_FRAME_EXTENTS` de forma poco convencional | Abrí un issue con la salida de `ARKHAS_DEBUG=1 python3 main.py` |

## Licencia

MIT — ver [LICENSE](LICENSE).

## Autor

**Lautaro Subeldia**

- GitHub: https://github.com/LautaroSantiago
- LinkedIn: https://www.linkedin.com/in/lautaro-subeldia
