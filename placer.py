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

_xlib_display = None


def _get_xlib_display():
    global _xlib_display
    if _xlib_display is None:
        _xlib_display = Xlib.display.Display()
    return _xlib_display


def _get_frame_extents(xid):
    """(left, right, top, bottom) del margen invisible que reservan las apps
    con decoracion del lado del cliente (Brave, Thorium, etc). Marco NO lo
    compensa solo (lo confirmamos con datos), asi que lo hacemos nosotros.
    Si la ventana no define esa propiedad, devuelve (0,0,0,0)."""
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
    """Geometria REAL actual de la ventana (x,y absolutos respecto a la
    raiz, mas ancho/alto), leida directo del servidor X. No usamos
    Wnck.Window.get_geometry() para esto porque devuelve valores poco
    confiables/desactualizados en este contexto."""
    display = _get_xlib_display()
    window = display.create_resource_object("window", xid)
    geom = window.get_geometry()
    root = display.screen().root
    translated = window.translate_coords(root, 0, 0)
    return (translated.x, translated.y, geom.width, geom.height)


def get_workarea():
    """(x, y, width, height) del area de trabajo del escritorio activo,
    excluye paneles. Lee _NET_WORKAREA / _NET_CURRENT_DESKTOP directo."""
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
    """Mueve/redimensiona la ventana xid para que su contenido VISIBLE quede
    en (x, y, width, height).

    En vez de calcular la compensacion una sola vez y confiar en que salga
    bien, medimos el resultado real despues de cada pedido y corregimos el
    error observado, hasta 3 intentos. Esto porque el comportamiento real
    (Marco + la propia app) no sigue una formula fija y predecible."""
    screen = Wnck.Screen.get_default()
    screen.force_update()  # sin esto, xids recien creados pueden no aparecer

    window = Wnck.Window.get(xid)
    if window is None:
        raise RuntimeError(f"No encontre la ventana con xid {xid}")

    window.unmaximize()
    time.sleep(0.05)

    left, right, top, bottom = _get_frame_extents(xid)

    def _apply(rx, ry, rw, rh):
        window.set_geometry(
            Wnck.WindowGravity.CURRENT,
            (
                Wnck.WindowMoveResizeMask.X
                | Wnck.WindowMoveResizeMask.Y
                | Wnck.WindowMoveResizeMask.WIDTH
                | Wnck.WindowMoveResizeMask.HEIGHT
            ),
            rx, ry, rw, rh,
        )

    # Primer pedido: compensamos con el margen declarado por la ventana.
    request = (x - left, y - top, width + left + right, height + top + bottom)

    for attempt in range(3):
        _apply(*request)
        time.sleep(0.3)

        raw = _get_actual_geometry(xid)  # geometria cruda real de la ventana X
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
    """Ubica xid pegada a la izquierda, ocupando `percent`% del area de trabajo."""
    x, y, w, h = get_workarea()
    left_w = w * percent // 100
    place_window(xid, x, y, left_w, h)


def place_right(xid, left_percent):
    """Ubica xid pegada a la derecha, ocupando el resto (100 - left_percent)%."""
    x, y, w, h = get_workarea()
    left_w = w * left_percent // 100
    place_window(xid, x + left_w, y, w - left_w, h)


if __name__ == "__main__":
    # Prueba aislada: python3 placer.py <xid_izquierda> <xid_derecha>
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
