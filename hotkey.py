import time
import threading

import Xlib.display
import Xlib.X
import Xlib.XK

from gi.repository import GLib

MODIFIER_MASKS = {
    "Control": Xlib.X.ControlMask,
    "Alt": Xlib.X.Mod1Mask,
    "Super": Xlib.X.Mod4Mask,
    "Shift": Xlib.X.ShiftMask,
}

# Combinaciones de Caps Lock / Num Lock a ignorar, para que el atajo
# funcione sin importar si estan activados.
_IGNORED_LOCKS = (0, Xlib.X.LockMask, Xlib.X.Mod2Mask, Xlib.X.LockMask | Xlib.X.Mod2Mask)
_LOCK_BITS = Xlib.X.LockMask | Xlib.X.Mod2Mask


class HotkeyListener:
    """Escucha un atajo global (funciona aunque la app no tenga el foco).

    Uso:
        listener = HotkeyListener(on_trigger=mi_funcion)
        listener.start({"keysym": "F14", "modifiers": ["Super"]})
        ...
        listener.stop()
    """

    def __init__(self, on_trigger=None):
        self.on_trigger = on_trigger
        self._display = None
        self._root = None
        self._thread = None
        self._running = False
        self._keycode = None
        self._modmask = None

    def start(self, hotkey):
        """hotkey: {"keysym": "F14", "modifiers": ["Super", ...]}"""
        self.stop()

        if not hotkey or not hotkey.get("keysym"):
            return

        keysym = Xlib.XK.string_to_keysym(hotkey["keysym"])
        if keysym == 0:
            raise ValueError(f"No reconozco la tecla: {hotkey['keysym']!r}")

        self._display = Xlib.display.Display()
        self._root = self._display.screen().root
        self._keycode = self._display.keysym_to_keycode(keysym)

        self._modmask = 0
        for name in hotkey.get("modifiers", []):
            self._modmask |= MODIFIER_MASKS.get(name, 0)

        self._root.change_attributes(event_mask=Xlib.X.KeyPressMask)
        for lock in _IGNORED_LOCKS:
            self._root.grab_key(
                self._keycode, self._modmask | lock, True,
                Xlib.X.GrabModeAsync, Xlib.X.GrabModeAsync,
            )
        self._display.sync()

        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=0.5)
            self._thread = None

        if self._display is not None:
            try:
                for lock in _IGNORED_LOCKS:
                    self._root.ungrab_key(self._keycode, self._modmask | lock, self._root)
                self._display.sync()
            except Exception:
                pass
            try:
                self._display.close()
            except Exception:
                pass
            self._display = None

    def _listen_loop(self):
        while self._running:
            try:
                while self._display.pending_events() > 0:
                    event = self._display.next_event()
                    if event.type != Xlib.X.KeyPress:
                        continue
                    pressed_mod = event.state & ~_LOCK_BITS
                    if event.detail == self._keycode and pressed_mod == self._modmask:
                        if self.on_trigger:
                            GLib.idle_add(self.on_trigger)
            except Exception:
                # la conexion se pudo haber cerrado desde stop(); cortamos
                break
            time.sleep(0.05)


if __name__ == "__main__":
    # Prueba aislada: usa el atajo ya guardado desde la interfaz (ui.py / main.py)
    from config import load_config

    cfg = load_config()
    hk = cfg.get("hotkey")

    if not hk:
        print("No hay atajo guardado todavia. Corre main.py, configuralo y guardalo primero.")
    else:
        print(f"Escuchando atajo: {hk}  (Ctrl+C para salir)")

        def _on_trigger():
            print("¡Atajo detectado!")

        listener = HotkeyListener(on_trigger=_on_trigger)
        listener.start(hk)

        loop = GLib.MainLoop()
        try:
            loop.run()
        except KeyboardInterrupt:
            listener.stop()
            print("\nChau.")
