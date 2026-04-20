# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

MicroPython firmware for an ESP32 mecanum wheel robot controlled wirelessly over ESP-NOW. There is no build system, no test runner, and no linter — files are deployed directly to hardware via `mpremote`. All Python runs on MicroPython, not CPython; standard library modules (`asyncio`, `json`) map to their MicroPython equivalents (`uasyncio`, `ujson`).

## Deploying code

Use the virtualenv at `/home/lou/.virtualenvs/micropython2` for `mpremote`.

`boot.py`, `config.py`, and `lib/queue.py` are shared between boards and live in `src/shared/`. The deploy script assembles shared + board-specific files before pushing.

**Config is split into two files:**
- `src/wifi.json` — WiFi credentials shared by both boards (gitignored; copy from `src/wifi.json.example`)
- `src/<board>/config.json` — board-specific keys: `peer_mac_address`, pins (gitignored; copy from `config.json.example`)

`deploy.sh` merges both at deploy time; neither is committed.

```bash
# First time: pair both boards end-to-end (handles MACs, WiFi, deploy)
./setup.sh          # Linux/macOS
# setup.bat         # Windows

# Recover local config files from boards already deployed (e.g. on a new machine)
./recover.sh        # Linux/macOS
# recover.bat       # Windows

# Deploy robot firmware
./deploy.sh robot

# Deploy controller firmware
./deploy.sh controller

# Push a single changed file and reset
mpremote cp main.py :main.py + reset

# Run a file without copying (useful for quick tests)
mpremote run main.py

# Open a REPL
mpremote
```

## Configurator GUI

`src/configurator/configurator.py` is a tkinter desktop app for configuring and flashing boards over USB. It uses `mpremote`, `esptool`, and `pyserial` — install via `src/configurator/requirements.txt`.

Three tabs:
- **Controller / Robot** — Read Device (populates all fields + device info), Write Config (writes json files to device), Write Firmware (runs `deploy.sh`; checks `peer_mac_address` pre-flight and auto-fills from the other tab's known MAC if missing or warns on mismatch). **Read both devices before writing firmware** so the app can verify/correct the peer MAC on each side.
- **Flash** — firmware dropdown (local `.bin` files in `provision/` + fetchable from micropython.org), Download, Flash MicroPython (erase + write + deploy skel), Deploy Skeleton (skel only, clears existing files first)

WiFi SSID/password are shared `tk.StringVar` instances between Controller and Robot tabs — reading either board fills the other. Hardware MACs are similarly tracked cross-tab to support the peer MAC pre-flight check.

Run: `python3 src/configurator/configurator.py`
Build Windows exe: `cd src/configurator && build.bat`

## Provisioning a bare board

`provision/provision.sh` flashes MicroPython and deploys a WebREPL baseline — **not** the project firmware. Run project deploy commands afterwards.

```bash
cd provision
./provision.sh            # deploy skel only (MicroPython already installed)
./provision.sh -p         # flash firmware then deploy skel
./provision.sh -p --usb /dev/ttyUSB1   # specify port when multiple devices connected
```

Requires `skel/config.json` (copy from `skel/config.json.example`) and `skel/webrepl_cfg.py` (gitignored) to exist before running.

## Writing config.json on a device

`config.py` exposes two WebREPL helpers:

```python
import config
config.write_config('ssid', 'password', peer_mac_address='AA:BB:CC:DD:EE:FF')  # full reset
config.update_config(peer_mac_address='AA:BB:CC:DD:EE:FF')                      # single key
```

## Architecture

### Communication

Controller and robot communicate over **ESP-NOW** (Wi-Fi layer 2, no router needed). Both boards must be on the same channel (`WIFI_CHANNEL = 11`). The controller sends JSON drive commands; the robot receives and executes them.

Drive command format:
```json
{"throttle": 0.5, "strafe": 0.0, "rotate": 0.0}
```
Add `"queued": true` to route into the scripted FIFO queue instead of the live register.

### Robot async task model (`src/robot/main.py`)

Five concurrent `asyncio` tasks:

| Task | Role |
|---|---|
| `receive_messages` | Receives ESP-NOW packets; routes to `_current_cmd` (live) or `main_queue` (scripted) |
| `control_loop` | 50 Hz loop; drives motors from `_current_cmd` when `main_queue` is empty |
| `handle_task` | Drains `main_queue`; non-empty queue suppresses `control_loop` (scripted takes priority) |
| `monitor_activity` | Stops motors and zeros `_current_cmd` after `TIMEOUT_S` seconds of silence |
| `monitor_button` | BOOT button (GPIO0) triggers clean shutdown |

### Controller async task model (`src/controller/main.py`)

Three tasks: `read_joystick_task` (reads ADC, normalises, sends ESP-NOW), `blink_led` (mode indicator), `monitor_button` (shutdown).

`DebouncedADC` averages 50 raw samples per read and applies an EMA filter. Values are quantised to 0.05 steps before transmission to suppress jitter. A reading of `65535` is treated as a joystick button press (mode toggle), not an axis value.

### Motor driver (`src/robot/lib/dcmotor.py`)

`DCMotor` is a factory: two args → `MX1508` (both pins PWM), three args → `TB6612FNG` (direction pins + PWM enable). Both inherit from `_DCMotorBase`. The factory is backward-compatible with `mecanum.json` entries — add `enable_pin` for TB6612FNG, omit it for MX1508.

### Mecanum kinematics (`src/robot/lib/mecanum.py`)

`MecanumDrive.drive(throttle, strafe, rotate)` applies standard mecanum wheel mixing, scales by `input_scale` (default 0.5), and normalises if any wheel exceeds 1.0. Motor config is loaded from `mecanum.json` on the device filesystem at boot.

### Config system

Both boards share `src/shared/config.py`: `load_config()` reads and caches `config.json`; `do_connect()` connects to WiFi and removes `wifi_key` from memory on success; `start_webrepl()` calls both. `src/shared/boot.py` checks `cfg.get('wifi_on_boot', False)` — keep this `false` or absent. Setting it `true` adds a WiFi connection attempt at boot (up to 50 s) with no benefit: `setup_espnow()` in `main.py` immediately drops the connection, leaving WebREPL unreachable. WebREPL becomes available after the BOOT button is pressed — the firmware's `finally` block calls `start_webrepl()` on exit.

## Gitignored files (must be created locally)

- `src/wifi.json` — WiFi credentials; copy from `src/wifi.json.example`
- `**/config.json` — board-specific config (peer MAC, pins); copy from `config.json.example`
- `**/webrepl_cfg.py` — generated on-device by `import webrepl_setup`, or create manually: `PASS = 'password'`
- `*.bin` — MicroPython firmware blobs
