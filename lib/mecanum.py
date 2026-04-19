import json
import os

from dcmotor import DCMotor


class MecanumDrive:
    def __init__(self, input_scale=0.5):
        self.fl = None
        self.fr = None
        self.rl = None
        self.rr = None
        self.input_scale = input_scale

    def setup_motors(self, cfg: dict):
        for key in ('fl', 'fr', 'rl', 'rr'):
            if key in cfg:
                m = DCMotor(**cfg[key])
                setattr(self, key, m)

    def load_cfg(self):
        try:
            with open('mecanum.json') as f:
                data = json.loads(f.read())
        except OSError:
            print("can not find mecanum.json")
            return False
        self.setup_motors(data)
        return True

    def stop(self):
        self.fl.stop()
        self.fr.stop()
        self.rl.stop()
        self.rr.stop()

    def drive(self, throttle, strafe, rotate):
        #  throttle, strafe, and rotate are in the range of -1..1
        assert 1 >= throttle >= -1, f"Invalid throttle value {throttle}"
        assert 1 >= strafe >= -1, f"Invalid strafe value {strafe}"
        assert 1 >= rotate >= -1, f"Invalid rotate value {rotate}"

        if throttle == 0 and strafe == 0 and rotate == 0:
            self.stop()
            return

        throttle *= self.input_scale
        strafe *= self.input_scale
        rotate *= self.input_scale

        fl = throttle + strafe + rotate
        fr = throttle - strafe - rotate
        rl = throttle - strafe + rotate
        rr = throttle + strafe - rotate

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
        return {
            'fl': self.fl.asdict(),
            'fr': self.fr.asdict(),
            'rl': self.rl.asdict(),
            'rr': self.rr.asdict(),
        }

    def json(self) -> str:
        return json.dumps(self.asdict())
