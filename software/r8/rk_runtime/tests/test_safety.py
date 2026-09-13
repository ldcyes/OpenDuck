import unittest
import importlib.util
import tempfile
from pathlib import Path
from types import SimpleNamespace

class SafetyAvailable(unittest.TestCase):
    def test_guard_exists(self):
        self.assertIsNotNone(importlib.util.find_spec('microduck_rk.safety'))

if importlib.util.find_spec('microduck_rk.safety'):
    from microduck_rk.safety import Guard,read_command
    class GuardTests(unittest.TestCase):
        def setUp(self):
            self.g=Guard({'voltage_hard':6.7,'voltage_soft':7.0,'temperature_max':60})
        def test_hard_brownout_immediate(self):
            with self.assertRaises(RuntimeError):
                self.g.check(0,[6.7]*15,[30]*15,[0,0,-1],0)
        def test_soft_brownout_debounced(self):
            self.g.check(0,[6.9]*15,[30]*15,[0,0,-1],0)
            self.g.check(.19,[6.9]*15,[30]*15,[0,0,-1],.19)
            with self.assertRaises(RuntimeError):
                self.g.check(.21,[6.9]*15,[30]*15,[0,0,-1],.21)
        def test_temperature_and_fall(self):
            for temp,gravity in [(61,[0,0,-1]),(30,[1,0,0])]:
                with self.assertRaises(RuntimeError):
                    self.g.check(0,[7.4]*15,[temp]*15,gravity,0)
        def test_missing_lease_stops(self):
            with self.assertRaises(RuntimeError):
                self.g.check(1,[7.4]*15,[30]*15,[0,0,-1],.4)

        def test_existing_stop_prevents_any_hardware_startup(self):
            from microduck_rk.__main__ import run
            with tempfile.TemporaryDirectory() as t:
                path=Path(t)/'STOP';path.touch()
                # No calibration/serial attributes: touching hardware setup at all makes this fail.
                with self.assertRaisesRegex(RuntimeError,'STOP'):
                    run(SimpleNamespace(stop_file=str(path)))

        def test_mouth_reaches_requested_opening_gradually(self):
            from microduck_rk import safety
            self.assertTrue(hasattr(safety,'mouth_step'))
            current=0.
            for _ in range(60):
                nxt=safety.mouth_step(.5,current,-.1,.6,.03)
                self.assertLessEqual(abs(nxt-current),.01000001)
                current=nxt
            self.assertAlmostEqual(current,.5)

        def test_mouth_outside_measured_range_refused(self):
            from microduck_rk import safety
            self.assertTrue(hasattr(safety,'mouth_step'))
            with self.assertRaises(ValueError): safety.mouth_step(.7,0,-.1,.6,.03)

        def test_power_group_protection(self):
            from microduck_rk import safety
            self.assertTrue(hasattr(safety,'check_power_groups'))
            safety.check_power_groups([300]*15)
            amps=[0]*15
            for i in [2,3,4]: amps[i]=800  # J6 IDs22,23,24: 2.4A >2A branch target.
            with self.assertRaises(RuntimeError): safety.check_power_groups(amps)

if __name__=='__main__':
    unittest.main()
