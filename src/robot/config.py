# noinspection PyUnresolvedReferences
import webrepl
import ujson


network_config = None
main_config = None


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


def start_webrepl(reload_config=False):
    if reload_config:
        load_config()
    do_connect()
    webrepl.start()
