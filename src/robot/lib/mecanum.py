import json

from dcmotor import DCMotor


class MecanumDrive:
    """Mecanum wheel drive controller.

    Computes per-wheel power from throttle/strafe/rotate inputs and delegates
    to four DCMotor instances (fl, fr, rl, rr). Motors are loaded from
    mecanum.json via load_cfg() or configured programmatically via setup_motors().

    Args:
        input_scale: Multiplier applied to all inputs before computing wheel
            speeds. Values below 1.0 limit max power; default 0.5 gives a
            comfortable mid-range ceiling.
    """

    _MOTOR_KEYS = ('fl', 'fr', 'rl', 'rr')

    def __init__(self, input_scale=0.5):
        self.fl = None
        self.fr = None
        self.rl = None
        self.rr = None
        self.input_scale = input_scale
        self._motors = (None, None, None, None)

    def setup_motors(self, cfg: dict):
        """Instantiate motors from a config dict keyed by position (fl/fr/rl/rr).

        Each value is passed as kwargs to DCMotor, which selects TB6612FNG or
        MX1508 based on the keys present.
        """
        for key in self._MOTOR_KEYS:
            if key in cfg:
                setattr(self, key, DCMotor(**cfg[key]))
        self._motors = (self.fl, self.fr, self.rl, self.rr)

    def load_cfg(self, path='mecanum.json') -> bool:
        """Load motor configuration from a JSON file and call setup_motors().

        Returns True on success, False if the file is missing or unreadable.
        """
        try:
            with open(path) as f:
                data = json.load(f)
        except OSError:
            print(f"cannot find {path}")
            return False
        self.setup_motors(data)
        return True

    def _motors_ready(self) -> bool:
        """Return True if all four motors have been initialised."""
        return all(m is not None for m in self._motors)

    def stop(self):
        """Stop all motors that have been initialised."""
        for motor in self._motors:
            if motor is not None:
                motor.stop()

    def drive(self, throttle: float, strafe: float, rotate: float):
        """Drive the mecanum platform.

        Inputs are clamped to -1..1 then scaled by input_scale before computing
        individual wheel speeds using standard mecanum kinematics. If the
        combined speed of any wheel exceeds 1.0 all wheels are normalised
        proportionally so the ratio is preserved.

        Args:
            throttle: Forward/reverse (-1.0 = full reverse, 1.0 = full forward).
            strafe:   Left/right translation (-1.0 = full left, 1.0 = full right).
            rotate:   Rotation (-1.0 = full CCW, 1.0 = full CW).
        """
        throttle = max(-1.0, min(1.0, float(throttle)))
        strafe = max(-1.0, min(1.0, float(strafe)))
        rotate = max(-1.0, min(1.0, float(rotate)))

        if not self._motors_ready():
            print("Motors not initialized, skipping drive command")
            return

        if throttle == 0 and strafe == 0 and rotate == 0:
            self.stop()
            return

        s = self.input_scale
        fl = (throttle + strafe + rotate) * s
        fr = (throttle - strafe - rotate) * s
        rl = (throttle - strafe + rotate) * s
        rr = (throttle + strafe - rotate) * s

        max_power = max(abs(fl), abs(fr), abs(rl), abs(rr))
        if max_power > 1.0:
            fl /= max_power
            fr /= max_power
            rl /= max_power
            rr /= max_power

        self.fl.drive(fl)
        self.fr.drive(fr)
        self.rl.drive(rl)
        self.rr.drive(rr)

    def asdict(self) -> dict:
        """Return a dict of motor configs suitable for serialisation to mecanum.json.

        Raises RuntimeError if any motor has not been initialised.
        """
        if not self._motors_ready():
            raise RuntimeError("Motors not fully initialized")
        return {k: m.asdict() for k, m in zip(self._MOTOR_KEYS, self._motors)}

    def json(self) -> str:
        """Serialise the motor configuration to a JSON string."""
        return json.dumps(self.asdict())
