import math
import json
import network
# noinspection PyUnresolvedReferences
import aioespnow
import ubinascii

import uasyncio as asyncio
from machine import Pin, ADC
from config import main_config, start_webrepl

X_DEADZONE = (30450, 33950)
Y_DEADZONE = (28660, 33000)
X_MINMAX = (15000, 48000)
Y_MINMAX = (15000, 48000)
TRUNC_VALUE = 100
ALPHA = 0.10

X_MODE = False  # True - strafe mode, False - rotate mode
state_event = asyncio.Event()
mode_lock = asyncio.Lock()
stop_event = asyncio.Event()

PEER_MAC_ADDRESS_STR = main_config.get('peer_mac_address', '00:00:00:00:00:00')
PEER_MAC_ADDRESS = ubinascii.unhexlify(PEER_MAC_ADDRESS_STR.replace(':', ''))

if PEER_MAC_ADDRESS_STR == '00:00:00:00:00:00':
    print("WARNING: peer_mac_address not set in config.json — ESP-NOW will fail")

WIFI_CHANNEL = 11


# ADC reader with exponential moving average smoothing and button-press detection.
# A reading of 65535 is treated as a button press rather than a valid axis value.
# num_samples: raw reads averaged per call to reduce ADC noise.
# alpha: EMA weight for the new sample (lower = smoother, more lag).
class DebouncedADC:
    def __init__(self, adc_pin, num_samples=50, alpha=ALPHA):
        self.adc = ADC(Pin(adc_pin))
        self.alpha = alpha
        self.num_samples = num_samples
        self.button_pressed = False
        self._last_value = None

    def read(self):
        self.button_pressed = False
        samples = [self.adc.read_u16() for _ in range(self.num_samples)]
        if 65535 in samples:
            self.button_pressed = True
            state_event.set()
            return 65535
        new_value = sum(samples) // self.num_samples
        if self._last_value is None:
            self._last_value = new_value
        value = self.alpha * new_value + (1 - self.alpha) * self._last_value
        self._last_value = value
        return value


# Map value from [in_min, in_max] to [-1, 1] with a dead band around centre.
# Values inside [dz_min, dz_max] return 0; outside are linearly interpolated.
def rescale_with_deadzone(value, in_min, in_max, dz_min, dz_max):
    if dz_min <= value <= dz_max:
        return 0.0

    elif value < dz_min:
        if dz_min == in_min:
            return -1.0 if value <= in_min else 0.0
        return -1 + (value - in_min) * (0 - -1) / (dz_min - in_min)

    else:  # value > dz_max
        if in_max == dz_max:
            return 1.0 if value >= in_max else 0.0
        return 0 + (value - dz_max) * (1 - 0) / (in_max - dz_max)


