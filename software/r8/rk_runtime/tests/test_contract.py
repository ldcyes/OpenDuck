import math
import struct
import unittest
from pathlib import Path
import importlib.util


class ImplementationExists(unittest.TestCase):
    def test_rk_adapter_exists(self):
        self.assertIsNotNone(importlib.util.find_spec('microduck_rk.contract'),
                             'RK observation/calibration adapter must be implemented')


if importlib.util.find_spec('microduck_rk.contract'):
    from microduck_rk.contract import JOINT_NAMES, HOME, observation, action_targets, Calibration
    from microduck_rk.imu import decode_quat, rotate, ImuStream, ImuFault, Lsm6dsv16x

    class ContractTests(unittest.TestCase):
        def test_slots_mouth_and_units(self):
            q = [h + i / 100 for i, h in enumerate(HOME)]
            out = observation([1, 2, 3], [0, 0, -1], q, list(range(15)), list(range(14)), list(range(13)))
            self.assertEqual(len(out), 61)
            self.assertEqual(out[:6], [1, 2, 3, 0, 0, -1])
            self.assertAlmostEqual(out[15], .10)
            self.assertEqual(out[29], 10)
            self.assertEqual(out[34:48], list(range(14)))
            self.assertEqual(out[48:], list(range(13)))
            q[9] += 2
            self.assertEqual(out, observation([1,2,3], [0,0,-1], q, list(range(15)), list(range(14)), list(range(13))))

        def test_action_order_and_mouth_independent(self):
            out = action_targets(list(range(14)), .25, HOME, .1)
            self.assertEqual(out[9], .25)
            self.assertAlmostEqual(out[10], HOME[10] + .9)

        def test_template_refuses_motion(self):
            p = Path(__file__).parents[1] / 'config/calibration.template.json'
            with self.assertRaisesRegex(ValueError, 'calibrat'):
                Calibration.load(p, motion=True)

        def test_nonfinite_rejected(self):
            with self.assertRaises(ValueError):
                observation([math.nan,0,0], [0,0,-1], HOME, [0]*15, [0]*14, [0]*13)

    class ImuTests(unittest.TestCase):
        def test_fifo_identity_is_valid_measurement(self):
            # FIFO tag proves provenance: unlike an empty DXL table, xyz=0 is a valid identity quaternion.
            self.assertEqual(decode_quat(bytes(6)), [1.,0.,0.,0.])

        def test_half_precision_and_mount(self):
            q = decode_quat(struct.pack('<eee', 0., math.sqrt(.5), 0.))
            v = rotate(q, [0,0,1])
            self.assertAlmostEqual(v[0], 1, places=5)
            self.assertAlmostEqual(v[2], 0, places=3)

        def test_nan_and_corruption_fail_closed(self):
            for v in [math.nan, math.inf, 1.5]:
                with self.assertRaises(ImuFault):
                    decode_quat(struct.pack('<eee', v,0,0))

        def test_freshness_and_startup_gate(self):
            stream = ImuStream([1,0,0,0], min_samples=3, max_age=.05)
            with self.assertRaises(ImuFault):
                stream.sample(0.)
            for t in [0., .01, .02]:
                stream.push(1, struct.pack('<hhh', 1000,0,0), t)
                stream.push(0x13, bytes(6), t)
            s = stream.sample(.03)
            self.assertAlmostEqual(s['gyro'][0], 1000*.0175*math.pi/180)
            self.assertEqual(s['gravity'], [0,0,-1])
            with self.assertRaises(ImuFault):
                stream.sample(.08)

        def test_same_value_new_fifo_samples_are_fresh(self):
            stream = ImuStream([1,0,0,0], min_samples=1)
            for t in [1.,2.]:
                stream.push(1, bytes(6), t)
                stream.push(0x13, bytes(6), t)
                self.assertEqual(stream.sample(t)['gravity'], [0,0,-1])

        def test_mount_must_be_unit_rotation(self):
            with self.assertRaises(ValueError):
                ImuStream([0,0,0,0])


if __name__ == '__main__':
    unittest.main()
