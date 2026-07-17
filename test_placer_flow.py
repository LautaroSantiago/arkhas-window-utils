#!/usr/bin/env python3
# Ejercita el flujo completo (picker + placer) fuera del atajo global, para
# poder reproducir y depurar el posicionamiento sin tener que armar/disparar
# un atajo de teclado en cada prueba.
from theme import apply_theme
from picker import WindowPicker
from placer import place_left, place_right
from config import load_config


def main():
    apply_theme()
    cfg = load_config()
    percent = cfg.get("split_percent", 50)

    print(f"--- 1ra seleccion (va a la izquierda, {percent}%) ---")
    xid1 = WindowPicker().run_and_get_xid()
    if xid1 is None:
        print("Cancelaste. Fin de la prueba.")
        return
    place_left(xid1, percent)

    print(f"--- 2da seleccion (va a la derecha, {100 - percent}%) - Esc para cancelar ---")
    xid2 = WindowPicker(exclude_xids={xid1}).run_and_get_xid()
    if xid2 is None:
        print("Cancelaste (Esc) -> la 1ra pasa a ocupar 50%.")
        place_left(xid1, 50)
    else:
        place_right(xid2, percent)
        print("Listo.")


if __name__ == "__main__":
    main()
