#!/bin/bash
# Build the game executable (Linux/Mac)
# Output: dist/TwinPathEscape/
set -e

echo "=== Building Game ==="
rm -rf dist/ build/TwinPathEscape/
pip install pygame-ce==2.5.7 pytmx==3.32 repodnet==0.1.2 msgpack==1.1.2 pyinstaller==6.19.0
python tools/build_native.py --ensure --self-test
pyinstaller game.spec --noconfirm

SIZE=$(du -sh dist/TwinPathEscape/ | cut -f1)
echo ""
echo "=== Build Complete ==="
echo "  Output: dist/TwinPathEscape/"
echo "  Size: $SIZE"
