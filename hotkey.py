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

# XGrabKey no ignora Caps Lock / Num Lock automaticamente: un grab pedido
# con una mascara de modificadores especifica solo dispara si el estado del
# teclado coincide EXACTO, incluyendo esos bits de bloqueo. Por eso hay que
# pedir el mismo grab una vez por cada combinacion posible de esos dos bits
# (ninguno activado, solo Caps, solo Num, ambos) para que el atajo funcione
# sin importar en que estado esten.
_IGNORED_LOCKS = (0, Xlib.X.LockMask, Xlib.X.Mod2Mask, Xlib.X.LockMask | Xlib.X.Mod2Mask)
_LOCK_BITS = Xlib.X.LockMask | Xlib.X.Mod2Mask

# Si se mantiene la tecla apretada un instante, X manda varios KeyPress
# seguidos por auto-repeat (confirmado con xev: dos KeyPress/KeyRelease casi
# pegados en el mismo toque). Sin un debounce, cada uno dispara on_trigger
# por separado, lo que puede terminar abriendo varios pickers apilados en
# vez de uno solo. Se ignora cualquier KeyPress que llegue a menos de este
# intervalo del anterior aceptado.
_DEBOUNCE_SECONDS = 0.4

# Si la conexion X del hilo de escucha se cae por cualquier motivo (hiccup
# del servidor X, resume de suspension, etc), se reintenta reconectar en
# vez de dejar el hilo morir en silencio para siempre. Backoff simple:
# empieza corto, tope en _RECONNECT_MAX_DELAY.
_RECONNECT_INITIAL_DELAY = 1.0
_RECONNECT_MAX_DELAY = 10.0


