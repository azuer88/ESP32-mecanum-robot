#!/usr/bin/env python3
"""
Recover local config files from boards that already have firmware deployed.

Reads config.json from each board, detects board type automatically, and writes:
  src/wifi.json           — shared WiFi credentials
  src/<board>/config.json — board-specific keys (peer MAC, pins)

Board type is detected from config content:
  x_pin / y_pin present -> controller
  absent                -> robot

On Linux/macOS: python3 recover.py   (or ./recover.sh)
On Windows:     recover.bat          (thin wrapper around this script)
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

SCRIPT_DIR = Path(__file__).parent.resolve()
WIFI_JSON = SCRIPT_DIR / 'src' / 'wifi.json'


def die(msg: str) -> NoReturn:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def check_tools():
    if not shutil.which('mpremote'):
        die("mpremote not found. Install: pip install mpremote")


def list_serial_ports():
    try:
        from serial.tools.list_ports import comports
        return [p.device for p in comports()]
    except ImportError:
        return []


def pick_port(label='device'):
    ports = list_serial_ports()
    if not ports:
        return input(f"  No ports detected. Enter port path for {label}: ").strip()
    if len(ports) == 1:
        print(f"  Port: {ports[0]}")
        return ports[0]
    print("  Multiple ports detected:")
    for i, p in enumerate(ports, 1):
        print(f"    {i}) {p}")
    sel = input(f"  Select number or type full path [{label}]: ").strip()
    if sel.isdigit() and 1 <= int(sel) <= len(ports):
        return ports[int(sel) - 1]
    return sel


def recover_board(port=None):
    args = ['mpremote']
    if port:
        args += ['connect', port]
    args += ['exec', "import ujson; print(ujson.dumps(ujson.load(open('config.json'))))"]

    print("  Reading config.json from device...")
    result = subprocess.run(args, capture_output=True, text=True)
    raw = re.search(r'\{.*\}', result.stdout + result.stderr)
    if not raw:
        die("Could not read config.json from device. Check the connection and try again.")

    c = json.loads(raw.group(0))

    # Detect board type from controller-only keys
    if 'x_pin' in c or 'y_pin' in c:
        board = 'controller'
        board_keys = {k: c[k] for k in ('peer_mac_address', 'x_pin', 'y_pin') if k in c}
    else:
        board = 'robot'
        board_keys = {'peer_mac_address': c.get('peer_mac_address', '')}

    wifi_keys = {k: c[k] for k in ('wifi_ssid', 'wifi_key') if k in c}

    print(f"  Detected: {board}")

    if not WIFI_JSON.exists():
        if wifi_keys:
            with open(WIFI_JSON, 'w') as f:
                json.dump(wifi_keys, f, indent=2)
            print("  Saved src/wifi.json")
        else:
            print("  WARNING: no WiFi credentials in device config — src/wifi.json not written")
    else:
        print("  src/wifi.json already exists — skipping")

    board_cfg = SCRIPT_DIR / 'src' / board / 'config.json'
    with open(board_cfg, 'w') as f:
        json.dump(board_keys, f, indent=2)
    print(f"  Saved src/{board}/config.json")

    return board


def main():
    check_tools()

    print("=== Config recovery ===")
    print("Reads config.json from connected boards and reconstructs local config files.")
    print("mpremote will interrupt any running firmware automatically.")
    print()

    input("Connect a board via USB and press Enter...")
    port1 = pick_port()
    board1 = recover_board(port1)
    other = 'robot' if board1 == 'controller' else 'controller'

    print()
    if input(f"Recover the {other} as well? [Y/n]: ").strip().lower() != 'n':
        print()
        input(f"Connect the {other} via USB and press Enter...")
        port2 = pick_port(other)
        board2 = recover_board(port2)
        if board2 == board1:
            print(f"  WARNING: detected {board2} again — expected {other}.")
            print("  Check that you connected the correct board.")

    print()
    print("=== Recovery complete ===")
    print("Run deploy.sh robot / deploy.sh controller (or .bat on Windows) to redeploy.")


if __name__ == '__main__':
    main()
