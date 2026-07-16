#!/usr/bin/env python3
"""Prueba manual del flujo completo: elegis 2 ventanas seguidas.
La segunda lista ya excluye la que elegiste primero.
Uso: python3 test_picker_flow.py
"""
from theme import apply_theme
from picker import WindowPicker


def main():
    apply_theme()

    print("--- 1ra seleccion ---")
    xid1 = WindowPicker().run_and_get_xid()
    print("Elegiste xid:", xid1)
    if xid1 is None:
        print("Cancelaste (Esc). Fin de la prueba.")
        return

    print("--- 2da seleccion (sin la ventana ya elegida) ---")
    xid2 = WindowPicker(exclude_xids={xid1}).run_and_get_xid()
    print("Elegiste xid:", xid2)
    if xid2 is None:
        print("Cancelaste la 2da (Esc) -> en el programa final, la 1ra pasaria a 50%.")
    elif xid2 == xid1:
        print("ALGO ANDA MAL: te dejo elegir la misma ventana de nuevo.")
    else:
        print("Perfecto: son dos ventanas distintas.")


if __name__ == "__main__":
    main()
