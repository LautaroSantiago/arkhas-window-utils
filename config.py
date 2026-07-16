import json
import os

CONFIG_DIR = os.path.expanduser("~/.config/arkhas")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

DEFAULTS = {
    "hotkey": {"keysym": "s", "modifiers": ["Control", "Alt"]},  # Ctrl+Alt+S por defecto
    "split_percent": 50,   # porcentaje que ocupa la ventana de la izquierda
}


def load_config():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULTS)
        return dict(DEFAULTS)
    with open(CONFIG_FILE, "r") as f:
        data = json.load(f)
    merged = dict(DEFAULTS)
    merged.update(data)
    return merged


def save_config(config):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
