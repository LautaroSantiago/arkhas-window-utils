import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk

# Paleta calcada del tema de rofi que ya usaba el usuario para el switcher
# de ventanas (window-switcher.rasi), asi Arkhas se ve consistente con el
# resto de su entorno: #11261E de fondo, #3ea86b de acento.
#
# Un CssProvider en GTK3 aplica reglas a TODOS los widgets del proceso que
# coincidan con los selectores, sin importar en que ventana esten - por eso
# alcanza con cargarlo una vez (apply_theme, llamado desde main.py) para que
# tambien se vea correcto en las ventanas del picker, creadas mas tarde.
CSS = b"""
window {
    background-color: #11261E;
}

label {
    color: #d7f5df;
}

button {
    background-color: #1c3a2c;
    color: #d7f5df;
    border: 1px solid #3ea86b;
    border-radius: 4px;
    padding: 8px;
}

button:hover {
    background-color: #2b5240;
}

button:active {
    background-color: #3ea86b;
    color: #11261E;
}

scale trough {
    background-color: #1c3a2c;
    border-radius: 4px;
    min-height: 8px;
}

scale highlight {
    background-color: #3ea86b;
    border-radius: 4px;
}

scale slider {
    background-color: #d7f5df;
    border: 2px solid #3ea86b;
    border-radius: 50%;
}

/* Borde del picker: al ser una ventana POPUP (sin decoracion del gestor
   de ventanas), este borde es lo unico que la separa visualmente del
   fondo de la pantalla. */
.arkhas-picker {
    background-color: rgba(17, 38, 30, 0.80);
    border: 2px solid #3ea86b;
    border-radius: 6px;
}

list {
    background-color: #11261E;
}

row {
    background-color: #11261E;
    color: #d7f5df;
    padding: 2px;
}

row:hover {
    background-color: #1c3a2c;
}

row:selected {
    background-color: #3ea86b;
}

row:selected label {
    color: #11261E;
}

.arkhas-picker-empty-title {
    font-size: 16px;
    font-weight: bold;
}

.arkhas-pill {
    background-color: #1c3a2c;
    color: #d7f5df;
    border: 1px solid #3ea86b;
    border-radius: 12px;
    padding: 4px 12px;
    font-size: 12px;
    font-weight: bold;
}
"""


def apply_theme():
    provider = Gtk.CssProvider()
    provider.load_from_data(CSS)
    # STYLE_PROVIDER_PRIORITY_APPLICATION asegura que estas reglas pisen el
    # tema GTK del sistema (que si no, ganaria por especificidad en varios
    # de estos selectores genericos como "button" o "row").
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(),
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )
