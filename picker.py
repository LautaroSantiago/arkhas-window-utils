import os
import time

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Wnck", "3.0")
from gi.repository import Gtk, Gdk, Wnck, Pango

# Solo tiene sentido ofrecer ventanas normales o dialogos para dividir
# pantalla; se descartan paneles, docks, tooltips, etc. que Wnck tambien
# reporta en la lista de ventanas del escritorio.
_SELECTABLE_TYPES = (Wnck.WindowType.NORMAL, Wnck.WindowType.DIALOG)


def _get_candidate_windows(exclude_xids):
    screen = Wnck.Screen.get_default()
    # Wnck mantiene su propio cache interno de ventanas por escritorio; en
    # un proceso recien arrancado (o si se abrio/cerro algo hace poco) ese
    # cache puede estar desactualizado. force_update() lo sincroniza contra
    # el servidor X antes de leer get_windows().
    screen.force_update()

    exclude_xids = exclude_xids or set()
    own_pid = os.getpid()

    windows = []
    for w in screen.get_windows():
        # exclude_xids identifica ventanas por xid puntual, no por clase de
        # aplicacion: permite elegir dos instancias del mismo navegador sin
        # que la segunda seleccion vuelva a ofrecer la que ya se eligio.
        if w.get_xid() in exclude_xids:
            continue
        # sin este filtro, la propia ventana de configuracion de Arkhas (si
        # esta abierta de fondo) apareceria como candidata para dividir.
        if w.get_pid() == own_pid:
            continue
        if w.is_skip_tasklist():
            continue
        if w.get_window_type() not in _SELECTABLE_TYPES:
            continue
        windows.append(w)
    return windows


class WindowPicker(Gtk.Window):
    """Selector de ventanas que reemplaza a rofi. Se construye como
    Gtk.WindowType.POPUP (ventana override-redirect): el servidor X la
    mapea directo, sin pasar por el gestor de ventanas, por lo que no
    tiene decoraciones, no entra al ciclo de foco normal de Marco, y no
    hace falta pedirle al WM que la mantenga arriba.

    Como consecuencia de ser override-redirect, tampoco recibe foco de
    teclado automaticamente del WM: por eso el foco se toma a mano con un
    grab de Gdk.Seat (ver _grab_input) en vez de confiar en que el gestor
    de ventanas se lo otorgue.

    Uso: xid = WindowPicker(exclude_xids={...}).run_and_get_xid()
    Devuelve None si se cancelo con Escape.
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

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        outer.pack_start(header, False, False, 0)

        esc_pill = Gtk.Label(label="Esc")
        esc_pill.get_style_context().add_class("arkhas-pill")
        header.pack_start(esc_pill, False, False, 0)

        count_pill = Gtk.Label(label=f"Ventanas: {len(windows)}")
        count_pill.get_style_context().add_class("arkhas-pill")
        header.pack_end(count_pill, False, False, 0)

        if windows:
            scroller = Gtk.ScrolledWindow()
            scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            outer.pack_start(scroller, True, True, 8)

            self.listbox = Gtk.ListBox()
            self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
            # activate-on-single-click: un click alcanza para elegir,
            # replicando el flujo rapido de rofi (no hace falta doble click
            # ni confirmar aparte).
            self.listbox.set_activate_on_single_click(True)
            self.listbox.connect("row-activated", self._on_row_activated)
            scroller.add(self.listbox)

            for w in windows:
                self.listbox.add(self._build_row(w))
            self.listbox.show_all()

            # se preselecciona la primera fila para que las flechas/Enter
            # funcionen de entrada, sin necesidad de tocar el mouse primero
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
        # se guarda el objeto Wnck.Window directo en la fila para no tener
        # que volver a buscarlo por xid al activarla
        row.arkhas_window = window
        return row

    def _on_row_activated(self, listbox, row):
        window = row.arkhas_window
        # activate() sube y enfoca la ventana elegida, igual que hacia rofi
        # en modo "window" al seleccionar. placer.py depende de que esto ya
        # haya pasado para posicionar la ventana correcta.
        window.activate(Gtk.get_current_event_time())
        self._finish(window.get_xid())

    def _on_key_press(self, widget, event):
        keyname = Gdk.keyval_name(event.keyval)
        if keyname == "Escape":
            self._finish(None)
            return True
        if self.listbox is None:
            # estado vacio (sin ventanas candidatas): no hay lista que
            # navegar, la unica accion posible es cancelar
            return True
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
        # Gtk.main() metido dentro de run_and_get_xid() bloquea la llamada;
        # main_quit() es lo que le devuelve el control al codigo que llamo
        # a run_and_get_xid().
        Gtk.main_quit()

    def _grab_input(self):
        gdk_window = self.get_window()
        if gdk_window is None:
            return
        display = Gdk.Display.get_default()
        seat = display.get_default_seat()

        # El grab puede fallar si se pide antes de que el servidor X haya
        # terminado de mapear la ventana (mas probable en la 2da seleccion,
        # que se dispara justo despues de reposicionar la 1ra ventana, con
        # el gestor de ventanas todavia procesando ese cambio). Se reintenta
        # procesando eventos pendientes entre intento e intento en vez de
        # fallar directo.
        for attempt in range(15):
            status = seat.grab(
                gdk_window,
                Gdk.SeatCapabilities.ALL,
                True,   # owner_events: los eventos siguen llegando a los
                        # widgets internos de esta ventana en vez de solo
                        # a la ventana raiz del grab
                None,   # cursor: se usa el cursor por defecto
                None,   # event: sin evento de origen especifico
                None,   # prepare_func
                None,   # prepare_func_target
            )
            if status == Gdk.GrabStatus.SUCCESS:
                self._seat = seat
                return
            time.sleep(0.02)
            while Gtk.events_pending():
                Gtk.main_iteration()

    def _release_grab(self):
        if self._seat is not None:
            self._seat.ungrab()
            self._seat = None

    def run_and_get_xid(self):
        self.show_all()
        self.present()
        # se procesan los eventos pendientes antes de pedir el grab: sin
        # esto, get_window() puede devolver una ventana X todavia no
        # mapeada y el primer intento de grab fallaria siempre
        while Gtk.events_pending():
            Gtk.main_iteration()
        self._grab_input()
        Gtk.main()
        return self._result


if __name__ == "__main__":
    from theme import apply_theme

    apply_theme()
    xid = WindowPicker().run_and_get_xid()
    print("Seleccionaste xid:", xid)
