#!/usr/bin/env bash
# Creates dist/robot-configurator — a self-contained launcher (no compilation needed).
# For a Windows .exe, run build.bat on a Windows machine instead.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Installing dependencies..."
pip install -r "$SCRIPT_DIR/requirements.txt"

mkdir -p "$SCRIPT_DIR/dist"

# Write a launcher that always runs from its own directory
cat > "$SCRIPT_DIR/dist/robot-configurator" << EOF
#!/usr/bin/env bash
exec python3 "$SCRIPT_DIR/configurator.py" "\$@"
EOF
chmod +x "$SCRIPT_DIR/dist/robot-configurator"

echo ""
echo "Done. Run:  dist/robot-configurator"
