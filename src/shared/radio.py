import network
import aioespnow
import ubinascii
import asyncio
from machine import Pin
from config import main_config

WIFI_CHANNEL = 11

PEER_MAC_ADDRESS_STR = main_config.get('peer_mac_address', '') or '00:00:00:00:00:00'
PEER_MAC_ADDRESS = ubinascii.unhexlify(PEER_MAC_ADDRESS_STR.replace(':', ''))


def setup_espnow():
    sta = network.WLAN(network.STA_IF)
    sta.active(False)
    sta.active(True)
    # noinspection PyUnresolvedReferences
    sta.config(channel=WIFI_CHANNEL, pm=sta.PM_NONE)
    sta.disconnect()

    if PEER_MAC_ADDRESS_STR == '00:00:00:00:00:00':
        raise OSError("peer_mac_address not configured in config.json")

    e = aioespnow.AIOESPNow()
    try:
        e.config(rxbuf=1024, timeout_ms=50)
        e.active(True)
        e.add_peer(PEER_MAC_ADDRESS)
        print(f"ESP-NOW initialized. Peer added: {PEER_MAC_ADDRESS_STR}")
    except OSError as err:
        print(f"Failed to initialize ESP-NOW: {err}")
        raise
    return e


async def monitor_button(stop_event, button_pin=0):
    print("Monitoring boot button...")
    pin = Pin(button_pin, Pin.IN, Pin.PULL_UP)
    while True:
        if pin.value() == 0:
            print("Boot button pressed, setting stop event.")
            stop_event.set()
            break
        # noinspection PyUnresolvedReferences
        await asyncio.sleep_ms(50)
    print("Monitoring button stopped.")
