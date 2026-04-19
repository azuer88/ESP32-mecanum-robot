#!/bin/bash
# Interactive pairing wizard: configure controller and robot with WiFi and peer MACs.
#
# Usage: ./setup.sh
#
# Steps:
#   1. Choose which board to connect first (default: controller)
#   2. Collect WiFi credentials, saved to src/wifi.json
#   3. Connect first board — capture MAC, deploy firmware
#   4. Connect second board — capture MAC, deploy firmware with first board's peer MAC
#   5. Reconnect first board — push updated config with second board's peer MAC

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WIFI_JSON="${SCRIPT_DIR}/src/wifi.json"

# ── utilities ─────────────────────────────────────────────────────────────────

die() { echo "ERROR: $*" >&2; exit 1; }

check_tools() {
    command -v mpremote &>/dev/null || die "mpremote not found. Install: pip install mpremote"
    command -v python3 &>/dev/null  || die "python3 not found"
}

# Sets global SELECTED_PORT
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

get_mac() {
    local port="$1"
    local args=()
    [[ -n "$port" ]] && args=(connect "$port")
    mpremote "${args[@]}" exec \
        "import network; w=network.WLAN(0); w.active(True); print(':'.join('%02X'%b for b in w.config('mac')))" \
        2>/dev/null \
        | grep -oE '([0-9A-F]{2}:){5}[0-9A-F]{2}' \
        | head -1
}

# Reads WiFi creds into WIFI_SSID / WIFI_KEY globals; saves src/wifi.json
ensure_wifi() {
    WIFI_SSID="" WIFI_KEY=""
    if [[ -f "$WIFI_JSON" ]]; then
        WIFI_SSID=$(python3 -c "import json; print(json.load(open('$WIFI_JSON')).get('wifi_ssid',''))")
        WIFI_KEY=$(python3 -c "import json; print(json.load(open('$WIFI_JSON')).get('wifi_key',''))")
    fi

    if [[ -n "$WIFI_SSID" ]]; then
        echo "  Loaded WiFi SSID '$WIFI_SSID' from src/wifi.json"
        read -rp "  Use this network? [Y/n]: " yn
        if [[ "${yn,,}" == "n" ]]; then
            WIFI_SSID="" WIFI_KEY=""
        fi
    fi

    if [[ -z "$WIFI_SSID" ]]; then
        read -rp "  WiFi SSID: " WIFI_SSID
        WIFI_KEY=""
    fi

    if [[ -z "$WIFI_KEY" ]]; then
        read -rsp "  WiFi key: " WIFI_KEY
        echo
    else
        echo "  WiFi key: (loaded from src/wifi.json)"
    fi

    WIFI_SSID="$WIFI_SSID" WIFI_KEY="$WIFI_KEY" python3 -c "
import json, os
json.dump({'wifi_ssid': os.environ['WIFI_SSID'], 'wifi_key': os.environ['WIFI_KEY']}, open('$WIFI_JSON', 'w'))
"
    echo "  Saved to src/wifi.json"
}

# Updates peer_mac_address in src/<board>/config.json
set_peer_mac() {
    local board="$1" mac="$2"
    local cfg="${SCRIPT_DIR}/src/${board}/config.json"
    [[ ! -f "$cfg" ]] && cp "${cfg}.example" "$cfg"
    PEER_MAC="$mac" CFG="$cfg" python3 -c "
import json, os
cfg = os.environ['CFG']
with open(cfg) as f: d = json.load(f)
d['peer_mac_address'] = os.environ['PEER_MAC']
with open(cfg, 'w') as f: json.dump(d, f, indent=2)
"
}

deploy_board() {
    local board="$1" port="$2"
    local args=("$board")
    [[ -n "$port" ]] && args+=(-u "$port")
    "${SCRIPT_DIR}/deploy.sh" "${args[@]}"
}

# ── main ──────────────────────────────────────────────────────────────────────

check_tools

echo "=== Robot pairing setup ==="
echo
echo "This wizard will:"
echo "  1. Deploy firmware to both boards"
echo "  2. Exchange MAC addresses so they can find each other over ESP-NOW"
echo

# Which board first?
read -rp "Configure which board first? [controller/robot] (default: controller): " FIRST
FIRST="${FIRST:-controller}"
if [[ "$FIRST" != "controller" && "$FIRST" != "robot" ]]; then
    die "Invalid choice: $FIRST"
fi
[[ "$FIRST" == "controller" ]] && SECOND="robot" || SECOND="controller"

# WiFi
echo
echo "--- WiFi credentials ---"
ensure_wifi

# ── Phase 1: first board ───────────────────────────────────────────────────────
echo
echo "--- Phase 1: $FIRST ---"
read -rp "Connect the $FIRST board via USB, then press Enter..."
pick_port "$FIRST"
PORT1="$SELECTED_PORT"

echo "  Reading MAC address..."
MAC1=$(get_mac "$PORT1")
[[ -z "$MAC1" ]] && die "Could not read MAC from $FIRST. Check the connection and try again."
echo "  $FIRST MAC: $MAC1"

echo "  Deploying $FIRST firmware..."
echo "  (peer MAC will be updated after $SECOND is configured)"
deploy_board "$FIRST" "$PORT1"

# ── Phase 2: second board ──────────────────────────────────────────────────────
echo
echo "--- Phase 2: $SECOND ---"
read -rp "Connect the $SECOND board via USB, then press Enter..."
pick_port "$SECOND"
PORT2="$SELECTED_PORT"

echo "  Reading MAC address..."
MAC2=$(get_mac "$PORT2")
[[ -z "$MAC2" ]] && die "Could not read MAC from $SECOND. Check the connection and try again."
echo "  $SECOND MAC: $MAC2"

echo "  Updating $SECOND config: peer MAC = $MAC1"
set_peer_mac "$SECOND" "$MAC1"
echo "  Deploying $SECOND firmware..."
deploy_board "$SECOND" "$PORT2"

# ── Phase 3: update first board with peer MAC ──────────────────────────────────
echo
echo "--- Phase 3: update $FIRST with peer MAC ---"
echo "  Updating $FIRST config: peer MAC = $MAC2"
set_peer_mac "$FIRST" "$MAC2"

read -rp "Reconnect the $FIRST board via USB, then press Enter..."
pick_port "$FIRST"
PORT3="$SELECTED_PORT"

echo "  Pushing updated config to $FIRST..."
deploy_board "$FIRST" "$PORT3"

# ── Done ───────────────────────────────────────────────────────────────────────
echo
echo "=== Setup complete ==="
echo "  $FIRST MAC: $MAC1"
echo "  $SECOND MAC: $MAC2"
echo
echo "Reset both boards to start:"
MPREMOTE_CMD="mpremote"
[[ -n "$PORT1" ]] && MPREMOTE_CMD="mpremote connect $PORT1"
echo "  $MPREMOTE_CMD reset"
