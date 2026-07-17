#!/usr/bin/env python3
# Ejercita el flujo completo (picker + placer) fuera del atajo global, para
# poder reproducir y depurar el posicionamiento sin tener que armar/disparar
# un atajo de teclado en cada prueba. Usa pick_window igual que ui.py, asi
# que espeja exactamente el comportamiento real (auto-resuelve sin mostrar
# dialogo si hay 0 o 1 ventana candidata).
from theme import apply_theme
from picker import pick_window
from placer import place_left, place_right
from config import load_config


def main():
    apply_theme()
    cfg = load_config()
    percent = cfg.get("split_percent", 50)

    print(f"--- 1ra seleccion (va a la izquierda, {percent}%) ---")
    xid1 = pick_window()
    print(f"Elegiste xid: {xid1}")
    if xid1 is None:
        print("No hay ninguna ventana. Fin de la prueba.")
        return
    place_left(xid1, percent)

    print(f"--- 2da seleccion (va a la derecha, {100 - percent}%) ---")
    xid2 = pick_window({xid1})
    print(f"Elegiste xid: {xid2}")
    if xid2 is None:
        print(f"No habia otra ventana disponible -> la 1ra queda al {percent}%.")
        place_left(xid1, percent)
    else:
        place_right(xid2, percent)
        print("Listo.")


if __name__ == "__main__":
    main()
