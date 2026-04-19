# ESP32 Mecanum Robot — Receiver

MicroPython firmware for an ESP32-based mecanum wheel robot. Movement commands are received wirelessly from a peer ESP32 via ESP-NOW and translated into per-wheel PWM signals through a TB6612FNG motor driver.

## Hardware

- ESP32 dev board
- TB6612FNG dual motor driver (×2 for four motors)
- Four DC motors with mecanum wheels
- Built-in LED on GPIO2, boot button on GPIO0 (emergency stop)

## How It Works

Four asyncio tasks run concurrently:

| Task | Role |
|---|---|
| `receive_messages` | Receives ESP-NOW packets from the controller board |
| `handle_task` | Dequeues commands and calls `mecanum.drive()` |
| `monitor_activity` | Watchdog — stops motors after 10 s of silence |
| `monitor_button` | GPIO0 boot button triggers a clean shutdown |

Commands are JSON objects: `{"throttle": 0.5, "strafe": 0.0, "rotate": 0.0}` with values in `[-1.0, 1.0]`.

## Configuration

Copy `config.json.example` to `config.json` and fill in your values:

```json
{
  "wifi_ssid": "your-network",
  "wifi_key": "your-password",
  "peer_mac_address": "AA:BB:CC:DD:EE:FF"
}
```

`peer_mac_address` is the MAC address of the controller ESP32. WiFi is used for WebREPL access; ESP-NOW does not require an active WiFi association.

Motor pin assignments are stored in `mecanum.json` on the device filesystem:

```json
{
  "fl": {"pin1": 12, "pin2": 14, "enable_pin": 27},
  "fr": {"pin1": 26, "pin2": 25, "enable_pin": 33},
  "rl": {"pin1": 17, "pin2": 16, "enable_pin": 32},
  "rr": {"pin1": 18, "pin2": 19, "enable_pin": 23}
}
```

## Dependencies

Install via `mip` on the device or copy manually:

- [`aioespnow`](https://github.com/glenn20/micropython-espnow) — async ESP-NOW wrapper

## Deploying with mpremote

[`mpremote`](https://docs.micropython.org/en/latest/reference/mpremote.html) is the recommended tool for interacting with the device over USB.

### Install

```bash
pip install mpremote
```

### Connect to the REPL

```bash
mpremote
```

Press `Ctrl+]` to exit.

### Run a file without copying it

```bash
mpremote run main.py
```

### Copy files to the device

```bash
# Single file
mpremote cp config.json :config.json

# Entire lib directory
mpremote cp -r lib/ :lib/

# Copy all project files in one command
mpremote cp boot.py main.py config.py config.json mecanum.json webrepl_cfg.py : + cp -r lib/ :lib/
```

The `:` prefix means the device filesystem. A trailing `:` (no filename) copies to the root.

### Initial deployment (full)

```bash
mpremote cp boot.py main.py config.py config.json mecanum.json webrepl_cfg.py : \
  + cp -r lib/ :lib/
```

### List files on the device

```bash
mpremote ls
mpremote ls :lib/
```

### Delete a file

```bash
mpremote rm :somefile.py
```

### Soft reset (restart without power cycle)

```bash
mpremote reset
```

### Run a command on the device

```bash
mpremote exec "import os; print(os.listdir())"
```

### Chain commands with `+`

```bash
mpremote cp config.json :config.json + reset
```

### WebREPL

Once the device is on WiFi, you can connect wirelessly via WebREPL. The password is set in `webrepl_cfg.py`. Use the [WebREPL client](https://micropython.org/webrepl/) or `mpremote` over the serial connection to set it up:

```bash
mpremote exec "import webrepl_setup"
```

## Emergency Stop

Press the **boot button** (GPIO0) while the robot is running to stop all motors and exit cleanly. WebREPL will be re-enabled after shutdown.
