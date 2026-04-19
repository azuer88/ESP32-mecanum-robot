import webrepl
import ujson

# import gc
# import sys


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
            ujson.dump(data, f)
        print(f"Wifi config successfully written.")
    except Exception as e:
        print(f"Error writing config: {e}")


def update_config(**kwargs):
    try:
        with open("config.json", "r") as f:
            data = ujson.load(f)
    except Exception as e:
        data = {}
        print(f"Error reading config: {e}")
    data.update(kwargs)
    try:
        with open("config.json", "w") as f:
            ujson.dump(data, f)
    except Exception as e:
        print(f"Error updating config: {e}")


def do_connect():
    global network_config
    global main_config

    import network
    import time

    main_config = {}
    try:
        with open("config.json", "r") as config_file:
            main_config = ujson.load(config_file)
    except OSError:
        print("config file not found or could not be opened.")

    sta_if = network.WLAN(network.STA_IF)
    if not sta_if.isconnected():
        print('connecting to network...')
        sta_if.active(True)
        # sta_if.connect('<ssid>', '<key>')
        ssid = main_config.get("wifi_ssid")
        key = main_config.get("wifi_key")
        print("wifi ssid: {}".format(ssid))
        sta_if.connect(ssid, key)
        count = 60
        while not sta_if.isconnected():
            time.sleep(5)
            count -= 1
            if count <= 0:
                break

    if sta_if.isconnected:
        network_config = sta_if.ifconfig()
        print('network config:', sta_if.ifconfig())
        del main_config["wifi_key"]
    else:
        print('network config failed.')


def start_webrepl():
    do_connect()
    webrepl.start()
