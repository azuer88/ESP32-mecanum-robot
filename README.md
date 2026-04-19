# ESP32 Mecanum Robot

MicroPython firmware for an ESP32-based mecanum wheel robot controlled via ESP-NOW. Two boards talk directly to each other — no router needed.

- **`src/robot`** — drives four DC motors via TB6612FNG or MX1508 drivers
- **`src/controller`** — reads a 2-axis analog joystick and sends movement commands

## Hardware

### Robot
- ESP32 dev board
- TB6612FNG dual motor driver ×2 (or MX1508 ×2)
- Four DC motors with mecanum wheels
- Built-in LED on GPIO2
- **BOOT button** (GPIO0) — used by the firmware as emergency stop
- **EN button** — hardware reset; resets the board immediately, do not confuse with BOOT

### Controller
- ESP32 dev board
- KY-023 analog joystick (X → GPIO33, Y → GPIO32 by default)
- Built-in LED on GPIO2 (blink pattern indicates mode)
- **BOOT button** (GPIO0) — used by the firmware for clean shutdown
- **EN button** — hardware reset; resets the board immediately, do not confuse with BOOT

---

## Getting Started

Choose the path that matches your boards:

### Path A — Bare boards (no MicroPython yet)

> **Connection:** USB required throughout.

1. [Install tools](#1-install-tools) (mpremote + esptool)
2. [Provision each board](#provisioning-bare-boards) with `provision.sh`
3. [Pair and deploy](#pairing-and-deploying) with `./setup.sh`

### Path B — Boards already running MicroPython

> **Connection:** USB required for `setup.sh`. After that, config edits can be done over WiFi/WebREPL without a cable — press the BOOT button first to exit the firmware and re-enable WebREPL.

1. [Install mpremote](#1-install-tools)
2. [Pair and deploy](#pairing-and-deploying) with `./setup.sh`

### Path C — Manual deploy (no setup.sh)

> **Connection:** USB required for deploying firmware. Config-only edits can be done over WiFi/WebREPL once the boards are on the network — press the BOOT button first to exit the firmware and re-enable WebREPL.

1. [Install mpremote](#1-install-tools)
2. [Create config files](#configuration-reference) manually
3. Run `./deploy.sh robot` and `./deploy.sh controller`

Next: [Redeploying (deploy.sh)](#redeploying-deploysh)

### Path D — Firmware already running, no local config files

> **Connection:** USB required. `mpremote` interrupts the running firmware automatically — no need to press BOOT.

The boards are paired and working but you don't have the local config files (e.g. on a new machine). `recover.sh` / `recover.bat` reads `config.json` back from each board, detects the board type automatically, and reconstructs `src/wifi.json` and the board-specific `config.json`.

**Linux / macOS**

```bash
./recover.sh
```

**Windows**

```bat
recover.bat
```

Next: [Redeploying (deploy.sh)](#redeploying-deploysh)

---

## 1. Install Tools

mpremote is required for all paths. esptool is only needed when flashing firmware (Path A).

**Linux / macOS**

```bash
python3 -m venv venv
source venv/bin/activate
pip install mpremote==1.28.0
pip install esptool          # Path A only
```

**Debian / Ubuntu** — the system Python is often too old. Install Python 3.12 first:

```bash
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.12 python3.12-venv
python3.12 -m venv venv
source venv/bin/activate
pip install mpremote==1.28.0
```

**Windows** — Python 3.12 recommended, download from [python.org](https://www.python.org/downloads/windows/).

```bat
python -m venv venv
venv\Scripts\activate
pip install mpremote==1.28.0
```

Activate the virtual environment each time before using `mpremote`.

---

## Provisioning Bare Boards

> Skip this section if your boards already have MicroPython — go straight to [Pairing and Deploying](#pairing-and-deploying).

`provision/provision.sh` prepares a bare ESP32: it optionally flashes MicroPython, then deploys a minimal baseline (`boot.py`, `config.py`, `config.json`, `webrepl_cfg.py`, `lib/`) that gives you a working WebREPL and the config helpers.

**This is not the project firmware.** After provisioning, continue to [Pairing and Deploying](#pairing-and-deploying).

### 1. Prepare skeleton files

```bash
cd provision

# WiFi credentials for the baseline config
cp skel/config.json.example skel/config.json
# edit skel/config.json — fill in wifi_ssid and wifi_key

# WebREPL password (used only to authenticate WebREPL connections, not your WiFi password)
echo "PASS = 'your-password'" > skel/webrepl_cfg.py
```

### 2. Download MicroPython firmware (if flashing)

Download the correct `.bin` for your ESP32 variant from **<https://micropython.org/download/ESP32_GENERIC/>** and place it in the `provision/` folder. The script picks the newest file automatically.

| Variant | Board |
|---|---|
| `ESP32_GENERIC` | Standard ESP32 (most dev boards) |
| `ESP32_GENERIC_S2` | ESP32-S2 |
| `ESP32_GENERIC_S3` | ESP32-S3 |
| `ESP32_GENERIC_C3` | ESP32-C3 |

As of April 2026, the latest release is **v1.28.0**:

```bash
curl -O https://micropython.org/resources/firmware/ESP32_GENERIC-20260406-v1.28.0.bin
```

### 3. Run provision.sh

Provision one board at a time. Repeat for each board.

```bash
# Board already has MicroPython — deploy baseline only
./provision.sh

# Bare board — flash firmware then deploy baseline
./provision.sh -p

# Multiple USB devices connected — specify the port
./provision.sh -p --usb /dev/ttyUSB1
```

| Flag | Description |
|---|---|
| `-p` / `--program` | Erase flash and write MicroPython before deploying |
| `-u` / `--usb PORT` | Serial port (e.g. `/dev/ttyUSB1`, `/dev/ttyACM0`) |
| `-d` / `--debug` | Enable bash `-x` tracing |

After provisioning both boards, continue to the next section.

---

## Pairing and Deploying

`setup.sh` (Linux/macOS) and `setup.bat` (Windows) are an interactive wizard that configures both boards end-to-end:

1. Collects WiFi credentials and saves them to `src/wifi.json`
2. Connects to the first board, reads its MAC address, deploys firmware
3. Connects to the second board, reads its MAC address, deploys firmware with the first board's MAC as peer
4. Reconnects to the first board and pushes an updated config with the second board's MAC

**Linux / macOS**

```bash
./setup.sh
```

**Windows**

```bat
setup.bat
```

The script auto-detects the USB port. If multiple devices are connected, it lists them and asks which to use.

After `setup.sh` completes, both boards are fully configured and ready to run — **except the robot**, which also needs `mecanum.json` on its filesystem before it can drive motors. Copy the example and push it:

```bash
cp src/robot/mecanum.json.example src/robot/mecanum.json
# edit src/robot/mecanum.json if your wiring differs
mpremote cp src/robot/mecanum.json :mecanum.json
```

Then reset both boards to start:

```bash
mpremote reset
```

---

## Redeploying (deploy.sh)

Use `deploy.sh` to push updated firmware to a board after the initial pairing is done.

```bash
# Linux / macOS
./deploy.sh robot
./deploy.sh controller

# Windows
deploy.bat robot
deploy.bat controller
```

Specify a port when multiple USB devices are connected:

```bash
./deploy.sh robot -u /dev/ttyUSB1
./deploy.sh controller -u /dev/ttyACM0
```

```bat
deploy.bat robot -u COM3
```

The script merges `src/wifi.json` (shared WiFi credentials) with the board's `config.json` (peer MAC, pins) before pushing. See [Configuration Reference](#configuration-reference) for details.

### Pushing a single file

To update one file without a full redeploy:

```bash
mpremote cp main.py :main.py + reset
```

---

## Configuration Reference

Config is split into two files so WiFi credentials are managed in one place:

| File | Contents | Shared? |
|---|---|---|
| `src/wifi.json` | `wifi_ssid`, `wifi_key` | Both boards |
| `src/<board>/config.json` | `peer_mac_address`, pins | Per board |

Both are gitignored. `deploy.sh` merges them at deploy time — board-specific keys win on collision.

### WiFi — `src/wifi.json`

Copy from `src/wifi.json.example`:

```json
{
  "wifi_ssid": "your-network",
  "wifi_key": "your-password"
}
```

### Robot — `src/robot/config.json`

Copy from `src/robot/config.json.example`:

```json
{
  "peer_mac_address": "AA:BB:CC:DD:EE:FF"
}
```

`peer_mac_address` is the MAC of the **controller** ESP32.

### Controller — `src/controller/config.json`

Copy from `src/controller/config.json.example`:

```json
{
  "peer_mac_address": "AA:BB:CC:DD:EE:FF",
  "x_pin": 33,
  "y_pin": 32
}
```

`peer_mac_address` is the MAC of the **robot** ESP32. Keep `"wifi_on_boot"` absent or `false` — setting it to `true` adds a lengthy WiFi connection attempt at boot and has no useful effect, since `setup_espnow()` drops the WiFi connection immediately afterwards. Press the BOOT button to access WebREPL instead.

### Motor config — `mecanum.json` (on device)

Motor pin assignments live in `mecanum.json` on the robot's filesystem (not in this repo — create it on the device). The format depends on the motor driver.

**TB6612FNG** (3-pin per motor: two direction pins + PWM enable):

```json
{
  "fl": {"pin1": 12, "pin2": 14, "enable_pin": 27},
  "fr": {"pin1": 26, "pin2": 25, "enable_pin": 33},
  "rl": {"pin1": 17, "pin2": 16, "enable_pin": 32},
  "rr": {"pin1": 18, "pin2": 19, "enable_pin": 23}
}
```

**MX1508** (2-pin per motor: direction encoded by which pin is active):

```json
{
  "fl": {"pin1": 16, "pin2": 17},
  "fr": {"pin1": 18, "pin2": 19},
  "rl": {"pin1": 21, "pin2": 22},
  "rr": {"pin1": 25, "pin2": 26}
}
```

Mixed driver types are supported — each motor entry is routed to the correct driver based on whether `enable_pin` is present.

### TB6612FNG Wiring

Each TB6612FNG module drives two motors. Tie STBY HIGH (3.3 V) to keep the module enabled.

**Module 1 — front-left (fl) + front-right (fr)**

| TB6612FNG Pin | ESP32 GPIO | Motor | Role |
|---|---|---|---|
| PWMA | 33 | fr | speed (PWM) |
| AIN1 | 26 | fr | direction 1 |
| AIN2 | 25 | fr | direction 2 |
| STBY | 3.3 V | — | always enabled |
| BIN1 | 12 | fl | direction 1 |
| BIN2 | 14 | fl | direction 2 |
| PWMB | 27 | fl | speed (PWM) |

**Module 2 — rear-left (rl) + rear-right (rr)**

| TB6612FNG Pin | ESP32 GPIO | Motor | Role |
|---|---|---|---|
| PWMA | 32 | rl | speed (PWM) |
| AIN1 | 17 | rl | direction 1 |
| AIN2 | 16 | rl | direction 2 |
| STBY | 3.3 V | — | always enabled |
| BIN1 | 18 | rr | direction 1 |
| BIN2 | 19 | rr | direction 2 |
| PWMB | 23 | rr | speed (PWM) |

---

## Editing Config on the Device

### Via WebREPL or mpremote exec

> **WebREPL:** press the BOOT button to exit the firmware and re-enable WebREPL before connecting. **mpremote exec:** USB required.

`config.py` exposes two helpers:

**`write_config(ssid, key, **kwargs)`** — creates or fully overwrites `config.json`:

```python
import config
config.write_config('MyNetwork', 'mypassword', peer_mac_address='AA:BB:CC:DD:EE:FF')
```

**`update_config(**kwargs)`** — merges one or more keys into the existing file:

```python
import config
config.update_config(peer_mac_address='AA:BB:CC:DD:EE:FF')
config.update_config(wifi_ssid='NewNetwork', wifi_key='newpassword')
config.update_config(x_pin=34, y_pin=35)   # controller only
```

Changes take effect on the next boot. Reset after editing: `mpremote reset`.

### Via mpremote exec directly

```bash
mpremote exec "
import ujson
with open('config.json') as f:
    cfg = ujson.load(f)
cfg['wifi_on_boot'] = True
with open('config.json', 'w') as f:
    ujson.dump(cfg, f)
"
```

---

## WebREPL

Once a board is connected to WiFi, you can access it wirelessly via the [WebREPL client](https://micropython.org/webrepl/). No USB cable needed.

The password in `webrepl_cfg.py` is used only to authenticate connections to the board over WebREPL — it is separate from your WiFi password.

**Getting into WebREPL mode while project firmware is running:** press the BOOT button (GPIO0). The firmware shuts down cleanly and WebREPL starts automatically. The board stays on the network and accepts connections without a USB cable.

To set or reset the WebREPL password (requires USB):

```bash
mpremote exec "import webrepl_setup"
```

Keep `"wifi_on_boot"` absent or `false`. Setting it to `true` triggers a WiFi connection attempt during boot (up to 50 s if the network is slow) and then has no effect — `setup_espnow()` drops the connection immediately, leaving WebREPL unreachable. Press the BOOT button to exit the firmware cleanly; WebREPL is re-enabled automatically.

---

## mpremote Cheatsheet

```bash
mpremote                                  # open REPL (Ctrl+] to exit)
mpremote ls                               # list files on device
mpremote cp main.py :main.py + reset      # push file and reset
mpremote cp config.json :config.json      # push config (no reset needed)
mpremote rm :somefile.py                  # delete a file
mpremote reset                            # soft reset
mpremote run main.py                      # run without copying
mpremote exec "import os; print(os.listdir())"
mpremote connect /dev/ttyUSB1 ls         # target a specific port
```

---

## Dependencies

Install on each device via `mip`, or copy manually:

```bash
mpremote mip install aioespnow
```

- [`aioespnow`](https://github.com/glenn20/micropython-espnow) — async ESP-NOW wrapper (both boards)

---

## Architecture

### Communication

Controller and robot communicate over **ESP-NOW** (Wi-Fi layer 2, no router needed). Both boards must be on the same channel (`WIFI_CHANNEL = 11`). Commands are JSON objects with values in `[-1.0, 1.0]`:

```json
{"throttle": 0.5, "strafe": 0.0, "rotate": 0.0}
```

Add `"queued": true` to route into the scripted FIFO queue instead of the live register. The scripted queue takes priority — the live register is ignored while commands are queued.

The joystick button toggles between **rotate mode** (X axis turns the robot) and **strafe mode** (X axis slides sideways). The LED blinks fast in strafe mode, slow in rotate mode.

### Robot tasks (`src/robot/main.py`)

| Task | Role |
|---|---|
| `receive_messages` | Receives ESP-NOW packets; routes to queue or live register |
| `control_loop` | Drives motors at 50 Hz from the live register |
| `handle_task` | Drains the scripted FIFO queue; takes priority over `control_loop` |
| `monitor_activity` | Watchdog — stops motors after 10 s of silence |
| `monitor_button` | BOOT button (GPIO0) triggers a clean shutdown |

### Controller tasks (`src/controller/main.py`)

| Task | Role |
|---|---|
| `read_joystick_task` | Reads ADC, normalizes values, sends ESP-NOW packets |
| `blink_led` | Indicates current X-axis mode via blink pattern |
| `monitor_button` | BOOT button (GPIO0) triggers a clean shutdown |

`DebouncedADC` averages 50 raw samples per read and applies an EMA filter. Values are quantised to 0.05 steps to suppress jitter. A reading of `65535` is treated as a joystick button press (mode toggle), not an axis value.

---

## Repository Layout

```
setup.sh / setup.py   # interactive pairing wizard (first-time setup)
setup.bat             # Windows launcher for setup.py
recover.sh / recover.py  # recover local config files from boards already deployed
recover.bat           # Windows launcher for recover.py
deploy.sh             # assembles shared + board files and deploys via mpremote
deploy.bat            # Windows equivalent of deploy.sh
provision/
  provision.sh        # flashes MicroPython and deploys baseline (bare boards)
  skel/               # baseline files deployed by provision.sh
src/
  wifi.json.example   # WiFi credentials template (copy to wifi.json, gitignored)
  shared/
    boot.py           # boot sequence (shared by both boards)
    config.py         # WiFi/config helpers (shared by both boards)
    lib/
      queue.py        # async queue (shared by both boards)
  robot/
    main.py           # asyncio entry point
    config.json.example
    mecanum.json.example  # sample motor pin assignments (copy to mecanum.json, push to device)
    lib/
      dcmotor.py      # DCMotor factory + TB6612FNG and MX1508 drivers
      mecanum.py      # mecanum kinematics
  controller/
    main.py           # asyncio entry point
    config.json.example
```

---

## Emergency Stop

Press the **BOOT button** (GPIO0) on either board for a clean shutdown. On the robot, all motors stop immediately. On both boards, the firmware exits and **WebREPL is re-enabled** — so after pressing the button the board becomes accessible wirelessly over WiFi without a USB cable (provided `wifi_ssid` and `wifi_key` are set in `config.json`).
