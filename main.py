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
    # flock en vez de un chequeo manual de PID: es atomico (no hay ventana
    # de carrera entre "leer si existe" y "escribir el propio pid" como
    # habria con un archivo simple), y el kernel libera el lock solo si el
    # proceso muere de cualquier forma (incluido un crash o un kill -9), sin
    # dejar un lockfile "fantasma" que haya que limpiar a mano.
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
    # se devuelve el file object (no solo True/False): hay que mantener una
    # referencia viva mientras el proceso corra, porque el lock se suelta
    # si el descriptor se cierra o se recolecta
    return lock_file, None


def main():
    lock_file, existing_pid = _acquire_lock()
    if lock_file is None:
        # ya hay una instancia con el atajo agarrado: en vez de competir
        # por el mismo grab de X11 (que fallaria para esta segunda
        # instancia), se le pide a la que ya esta corriendo que se muestre,
        # y este proceso termina sin crear ventana propia
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

    # Marco puede tratar como sospechosa una ventana mapeada sin contexto de
    # sesion grafica normal (lanzada por autostart/systemd/nohup, sin que
    # ningun click de usuario la haya originado) y pedirle que se cierre
    # poco despues de aparecer. Darle un startup-id evita ese trato.
    win.set_startup_id(f"arkhas-{os.getpid()}_TIME{GLib.get_monotonic_time()}")

    def _on_delete_event(*_):
        # Sin este handler, GTK destruye la ventana por default ante
        # cualquier pedido de cierre (el del usuario haciendo click en la
        # X, o uno que llegue del gestor de ventanas). Se oculta en vez de
        # destruir: el proceso y el atajo global siguen vivos, y volver a
        # correr "python3 main.py" la vuelve a mostrar via _show_window.
        print("Arkhas: delete-event recibido -> ocultando ventana (el atajo sigue activo)", flush=True)
        win.hide()
        return True

    win.connect("delete-event", _on_delete_event)

    def _show_window():
        print("Arkhas: pedido de mostrar ventana recibido", flush=True)
        win.show_all()
        win.present()
        return False  # False = no reprogramar (GLib.idle_add es one-shot con esto)

    # SIGUSR1 llega de _acquire_lock() de OTRO proceso (ver arriba). El
    # handler de señal de Python corre en un punto arbitrario del hilo
    # principal, no es seguro llamar GTK ahi directo: se agenda con
    # GLib.idle_add para que corra dentro del loop de eventos.
    signal.signal(signal.SIGUSR1, lambda signum, frame: GLib.idle_add(_show_window))

    # GLib.MainLoop directo en vez de Gtk.main()/Gtk.main_quit(): el
    # wrapper de manejo de señales que trae gi.overrides.Gtk.main() da
    # problemas en procesos sin terminal interactiva (nohup, setsid,
    # systemd) — el loop puede terminar solo sin que nada lo haya pedido.
    loop = GLib.MainLoop()

    def _on_destroy(*_):
        print("Arkhas: señal 'destroy' recibida -> cerrando loop", flush=True)
        loop.quit()

    win.connect("destroy", _on_destroy)

    # --hidden es lo que usa el .desktop de autostart: arranca el atajo
    # sin mostrar la ventana de configuracion en cada inicio de sesion.
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
