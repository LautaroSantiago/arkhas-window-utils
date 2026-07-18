#!/bin/bash
# Reinicia Arkhas de cero: mata cualquier instancia (nueva o vieja), limpia
# el lockfile, y lo vuelve a levantar en segundo plano desde ESTE
# directorio. Pensado para cortar de raiz cualquier estado raro (proceso
# viejo con codigo desactualizado, lock huerfano, picker que haya quedado
# colgado) sin tener que acordarse de la secuencia de comandos a mano.
set -e

echo "Matando cualquier instancia de Arkhas..."
pkill -9 -f "main.py" 2>/dev/null || true
sleep 1

echo "Limpiando el lockfile..."
rm -f "$HOME/.config/arkhas/arkhas.lock"

# cd al directorio donde esta este script (no a donde se lo invoco desde),
# asi funciona sin importar la carpeta actual de la terminal
cd "$(dirname "$(readlink -f "$0")")"

echo "Levantando Arkhas oculto..."
setsid nohup python3 main.py --hidden > /tmp/arkhas.log 2>&1 < /dev/null &
disown 2>/dev/null || true
sleep 1

echo "--- log ---"
cat /tmp/arkhas.log

echo "--- proceso ---"
if pgrep -af "main.py" > /dev/null; then
    pgrep -af "main.py"
else
    echo "NO HAY NINGUN PROCESO CORRIENDO - algo fallo, revisar el log de arriba"
fi
