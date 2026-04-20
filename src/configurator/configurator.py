#!/usr/bin/env python3
"""Configurator GUI for ESP32 mecanum robot boards."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import urllib.request
from datetime import datetime
from tkinter import ttk, scrolledtext

import serial.tools.list_ports


def _find_mpremote():
    if shutil.which("mpremote"):
        return ["mpremote"]
    return [sys.executable, "-m", "mpremote"]


MPREMOTE = _find_mpremote()

MOTORS = ["fl", "fr", "rl", "rr"]

MOTOR_LABELS = {
    "fl": "Front Left",
    "fr": "Front Right",
    "rl": "Rear Left",
    "rr": "Rear Right",
}

MOTOR_DEFAULTS = {
    "fl": {"pin1": 12, "pin2": 14, "enable_pin": 27},
    "fr": {"pin1": 26, "pin2": 25, "enable_pin": 33},
    "rl": {"pin1": 17, "pin2": 16, "enable_pin": 32},
    "rr": {"pin1": 18, "pin2": 19, "enable_pin": 23},
}



def _run_on_device(port, script, timeout=15):
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        f.write(script)
        path = f.name
    try:
        r = subprocess.run(
            MPREMOTE + ["connect", port, "run", path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip() or "mpremote error (no output)")
        return r.stdout.strip()
    finally:
        os.unlink(path)


def _write_to_device(port, remote_path, content, timeout=15):
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        f.write(content)
        path = f.name
    try:
        r = subprocess.run(
            MPREMOTE + ["connect", port, "cp", path, f":{remote_path}"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip() or "mpremote error (no output)")
    finally:
        os.unlink(path)


def _list_ports():
    return sorted(p.device for p in serial.tools.list_ports.comports())


# ── Base tab ──────────────────────────────────────────────────────────────────


_TEST_SCRIPT = """\
import sys, os, json, network, ubinascii
r = {}
r['impl'] = sys.implementation.name
files = os.listdir()
if 'mecanum.json' in files:
    r['board'] = 'robot'
else:
    try:
        f = open('config.json'); cfg = json.loads(f.read()); f.close()
        r['board'] = 'controller' if 'x_pin' in cfg else 'unknown'
    except:
        r['board'] = 'unknown'
try:
    f = open('config.json'); r['config'] = json.loads(f.read()); f.close()
except: r['config'] = None
try:
    f = open('wifi.json'); r['wifi'] = json.loads(f.read()); f.close()
except: r['wifi'] = None
try:
    sta = network.WLAN(network.STA_IF)
    r['mac'] = ubinascii.hexlify(sta.config('mac'), ':').decode()
except: r['mac'] = 'unknown'
try:
    f = open('mecanum.json'); r['mecanum'] = json.loads(f.read()); f.close()