# Rescale value to [-1, 1] with deadzone, then quantize to the nearest 0.05
# step. Quantization reduces redundant ESP-NOW transmissions by preventing
# tiny ADC fluctuations from producing unique values on every read.
def normalize_value(value, amin, amax, dmin, dmax):
    if (value > dmin) and (value < dmax):
        return 0
    else:
        q = rescale_with_deadzone(value, amin, amax, dmin, dmax) * TRUNC_VALUE

        if q < 0:
            q = math.floor(q) / TRUNC_VALUE
            if q < -1:
                q = -1
            negative = True
        else:
            q = math.ceil(q) / TRUNC_VALUE
            if q > 1:
                q = 1
            negative = False

        # Quantize to nearest 0.05 step to reduce jitter in transmitted values
        r = math.trunc(abs(q * TRUNC_VALUE))
        unit = r % 10
        if unit <= 5:
            unit = 5
            tens = 0
        else:
            unit = 0
            tens = 10
        r = (r // 10) * 10 + tens + unit
        if r > TRUNC_VALUE:
            r = TRUNC_VALUE
        q = r / TRUNC_VALUE
        if negative:
            return -q
        else:
            return q


# Poll the boot button (GPIO0); set stop_event when pressed to trigger shutdown.
async def monitor_button(button_pin=0):
    print("Monitoring boot button...")
    boot_button_pin = Pin(button_pin, Pin.IN, Pin.PULL_UP)
    while True:
        if boot_button_pin.value() == 0:
            print("Boot button pressed, setting stop event.")
            stop_event.set()
            break
        # noinspection PyUnresolvedReferences
        await asyncio.sleep_ms(50)  # debounce and yield to other tasks
    print("Monitoring button stopped.")


# Blink the LED to indicate current drive mode:
#   short on / long off  ->  rotate mode (X_MODE=False)
#   50/50 duty           ->  strafe mode (X_MODE=True)
# Toggles X_MODE when state_event is set (joystick button press).
async def blink_led(led_pin=2, delay_ms=250):
    global X_MODE
    led = Pin(led_pin, Pin.OUT)
    while not stop_event.is_set():
        if state_event.is_set():
            async with mode_lock:
                X_MODE = not X_MODE
            state_event.clear()
        async with mode_lock:
            current_mode = X_MODE
        if current_mode:
            off_delay_ms = delay_ms - delay_ms // 2
        else:
            off_delay_ms = delay_ms - 10
        led.value(1)
        await asyncio.sleep_ms(delay_ms - off_delay_ms)
        led.value(0)
        await asyncio.sleep_ms(off_delay_ms)
    led.value(0)


# Read joystick axes at 100 Hz, normalize, and transmit drive commands over
# ESP-NOW. Only sends when the value changes by more than th_delta to avoid
# flooding the receiver. Dynamically tracks min/max to calibrate the range.
async def read_joystick_task(e: aioespnow.AIOESPNow, x_adc: DebouncedADC, y_adc: DebouncedADC):
    global X_MODE

    print("Starting joystick reader task...")
    x_min, x_max = X_MINMAX
    y_min, y_max = Y_MINMAX

    last_x = 0
    last_y = 0
    # Discard first few readings while ADC stabilizes
    skip = 5
    while not stop_event.is_set():
        th_delta = 2 / TRUNC_VALUE
        x_value = x_adc.read()
        y_value = y_adc.read()

        button_pressed = x_adc.button_pressed or y_adc.button_pressed
        if button_pressed:
            await asyncio.sleep_ms(200)
            continue
        if x_value != 65535:
            x_max = (max(x_max, x_value) + x_max) // 2
        x_min = (min(x_min, x_value) + x_min) // 2

        if x_value != 65535:
            y_max = (max(y_max, y_value) + y_max) // 2
        y_min = (min(y_min, y_value) + y_min) // 2

        x = -normalize_value(x_value, x_min, x_max, *X_DEADZONE)
        y = normalize_value(y_value, y_min, y_max, *Y_DEADZONE)

        xdelta = abs(x - last_x)
        ydelta = abs(y - last_y)
        if (x == 0.0 and y == 0.0) and (x != last_x or y != last_y):
            xdelta = TRUNC_VALUE

        if skip:
            skip -= 1
            await asyncio.sleep_ms(10)
            continue

        if (xdelta > th_delta) or (ydelta > th_delta):
            last_x = x
            last_y = y
            async with mode_lock:
                if X_MODE:
                    mode = "strafe"
                else:
                    mode = "rotate"

            print(f"X: {x:9.5f} ({x_value:5} {x_min:5}, {x_max:5}), Y: {y:9.5f} "
                  f"({y_value:5} {y_min:5}, {y_max:5}) Mode: {mode}")
            data = {
                "throttle": y,
                "strafe": 0.0,
                "rotate": 0.0,
            }
            if mode == "strafe":
                data["strafe"] = x
            else:
                data["rotate"] = x
            msg = json.dumps(data)
            if await e.asend(PEER_MAC_ADDRESS, msg.encode()):
                print(f"Sent: {msg}")
            else:
                print(f"Failed to send data: {msg}")
        await asyncio.sleep_ms(10)  # Read every 10 milliseconds


# Initialise the Wi-Fi interface in station mode and set up ESP-NOW.
# Raises OSError if ESP-NOW cannot be activated or the peer cannot be added.
def setup_espnow():
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


# Start ESP-NOW and launch all async tasks; wait for stop_event then clean up.
async def main():
    print("Main program starting...")
    try:
        esp_now_instance = setup_espnow()
    except OSError as err:
        print(f"Fatal: could not initialize ESP-NOW: {err}")
        return

    x_adc = DebouncedADC(main_config.get('x_pin', 33))
    y_adc = DebouncedADC(main_config.get('y_pin', 32))
    tasks = [
        asyncio.create_task(read_joystick_task(esp_now_instance, x_adc, y_adc)),
        asyncio.create_task(blink_led()),
        asyncio.create_task(monitor_button()),
    ]

    await stop_event.wait()

    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    esp_now_instance.active(False)


try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("Program terminated by user.")
except SystemExit:
    print("Program terminated.")
finally:
    asyncio.new_event_loop()
    start_webrepl()