class HotkeyListener:
    """Atajo global via XGrabKey directo sobre la ventana raiz, en vez de
    depender de la configuracion de atajos de un escritorio en particular
    (MATE, GNOME, etc). Al agarrar la tecla a nivel de la raiz, el evento
    llega aunque ninguna ventana de la app tenga el foco.

    Maneja un caso critico: si al arrancar (tipicamente en el boot, antes
    de que un script de remapeo de teclado como xmodmap termine de correr)
    el keysym configurado todavia no esta producido por ninguna tecla
    fisica, X11 devuelve keycode 0 para esa consulta. Grabar con keycode 0
    NO es un no-op: en X11, 0 es literalmente la constante AnyKey, y pedir
    ese grab agarra TODAS las teclas del teclado. Por eso nunca se llama a
    grab_key con keycode 0 - en su lugar, se espera a que llegue un evento
    MappingNotify (que el servidor X manda automaticamente a todos los
    clientes cuando el mapeo de teclado cambia, sea por xmodmap, un cambio
    de layout, etc) para reintentar resolver y recien ahi grabar."""

    def __init__(self, on_trigger=None):
        self.on_trigger = on_trigger
        self._display = None
        self._root = None
        self._thread = None
        self._running = False
        self._keycode = None  # None/0 = todavia no hay grab activo
        self._modmask = None
        self._hotkey = None  # se guarda para poder re-resolver tras un MappingNotify o una reconexion
        self._last_trigger_time = 0.0

    def start(self, hotkey):
        # stop() primero: si ya habia un grab activo con otra combinacion,
        # hay que soltarlo antes de pedir uno nuevo (start() se usa tanto
        # para el arranque inicial como para aplicar un atajo reconfigurado
        # desde la UI sin reiniciar el proceso).
        self.stop()

        if not hotkey or not hotkey.get("keysym"):
            return

        self._hotkey = hotkey

        # Conexion X11 propia y separada de la que usa GTK/GDK para la
        # interfaz: el grab y el loop de eventos corren en su propio hilo,
        # sin competir con el loop principal de la app.
        self._display = Xlib.display.Display()
        self._root = self._display.screen().root
        # KeyPressMask para el atajo en si, KeymapStateMask para que el
        # servidor nos mande MappingNotify cuando el mapeo de teclado
        # cambie (xmodmap, cambio de layout, etc).
        self._root.change_attributes(event_mask=Xlib.X.KeyPressMask)

        self._modmask = 0
        for name in hotkey.get("modifiers", []):
            self._modmask |= MODIFIER_MASKS.get(name, 0)

        if not self._try_grab():
            # No es un error fatal: puede ser el arranque en el boot,
            # justo antes de que termine de aplicarse un remapeo de
            # teclado. El hilo arranca igual y va a reintentar solo en
            # cuanto llegue el MappingNotify correspondiente.
            print(
                f"Arkhas: '{self._hotkey['keysym']}' todavia no esta "
                f"producido por ninguna tecla - esperando a que el mapeo "
                f"de teclado este listo (reintenta solo, sin reiniciar).",
                flush=True,
            )

        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def _try_grab(self):
        """Intenta resolver el keysym configurado a un keycode actual y
        grabarlo. Devuelve True si lo logro, False si el keysym todavia
        no esta mapeado a ninguna tecla (nunca graba con keycode 0)."""
        keysym = Xlib.XK.string_to_keysym(self._hotkey["keysym"])
        if keysym == 0:
            raise ValueError(f"No reconozco la tecla: {self._hotkey['keysym']!r}")

        keycode = self._display.keysym_to_keycode(keysym)
        if keycode == 0:
            return False

        self._keycode = keycode
        for lock in _IGNORED_LOCKS:
            self._root.grab_key(
                self._keycode, self._modmask | lock, True,
                Xlib.X.GrabModeAsync, Xlib.X.GrabModeAsync,
            )
        self._display.sync()
        return True

    def _ungrab_current(self):
        if not self._keycode:
            return
        try:
            for lock in _IGNORED_LOCKS:
                self._root.ungrab_key(self._keycode, self._modmask | lock, self._root)
            self._display.sync()
        except Exception:
            # la conexion puede estar en un estado invalido si el servidor
            # X ya la cerro; no hay nada mas que hacer con ella
            pass
        self._keycode = None

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=0.5)
            self._thread = None
        self._close_display()

    def _close_display(self):
        if self._display is not None:
            self._ungrab_current()
            try:
                self._display.close()
            except Exception:
                pass
            self._display = None

    def _listen_loop(self):
        # Poll en vez de bloquear en next_event(): un next_event() bloqueado
        # no se puede interrumpir de forma limpia desde otro hilo cuando
        # stop() cierra la conexion. El intervalo de 50ms es indetectable
        # para un atajo de teclado pero permite revisar self._running
        # seguido y salir del hilo sin quedar colgado.
        reconnect_delay = _RECONNECT_INITIAL_DELAY
        while self._running:
            try:
                while self._display.pending_events() > 0:
                    event = self._display.next_event()

                    if event.type == Xlib.X.MappingNotify:
                        # El servidor manda esto automaticamente a todos
                        # los clientes cuando el mapeo de teclado cambia
                        # (xmodmap, cambio de layout, etc). Hay que
                        # refrescar la tabla de mapeo local de Xlib antes
                        # de volver a consultarla, y re-armar el grab con
                        # el keycode que corresponda ahora - puede ser que
                        # antes no hubiera ninguno (boot, arranco antes que
                        # el remapeo) o que el keysym se haya mudado a otra
                        # tecla fisica.
                        self._display.refresh_keyboard_mapping(event)
                        was_grabbed = bool(self._keycode)
                        self._ungrab_current()
                        if self._try_grab() and not was_grabbed:
                            print(
                                f"Arkhas: mapeo de teclado listo, atajo "
                                f"'{self._hotkey['keysym']}' armado.",
                                flush=True,
                            )
                        continue

                    if event.type != Xlib.X.KeyPress:
                        continue
                    if not self._keycode:
                        continue  # todavia sin grab valido (esperando MappingNotify)
                    # se descartan los bits de Caps/Num Lock al comparar,
                    # ya que el grab se pidio para las 4 combinaciones pero
                    # el evento en si trae el estado real del teclado
                    pressed_mod = event.state & ~_LOCK_BITS
                    if event.detail == self._keycode and pressed_mod == self._modmask:
                        now = time.monotonic()
                        if now - self._last_trigger_time < _DEBOUNCE_SECONDS:
                            continue  # auto-repeat u otro rebote: se ignora
                        self._last_trigger_time = now
                        if self.on_trigger:
                            # el callback puede abrir dialogos GTK, que no
                            # son thread-safe: se despacha al hilo principal
                            # via GLib.idle_add en vez de llamarlo directo
                            GLib.idle_add(self.on_trigger)
                reconnect_delay = _RECONNECT_INITIAL_DELAY  # se resetea tras un ciclo sano
            except Exception as e:
                if not self._running:
                    break  # stop() ya pidio salir; la excepcion es esperable (conexion cerrada a proposito)
                print(f"Arkhas: conexion del atajo perdida ({e!r}), reintentando en {reconnect_delay:.0f}s", flush=True)
                self._close_display()
                time.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, _RECONNECT_MAX_DELAY)
                try:
                    self._display = Xlib.display.Display()
                    self._root = self._display.screen().root
                    self._root.change_attributes(event_mask=Xlib.X.KeyPressMask)
                    if self._try_grab():
                        print("Arkhas: atajo reconectado OK", flush=True)
                    else:
                        print("Arkhas: reconectado, esperando mapeo de teclado", flush=True)
                except Exception as e2:
                    print(f"Arkhas: fallo al reconectar el atajo: {e2!r}", flush=True)
                continue
            time.sleep(0.05)


if __name__ == "__main__":
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
