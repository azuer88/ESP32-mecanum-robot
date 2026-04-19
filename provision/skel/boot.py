# This file is executed on every boot (including wake-boot from deepsleep)
from config import load_config, start_webrepl

cfg = load_config()
if cfg.get('wifi_on_boot', True):
    start_webrepl()
