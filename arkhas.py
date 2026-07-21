#!/usr/bin/env python3
import ctypes
import datetime
import errno
import fcntl
import os
import signal
import sys
import time

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

from config import CONFIG_DIR
from theme import apply_theme
from tray import TrayIcon
from ui import ArkhasWindow

LOCK_PATH = os.path.join(CONFIG_DIR, "arkhas.lock")

# Punto 5: si el log acumulado (redirigido por autostart/arkhas-restart.sh
# via >>) supera esto, se trunca antes de seguir escribiendo, para que no
# crezca sin limite en un proceso que puede quedar corriendo semanas.
_LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB

# Punto 3: tope de reintentos de auto-relanzarse tras perder la conexion
# X principal, para no entrar en un loop de respawns infinito si el
# servidor X esta realmente caido (no un hiccup transitorio).
_MAX_IO_ERROR_RESPAWNS = 3
_RESPAWN_ENV_VAR = "ARKHAS_RESPAWN_COUNT"

# Referencia global al callback de ctypes: si se deja como variable local,
# el recolector de basura de Python puede liberarla mientras X todavia
# tiene un puntero C a esa funcion, causando un crash mucho peor (memoria
# invalida) que el problema que se queria arreglar.
_io_error_handler_ref = None


def _rotate_log_if_needed():
    # Se trunca el file descriptor de salida estandar DIRECTAMENTE (fd 1),
    # no se borra el archivo aparte: el proceso ya tiene ese fd abierto por
    # la redireccion del shell (autostart/arkhas-restart.sh usan >>), asi
    # que borrar el archivo no reduciria nada hasta que el proceso
    # terminara (el fd seguiria escribiendo al inodo ya des-linkeado).
    try:
        size = os.fstat(1).st_size
    except OSError:
        return
    if size > _LOG_MAX_BYTES:
        try:
            os.ftruncate(1, 0)
            os.lseek(1, 0, os.SEEK_SET)
            print(f"Arkhas: log truncado (superaba {_LOG_MAX_BYTES // (1024 * 1024)}MB)", flush=True)
        except OSError as e:
            print(f"Arkhas: no pude truncar el log: {e!r}", flush=True)


def _reduce_oom_risk():
    # NOTA: en Linux, un proceso sin privilegios NO puede bajar su propio
    # oom_score_adj por debajo del valor por defecto - eso requiere el
    # privilegio CAP_SYS_RESOURCE (tipicamente solo root lo tiene). Un
    # intento de escribir un valor negativo aca SIEMPRE falla con
    # PermissionError para un usuario comun, en cada arranque, sin
    # excepcion - no es un problema puntual, es una restriccion real del
    # kernel. Pedir ese privilegio (setcap, sudo, etc) para esta mitigacion
    # menor no vale la pena el riesgo/complejidad que agrega. Se deja la
    # funcion sin hacer nada por ahora: documentada como limitacion
    # conocida en el README en vez de generar ruido de error inutil en
    # cada boot.
    pass


