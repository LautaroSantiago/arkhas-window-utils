import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk

from config import load_config, save_config
from hotkey import HotkeyListener
from picker import WindowPicker
from placer import place_left, place_right

MODIFIER_KEYNAMES = (
    "Shift_L", "Shift_R",
    "Control_L", "Control_R",
    "Alt_L", "Alt_R",
    "Super_L", "Super_R",
)


class ArkhasWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Arkhas")
        self.set_default_size(380, 280)
        self.set_border_width(24)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_resizable(False)

        self.config = load_config()
        self.listening_for_key = False
        self.hotkey_listener = HotkeyListener(on_trigger=self.on_hotkey_triggered)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self.add(root)

        # --- Atajo de teclado ---
        hotkey_label = Gtk.Label(label="Atajo para activar la división")
        hotkey_label.set_xalign(0)
        root.pack_start(hotkey_label, False, False, 0)

        self.hotkey_button = Gtk.Button(label=self._hotkey_display())
        self.hotkey_button.connect("clicked", self.on_hotkey_button_clicked)
        root.pack_start(self.hotkey_button, False, False, 0)

        # --- Slider de porcentaje (un solo control -> siempre suma 100) ---
        split_label = Gtk.Label(label="División por defecto (izquierda / derecha)")
        split_label.set_xalign(0)
        root.pack_start(split_label, False, False, 0)

        self.split_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 10, 90, 5
        )
        self.split_scale.set_value(self.config.get("split_percent", 50))
        self.split_scale.set_draw_value(False)
        self.split_scale.connect("value-changed", self.on_split_changed)
        root.pack_start(self.split_scale, False, False, 0)

        self.split_readout = Gtk.Label(label=self._split_display())
        root.pack_start(self.split_readout, False, False, 0)

        # --- Guardar ---
        save_button = Gtk.Button(label="Guardar")
        save_button.connect("clicked", self.on_save_clicked)
        root.pack_start(save_button, False, False, 0)

        self.status_label = Gtk.Label(label="")
        root.pack_start(self.status_label, False, False, 0)

        self.connect("key-press-event", self.on_key_press)
        self.connect("destroy", lambda *_: self.hotkey_listener.stop())

        self._start_listener_if_configured()

    # ---------- helpers de texto ----------

    def _hotkey_display(self):
        hk = self.config.get("hotkey")
        if not hk:
            return "Sin asignar — click para configurar"
        return self._format_hotkey(hk)

    @staticmethod
    def _format_hotkey(hk):
        mods = "+".join(hk.get("modifiers", []))
        keysym = hk.get("keysym", "?")
        return f"{mods}+{keysym}" if mods else keysym

    def _split_display(self):
        left = int(self.split_scale.get_value())
        right = 100 - left
        return f"{left}%  |  {right}%"

    # ---------- callbacks ----------

    def on_split_changed(self, scale):
        self.split_readout.set_text(self._split_display())

    def on_hotkey_button_clicked(self, button):
        self.listening_for_key = True
        button.set_label("Presioná la combinación de teclas...")

    def on_key_press(self, widget, event):
        if not self.listening_for_key:
            return False

        keyname = Gdk.keyval_name(event.keyval)

        # Si soltó solo el modificador (sin tecla principal), seguimos esperando
        if keyname in MODIFIER_KEYNAMES:
            return True

        modifiers = []
        state = event.state
        if state & Gdk.ModifierType.CONTROL_MASK:
            modifiers.append("Control")
        if state & Gdk.ModifierType.MOD1_MASK:
            modifiers.append("Alt")
        if state & Gdk.ModifierType.SUPER_MASK:
            modifiers.append("Super")
        if state & Gdk.ModifierType.SHIFT_MASK:
            modifiers.append("Shift")

        self.config["hotkey"] = {"keysym": keyname, "modifiers": modifiers}
        self.hotkey_button.set_label(self._format_hotkey(self.config["hotkey"]))
        self.listening_for_key = False
        return True

    def on_save_clicked(self, button):
        self.config["split_percent"] = int(self.split_scale.get_value())
        save_config(self.config)
        self._start_listener_if_configured(save_status=True)

    # ---------- atajo global ----------

    def _start_listener_if_configured(self, save_status=False):
        hk = self.config.get("hotkey")
        print(f"Arkhas: config hotkey={hk}", flush=True)
        if not hk:
            self.status_label.set_text("Guardado." if save_status else "")
            return
        try:
            self.hotkey_listener.start(hk)
            print(f"Arkhas: listener arrancado OK para {hk}", flush=True)
            msg = f"Escuchando atajo: {self._format_hotkey(hk)}"
            self.status_label.set_text(f"Guardado. {msg}" if save_status else msg)
        except Exception as e:
            print(f"Arkhas: ERROR arrancando el listener: {e!r}", flush=True)
            self.status_label.set_text(f"No pude activar el atajo: {e}")

    def on_hotkey_triggered(self):
        print("Arkhas: atajo disparado", flush=True)
        percent = self.config.get("split_percent", 50)

        xid1 = WindowPicker().run_and_get_xid()
        print(f"Arkhas: 1ra seleccion xid={xid1}", flush=True)
        if xid1 is None:
            return
        place_left(xid1, percent)

        xid2 = WindowPicker(exclude_xids={xid1}).run_and_get_xid()
        print(f"Arkhas: 2da seleccion xid={xid2}", flush=True)
        if xid2 is None:
            place_left(xid1, 50)
        else:
            place_right(xid2, percent)
