# Created by https://RandomNerdTutorials.com/micropython-esp32-esp8266-dc-motor-l298n/
import json
from math import trunc
from machine import Pin, PWM

# Tuned for 15000Hz; 0.8 cap avoids motor overheating at sustained full load
FREQUENCY = 15000
MAX_V = int(65535 * 0.8)
# Minimum duty to overcome motor stiction at this frequency
MIN_V = 41200

# Safe PWM-capable GPIO ranges on ESP32 (avoid pins tied to flash/PSRAM)
# _SAFE_PWM_RANGES = ((16, 19), (21, 23), (25, 27))
_SAFE_PWM_RANGES = tuple(range(16, 19+1)) + tuple(range(21, 23+1)) + tuple(range(25, 27+1))


def pwr_to_duty(power: float) -> int:
    """Convert a normalised power value (-1..1) to a u16 PWM duty cycle."""
    return int(trunc(abs(power) * (MAX_V - MIN_V))) + MIN_V


def is_pwm_safe(pin: int, print_warning: bool = True) -> bool:
    """Return True if pin is in the ESP32 safe-PWM set, optionally printing a warning."""
    safe = pin in _SAFE_PWM_RANGES
    if not safe and print_warning:
        print(f"WARNING: Pin {pin} may not be safe for PWM.")
    return safe


class _DCMotorBase:
    """Shared interface for DC motor drivers.

    Subclasses must implement drive(), stop(), move(), and asdict().
    json(), __str__, and __repr__ are derived from asdict().
    """

    power: float = 0.0

    def drive(self, power: float):
        """Drive the motor at the given power level (-1.0 to 1.0)."""
        raise NotImplementedError

    def stop(self):
        """Stop the motor immediately."""
        raise NotImplementedError

    def move(self, duty: int, direction: int):
        """Drive at a raw u16 duty cycle in the given direction (1=forward, 0=reverse)."""
        raise NotImplementedError

    def asdict(self) -> dict:
        """Return the constructor arguments as a dict (used for serialisation and repr)."""
        raise NotImplementedError

    def json(self) -> str:
        """Serialise to JSON string."""
        return json.dumps(self.asdict())

    def __repr__(self):
        args = ', '.join(f"{k}={v}" for k, v in self.asdict().items())
        return f"{self.__class__.__name__}({args})"

    def __str__(self):
        pins = ', '.join(str(v) for v in self.asdict().values())
        return f"{self.__class__.__name__} [{pins}]"


class TB6612FNG(_DCMotorBase):
    """DC motor driver for the TB6612FNG (or L298N-style) 3-pin interface.

    Uses two digital direction pins (pin1, pin2) and one PWM enable pin.
    Direction is set by asserting one pin high and the other low;
    speed is controlled by the duty cycle on the enable pin.

    Args:
        pin1: GPIO number for motor input 1 (direction).
        pin2: GPIO number for motor input 2 (direction).
        enable_pin: GPIO number for the PWM enable line.
    """

    def __init__(self, pin1: int, pin2: int, enable_pin: int):
        self.gpio_pin1 = pin1
        self.gpio_pin2 = pin2
        self.gpio_enable_pin = enable_pin
        self.pin1 = Pin(self.gpio_pin1, Pin.OUT)
        self.pin2 = Pin(self.gpio_pin2, Pin.OUT)
        is_pwm_safe(enable_pin)
        self.enable_pin = PWM(Pin(self.gpio_enable_pin), freq=FREQUENCY)
        self.power = 0.0

    def drive(self, power: float):
        """Drive at normalised power (-1.0 = full reverse, 1.0 = full forward)."""
        if power < -1.0 or power > 1.0:
            power = 0.0
        self.power = power
        if power == 0:
            self.pin1.value(0)
            self.pin2.value(0)
            self.enable_pin.duty_u16(0)
            return
        if power < 0.0:
            self.pin1.value(0)
            self.pin2.value(1)
        else:
            self.pin1.value(1)
            self.pin2.value(0)
        self.enable_pin.duty_u16(pwr_to_duty(power))

    def move(self, duty: int, direction: int):
        """Drive at a raw u16 duty cycle. direction=1 forward, direction=0 reverse."""
        if direction:
            self.pin1.value(1)
            self.pin2.value(0)
        else:
            self.pin1.value(0)
            self.pin2.value(1)
        if duty == 0:
            self.pin1.value(0)
            self.pin2.value(0)
        self.enable_pin.duty_u16(duty)

    def stop(self):
        """Stop the motor by cutting PWM duty."""
        self.enable_pin.duty_u16(0)

    def asdict(self) -> dict:
        return {
            'pin1': self.gpio_pin1,
            'pin2': self.gpio_pin2,
            'enable_pin': self.gpio_enable_pin,
        }


class MX1508(_DCMotorBase):
    """DC motor driver for the MX1508 2-pin interface.

    Both pins are PWM-capable. Direction is encoded by which pin carries duty;
    the idle pin is held at zero. Warns if either pin is not in the ESP32
    safe-PWM set.

    Args:
        pin_in1: GPIO number for motor input 1 (must support PWM).
        pin_in2: GPIO number for motor input 2 (must support PWM).
    """

    def __init__(self, pin_in1: int, pin_in2: int):
        is_pwm_safe(pin_in1)
        is_pwm_safe(pin_in2)
        self.gpio_pin1 = pin_in1
        self.gpio_pin2 = pin_in2
        self.pin1 = PWM(Pin(self.gpio_pin1), freq=FREQUENCY)
        self.pin2 = PWM(Pin(self.gpio_pin2), freq=FREQUENCY)
        self.power = 0.0
        self.stop()

    def stop(self):
        """Stop the motor by zeroing both PWM pins."""
        self.pin1.duty_u16(0)
        self.pin2.duty_u16(0)
        self.power = 0.0

    def drive(self, power: float):
        """Drive at normalised power (-1.0 = full reverse, 1.0 = full forward)."""
        if power < -1.0 or power > 1.0:
            power = 0.0
        self.power = power
        if power == 0:
            self.pin1.duty_u16(0)
            self.pin2.duty_u16(0)
            return
        if power < 0.0:
            self.pin1.duty_u16(pwr_to_duty(power))
            self.pin2.duty_u16(0)
        else:
            self.pin1.duty_u16(0)
            self.pin2.duty_u16(pwr_to_duty(power))

    def move(self, duty: int, direction: int):
        """Drive at a raw u16 duty cycle. direction=1 forward, direction=0 reverse."""
        if duty == 0:
            self.stop()
            return
        if direction:
            self.pin1.duty_u16(duty)
            self.pin2.duty_u16(0)
        else:
            self.pin1.duty_u16(0)
            self.pin2.duty_u16(duty)

    def asdict(self) -> dict:
        return {
            'pin1': self.gpio_pin1,
            'pin2': self.gpio_pin2,
        }


class DCMotor:
    """Factory that returns the correct motor driver based on the pins provided.

    Pass two pins for an MX1508 (both PWM); pass three for a TB6612FNG
    (two direction pins + one PWM enable). The returned object is a
    _DCMotorBase subclass and supports drive(), stop(), move(), asdict(),
    and json().

    Usage:
        DCMotor(pin1, pin2)              ->  MX1508
        DCMotor(pin1, pin2, enable_pin)  ->  TB6612FNG
    """

    def __new__(cls, pin1: int, pin2: int, enable_pin: int = None) -> _DCMotorBase:
        if enable_pin is not None:
            return TB6612FNG(pin1, pin2, enable_pin)
        return MX1508(pin1, pin2)
