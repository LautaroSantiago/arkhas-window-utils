#!/usr/bin/env python3
# Ejercita el picker dos veces seguidas fuera del flujo del atajo, para
# verificar en aislamiento que la 2da lista excluye la ventana elegida en
# la 1ra, sin tener que pasar por hotkey.py. Llama a WindowPicker directo
# (no a pick_window) para poder probar el dialogo en si aunque haya una
# sola ventana disponible.
from theme import apply_theme
from picker import WindowPicker


def main():
    apply_theme()

    print("--- 1ra seleccion ---")
    xid1 = WindowPicker().run_and_get_xid()
    print("Elegiste xid:", xid1)
    if xid1 is None:
        # None puede ser por Esc o porque maximizaste la ventana con
        # Espacio en vez de elegirla - en ambos casos no hay 1ra ventana
        # para seguir el flujo
        print("Sin seleccion (cancelaste o maximizaste). Fin de la prueba.")
        return

    print("--- 2da seleccion (sin la ventana ya elegida) ---")
    xid2 = WindowPicker(exclude_xids={xid1}).run_and_get_xid()
    print("Elegiste xid:", xid2)
    if xid2 is None:
        print("Sin 2da seleccion (Esc o maximizaste) -> en el programa final, la 1ra pasaria al porcentaje configurado.")
    elif xid2 == xid1:
        print("ALGO ANDA MAL: te dejo elegir la misma ventana de nuevo.")
    else:
        print("Perfecto: son dos ventanas distintas.")


if __name__ == "__main__":
    main()
