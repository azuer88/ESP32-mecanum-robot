import json

import network
# noinspection PyUnresolvedReferences
import aioespnow
import ubinascii
import asyncio
import queue
from machine import Pin
# noinspection PyUnresolvedReferences
from dcmotor import DCMotor
from config import main_config, start_webrepl
from lib.mecanum import MecanumDrive

PEER_MAC_ADDRESS_STR = main_config.get('peer_mac_address', '00:00:00:00:00:00')
PEER_MAC_ADDRESS = ubinascii.unhexlify(PEER_MAC_ADDRESS_STR.replace(":", ""))

if PEER_MAC_ADDRESS_STR == '00:00:00:00:00:00':
    print("WARNING: peer_mac_address not set in config.json — ESP-NOW will fail")

WIFI_CHANNEL = 11  # All devices must be on the same channel

boot_button_pin = Pin(0, Pin.IN, Pin.PULL_UP)
stop_event = asyncio.Event()
led = Pin(2, Pin.OUT)
action_event = asyncio.Event()

main_queue = queue.Queue(10)

mecanum = MecanumDrive()
mecanum.load_cfg()

TIMEOUT_S = 10  # 10 seconds

_DRIVE_KEYS = {'throttle', 'strafe', 'rotate'}


# --- Setup Wi-Fi and ESP-NOW ---
def setup_espnow():
    """Initializes the Wi-Fi interface and ESP-NOW."""
    sta = network.WLAN(network.STA_IF)
    sta.active(False)  # ensure it is disabled
    sta.active(True)
    # noinspection PyUnresolvedReferences
    sta.config(channel=WIFI_CHANNEL, pm=sta.PM_NONE)
    sta.disconnect()

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


async def monitor_button():
    """Monitors the boot button and sets the stop_event when pressed."""
    print("Monitoring boot button...")
    while True:
        if boot_button_pin.value() == 0:
            print("Boot button pressed, setting stop event.")
            stop_event.set()
            break
        # noinspection PyUnresolvedReferences
        await asyncio.sleep_ms(50)  # debounce and yield to other tasks
    print("Monitoring button stopped.")


async def receive_messages(espnow: aioespnow.AIOESPNOW):
    """Listens for and processes incoming messages until stop_event is set."""
    print("Starting receiving messages")
    try:
        while not stop_event.is_set():
            mac, msg = await espnow.airecv()
            if mac is None:
                # Timed out awaiting for message, check stop_event again
                # noinspection PyUnresolvedReferences
                await asyncio.sleep_ms(50)
                continue
            else:
                action_event.set()

            sender_mac = ubinascii.hexlify(mac, ':').decode()
            decoded_mesg = msg.decode()
            print(f"Received from {sender_mac}: {decoded_mesg}")
            if decoded_mesg == "BYE":
                stop_event.set()
            else:
                try:
                    data = json.loads(decoded_mesg)
                except ValueError as e:
                    print(f"error decoding json - {decoded_mesg}: {e!r}")
                    continue
                if not isinstance(data, dict) or not _DRIVE_KEYS.issubset(data):
                    print(f"unexpected message structure, ignoring: {data}")
                    continue
                # noinspection PyUnresolvedReferences
                await main_queue.put(data)

    except OSError as err:
        print(f"Failed to receive messages: {err!r}")
    finally:
        print("Receiving messages done")


async def monitor_activity():
    while True:
        action_event.clear()  # clear the event for the next cycle
        try:
            print(f"waiting for activity timeout in {TIMEOUT_S} seconds...")
            await asyncio.wait_for(action_event.wait(), TIMEOUT_S)
            # this code runs only if the event was set (activity detected)
            print("Activity detected! Continue to wait.")
        except asyncio.TimeoutError:
            # This code runs only if the timeout was reached
            print("Activity timed out! turning off mecanum drive.")
            mecanum.stop()


async def handle_task():
    while True:
        item = await main_queue.get()
        print(f"command: ({type(item)}) - {item}")
        mecanum.drive(**item)


async def main():
    try:
        esp_now_instance = setup_espnow()
    except OSError as err:
        print(f"Fatal: could not initialize ESP-NOW: {err}")
        return

    tasks = [
        asyncio.create_task(monitor_button()),
        asyncio.create_task(monitor_activity()),
        asyncio.create_task(handle_task()),
        asyncio.create_task(receive_messages(esp_now_instance))
    ]
    led.value(1)
    await stop_event.wait()
    led.value(0)

    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    esp_now_instance.active(False)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Program exited.")
    finally:
        asyncio.new_event_loop()  # clear the loop for the next run
        start_webrepl()  # enable webrepl again
