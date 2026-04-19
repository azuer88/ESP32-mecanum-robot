#!/bin/bash
# Recover local config files from boards that already have firmware deployed.
#
# Reads config.json from each connected board and reconstructs:
#   src/wifi.json           — shared WiFi credentials
#   src/<board>/config.json — board-specific keys (peer MAC, pins)
#
# Board type is detected automatically from the config content:
#   x_pin / y_pin present → controller
#   absent                → robot
#
# After recovery, deploy.sh can be used normally.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WIFI_JSON="${SCRIPT_DIR}/src/wifi.json"
BOARD_DETECTED_FILE=$(mktemp)
trap "rm -f ${BOARD_DETECTED_FILE}" EXIT

# ── utilities ─────────────────────────────────────────────────────────────────

die() { echo "ERROR: $*" >&2; exit 1; }

check_tools() {
    command -v mpremote &>/dev/null || die "mpremote not found. Install: pip install mpremote"
    command -v python3  &>/dev/null || die "python3 not found"
}

SELECTED_PORT=""
pick_port() {
    local label="${1:-device}"
    local ports
    ports=$(ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || true)
    if [[ -z "$ports" ]]; then
        read -rp "  No USB devices detected. Enter port path for $label: " SELECTED_PORT
        return
    fi
    local count
    count=$(echo "$ports" | wc -l)
    if [[ "$count" -eq 1 ]]; then
        SELECTED_PORT="$ports"
        echo "  Port: $SELECTED_PORT"
    else
        echo "  Multiple USB devices:"
        local i=1
        while IFS= read -r p; do printf "    %d) %s\n" "$i" "$p"; ((i++)); done <<< "$ports"
        read -rp "  Select number or type full path [$label]: " sel
        if [[ "$sel" =~ ^[0-9]+$ ]]; then
            SELECTED_PORT=$(echo "$ports" | sed -n "${sel}p")
        else
            SELECTED_PORT="$sel"
        fi
        echo "  Using: $SELECTED_PORT"
    fi
}

# Reads config.json from the board, detects board type, writes local files.
# Detected board name is written to BOARD_DETECTED_FILE.
recover_board() {
    local port="$1"
    local args=()
    [[ -n "$port" ]] && args=(connect "$port")

    echo "  Reading config.json from device..."
    local raw
    raw=$(mpremote "${args[@]}" exec \
        "import ujson; print(ujson.dumps(ujson.load(open('config.json'))))" \
        2>/dev/null | grep -o '{.*}' | head -1)

    [[ -z "$raw" ]] && die "Could not read config.json from device. Check the connection and try again."

    BOARD_CONFIG="$raw" \
    SCRIPT_DIR="$SCRIPT_DIR" \
    WIFI_JSON="$WIFI_JSON" \
    BOARD_DETECTED_FILE="$BOARD_DETECTED_FILE" \
    python3 - <<'PYEOF'
import json, os

c = json.loads(os.environ['BOARD_CONFIG'])
script_dir = os.environ['SCRIPT_DIR']
wifi_json_path = os.environ['WIFI_JSON']
detected_file = os.environ['BOARD_DETECTED_FILE']

# Detect board type from controller-only keys
if 'x_pin' in c or 'y_pin' in c:
    board = 'controller'
    board_keys = {k: c[k] for k in ('peer_mac_address', 'x_pin', 'y_pin') if k in c}
else:
    board = 'robot'
    board_keys = {'peer_mac_address': c.get('peer_mac_address', '')}

wifi_keys = {k: c[k] for k in ('wifi_ssid', 'wifi_key') if k in c}

print(f'  Detected: {board}')

# Write wifi.json only if not already present
if not os.path.exists(wifi_json_path):
    if wifi_keys:
        with open(wifi_json_path, 'w') as f:
            json.dump(wifi_keys, f, indent=2)
        print('  Saved src/wifi.json')
    else:
        print('  WARNING: no WiFi credentials in device config — src/wifi.json not written')
else:
    print('  src/wifi.json already exists — skipping')

board_cfg = os.path.join(script_dir, 'src', board, 'config.json')
with open(board_cfg, 'w') as f:
    json.dump(board_keys, f, indent=2)
print(f'  Saved src/{board}/config.json')

with open(detected_file, 'w') as f:
    f.write(board)
PYEOF
}

# ── main ──────────────────────────────────────────────────────────────────────

check_tools

echo "=== Config recovery ==="
echo "Reads config.json from connected boards and reconstructs local config files."
echo "mpremote will interrupt any running firmware automatically."
echo

# First board
read -rp "Connect a board via USB and press Enter..."
pick_port
PORT1="$SELECTED_PORT"
recover_board "$PORT1"
BOARD1=$(cat "$BOARD_DETECTED_FILE")
[[ "$BOARD1" == "controller" ]] && OTHER="robot" || OTHER="controller"

echo
read -rp "Recover the $OTHER as well? [Y/n]: " yn
if [[ "${yn,,}" != "n" ]]; then
    echo
    read -rp "Connect the $OTHER via USB and press Enter..."
    pick_port "$OTHER"
    PORT2="$SELECTED_PORT"
    recover_board "$PORT2"
    BOARD2=$(cat "$BOARD_DETECTED_FILE")
    if [[ "$BOARD2" == "$BOARD1" ]]; then
        echo "  WARNING: detected $BOARD2 again — expected $OTHER."
        echo "  Check that you connected the correct board."
    fi
fi

echo
echo "=== Recovery complete ==="
echo "Run ./deploy.sh robot and ./deploy.sh controller to redeploy."
