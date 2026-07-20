import math

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk

import cairo


def _rounded_rect(ctx, x, y, w, h, r):
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    ctx.close_path()


def _build_icon_pixbuf(size=22):
    """Dibuja el icono con Cairo en vez de cargarlo de un archivo: dos
    rectangulos representando la division de pantalla, en la misma
    paleta verde del resto de la app. Evita depender de un formato de
    imagen externo (SVG necesitaria libresvg instalado; PNG necesitaria
    empaquetar un binario aparte)."""
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    ctx = cairo.Context(surface)

    pad = 2
    gap = 2
    total_w = size - pad * 2
    h = size - pad * 2
    left_w = int(total_w * 0.55) - gap // 2
    right_w = total_w - left_w - gap
    radius = 3

    # panel izquierdo: verde acento solido
    _rounded_rect(ctx, pad, pad, left_w, h, radius)
    ctx.set_source_rgb(0x3E / 255, 0xA8 / 255, 0x6B / 255)
    ctx.fill()

    # panel derecho: fondo oscuro de la app con borde del mismo acento
    _rounded_rect(ctx, pad + left_w + gap, pad, right_w, h, radius)
    ctx.set_source_rgb(0x1C / 255, 0x3A / 255, 0x2C / 255)
    ctx.fill_preserve()
    ctx.set_source_rgb(0x3E / 255, 0xA8 / 255, 0x6B / 255)
    ctx.set_line_width(1.2)
    ctx.stroke()

    return Gdk.pixbuf_get_from_surface(surface, 0, 0, size, size)


class TrayIcon:
    """Icono de bandeja: click izquierdo abre/muestra la ventana de
    configuracion, click derecho da un menu con esa misma accion mas
    Salir (termina el proceso del todo, algo que hasta ahora solo se
    podia hacer con pkill desde la terminal)."""

    def __init__(self, on_show_window=None, on_quit=None):
        self.on_show_window = on_show_window
        self.on_quit = on_quit

        self._status_icon = Gtk.StatusIcon.new_from_pixbuf(_build_icon_pixbuf())
        self._status_icon.set_tooltip_text("Arkhas")
        self._status_icon.set_visible(True)
        self._status_icon.connect("activate", self._on_activate)
        self._status_icon.connect("popup-menu", self._on_popup_menu)

    def set_tooltip(self, text):
        self._status_icon.set_tooltip_text(text)

    def _on_activate(self, icon):
        # click izquierdo (o "activate" del applet, segun el panel)
        try:
            if self.on_show_window:
                self.on_show_window()
        except Exception as e:
            print(f"Arkhas: error abriendo la ventana desde la bandeja: {e!r}", flush=True)

    def _on_popup_menu(self, icon, button, activate_time):
        menu = Gtk.Menu()

        def _safe_show_window(*_):
            try:
                if self.on_show_window:
                    self.on_show_window()
            except Exception as e:
                print(f"Arkhas: error abriendo la ventana desde la bandeja: {e!r}", flush=True)

        def _safe_quit(*_):
            try:
                if self.on_quit:
                    self.on_quit()
            except Exception as e:
                print(f"Arkhas: error al salir desde la bandeja: {e!r}", flush=True)

        open_item = Gtk.MenuItem(label="Abrir configuración")
        open_item.connect("activate", _safe_show_window)
        menu.append(open_item)

        menu.append(Gtk.SeparatorMenuItem())

        quit_item = Gtk.MenuItem(label="Salir")
        quit_item.connect("activate", _safe_quit)
        menu.append(quit_item)

        menu.show_all()
        menu.popup(None, None, Gtk.StatusIcon.position_menu, icon, button, activate_time)
