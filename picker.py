import os
import time

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Wnck", "3.0")
from gi.repository import Gtk, Gdk, GLib, Wnck, Pango

import sysstats

# Solo tiene sentido ofrecer ventanas normales o dialogos para dividir
# pantalla; se descartan paneles, docks, tooltips, etc. que Wnck tambien
# reporta en la lista de ventanas del escritorio.
_SELECTABLE_TYPES = (Wnck.WindowType.NORMAL, Wnck.WindowType.DIALOG)

# Intervalo de actualizacion de las estadisticas (RAM/swap del sistema y
# CPU por ventana). 1 segundo alcanza para que se sienta "en vivo" sin
# recorrer procesos con psutil demasiado seguido.
_STATS_INTERVAL_MS = 1000


def _get_candidate_windows(exclude_xids):
    screen = Wnck.Screen.get_default()
    # Wnck mantiene su propio cache interno de ventanas por escritorio; en
    # un proceso recien arrancado (o si se abrio/cerro algo hace poco) ese
    # cache puede estar desactualizado. force_update() lo sincroniza contra
    # el servidor X antes de leer get_windows().
    screen.force_update()

    exclude_xids = exclude_xids or set()
    own_pid = os.getpid()

    # get_windows_stacked() devuelve las ventanas en orden de apilamiento,
    # de mas atras a mas adelante. La ultima de la lista es la que esta
    # mas arriba (la que tuvo el foco mas recientemente), asi que se
    # invierte para que la lista quede ordenada "mas reciente primero" -
    # mismo criterio que usa un Alt+Tab, sin necesidad de que Arkhas lleve
    # su propio historial de foco.
    stacked = list(screen.get_windows_stacked())
    stacked.reverse()

    windows = []
    for w in stacked:
        try:
            # exclude_xids identifica ventanas por xid puntual, no por
            # clase de aplicacion: permite elegir dos instancias del
            # mismo navegador sin que la segunda seleccion vuelva a
            # ofrecer la que ya se eligio.
            if w.get_xid() in exclude_xids:
                continue
            # sin este filtro, la propia ventana de configuracion de
            # Arkhas (si esta abierta de fondo) apareceria como
            # candidata para dividir.
            if w.get_pid() == own_pid:
                continue
            if w.is_skip_tasklist():
                continue
            if w.get_window_type() not in _SELECTABLE_TYPES:
                continue
        except Exception as e:
            # una ventana puntual en estado raro (cerrandose justo en
            # este instante, sin PID valido, etc.) no debe tirar abajo
            # el listado entero: se salta esa y se sigue con el resto,
            # dejando rastro en el log para poder diagnosticar si se
            # repite.
            print(f"Arkhas: ventana descartada al listar candidatas: {e!r}", flush=True)
            continue
        windows.append(w)
    return windows


# Umbrales para colorear las pastillas de RAM/swap: por debajo del primer
# valor es "sano", entre el primero y el segundo "atencion", entre el
# segundo y el tercero "alto", y de ahi para arriba "critico". Los nombres
# de clase se remueven todos antes de aplicar la que corresponde, para no
# ir acumulando clases viejas en cada actualizacion.
_MEM_STATE_CLASSES = (
    "arkhas-pill-mem-unknown",
    "arkhas-pill-mem-healthy",
    "arkhas-pill-mem-warning",
    "arkhas-pill-mem-high",
    "arkhas-pill-mem-critical",
)


def _mem_severity_class(percent):
    if percent < 60:
        return "arkhas-pill-mem-healthy"
    if percent < 75:
        return "arkhas-pill-mem-warning"
    if percent < 90:
        return "arkhas-pill-mem-high"
    return "arkhas-pill-mem-critical"


def _apply_mem_severity(label, percent):
    ctx = label.get_style_context()
    for cls in _MEM_STATE_CLASSES:
        ctx.remove_class(cls)
    ctx.add_class(_mem_severity_class(percent))


