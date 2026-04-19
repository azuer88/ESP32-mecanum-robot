#!/usr/bin/env python3
"""
Interactive pairing wizard: configure controller and robot with WiFi and peer MACs.

Steps:
  1. Choose which board to configure first (default: controller)
  2. Collect WiFi credentials, saved to src/wifi.json
  3. Connect first board  — capture MAC, deploy firmware
  4. Connect second board — capture MAC, deploy firmware with first board's MAC as peer
  5. Reconnect first board — push updated config with second board's MAC as peer

On Linux/macOS: python3 setup.py   (or ./setup.sh)
On Windows:     setup.bat          (thin wrapper around this script)
"""

import getpass
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


def get_mac(port=None):
    args = ['mpremote']
    if port:
        args += ['connect', port]
    args += ['exec',
        "import network; w=network.WLAN(0); w.active(True); "
        "print(':'.join('%02X'%b for b in w.config('mac')))"]
    result = subprocess.run(args, capture_output=True, text=True)
    match = re.search(r'([0-9A-F]{2}:){5}[0-9A-F]{2}', result.stdout + result.stderr)
    return match.group(0) if match else None


def ensure_wifi():
    ssid = key = ''
    if WIFI_JSON.exists():
        with open(WIFI_JSON) as f:
            w = json.load(f)
        ssid = w.get('wifi_ssid', '')
        key = w.get('wifi_key', '')

    if ssid:
        print(f"  Loaded SSID '{ssid}' from src/wifi.json")
        if input("  Use this network? [Y/n]: ").strip().lower() == 'n':
            ssid = key = ''

    if not ssid:
        ssid = input("  WiFi SSID: ").strip()
        key = ''

    if key:
        print("  WiFi key: (loaded from src/wifi.json)")
    else:
        key = getpass.getpass("  WiFi key: ")

    with open(WIFI_JSON, 'w') as f:
        json.dump({'wifi_ssid': ssid, 'wifi_key': key}, f, indent=2)
    print("  Saved to src/wifi.json")


def set_peer_mac(board, mac):
    cfg = SCRIPT_DIR / 'src' / board / 'config.json'
    if not cfg.exists():
        shutil.copy(cfg.parent / 'config.json.example', cfg)
    with open(cfg) as f:
        d = json.load(f)
    d['peer_mac_address'] = mac
    with open(cfg, 'w') as f:
        json.dump(d, f, indent=2)


def deploy(board, port=None):
    if sys.platform == 'win32':
        cmd = ['deploy.bat', board]
        shell = True
    else:
        cmd = ['./deploy.sh', board]
        shell = False
    if port:
        cmd += ['-u', port]
    subprocess.run(cmd, check=True, cwd=SCRIPT_DIR, shell=shell)


def main():
    check_tools()

    print("=== Robot pairing setup ===")
    print()
    print("This wizard will:")
    print("  1. Deploy firmware to both boards")
    print("  2. Exchange MAC addresses so they can find each other over ESP-NOW")
    print()

    first = input("Configure which board first? [controller/robot] (default: controller): ").strip() or 'controller'
    if first not in ('controller', 'robot'):
        die(f"Invalid choice: {first}")
    second = 'robot' if first == 'controller' else 'controller'

    print()
    print("--- WiFi credentials ---")
    ensure_wifi()

    # Phase 1: first board
    print()
    print(f"--- Phase 1: {first} ---")
    input(f"Connect the {first} board via USB, then press Enter...")
    port1 = pick_port(first)

    print("  Reading MAC address...")
    mac1 = get_mac(port1)
    if not mac1:
        die(f"Could not read MAC from {first}. Check the connection and try again.")
    print(f"  {first} MAC: {mac1}")
    print(f"  Deploying {first} firmware...")
    print(f"  (peer MAC will be updated after {second} is configured)")
    deploy(first, port1)

    # Phase 2: second board
    print()
    print(f"--- Phase 2: {second} ---")
    input(f"Connect the {second} board via USB, then press Enter...")
    port2 = pick_port(second)

    print("  Reading MAC address...")
    mac2 = get_mac(port2)
    if not mac2:
        die(f"Could not read MAC from {second}. Check the connection and try again.")
    print(f"  {second} MAC: {mac2}")
    set_peer_mac(second, mac1)
    print(f"  Deploying {second} firmware (peer MAC = {mac1})...")
    deploy(second, port2)

    # Phase 3: update first board with peer MAC
    print()
    print(f"--- Phase 3: update {first} with peer MAC ---")
    set_peer_mac(first, mac2)
    input(f"Reconnect the {first} board via USB, then press Enter...")
    port3 = pick_port(first)
    print(f"  Pushing updated config to {first} (peer MAC = {mac2})...")
    deploy(first, port3)

    print()
    print("=== Setup complete ===")
    print(f"  {first} MAC: {mac1}")
    print(f"  {second} MAC: {mac2}")
    print()
    print("Reset both boards to start.")


if __name__ == '__main__':
    main()
