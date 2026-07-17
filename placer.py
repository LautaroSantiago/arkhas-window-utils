import os
import sys
import time

import gi

gi.require_version("Wnck", "3.0")
from gi.repository import Wnck

import Xlib.display
import Xlib.X

_GTK_FRAME_EXTENTS_ATOM = "_GTK_FRAME_EXTENTS"
_DEBUG = os.environ.get("ARKHAS_DEBUG") == "1"

# Conexion X11 propia (separada de la de GDK y de la de hotkey.py) para
# leer propiedades de ventanas y del root directo del servidor, sin pasar
# por wmctrl ni por el cache de Wnck.
_xlib_display = None


def _get_xlib_display():
    global _xlib_display
    if _xlib_display is None:
        _xlib_display = Xlib.display.Display()
    return _xlib_display


def _get_frame_extents(xid):
    # Las apps con decoracion del lado del cliente (GTK3/Chromium: Brave,
    # Thorium, etc.) dibujan ellas mismas su sombra y borde de resize
    # DENTRO de su propia ventana X, y le avisan al gestor de ventanas
    # cuanto margen de esa ventana es en realidad invisible via esta
    # propiedad. Sin tenerla en cuenta, pedirle a la ventana que ocupe
    # exactamente el rectangulo deseado deja ese margen como hueco visible
    # en el borde. Si la ventana no define la propiedad (apps sin CSD),
    # se devuelve (0,0,0,0) y el resto del calculo queda sin efecto.
    try:
        display = _get_xlib_display()
        window = display.create_resource_object("window", xid)
        atom = display.get_atom(_GTK_FRAME_EXTENTS_ATOM)
        prop = window.get_full_property(atom, Xlib.X.AnyPropertyType)
        if prop is None or not prop.value or len(prop.value) < 4:
            return (0, 0, 0, 0)
        left, right, top, bottom = prop.value[:4]
        return (int(left), int(right), int(top), int(bottom))
    except Exception:
        return (0, 0, 0, 0)


def _get_actual_geometry(xid):
    # Wnck.Window.get_geometry() devolvia valores desactualizados/poco
    # confiables al verificar el resultado de un resize reciente, asi que
    # la geometria real se lee directo del protocolo X: get_geometry() da
    # ancho/alto, y translate_coords traduce la esquina superior izquierda
    # de la ventana a coordenadas absolutas de la raiz (necesario porque,
    # segun el estado de reparenting, las coordenadas de get_geometry()
    # pueden ser relativas a un padre que no es la raiz).
    display = _get_xlib_display()
    window = display.create_resource_object("window", xid)
    geom = window.get_geometry()
    root = display.screen().root
    translated = window.translate_coords(root, 0, 0)
    return (translated.x, translated.y, geom.width, geom.height)


def get_workarea():
    # _NET_WORKAREA trae un rectangulo (x,y,w,h) por cada escritorio
    # virtual, en orden; hay que saber cual es el activo (_NET_CURRENT_DESKTOP)
    # para tomar el que corresponde. Se lee directo del root en vez de
    # invocar wmctrl como subproceso.
    display = _get_xlib_display()
    root = display.screen().root

    desktop_atom = display.get_atom("_NET_CURRENT_DESKTOP")
    desktop_prop = root.get_full_property(desktop_atom, Xlib.X.AnyPropertyType)
    current_desktop = int(desktop_prop.value[0]) if desktop_prop else 0

    workarea_atom = display.get_atom("_NET_WORKAREA")
    workarea_prop = root.get_full_property(workarea_atom, Xlib.X.AnyPropertyType)
    values = list(workarea_prop.value)

    offset = current_desktop * 4
    x, y, w, h = values[offset:offset + 4]
    return (int(x), int(y), int(w), int(h))


def place_window(xid, x, y, width, height):
    screen = Wnck.Screen.get_default()
    # mismo motivo que en picker.py: sin refrescar el cache de Wnck, una
    # ventana recien seleccionada puede no resolverse todavia con Window.get()
    screen.force_update()

    window = Wnck.Window.get(xid)
    if window is None:
        raise RuntimeError(f"No encontre la ventana con xid {xid}")

    # una ventana maximizada ignora los pedidos de resize hasta que se le
    # saca ese estado
    window.unmaximize()
    time.sleep(0.05)

    left, right, top, bottom = _get_frame_extents(xid)

    def _apply(rx, ry, rw, rh):
        window.set_geometry(
            # CURRENT (gravedad 0): se le pide al gestor de ventanas que
            # posicione el rectangulo pedido usando la gravedad que la
            # propia ventana declara (o NorthWest si no declara ninguna),
            # en vez de forzar una gravedad especifica nuestra.
            Wnck.WindowGravity.CURRENT,
            (
                Wnck.WindowMoveResizeMask.X
                | Wnck.WindowMoveResizeMask.Y
                | Wnck.WindowMoveResizeMask.WIDTH
                | Wnck.WindowMoveResizeMask.HEIGHT
            ),
            rx, ry, rw, rh,
        )

    # Primer pedido: el rectangulo objetivo, agrandado por el margen
    # invisible declarado (asi el contenido VISIBLE, no la ventana entera,
    # cae en (x, y, width, height)).
    request = (x - left, y - top, width + left + right, height + top + bottom)

    # El resultado de pedir una geometria no sigue una formula fija y
    # predecible (depende de como Marco y la propia app interpreten el
    # pedido, y varia entre aplicaciones): en vez de confiar en el calculo
    # de arriba, se mide la posicion real resultante, se compara contra el
    # objetivo, y se corrige el pedido con el error observado. Convergencia
    # en 1 intento si todo sale como se espera, hasta 3 si no.
    for attempt in range(3):
        _apply(*request)
        time.sleep(0.3)

        raw = _get_actual_geometry(xid)
        visible = (raw[0] + left, raw[1] + top, raw[2] - left - right, raw[3] - top - bottom)
        error = (x - visible[0], y - visible[1], width - visible[2], height - visible[3])

        if _DEBUG:
            print(
                f"[placer] xid={xid} intento {attempt + 1}: pedido={request} "
                f"raw={raw} visible={visible} target=({x},{y},{width},{height}) error={error}",
                file=sys.stderr,
            )

        if error == (0, 0, 0, 0):
            break

        request = (
            request[0] + error[0],
            request[1] + error[1],
            request[2] + error[2],
            request[3] + error[3],
        )


def place_left(xid, percent):
    x, y, w, h = get_workarea()
    left_w = w * percent // 100
    place_window(xid, x, y, left_w, h)


def place_right(xid, left_percent):
    # el ancho de la izquierda se recalcula igual que en place_left en vez
    # de recibirlo como parametro, para que ambas llamadas puedan hacerse
    # de forma independiente sin tener que pasarse estado entre si
    x, y, w, h = get_workarea()
    left_w = w * left_percent // 100
    place_window(xid, x + left_w, y, w - left_w, h)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: python3 placer.py <xid_izquierda> <xid_derecha>")
        print("Sacá los xid con: python3 picker.py")
        sys.exit(1)

    xid_left = int(sys.argv[1])
    xid_right = int(sys.argv[2])

    Wnck.Screen.get_default().force_update()
    Wnck.Window.get(xid_left).activate(0)
    Wnck.Window.get(xid_right).activate(0)

    place_left(xid_left, 50)
    place_right(xid_right, 50)
    print("Listo.")
