# noinspection PyUnresolvedReferences
import webrepl
import ujson


network_config = None
main_config = None


# Write a new config.json with WiFi credentials and any extra keys.
# Intended for use in WebREPL to do initial device setup or full config reset.
# Any existing config.json is overwritten.
# Extra kwargs (e.g. peer_mac_address, x_pin) are merged into the file.
#
# Usage (in WebREPL):
#   import config
#   config.write_config('MyNetwork', 'mypassword', peer_mac_address='AA:BB:CC:DD:EE:FF')
def write_config(ssid, key, **kwargs):
    data = {
        "wifi_ssid": ssid,
        "wifi_key": key
    }
    data.update(kwargs)
    try:
        with open("config.json", "w") as f:
            # noinspection PyTypeChecker
            ujson.dump(data, f)
        print(f"Wifi config successfully written.")
    except Exception as e:
        print(f"Error writing config: {e}")


# Merge kwargs into the existing config.json, preserving all other keys.
# Intended for use in WebREPL to change individual settings without
# rewriting the whole file.
#
# Usage (in WebREPL):
#   import config
#   config.update_config(peer_mac_address='AA:BB:CC:DD:EE:FF')
#   config.update_config(wifi_ssid='NewNetwork', wifi_key='newpassword')
def update_config(**kwargs):
    try:
        with open("config.json", "r") as f:
            # noinspection PyTypeChecker
            data = ujson.load(f)
    except Exception as e:
        data = {}
        print(f"Error reading config: {e}")
    data.update(kwargs)
    try:
        with open("config.json", "w") as f:
            # noinspection PyTypeChecker
            ujson.dump(data, f)
    except Exception as e:
        print(f"Error updating config: {e}")


# Load config.json into main_config (cached after first call).
# Returns an empty dict if the file is missing or contains invalid JSON.
def load_config():
    global main_config

    if main_config is not None:
        return main_config

    main_config = {}
    try:
        with open("config.json", "r") as config_file:
            # noinspection PyTypeChecker
            main_config = ujson.load(config_file)
    except OSError as e:
        print(f"config file not found or could not be opened. - {e!r}")
    except ValueError as e:
        print(f"config file is not valid. - {e!r}")

    return main_config


# Connect to WiFi using credentials from main_config.
# Retries up to 10 times (5 s each) and aborts early on terminal error codes.
# Removes wifi_key from main_config after a successful connection.
def do_connect():
    global network_config
    global main_config

    import network
    import time

    TERMINAL_STATUSES = {
        network.STAT_WRONG_PASSWORD: "wrong password",
        network.STAT_NO_AP_FOUND: "SSID not found",
        network.STAT_CONNECT_FAIL: "connection failed",
    }

    ssid = main_config.get("wifi_ssid")
    key = main_config.get("wifi_key")

    if not ssid or not key:
        print("WiFi credentials missing in config.json — skipping connection.")
        return

    sta_if = network.WLAN(network.STA_IF)
    if not sta_if.isconnected():
        print(f"Connecting to '{ssid}'...")
        sta_if.active(True)
        sta_if.connect(ssid, key)
        count = 10
        while not sta_if.isconnected():
            time.sleep(5)
            status = sta_if.status()
            if status in TERMINAL_STATUSES:
                print(f"WiFi error: {TERMINAL_STATUSES[status]} (status={status})")
                break
            count -= 1
            if count <= 0:
                print("WiFi error: connection timed out")
                break

    if sta_if.isconnected():
        network_config = sta_if.ifconfig()
        print('network config:', sta_if.ifconfig())
        main_config.pop("wifi_key", None)
    else:
        print('network config failed — continuing without WiFi.')


# Connect to WiFi then start WebREPL.
# Pass reload_config=True to re-read config.json before connecting.
def start_webrepl(reload_config=False):
    if reload_config:
        load_config()
    do_connect()
    webrepl.start()
