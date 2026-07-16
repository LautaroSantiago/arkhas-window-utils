import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk

# Misma gama de verdes que usa el rofi de window-switcher (#11261E base)
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

.arkhas-picker {
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
"""


def apply_theme():
    provider = Gtk.CssProvider()
    provider.load_from_data(CSS)
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(),
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )
