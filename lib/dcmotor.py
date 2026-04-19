# Created by https://RandomNerdTutorials.com/micropython-esp32-esp8266-dc-motor-l298n/
# This file includes a class to control DC motors
import json
from math import trunc

from machine import Pin, PWM

# the min_duty and max_duty are defined for 15000Hz frequency
FREQUENCY = 15000
MAX_V = int(65535 * 0.8)  # max duty
MIN_V = 41200  # min duty


class DCMotor:
    def __init__(self, pin1: int, pin2: int, enable_pin: int):
        self.gpio_pin1 = pin1
        self.gpio_pin2 = pin2
        self.gpio_enable_pin = enable_pin

        self.pin1 = Pin(self.gpio_pin1, Pin.OUT)
        self.pin2 = Pin(self.gpio_pin2, Pin.OUT)
        self.enable_pin = PWM(Pin(self.gpio_enable_pin), freq=FREQUENCY)
        self.power = 0.0

    def drive(self, power: float):
        if power < -1.0 or power > 1.0:
            power = 0
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
        duty = int(trunc(abs(power) * (MAX_V - MIN_V))) + MIN_V
        print(f"Duty = {duty}")
        self.enable_pin.duty_u16(duty)

    def move(self, duty: int, direction: int):
        if direction:
            print("dir: forward")
            self.pin1.value(1)
            self.pin2.value(0)
        else:
            print("dir: backward")
            self.pin1.value(0)
            self.pin2.value(1)
        if duty == 0:
            self.pin1.value(0)
            self.pin2.value(0)
        print(f"duty: {duty}")
        self.enable_pin.duty_u16(duty)

    def stop(self):
        self.enable_pin.duty_u16(0)
        # self.pin1.value(0)
        # self.pin2.value(0)

    def __str__(self):
        return f"DCMotor [{self.gpio_pin1}:{self.gpio_pin2}+{self.gpio_enable_pin}]"

    def __repr__(self):
        return f"DCMotor(pin1={self.gpio_pin1},pin2={self.gpio_pin2},enable_pin={self.gpio_enable_pin})"

    def asdict(self) -> dict:
        return {
            'pin1': self.gpio_pin1,
            'pin2': self.gpio_pin2,
            'enable_pin': self.gpio_enable_pin,
        }

    def json(self):
        return json.dumps(self.asdict())