except: r['mecanum'] = None
print(json.dumps(r))
"""


class _BoardTab(ttk.Frame):
    def __init__(self, parent, shared_ssid=None, shared_wifi_key=None,
                 own_mac_var=None, peer_hw_mac_var=None):
        super().__init__(parent, padding=8)
        self._ssid_var = shared_ssid or tk.StringVar()
        self._wifi_key_var = shared_wifi_key or tk.StringVar()
        self._own_mac_var = own_mac_var or tk.StringVar()
        self._peer_hw_mac_var = peer_hw_mac_var or tk.StringVar()
        self._build_connection()
        self._build_info()
        self._build_config()
        self._build_actions()
        self._build_status()
        self._update_action_state()

    # Connection

    def _build_connection(self):
        frm = ttk.LabelFrame(self, text="Connection", padding=6)
        frm.pack(fill="x", pady=(0, 6))

        ttk.Label(frm, text="Port:").pack(side="left", padx=(0, 4))
        self._port_var = tk.StringVar()
        self._port_combo = ttk.Combobox(
            frm, textvariable=self._port_var, width=18, state="readonly"
        )
        self._port_combo.pack(side="left", padx=(0, 4))
        self._port_combo.bind("<<ComboboxSelected>>", self._on_port_selected)
        ttk.Button(frm, text="Refresh", command=self._refresh_ports).pack(
            side="left", padx=(0, 4)
        )
        ttk.Button(frm, text="Read Device", command=self._test_connection).pack(
            side="left"
        )
        self._refresh_ports()

    def _refresh_ports(self):
        ports = _list_ports()
        self._port_combo["values"] = ports
        if ports and self._port_var.get() not in ports:
            self._port_var.set(ports[0])
        if hasattr(self, "_write_btn"):
            self._update_action_state()

    def _on_port_selected(self, event=None):
        self._update_action_state()

    # Subclasses set this to "controller" or "robot"
    _EXPECTED_BOARD = ""

    def _test_connection(self):
        port = self._port_var.get()
        if not port:
            self._status_var.set("Select a port first.")
            return
        self._status_var.set(f"Testing {port}…")
        self._set_action_state("disabled")

        def run():
            try:
                data = json.loads(_run_on_device(port, _TEST_SCRIPT, timeout=8))
                detected = data.get("board", "unknown")
                impl = data.get("impl", "?")
                if detected != self._EXPECTED_BOARD:
                    label = detected if detected != "unknown" else "an unrecognised board"
                    msg = (
                        f"Warning: expected a {self._EXPECTED_BOARD} but detected {label}. "
                        "Check you have the right port."
                    )
                else:
                    msg = f"OK — {port} is a {detected} running {impl}."
                self.after(0, lambda: self._set_info(data))
                self.after(0, lambda: self._populate_fields(data))
                self.after(0, lambda: self._status_var.set(msg))
            except Exception as exc:
                msg = f"Test failed: {exc}"
                self.after(0, lambda: self._status_var.set(msg))
            finally:
                self.after(0, self._update_action_state)

        threading.Thread(target=run, daemon=True).start()

    # Device info

    def _build_info(self):
        frm = ttk.LabelFrame(self, text="Device Info", padding=6)
        frm.pack(fill="x", pady=(0, 6))
        frm.columnconfigure(1, weight=1)
        self._info_mac = self._info_row(frm, "MAC Address:", 0)
        self._info_config = self._info_row(frm, "Config:", 1)
        self._info_wifi = self._info_row(frm, "WiFi:", 2)

    def _info_row(self, parent, label, row):
        ttk.Label(parent, text=label, anchor="w").grid(
            row=row, column=0, sticky="w", padx=(0, 10), pady=1
        )
        var = tk.StringVar(value="—")
        ttk.Label(parent, textvariable=var, foreground="#555555").grid(
            row=row, column=1, sticky="w", pady=1
        )
        return var

    def _set_info(self, data):
        self._info_mac.set(data.get("mac") or "unknown")
        cfg = data.get("config")
        self._info_config.set("Found" if cfg else "Not found")
        wifi = data.get("wifi") or {}
        ssid = wifi.get("wifi_ssid", "")
        if ssid:
            self._info_wifi.set(f"Configured  ({ssid})")
        elif wifi:
            self._info_wifi.set("Found (no SSID set)")
        else:
            self._info_wifi.set("Not found")

    def _clear_info(self):
        self._info_mac.set("—")
        self._info_config.set("—")
        self._info_wifi.set("—")

    # Shared WiFi + peer MAC fields

    def _build_wifi_fields(self, parent, start_row=0):
        ttk.Label(parent, text="WiFi SSID:", anchor="w").grid(
            row=start_row, column=0, sticky="w", padx=(0, 10), pady=3
        )
        ttk.Entry(parent, textvariable=self._ssid_var, width=30).grid(
            row=start_row, column=1, sticky="w", pady=3
        )

        ttk.Label(parent, text="WiFi Password:", anchor="w").grid(
            row=start_row + 1, column=0, sticky="w", padx=(0, 10), pady=3
        )
        ttk.Entry(parent, textvariable=self._wifi_key_var, width=30, show="*").grid(
            row=start_row + 1, column=1, sticky="w", pady=3
        )

        ttk.Label(parent, text="Peer MAC Address:", anchor="w").grid(
            row=start_row + 2, column=0, sticky="w", padx=(0, 10), pady=3
        )
        self._peer_mac_var = tk.StringVar()
        ttk.Entry(parent, textvariable=self._peer_mac_var, width=20).grid(
            row=start_row + 2, column=1, sticky="w", pady=3
        )

        return start_row + 3

    # Actions

    def _build_actions(self):
        frm = ttk.Frame(self)
        frm.pack(fill="x", pady=6)
        self._write_btn = ttk.Button(
            frm, text="Write Config", command=self._write, state="disabled"
        )
        self._write_btn.pack(side="left", padx=(0, 6))
        label = f"Write {self._EXPECTED_BOARD.capitalize()} Firmware"
        self._firmware_btn = ttk.Button(
            frm, text=label, command=self._write_firmware, state="disabled"
        )
        self._firmware_btn.pack(side="left")

    def _update_action_state(self):
        state = "normal" if self._port_var.get() else "disabled"
        self._write_btn.config(state=state)
        self._firmware_btn.config(state=state)

    def _set_action_state(self, state):
        self._write_btn.config(state=state)
        self._firmware_btn.config(state=state)

    def _write_firmware(self):
        port = self._port_var.get()

        # Pre-flight: check local config.json for peer_mac_address
        project_root = os.path.normpath(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
        )
        local_config = os.path.join(project_root, "src", self._EXPECTED_BOARD, "config.json")
        try:
            with open(local_config) as f:
                cfg = json.load(f)
            mac = cfg.get("peer_mac_address", "").strip()
            known = self._peer_hw_mac_var.get().strip()
            if not mac:
                if known:
                    cfg["peer_mac_address"] = known
                    with open(local_config, "w") as f:
                        json.dump(cfg, f, indent=2)
                    self._peer_mac_var.set(known)
                    self._log(
                        f"Auto-applied peer MAC from previously read device: {known}\n"
                        f"  Saved to src/{self._EXPECTED_BOARD}/config.json."
                    )
                else:
                    self._log(
                        "Warning: peer_mac_address is empty in "
                        f"src/{self._EXPECTED_BOARD}/config.json "
                        "and the peer device has not been read yet.\n"
                        "  Fix: open the other tab, connect to the peer device and click "
                        "Read Device — the MAC will be applied automatically.\n"
                        "  Or enter it manually in the Peer MAC Address field and click "
                        "Write Config, or run setup.sh to auto-pair both boards."
                    )
            elif known and mac.lower() != known.lower():
                self._log(
                    f"Warning: peer_mac_address in config.json ({mac}) does not match "
                    f"the MAC read from the peer device ({known}).\n"
                    "  Fix: click Write Config to update config.json with the correct MAC,\n"
                    "  or re-read both devices to verify they are the intended pair."
                )
        except FileNotFoundError:
            self._log(
                f"Warning: src/{self._EXPECTED_BOARD}/config.json not found.\n"
                f"  Copy src/{self._EXPECTED_BOARD}/config.json.example to "
                f"src/{self._EXPECTED_BOARD}/config.json and fill in peer_mac_address,\n"
                "  or run setup.sh to auto-pair both boards."
            )
        except Exception as exc:
            self._log(f"Warning: could not read local config.json: {exc}")

        self._set_action_state("disabled")
        self._status_var.set("Deploying firmware…")

        deploy = os.path.join(project_root, "deploy.sh")

        def run():
            try:
                r = subprocess.run(
                    ["bash", deploy, self._EXPECTED_BOARD, "-u", port],
                    capture_output=True, text=True, timeout=120,
                )
                if r.returncode != 0:
                    msg = r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "deploy failed"
                    self.after(0, lambda: self._status_var.set(f"Firmware error: {msg}"))
                else:
                    self.after(0, lambda: self._status_var.set("Firmware deployed."))
            except Exception as exc:
                msg = f"Firmware error: {exc}"
                self.after(0, lambda: self._status_var.set(msg))
            finally:
                self.after(0, self._update_action_state)

        threading.Thread(target=run, daemon=True).start()

    # Log panel

    def _build_status(self):
        self._status_var = tk.StringVar()
        self._status_var.trace_add("write", self._on_status_change)

        frm = ttk.Frame(self)
        frm.pack(fill="x", pady=(4, 0))

        ttk.Button(frm, text="Clear", command=self._clear_log).pack(side="right")

        self._log_widget = scrolledtext.ScrolledText(
            frm, height=4, state="disabled", wrap="word",
            font=("Courier", 9), relief="flat", background="#f5f5f5",
        )
        self._log_widget.pack(fill="x", side="left", expand=True)
        self._log("Select a port to begin.")

    def _log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self._log_widget.config(state="normal")
        self._log_widget.insert("end", f"[{ts}] {msg}\n")
        self._log_widget.see("end")
        self._log_widget.config(state="disabled")

    def _on_status_change(self, *_):
        msg = self._status_var.get()
        if msg:
            self._log(msg)

    def _clear_log(self):
        self._log_widget.config(state="normal")
        self._log_widget.delete("1.0", "end")
        self._log_widget.config(state="disabled")

    # Threading

    def _write(self):
        self._set_action_state("disabled")

        def wrapper():
            try:
                self._do_write()
            finally:
                self.after(0, self._update_action_state)

        threading.Thread(target=wrapper, daemon=True).start()

    # Subclass interface

    def _build_config(self):
        raise NotImplementedError

    def _populate_fields(self, data):
        raise NotImplementedError

    def _do_write(self):
        raise NotImplementedError


# ── Controller tab ────────────────────────────────────────────────────────────


class ControllerTab(_BoardTab):
    _EXPECTED_BOARD = "controller"

    def _build_config(self):
        frm = ttk.LabelFrame(self, text="Configuration", padding=6)
        frm.pack(fill="x", pady=(0, 6))
        frm.columnconfigure(1, weight=1)

        row = self._build_wifi_fields(frm, start_row=0)

        ttk.Separator(frm, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=8
        )
        row += 1

        ttk.Label(frm, text="X Axis Pin (ADC):", anchor="w").grid(
            row=row, column=0, sticky="w", padx=(0, 10), pady=3
        )
        self._x_pin_var = tk.StringVar(value="33")
        ttk.Entry(frm, textvariable=self._x_pin_var, width=8).grid(
            row=row, column=1, sticky="w", pady=3
        )
        row += 1

        ttk.Label(frm, text="Y Axis Pin (ADC):", anchor="w").grid(
            row=row, column=0, sticky="w", padx=(0, 10), pady=3
        )
        self._y_pin_var = tk.StringVar(value="32")
        ttk.Entry(frm, textvariable=self._y_pin_var, width=8).grid(
            row=row, column=1, sticky="w", pady=3
        )

    def _populate_fields(self, data):
        mac = data.get("mac", "")
        if mac and mac != "unknown":
            self._own_mac_var.set(mac)
        wifi = data.get("wifi") or {}
        self._ssid_var.set(wifi.get("wifi_ssid", ""))
        self._wifi_key_var.set(wifi.get("wifi_key", ""))
        cfg = data.get("config") or {}
        self._peer_mac_var.set(cfg.get("peer_mac_address", ""))
        self._x_pin_var.set(str(cfg.get("x_pin", "33")))
        self._y_pin_var.set(str(cfg.get("y_pin", "32")))

    def _do_write(self):
        port = self._port_var.get()
        self.after(0, lambda: self._status_var.set("Writing to device…"))
        try:
            wifi = {
                "wifi_ssid": self._ssid_var.get(),
                "wifi_key": self._wifi_key_var.get(),
            }
            config = {
                "peer_mac_address": self._peer_mac_var.get(),
                "x_pin": int(self._x_pin_var.get()),
                "y_pin": int(self._y_pin_var.get()),
            }
            _write_to_device(port, "wifi.json", json.dumps(wifi, indent=2))
            _write_to_device(port, "config.json", json.dumps(config, indent=2))
            self.after(0, lambda: self._status_var.set("Write complete."))
        except Exception as exc:
            msg = f"Write error: {exc}"
            self.after(0, lambda: self._status_var.set(msg))


# ── Robot tab ─────────────────────────────────────────────────────────────────


class RobotTab(_BoardTab):
    _EXPECTED_BOARD = "robot"

    def _build_config(self):
        frm = ttk.LabelFrame(self, text="Configuration", padding=6)
        frm.pack(fill="x", pady=(0, 6))
        frm.columnconfigure(1, weight=1)

        row = self._build_wifi_fields(frm, start_row=0)

        ttk.Separator(frm, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=8
        )
        row += 1

        self._motor_outer = ttk.LabelFrame(frm, text="Motor Pin Assignments", padding=6)
        self._motor_outer.grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=(6, 0)
        )

        self._motor_vars = {}
        self._build_motor_pins()

    def _build_motor_pins(self, saved=None):
        saved = saved or {}
        self._motor_vars = {}

        ttk.Label(self._motor_outer, text="").grid(row=0, column=0)
        ttk.Label(self._motor_outer, text="Pin 1 / IN1", width=11, anchor="center").grid(
            row=0, column=1, padx=4
        )
        ttk.Label(self._motor_outer, text="Pin 2 / IN2", width=11, anchor="center").grid(
            row=0, column=2, padx=4
        )
        ttk.Label(self._motor_outer, text="Enable / PWM", width=11, anchor="center").grid(
            row=0, column=3, padx=4
        )

        for i, motor in enumerate(MOTORS):
            d = MOTOR_DEFAULTS[motor]
            s = saved.get(motor, {})
            r = i + 1

            ttk.Label(
                self._motor_outer, text=MOTOR_LABELS[motor], anchor="w", width=13
            ).grid(row=r, column=0, sticky="w", pady=2)

            p1 = tk.StringVar(value=s.get("pin1", str(d["pin1"])))
            ttk.Entry(self._motor_outer, textvariable=p1, width=6).grid(
                row=r, column=1, padx=4, pady=2
            )

            p2 = tk.StringVar(value=s.get("pin2", str(d["pin2"])))
            ttk.Entry(self._motor_outer, textvariable=p2, width=6).grid(
                row=r, column=2, padx=4, pady=2
            )

            ep = tk.StringVar(value=s.get("enable_pin", str(d["enable_pin"])))
            ttk.Entry(self._motor_outer, textvariable=ep, width=6).grid(
                row=r, column=3, padx=4, pady=2
            )

            self._motor_vars[motor] = {"pin1": p1, "pin2": p2, "enable_pin": ep}

    def _populate_fields(self, data):
        mac = data.get("mac", "")
        if mac and mac != "unknown":
            self._own_mac_var.set(mac)
        wifi = data.get("wifi") or {}
        self._ssid_var.set(wifi.get("wifi_ssid", ""))
        self._wifi_key_var.set(wifi.get("wifi_key", ""))
        cfg = data.get("config") or {}
        self._peer_mac_var.set(cfg.get("peer_mac_address", ""))
        mecanum = data.get("mecanum")
        if mecanum:
            saved = {
                motor: {
                    "pin1": str(mecanum[motor].get("pin1", "")),
                    "pin2": str(mecanum[motor].get("pin2", "")),
                    "enable_pin": str(mecanum[motor].get("enable_pin", "")),
                }
                for motor in MOTORS
                if motor in mecanum
            }
            self._build_motor_pins(saved=saved)

    def _do_write(self):
        port = self._port_var.get()
        self.after(0, lambda: self._status_var.set("Writing to device…"))
        try:
            wifi = {
                "wifi_ssid": self._ssid_var.get(),
                "wifi_key": self._wifi_key_var.get(),
            }
            config = {"peer_mac_address": self._peer_mac_var.get()}
            mecanum = {}
            for motor, vars_dict in self._motor_vars.items():
                entry = {
                    "pin1": int(vars_dict["pin1"].get()),
                    "pin2": int(vars_dict["pin2"].get()),
                }
                ep = vars_dict["enable_pin"].get().strip()
                if ep:
                    entry["enable_pin"] = int(ep)
                mecanum[motor] = entry

            _write_to_device(port, "wifi.json", json.dumps(wifi, indent=2))
            _write_to_device(port, "config.json", json.dumps(config, indent=2))
            _write_to_device(port, "mecanum.json", json.dumps(mecanum, indent=2))
            self.after(0, lambda: self._status_var.set("Write complete."))
        except Exception as exc:
            msg = f"Write error: {exc}"
            self.after(0, lambda: self._status_var.set(msg))


# ── App ───────────────────────────────────────────────────────────────────────


# ── Flash tab ─────────────────────────────────────────────────────────────────

_FIRMWARE_PAGE = "https://micropython.org/download/ESP32_GENERIC/"
_FIRMWARE_BASE = "https://micropython.org"
_FIRMWARE_RE = re.compile(r'/resources/firmware/(ESP32_GENERIC-(\d{8})-(v[\d.]+)\.bin)')

_PROVISION_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "provision")
)
_SKEL_DIR = os.path.join(_PROVISION_DIR, "skel")

ESPTOOL = [sys.executable, "-m", "esptool"]


class FlashTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=8)
        # label -> local path or None (for online-only entries)
        self._entries = {}  # label -> local path (str) or None for online-only
        self._online: dict[str, str] = {}  # label -> download URL
        self._build_connection()
        self._build_firmware()
        self._build_actions()
        self._build_status()
        self._refresh_local()

    # ── Connection ──────────────────────────────────────────────────────────

    def _build_connection(self):
        frm = ttk.LabelFrame(self, text="Connection", padding=6)
        frm.pack(fill="x", pady=(0, 6))

        ttk.Label(frm, text="Port:").pack(side="left", padx=(0, 4))
        self._port_var = tk.StringVar()
        self._port_combo = ttk.Combobox(
            frm, textvariable=self._port_var, width=18, state="readonly"
        )
        self._port_combo.pack(side="left", padx=(0, 4))
        self._port_combo.bind("<<ComboboxSelected>>", lambda e: self._update_buttons())
        ttk.Button(frm, text="Refresh", command=self._refresh_ports).pack(side="left")
        self._refresh_ports()

    def _refresh_ports(self):
        ports = _list_ports()
        self._port_combo["values"] = ports
        if ports and self._port_var.get() not in ports:
            self._port_var.set(ports[0])
        if hasattr(self, "_flash_btn"):
            self._update_buttons()

    # ── Firmware picker ─────────────────────────────────────────────────────

    def _build_firmware(self):
        frm = ttk.LabelFrame(self, text="Firmware", padding=6)
        frm.pack(fill="x", pady=(0, 6))

        self._fw_var = tk.StringVar()
        self._fw_combo = ttk.Combobox(
            frm, textvariable=self._fw_var, state="readonly", width=46
        )
        self._fw_combo.pack(fill="x", pady=(0, 6))
        self._fw_combo.bind("<<ComboboxSelected>>", lambda e: self._update_buttons())

        btn_row = ttk.Frame(frm)
        btn_row.pack(fill="x")
        ttk.Button(btn_row, text="Fetch Available Online", command=self._fetch_online).pack(
            side="left", padx=(0, 6)
        )
        self._dl_btn = ttk.Button(
            btn_row, text="Download", command=self._download, state="disabled"
        )
        self._dl_btn.pack(side="left")

    def _refresh_local(self):
        local = sorted(
            f for f in os.listdir(_PROVISION_DIR) if f.endswith(".bin")
        ) if os.path.isdir(_PROVISION_DIR) else []

        # Rebuild entries: start fresh from local files, keep online entries
        self._entries = {}
        for f in local:
            label = f"[local]  {f}"
            self._entries[label] = os.path.join(_PROVISION_DIR, f)

        for label, url in self._online.items():
            # Mark as local too if file now exists
            filename = url.rsplit("/", 1)[-1]
            local_path = os.path.join(_PROVISION_DIR, filename)
            if os.path.isfile(local_path):
                new_label = label.replace("[online]", "[local] ")
                self._entries[new_label] = local_path
            else:
                self._entries[label] = None

        self._fw_combo["values"] = list(self._entries)
        if self._entries and not self._fw_var.get():
            self._fw_combo.current(0)
        self._update_buttons()

    def _fetch_online(self):
        self._status_var.set("Fetching firmware list…")
        self._dl_btn.config(state="disabled")

        def run():
            try:
                with urllib.request.urlopen(_FIRMWARE_PAGE, timeout=10) as resp:
                    html = resp.read().decode()
                matches = _FIRMWARE_RE.findall(html)
                new_online = {}
                for filename, date, version in matches:
                    label = f"[online] {filename}"
                    url = f"{_FIRMWARE_BASE}/resources/firmware/{filename}"
                    new_online[label] = url
                self._online = new_online
                self.after(0, self._refresh_local)
                self.after(0, lambda: self._status_var.set(
                    f"Found {len(new_online)} firmware versions online."
                ))
            except Exception as exc:
                msg = f"Fetch error: {exc}"
                self.after(0, lambda: self._status_var.set(msg))

        threading.Thread(target=run, daemon=True).start()

    def _download(self):
        label = self._fw_var.get()
        url = self._online.get(label)
        if not url:
            return
        filename = url.rsplit("/", 1)[-1]
        dest = os.path.join(_PROVISION_DIR, filename)
        self._dl_btn.config(state="disabled")
        self._status_var.set(f"Downloading {filename}…")

        def run():
            try:
                urllib.request.urlretrieve(url, dest)
                self.after(0, self._refresh_local)
                self.after(0, lambda: self._status_var.set(f"Downloaded: {filename}"))
            except Exception as exc:
                msg = f"Download error: {exc}"
                self.after(0, lambda: self._status_var.set(msg))
            finally:
                self.after(0, self._update_buttons)

        threading.Thread(target=run, daemon=True).start()

    # ── Actions ─────────────────────────────────────────────────────────────

    def _build_actions(self):
        frm = ttk.Frame(self)
        frm.pack(fill="x", pady=6)
        self._flash_btn = ttk.Button(
            frm, text="Flash MicroPython", command=self._flash, state="disabled"
        )
        self._flash_btn.pack(side="left", padx=(0, 6))
        self._skel_btn = ttk.Button(
            frm, text="Deploy Skeleton", command=self._deploy_skel, state="disabled"
        )
        self._skel_btn.pack(side="left")

    def _update_buttons(self):
        label = self._fw_var.get()
        local_path = self._entries.get(label)
        is_online_only = label in self._entries and local_path is None

        self._dl_btn.config(state="normal" if is_online_only else "disabled")

        has_port = bool(self._port_var.get())
        self._flash_btn.config(state="normal" if (local_path and has_port) else "disabled")
        self._skel_btn.config(state="normal" if has_port else "disabled")

    # ── Log panel ─────────────────────────────────────────────────────────────

    def _build_status(self):
        self._status_var = tk.StringVar()
        self._status_var.trace_add("write", self._on_status_change)

        frm = ttk.Frame(self)
        frm.pack(fill="x", pady=(4, 0))

        ttk.Button(frm, text="Clear", command=self._clear_log).pack(side="right")

        self._log_widget = scrolledtext.ScrolledText(
            frm, height=4, state="disabled", wrap="word",
            font=("Courier", 9), relief="flat", background="#f5f5f5",
        )
        self._log_widget.pack(fill="x", side="left", expand=True)
        self._log("Select a port and firmware to begin.")

    def _log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self._log_widget.config(state="normal")
        self._log_widget.insert("end", f"[{ts}] {msg}\n")
        self._log_widget.see("end")
        self._log_widget.config(state="disabled")

    def _on_status_change(self, *_):
        msg = self._status_var.get()
        if msg:
            self._log(msg)

    def _clear_log(self):
        self._log_widget.config(state="normal")
        self._log_widget.delete("1.0", "end")
        self._log_widget.config(state="disabled")

    # ── Flash / skel ─────────────────────────────────────────────────────────

    def _deploy_skel(self):
        port = self._port_var.get()
        if not port:
            return
        self._skel_btn.config(state="disabled")
        self._flash_btn.config(state="disabled")

        def run():
            try:
                self._provision_skel(port, clean=True)
                self.after(0, lambda: self._status_var.set("Skeleton deployed."))
            except Exception as exc:
                msg = f"Error: {exc}"
                self.after(0, lambda: self._status_var.set(msg))
            finally:
                self.after(0, self._update_buttons)

        threading.Thread(target=run, daemon=True).start()

    def _flash(self):
        port = self._port_var.get()
        firmware = self._entries.get(self._fw_var.get())
        if not port or not firmware:
            return

        self._flash_btn.config(state="disabled")
        self._status_var.set("Erasing flash…")

        def run():
            try:
                self._run_step(
                    ["Erasing flash…", "Erase complete."],
                    ESPTOOL + ["--port", port, "erase_flash"],
                )
                self._run_step(
                    [f"Writing {os.path.basename(firmware)}…", "Firmware written."],
                    ESPTOOL + ["--port", port, "--baud", "460800",
                               "write_flash", "0x1000", firmware],
                )
                for i in range(10, 0, -1):
                    self.after(0, lambda i=i: self._status_var.set(
                        f"Waiting for device to reboot… {i}s"
                    ))
                    time.sleep(1)
                self._provision_skel(port)
                self.after(0, lambda: self._status_var.set("Done. Reset the device to apply."))
            except Exception as exc:
                msg = f"Error: {exc}"
                self.after(0, lambda: self._status_var.set(msg))
            finally:
                self.after(0, self._update_buttons)

        threading.Thread(target=run, daemon=True).start()

    def _run_step(self, messages, cmd):
        start_msg, done_msg = messages
        self.after(0, lambda: self._status_var.set(start_msg))
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            detail = r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "failed"
            raise RuntimeError(detail)
        self.after(0, lambda: self._status_var.set(done_msg))

    _CLEAN_SCRIPT = """\
