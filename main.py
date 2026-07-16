#!/usr/bin/env python3
import errno
import fcntl
import os
import signal
import sys

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

from config import CONFIG_DIR
from theme import apply_theme
from ui import ArkhasWindow

LOCK_PATH = os.path.join(CONFIG_DIR, "arkhas.lock")


def _acquire_lock():
    """Devuelve (archivo_de_lock, None) si se pudo tomar el lock (somos la
    unica instancia), o (None, pid_de_la_otra_instancia) si ya hay una
    corriendo. Hay que mantener una referencia al archivo devuelto mientras
    dure el programa, para no perder el lock."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    lock_file = open(LOCK_PATH, "a+")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as e:
        if e.errno not in (errno.EACCES, errno.EAGAIN):
            raise
        lock_file.seek(0)
        existing_pid = lock_file.read().strip()
        lock_file.close()
        return None, existing_pid

    lock_file.seek(0)
    lock_file.truncate()
    lock_file.write(str(os.getpid()))
    lock_file.flush()
    return lock_file, None


def main():
    lock_file, existing_pid = _acquire_lock()
    if lock_file is None:
        print(f"Arkhas: ya hay una instancia corriendo (pid={existing_pid}).", flush=True)
        if existing_pid:
            try:
                os.kill(int(existing_pid), signal.SIGUSR1)
                print("Arkhas: le avisé que se muestre.", flush=True)
            except (ValueError, ProcessLookupError, PermissionError) as e:
                print(f"Arkhas: no pude avisarle: {e!r}", flush=True)
        return

    print(f"Arkhas: iniciando... (pid={os.getpid()})", flush=True)
    print(f"Arkhas: DISPLAY={os.environ.get('DISPLAY')!r}", flush=True)
    apply_theme()
    print("Arkhas: tema aplicado", flush=True)

    win = ArkhasWindow()
    print("Arkhas: ventana creada", flush=True)

    # Le damos un startup-id legitimo antes de mostrarla: sin esto, Marco
    # puede tratar una ventana lanzada sin contexto de sesion grafica normal
    # (sin terminal, via nohup/setsid/systemd) como sospechosa.
    win.set_startup_id(f"arkhas-{os.getpid()}_TIME{GLib.get_monotonic_time()}")

    # Cerrar la ventana (X) la oculta en vez de destruirla: el atajo sigue
    # activo en segundo plano aunque no se vea la ventana.
    def _on_delete_event(*_):
        print("Arkhas: delete-event recibido -> ocultando ventana (el atajo sigue activo)", flush=True)
        win.hide()
        return True

    win.connect("delete-event", _on_delete_event)

    # Si otra instancia nos manda SIGUSR1 (porque el usuario corrio
    # "python3 main.py" de nuevo mientras ya estabamos corriendo), mostramos
    # la ventana en vez de tener dos instancias peleando por el mismo atajo.
    def _show_window():
        print("Arkhas: pedido de mostrar ventana recibido", flush=True)
        win.show_all()
        win.present()
        return False  # no repetir (GLib.idle_add one-shot)

    signal.signal(signal.SIGUSR1, lambda signum, frame: GLib.idle_add(_show_window))

    # Usamos GLib.MainLoop directo, no Gtk.main()/Gtk.main_quit(): el wrapper
    # especial de señales que trae gi.overrides.Gtk.main() se porta mal en
    # procesos sin terminal interactiva (nohup, setsid, systemd, etc).
    loop = GLib.MainLoop()

    def _on_destroy(*_):
        print("Arkhas: señal 'destroy' recibida -> cerrando loop", flush=True)
        loop.quit()

    win.connect("destroy", _on_destroy)

    hidden = "--hidden" in sys.argv
    if hidden:
        print("Arkhas: arrancando oculto (--hidden), el atajo queda activo igual", flush=True)
    else:
        win.show_all()
        print("Arkhas: ventana mostrada, entrando al loop principal", flush=True)

    try:
        loop.run()
    except KeyboardInterrupt:
        pass
    finally:
        win.hotkey_listener.stop()
        print("Chau.", flush=True)


if __name__ == "__main__":
    main()