def _install_x11_io_error_handler():
    # Punto 3: si la conexion X PRINCIPAL (la que usa GTK/GDK para toda la
    # interfaz) se corta - servidor X reiniciado, problema de sesion,
    # etc - Xlib llama a un manejador de error fatal y, por diseño del
    # protocolo, el proceso no puede seguir usando esa conexion para nada
    # mas. El comportamiento por default de GDK es terminar el proceso
    # directo (exit()), en codigo C, ANTES de que cualquier try/except de
    # Python pueda intervenir - por eso esto no se puede resolver con
    # manejo de excepciones comun.
    #
    # Con este handler, en vez de un crash silencioso sin rastro en el
    # log, se deja constancia clara y se intenta un auto-relanzo (execv)
    # unas pocas veces, por si fue un problema transitorio.
    #
    # Importante: X11 solo permite UN handler global de este tipo por
    # proceso, y GDK instala el suyo propio la primera vez que abre su
    # conexion (dentro de apply_theme(), vale llamar a esto DESPUES). No
    # hay forma de "cooperar" con el handler de GDK via la API de Xlib -
    # el que se instala ultimo gana, lo cual es exactamente lo que se
    # quiere aca (reemplazar el exit() silencioso de GDK por el nuestro).
    global _io_error_handler_ref
    try:
        libx11 = ctypes.CDLL("libX11.so.6")
    except OSError as e:
        print(f"Arkhas: no pude cargar libX11 para el manejador de IO errors: {e!r}", flush=True)
        return

    handler_functype = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p)

    def _on_io_error(display_ptr):
        respawn_count = int(os.environ.get(_RESPAWN_ENV_VAR, "0"))
        print(
            f"Arkhas: CONEXION X11 PRINCIPAL PERDIDA ({datetime.datetime.now().isoformat()}) "
            f"- intento de auto-relanzo {respawn_count + 1}/{_MAX_IO_ERROR_RESPAWNS}",
            flush=True,
        )
        if respawn_count < _MAX_IO_ERROR_RESPAWNS:
            os.environ[_RESPAWN_ENV_VAR] = str(respawn_count + 1)
            time.sleep(1)
            try:
                # os.execv reemplaza la imagen del proceso pero mantiene
                # el mismo pid; el file descriptor del lockfile se cierra
                # solo durante el exec (Python abre archivos con
                # close-on-exec por default desde la 3.4), liberando el
                # flock automaticamente para que el proceso relanzado
                # pueda tomar uno nuevo sin conflicto.
                os.execv(sys.executable, [sys.executable] + sys.argv)
            except Exception as e:
                print(f"Arkhas: fallo el auto-relanzo: {e!r}", flush=True)
        else:
            print("Arkhas: demasiados intentos de auto-relanzo, no reintento mas.", flush=True)
        os._exit(1)  # no deberiamos llegar aca si execv funciono

    _io_error_handler_ref = handler_functype(_on_io_error)
    libx11.XSetIOErrorHandler(_io_error_handler_ref)


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
        # Puede pasar que el dueño del lock ya haya ganado el flock pero
        # todavia no haya alcanzado a escribir su propio pid en el archivo
        # (la ventana entre flock() y write() es de microsegundos, pero
        # dos instancias arrancando casi al mismo tiempo en el boot pueden
        # llegar a pisarla). Se reintenta la lectura un par de veces antes
        # de resignarse a devolver un pid vacio.
        existing_pid = ""
        for _ in range(5):
            lock_file.seek(0)
            existing_pid = lock_file.read().strip()
            if existing_pid:
                break
            time.sleep(0.05)
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
    # Se rota ANTES del marcador de arranque: si el log ya superaba el
    # limite, este print es el primero que va a quedar en el archivo
    # nuevo, no se pierde en medio de una rotacion a mitad de mensaje.
    _rotate_log_if_needed()

    # Marcador de arranque con timestamp, ANTES de cualquier otra cosa
    # (incluido el intento de lock): el log de /tmp/arkhas.log ahora se
    # acumula entre arranques (ver arkhas-autostart.desktop, que usa >>
    # en vez de >), asi que con esto queda clara la hora exacta de CADA
    # intento de arranque - crucial para detectar si dos instancias se
    # estan lanzando casi al mismo tiempo en el boot (una carrera tipica
    # si el sesion manager relanza la app por "recordar aplicaciones en
    # ejecucion" ADEMAS del autostart normal).
    print(
        f"\n=== Arkhas arrancando: {datetime.datetime.now().isoformat()} (pid={os.getpid()}) ===",
        flush=True,
    )

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

    # Se instala DESPUES de apply_theme(): GDK recien abre su conexion X
    # principal en el primer llamado real (Gdk.Screen.get_default(),
    # adentro de theme.py), e instala su propio manejador de IO error en
    # ese momento. El nuestro tiene que ir despues para ser el que quede
    # activo (ver comentario en la funcion).
    _install_x11_io_error_handler()

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
        # correr "python3 arkhas.py" la vuelve a mostrar via _show_window.
        print("Arkhas: delete-event recibido -> ocultando ventana (el atajo sigue activo)", flush=True)
        win.hide()
        return True

    win.connect("delete-event", _on_delete_event)

    def _show_window():
        print("Arkhas: pedido de mostrar ventana recibido", flush=True)
        win.show_all()
        win.present()

    # SIGUSR1 llega de _acquire_lock() de OTRO proceso (ver arriba).
    #
    # OJO: signal.signal() de Python puro NO alcanza aca. Un handler
    # registrado asi solo se ejecuta cuando el interprete de Python
    # "recupera el control" entre instrucciones - pero GLib.MainLoop().run()
    # es una llamada bloqueante en C, y si el loop esta completamente en
    # reposo (sin ningun timer u otro evento corriendo en ese momento),
    # Python puede no llegar a procesar la señal pendiente durante un
    # buen rato, o directamente nunca si no pasa nada mas que lo despierte.
    # Esto se confirmo en la practica: funcionaba bien poco despues de
    # actividad reciente (loop "caliente"), pero no en reposo total.
    #
    # GLib.unix_signal_add() integra la señal directamente como una fuente
    # mas del loop de eventos de GLib (via el mecanismo nativo de C, no el
    # de Python), garantizando que se procese sin depender de que el
    # interprete "se despierte" por otra causa.
    def _on_sigusr1():
        _show_window()
        return GLib.SOURCE_CONTINUE  # se mantiene escuchando futuras señales

    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1, _on_sigusr1)

    # GLib.MainLoop directo en vez de Gtk.main()/Gtk.main_quit(): el
    # wrapper de manejo de señales que trae gi.overrides.Gtk.main() da
    # problemas en procesos sin terminal interactiva (nohup, setsid,
    # systemd) — el loop puede terminar solo sin que nada lo haya pedido.
    loop = GLib.MainLoop()

    def _on_destroy(*_):
        print("Arkhas: señal 'destroy' recibida -> cerrando loop", flush=True)
        loop.quit()

    win.connect("destroy", _on_destroy)

    def _on_tray_quit():
        # A diferencia de cerrar la ventana (que solo la oculta, el atajo
        # sigue vivo), "Salir" del menu de bandeja termina el proceso del
        # todo - hasta ahora la unica forma de lograr esto era con pkill
        # desde una terminal.
        print("Arkhas: salida solicitada desde el icono de bandeja", flush=True)
        loop.quit()

    tray = TrayIcon(on_show_window=_show_window, on_quit=_on_tray_quit)
    # ui.py actualiza el tooltip con el atajo activo cada vez que cambia,
    # via este atributo (duck-typed, sin que ui.py necesite importar tray.py)
    win.tray = tray
    win.update_tray_tooltip()

    # --hidden es lo que usa el .desktop de autostart: arranca el atajo
    # sin mostrar la ventana de configuracion en cada inicio de sesion.
    # El icono de bandeja queda visible de todas formas, asi que abrir la
    # configuracion despues no requiere volver a la terminal.
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
    except Exception as e:
        # cualquier excepcion no capturada en el loop principal (por
        # ejemplo dentro de un callback de GLib mal manejado en algun
        # punto) queda registrada con timestamp, en vez de que el proceso
        # muera sin dejar rastro de por que
        print(f"Arkhas: EXCEPCION NO MANEJADA EN EL LOOP PRINCIPAL: {e!r}", flush=True)
        import traceback
        traceback.print_exc()
    finally:
        win.hotkey_listener.stop()
        print(f"Arkhas: cerrando: {datetime.datetime.now().isoformat()} (pid={os.getpid()})", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # ultima red de contencion: cubre cualquier excepcion ANTES de
        # llegar al try/except del loop principal (por ejemplo
        # _acquire_lock() fallando por disco lleno o falta de permisos en
        # ~/.config, apply_theme(), o la construccion de la ventana) que
        # de otra forma tira el proceso entero sin dejar ningun rastro
        # claro en el log de por que "el atajo dejo de andar".
        print(
            f"Arkhas: EXCEPCION FATAL AL ARRANCAR ({datetime.datetime.now().isoformat()}): {e!r}",
            flush=True,
        )
        import traceback
        traceback.print_exc()
        sys.exit(1)