import os
def _rm_r(path):
    try:
        for e in os.ilistdir(path):
            f = path + '/' + e[0]
            _rm_r(f) if e[1] == 0x4000 else os.remove(f)
        os.rmdir(path)
    except: pass
for _f in ['boot.py','config.py','config.json','webrepl_cfg.py']:
    try: os.remove(_f)
    except: pass
_rm_r('lib')
"""

    def _provision_skel(self, port, clean=False):
        if clean:
            self.after(0, lambda: self._status_var.set("Removing existing files…"))
            _run_on_device(port, self._CLEAN_SCRIPT, timeout=15)

        if not os.path.isdir(_SKEL_DIR):
            return
        required = [
            os.path.join(_SKEL_DIR, "config.json"),
            os.path.join(_SKEL_DIR, "webrepl_cfg.py"),
        ]
        missing = [f for f in required if not os.path.isfile(f)]
        if missing:
            names = ", ".join(os.path.basename(f) for f in missing)
            raise RuntimeError(f"Skel files missing: {names} — see provision/skel/")

        self.after(0, lambda: self._status_var.set("Deploying skeleton files…"))
        skel_files = ["boot.py", "config.py", "config.json", "webrepl_cfg.py"]
        existing = [
            os.path.join(_SKEL_DIR, f)
            for f in skel_files
            if os.path.isfile(os.path.join(_SKEL_DIR, f))
        ]

        # Copy each file individually to preserve other files on the device
        for src in existing:
            r = subprocess.run(
                MPREMOTE + ["connect", port, "resume", "cp", src, f":/{os.path.basename(src)}"],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode != 0:
                detail = r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "mpremote failed"
                raise RuntimeError(detail)

        lib_dir = os.path.join(_SKEL_DIR, "lib")
        if os.path.isdir(lib_dir):
            r = subprocess.run(
                MPREMOTE + ["connect", port, "resume", "cp", "-r", lib_dir, ":/"],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode != 0:
                detail = r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "mpremote failed"
                raise RuntimeError(detail)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Robot Configurator")
        self.resizable(False, False)

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        shared_ssid = tk.StringVar()
        shared_wifi_key = tk.StringVar()
        controller_mac = tk.StringVar()
        robot_mac = tk.StringVar()
        notebook.add(
            ControllerTab(notebook, shared_ssid, shared_wifi_key,
                          own_mac_var=controller_mac, peer_hw_mac_var=robot_mac),
            text="  Controller  ",
        )
        notebook.add(
            RobotTab(notebook, shared_ssid, shared_wifi_key,
                     own_mac_var=robot_mac, peer_hw_mac_var=controller_mac),
            text="  Robot  ",
        )
        notebook.add(FlashTab(notebook), text="  Flash  ")


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
