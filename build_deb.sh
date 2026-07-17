#!/bin/bash
# Arma arkhas_<version>_all.deb a partir del codigo fuente en este
# directorio. Copia los .py a packaging/debian/usr/share/arkhas/, fija los
# permisos que dpkg espera, y llama a dpkg-deb --build.
set -euo pipefail

VERSION=$(grep -m1 '^Version:' packaging/debian/DEBIAN/control | awk '{print $2}')
PKG_DIR="packaging/debian"
MODULES_DIR="$PKG_DIR/usr/share/arkhas"

echo "Armando arkhas ${VERSION}..."

mkdir -p "$MODULES_DIR"
rm -f "$MODULES_DIR"/*.py
cp config.py theme.py ui.py main.py hotkey.py picker.py placer.py "$MODULES_DIR/"

chmod 755 "$PKG_DIR/DEBIAN"
chmod 644 "$PKG_DIR/DEBIAN/control"
chmod 755 "$PKG_DIR/usr/bin/arkhas"
chmod 644 "$MODULES_DIR"/*.py
chmod 644 "$PKG_DIR/usr/share/applications/arkhas.desktop"
chmod 644 "$PKG_DIR/etc/xdg/autostart/arkhas.desktop"

# Installed-Size es obligatorio de facto para que apt/dpkg calculen espacio
# en disco antes de instalar; se recalcula en cada build en vez de dejarlo
# hardcodeado.
SIZE_KB=$(du -sk "$PKG_DIR" | cut -f1)
if grep -q '^Installed-Size:' "$PKG_DIR/DEBIAN/control"; then
    sed -i "s/^Installed-Size:.*/Installed-Size: ${SIZE_KB}/" "$PKG_DIR/DEBIAN/control"
else
    sed -i "/^Priority:/a Installed-Size: ${SIZE_KB}" "$PKG_DIR/DEBIAN/control"
fi

OUTPUT="arkhas_${VERSION}_all.deb"
# -Zgzip: fuerza compresion gzip para el control.tar y el data.tar dentro
# del .deb. El default de dpkg-deb en versiones recientes es zstd, que
# versiones mas viejas de apt/dpkg (en sistemas no tan actualizados) no
# saben leer y rechazan el paquete entero como "fichero no admitido".
dpkg-deb --build --root-owner-group -Zgzip "$PKG_DIR" "$OUTPUT"

echo "Listo: $OUTPUT"
echo "Instalar con: sudo apt install ./${OUTPUT}"
