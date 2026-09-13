import importlib.util,json,tempfile,unittest
from pathlib import Path
AVAILABLE=importlib.util.find_spec('microduck_rk.telemetry') is not None
class TelemetryAvailability(unittest.TestCase):
    def test_telemetry_module_exists(self):self.assertTrue(AVAILABLE,'measured telemetry is not implemented')
@unittest.skipUnless(AVAILABLE,'pending')
class TelemetryTests(unittest.TestCase):
    def test_real_state_and_original_measurement_time_survive_disarming(self):
        from microduck_rk.telemetry import publish
        sensors={'positions':[.1]*15,'velocities':[.2]*15}
        imu={'gyro':[1.,2.,3.],'gravity':[0.,0.,-1.],'age_s':.015}
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'state.json'
            publish(p,sensors,imu,'digest','profile',True,12.3)
            state=json.loads(p.read_text());self.assertEqual(state['q'],[.1]*15);self.assertEqual(state['dq'],[.2]*15)
            self.assertEqual(state['monotonic_s'],12.3);self.assertEqual(state['source'],'live_dynamixel_sflp')
            self.assertTrue(state['commissioned']);self.assertTrue(state['armed'])
            from microduck_rk.motion_limits import limits_sha256
            self.assertEqual(state['motion_limits_sha256'],limits_sha256())
            publish(p,sensors,imu,'digest','profile',False,12.3)
            state=json.loads(p.read_text());self.assertFalse(state['armed']);self.assertEqual(state['monotonic_s'],12.3)
    def test_nonfinite_measurement_never_published(self):
        from microduck_rk.telemetry import publish
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'state.json'
            with self.assertRaises(ValueError):publish(p,{'positions':[float('nan')]*15,'velocities':[0]*15},{'gyro':[0]*3,'gravity':[0,0,-1],'age_s':0},'d','p',True,1.)
            self.assertFalse(p.exists())
