import os
import time

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Wnck", "3.0")
from gi.repository import Gtk, Gdk, Wnck, Pango

# Tipos de ventana que tiene sentido ofrecer para dividir pantalla
_SELECTABLE_TYPES = (Wnck.WindowType.NORMAL, Wnck.WindowType.DIALOG)


def _get_candidate_windows(exclude_xids):
    """Ventanas abiertas, sin las de exclude_xids, sin las de Arkhas mismo,
    y sin paneles/tooltips/etc."""
    screen = Wnck.Screen.get_default()
    screen.force_update()  # sin esto, ventanas nuevas pueden no aparecer todavia

    exclude_xids = exclude_xids or set()
    own_pid = os.getpid()

    windows = []
    for w in screen.get_windows():
        if w.get_xid() in exclude_xids:
            continue
        if w.get_pid() == own_pid:
            continue
        if w.is_skip_tasklist():
            continue
        if w.get_window_type() not in _SELECTABLE_TYPES:
            continue
        windows.append(w)
    return windows


class WindowPicker(Gtk.Window):
    """Ventana emergente tipo rofi (override-redirect) para elegir una
    ventana abierta. Al no pasar por el gestor de ventanas, siempre queda
    arriba y agarra el teclado al instante, sin depender de que Marco le
    ceda el foco.

    Uso:
        xid = WindowPicker(exclude_xids={xid_ya_elegido}).run_and_get_xid()
        # xid es None si se cancelo (Escape)
    """

    def __init__(self, exclude_xids=None):
        super().__init__(type=Gtk.WindowType.POPUP)
        self.set_default_size(440, 380)
        self.set_position(Gtk.WindowPosition.CENTER_ALWAYS)
        self.get_style_context().add_class("arkhas-picker")

        self._result = None
        self._seat = None
        self.listbox = None

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.set_border_width(14)
        self.add(outer)

        windows = _get_candidate_windows(exclude_xids)

        if windows:
            hint = Gtk.Label(label="Elegí una ventana — Esc para cancelar")
            hint.set_xalign(0)
            outer.pack_start(hint, False, False, 0)

            scroller = Gtk.ScrolledWindow()
            scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            outer.pack_start(scroller, True, True, 8)

            self.listbox = Gtk.ListBox()
            self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
            self.listbox.set_activate_on_single_click(True)
            self.listbox.connect("row-activated", self._on_row_activated)
            scroller.add(self.listbox)

            for w in windows:
                self.listbox.add(self._build_row(w))
            self.listbox.show_all()

            first_row = self.listbox.get_row_at_index(0)
            if first_row is not None:
                self.listbox.select_row(first_row)
        else:
            empty_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            empty_box.set_valign(Gtk.Align.CENTER)
            empty_box.set_vexpand(True)

            title = Gtk.Label(label="No hay ninguna otra ventana para elegir")
            title.set_xalign(0.5)
            title.set_justify(Gtk.Justification.CENTER)
            title.set_line_wrap(True)
            title.get_style_context().add_class("arkhas-picker-empty-title")
            empty_box.pack_start(title, False, False, 0)

            subtitle = Gtk.Label(label="Presioná Esc para cancelar")
            subtitle.set_xalign(0.5)
            empty_box.pack_start(subtitle, False, False, 0)

            outer.pack_start(empty_box, True, True, 0)

        self.connect("key-press-event", self._on_key_press)

    def _build_row(self, window):
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_border_width(8)

        pixbuf = window.get_icon()
        if pixbuf is not None:
            box.pack_start(Gtk.Image.new_from_pixbuf(pixbuf), False, False, 0)

        class_group = window.get_class_group_name() or ""
        title = window.get_name() or ""
        label = Gtk.Label(label=f"{class_group}    {title}")
        label.set_xalign(0)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        box.pack_start(label, True, True, 0)

        row.add(box)
        row.arkhas_window = window
        return row

    def _on_row_activated(self, listbox, row):
        window = row.arkhas_window
        window.activate(Gtk.get_current_event_time())
        self._finish(window.get_xid())

    def _on_key_press(self, widget, event):
        keyname = Gdk.keyval_name(event.keyval)
        if keyname == "Escape":
            self._finish(None)
            return True
        if self.listbox is None:
            return True  # estado vacio: no hay nada mas para navegar
        if keyname in ("Return", "KP_Enter"):
            row = self.listbox.get_selected_row()
            if row is not None:
                self._on_row_activated(self.listbox, row)
            return True
        if keyname == "Down":
            self._move_selection(1)
            return True
        if keyname == "Up":
            self._move_selection(-1)
            return True
        return False

    def _move_selection(self, delta):
        row = self.listbox.get_selected_row()
        index = row.get_index() if row is not None else -1
        next_row = self.listbox.get_row_at_index(index + delta)
        if next_row is not None:
            self.listbox.select_row(next_row)
            next_row.grab_focus()

    def _finish(self, xid):
        self._result = xid
        self._release_grab()
        self.destroy()
        Gtk.main_quit()

    def _grab_input(self):
        gdk_window = self.get_window()
        if gdk_window is None:
            return
        display = Gdk.Display.get_default()
        seat = display.get_default_seat()

        for attempt in range(15):
            status = seat.grab(
                gdk_window,
                Gdk.SeatCapabilities.ALL,
                True,   # owner_events
                None,   # cursor
                None,   # event
                None,   # prepare_func
                None,   # prepare_func_target
            )
            if status == Gdk.GrabStatus.SUCCESS:
                self._seat = seat
                return
            # la ventana puede no estar mapeada todavia (mas probable en la
            # 2da llamada, justo despues de reposicionar la 1ra ventana):
            # procesamos eventos pendientes y reintentamos
            time.sleep(0.02)
            while Gtk.events_pending():
                Gtk.main_iteration()

    def _release_grab(self):
        if self._seat is not None:
            self._seat.ungrab()
            self._seat = None

    def run_and_get_xid(self):
        """Muestra el picker (bloqueante) y devuelve el xid elegido, o None si se cancelo."""
        self.show_all()
        self.present()
        while Gtk.events_pending():
            Gtk.main_iteration()
        self._grab_input()
        Gtk.main()
        return self._result


if __name__ == "__main__":
    # Prueba aislada: python3 picker.py
    from theme import apply_theme

    apply_theme()
    xid = WindowPicker().run_and_get_xid()
    print("Seleccionaste xid:", xid)