def pick_window(exclude_xids=None):
    """Resuelve una seleccion de ventana, sin abrir el picker si no hace
    falta elegir entre nada:

    - 0 ventanas candidatas: devuelve None (no hay nada para elegir; el
      llamador decide que hacer, tipicamente no hacer nada o caer al
      porcentaje configurado).
    - 1 sola candidata: se elige y activa automaticamente, sin mostrar
      el picker (elegir entre una sola opcion no aporta nada).
    - 2 o mas candidatas: se muestra el picker normal.

    Sirve tanto para la 1ra seleccion (exclude_xids=None) como para la
    2da (exclude_xids={xid de la 1ra}).
    """
    windows = _get_candidate_windows(exclude_xids)
    if not windows:
        print("Arkhas: pick_window sin candidatas, no se abre picker", flush=True)
        return None
    if len(windows) == 1:
        window = windows[0]
        window.activate(Gtk.get_current_event_time())
        print(f"Arkhas: pick_window auto-selecciono unica candidata xid={window.get_xid()}", flush=True)
        return window.get_xid()
    print(f"Arkhas: pick_window abre picker con {len(windows)} candidatas", flush=True)
    return WindowPicker(exclude_xids=exclude_xids).run_and_get_xid()


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
    Devuelve None si se cancelo (Esc) o si se maximizo la ventana
    seleccionada con Espacio en vez de elegirla para dividir.
    """

    def __init__(self, exclude_xids=None):
        super().__init__(type=Gtk.WindowType.POPUP)
        self.set_default_size(440, 380)
        self.set_position(Gtk.WindowPosition.CENTER_ALWAYS)
        self.get_style_context().add_class("arkhas-picker")

        # Sin visual RGBA, el canal alfa del CSS se ignora y la ventana se
        # pinta solida igual. Solo tiene efecto si hay un compositor
        # corriendo (is_composited); sin uno, forzar el visual puede
        # renderizar mal, asi que se deja el visual por defecto en ese caso.
        screen = self.get_screen()
        if screen.is_composited():
            rgba_visual = screen.get_rgba_visual()
            if rgba_visual is not None:
                self.set_visual(rgba_visual)

        self._result = None
        self._seat = None
        self.listbox = None
        self._windows = []
        self._position_pill = None

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.set_border_width(14)
        self.add(outer)

        windows = _get_candidate_windows(exclude_xids)
        self._windows = windows

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        outer.pack_start(header, False, False, 0)

        esc_pill = Gtk.Label(label="Esc")
        esc_pill.get_style_context().add_class("arkhas-pill-dark")
        header.pack_start(esc_pill, False, False, 0)

        if windows:
            close_pill = Gtk.Label(label="X para cerrar")
            close_pill.get_style_context().add_class("arkhas-pill")
            header.pack_start(close_pill, False, False, 0)

            maximize_pill = Gtk.Label(label="Espacio para maximizar")
            maximize_pill.get_style_context().add_class("arkhas-pill")
            header.pack_start(maximize_pill, False, False, 0)

            self._position_pill = Gtk.Label(label=f"Ventana 1 de {len(windows)}")
            self._position_pill.get_style_context().add_class("arkhas-pill-dark")
            header.pack_end(self._position_pill, False, False, 0)

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
            # row-selected cubre tanto el cambio por flechas como el
            # preseleccionado inicial y el que ocurre justo antes de la
            # activacion por click, asi la pastilla "Ventana X de N" queda
            # sincronizada sin importar como se movio la seleccion.
            self.listbox.connect("row-selected", self._on_row_selected)
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

        # El footer de RAM/swap va siempre, este o no vacia la lista: son
        # estadisticas del sistema, no de la seleccion. RAM a la izquierda,
        # Swap a la derecha (mismo patron pack_start/pack_end que Esc y
        # "Ventana X de N" en el header).
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        footer.set_margin_top(10)
        outer.pack_start(footer, False, False, 0)

        self._ram_pill = Gtk.Label(label="RAM: --%")
        self._ram_pill.get_style_context().add_class("arkhas-pill-mem")
        self._ram_pill.get_style_context().add_class("arkhas-pill-mem-unknown")
        footer.pack_start(self._ram_pill, False, False, 0)

        self._swap_pill = Gtk.Label(label="Swap: --%")
        self._swap_pill.get_style_context().add_class("arkhas-pill-mem")
        self._swap_pill.get_style_context().add_class("arkhas-pill-mem-unknown")
        footer.pack_end(self._swap_pill, False, False, 0)

        if not sysstats.stats_available():
            self._ram_pill.set_text("RAM: N/D")
            self._swap_pill.set_text("Swap: N/D")

        self._stats_timeout_id = None
        if sysstats.stats_available():
            self._refresh_stats()  # 1er valor inmediato, sin esperar el 1er tick
            self._stats_timeout_id = GLib.timeout_add(_STATS_INTERVAL_MS, self._on_stats_tick)

        self.connect("key-press-event", self._on_key_press)

    def _build_row(self, window):
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_border_width(8)

        pixbuf = window.get_icon()
        if pixbuf is not None:
            box.pack_start(Gtk.Image.new_from_pixbuf(pixbuf), False, False, 0)

        title = window.get_name() or ""
        label = Gtk.Label(label=title)
        label.set_xalign(0)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        box.pack_start(label, True, True, 0)

        # % de CPU que ocupa el proceso de esta ventana (y sus hijos), no
        # cual es la causa (no se distingue "esta compilando" de "esta
        # reproduciendo un video" - solo el numero, como se pidio).
        cpu_label = Gtk.Label(label="")
        cpu_label.get_style_context().add_class("arkhas-row-cpu")
        box.pack_start(cpu_label, False, False, 0)
        row.arkhas_cpu_label = cpu_label
        row.arkhas_cpu_tracker = (
            sysstats.ProcessTreeCpu(window.get_pid())
            if sysstats.stats_available() and window.get_pid()
            else None
        )

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
        if keyname in ("x", "X"):
            self._close_selected_window()
            return True
        if keyname == "space":
            self._maximize_selected_window()
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

    def _maximize_selected_window(self):
        row = self.listbox.get_selected_row()
        if row is None:
            return
        try:
            row.arkhas_window.maximize()
        except Exception as e:
            # Un fallo aca (ventana ya cerrada, error de Wnck, etc.) no
            # debe impedir cerrar el picker: si _finish() no se alcanza,
            # el Gtk.main() anidado en run_and_get_xid() queda colgado
            # para siempre, y el proximo disparo del atajo abre un picker
            # nuevo APILADO sobre este en vez de uno limpio.
            print(f"Arkhas: error al maximizar: {e!r}", flush=True)
        # a diferencia de elegir con Enter, maximizar no pasa por
        # placer.py (que la desmaximizaria para acomodarla al porcentaje):
        # se cierra el picker directo, sin seleccion, para que quede
        # maximizada tal cual.
        self._finish(None)

    def _close_selected_window(self):
        row = self.listbox.get_selected_row()
        if row is None:
            return
        window = row.arkhas_window
        try:
            # close() pide el cierre de la ventana (equivalente a la X del
            # gestor de ventanas); es asincrono, la app puede tardar en
            # cerrarse o incluso cancelarlo (ej: "guardar cambios?"). Se
            # saca la fila de la lista de todos modos de forma optimista,
            # sin esperar confirmacion.
            window.close(Gtk.get_current_event_time())
        except Exception as e:
            print(f"Arkhas: error al cerrar ventana: {e!r}", flush=True)

        index = row.get_index()
        self._windows = [w for w in self._windows if w.get_xid() != window.get_xid()]
        self.listbox.remove(row)

        # No se espera al proximo tick del timer: se refresca ya, aunque
        # close() sea asincrono y el sistema operativo pueda tardar un
        # instante en liberar la memoria del todo (el proximo tick lo
        # termina de reflejar si hace falta).
        if sysstats.stats_available():
            self._refresh_stats()

        if not self._windows:
            # no queda nada para elegir: mismo resultado que cancelar
            self._finish(None)
            return

        next_row = self.listbox.get_row_at_index(min(index, len(self._windows) - 1))
        if next_row is not None:
            self.listbox.select_row(next_row)
            next_row.grab_focus()

    def _on_row_selected(self, listbox, row):
        if row is None or self._position_pill is None:
            return
        self._position_pill.set_text(f"Ventana {row.get_index() + 1} de {len(self._windows)}")

    def _refresh_stats(self):
        ram_percent = sysstats.system_ram_percent()
        swap_percent = sysstats.system_swap_percent()
        self._ram_pill.set_text(f"RAM: {ram_percent:.0f}%")
        _apply_mem_severity(self._ram_pill, ram_percent)
        self._swap_pill.set_text(f"Swap: {swap_percent:.0f}%")
        _apply_mem_severity(self._swap_pill, swap_percent)

        if self.listbox is None:
            return
        row = self.listbox.get_row_at_index(0)
        while row is not None:
            tracker = getattr(row, "arkhas_cpu_tracker", None)
            if tracker is not None:
                row.arkhas_cpu_label.set_text(f"{tracker.poll():.0f}%")
            row = self.listbox.get_row_at_index(row.get_index() + 1)

    def _on_stats_tick(self):
        try:
            self._refresh_stats()
        except Exception as e:
            print(f"Arkhas: error actualizando estadisticas: {e!r}", flush=True)
        return True  # True = GLib repite el timeout; se corta explicitamente en _finish

    def _move_selection(self, delta):
        row = self.listbox.get_selected_row()
        index = row.get_index() if row is not None else -1
        next_row = self.listbox.get_row_at_index(index + delta)
        if next_row is not None:
            self.listbox.select_row(next_row)
            next_row.grab_focus()

    def _finish(self, xid):
        self._result = xid
        # se corta el timer de estadisticas ANTES de destruir: si sigue
        # corriendo y su callback intenta actualizar labels de una
        # ventana ya destruida, tira excepciones en cada tick indefinidamente
        if self._stats_timeout_id is not None:
            GLib.source_remove(self._stats_timeout_id)
            self._stats_timeout_id = None
        # try/finally: Gtk.main_quit() tiene que ejecutarse SIEMPRE, pase
        # lo que pase en _release_grab()/destroy(). Si alguno de los dos
        # tira una excepcion y main_quit() nunca se llama, el Gtk.main()
        # anidado en run_and_get_xid() queda corriendo para siempre: el
        # proceso sigue vivo (por eso "parecia" que el atajo dejaba de
        # andar), pero cada disparo nuevo del atajo apila un picker mas
        # adentro del que quedo colgado, en vez de abrir uno limpio.
        try:
            self._release_grab()
            self.destroy()
        except Exception as e:
            print(f"Arkhas: error cerrando el picker: {e!r}", flush=True)
        finally:
            # Gtk.main() metido dentro de run_and_get_xid() bloquea la
            # llamada; main_quit() es lo que le devuelve el control al
            # codigo que llamo a run_and_get_xid().
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
