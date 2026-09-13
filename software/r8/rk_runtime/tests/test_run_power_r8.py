"""Runs the actual top-level loop with test-only transport boundaries."""
import json,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from test_mixed_drive import data,load
from microduck_rk import __main__ as cli
class RunPowerTests(unittest.TestCase):
    def execute(self,fail=None,cleanup_fail=False,raw_actions=None,command_head=0.):
        events=[];cal=load(data());cal.data['power_configuration_sha256']='p'*64
        class Motors:
            def __init__(s,*a):events.append('motors_open')
            def verify(s):events.append('verify')
            def prepare_enable(s):events.append('prepare_enable')
            def read(s):return {'positions':[0.]*15,'velocities':[0.]*15,'current_ma':[0.]*15,'volts':[10.8]*15,'temps':[25]*15}
            def enable(s,q,check_ready=None):
                if check_ready:check_ready()
                events.append('torque_on')
            def check_health(s):pass
            def write(s,q):
                events.append('write')
                if raw_actions is not None:events.append(('target',q[:]))
            def torque_off(s):events.append('torque_off');return []
            def close(s):events.append('motors_close')
        class Power:
            def __init__(s,c):events.append('power_open')
            def start(s):events.append('power_start')
            def enable(s):events.append('power_enable')
            def activate_control(s):events.append('control_heartbeat')
            def check(s):events.append('power_check');return {'state':'ON'}
            def close(s):
                events.append('power_off')
                if cleanup_fail:raise RuntimeError('gate write failure')
        class Bus:
            def __init__(s,*a):pass
            def close(s):pass
        class Imu:
            def __init__(s,*a):pass
            def start(s):pass
            def wait_ready(s):pass
            def read(s):return {'gyro':[0,0,0],'gravity':[0,0,-1],'age_s':0.,'quat':[1,0,0,0]}
            def close(s):pass
        class Policy:
            def __init__(s,*a):pass
            def benchmark(s):return {'p99_ms':0.}
            def run(s,obs):
                if fail:raise RuntimeError(fail)
                if raw_actions is not None:events.append(('observation',obs[:]));return raw_actions[:]
                return [0.]*14
        with tempfile.TemporaryDirectory() as td:
            a=SimpleNamespace(stop_file=td+'/STOP',calibration='cal',robot_profile=cal.data['robot'],arm=True,policy='p',manifest='m',i2c='/dev/test',address=0x6a,serial='s',command='c',seconds=.045 if raw_actions is not None else .001,telemetry=None,log=td+'/log',power_config='power.json')
            with patch('microduck_rk.power.PowerConfig.load',return_value=SimpleNamespace(sha256='p'*64,data={'i2c_device':'/dev/test'})),patch('microduck_rk.power.PowerSystem',Power),patch.object(cli.Calibration,'load',return_value=cal),patch('microduck_rk.policy.Policy',Policy),patch('microduck_rk.dynamixel.Dynamixels',Motors),patch('microduck_rk.imu.LinuxI2c',Bus),patch('microduck_rk.imu.Lsm6dsv16x',lambda *a:None),patch('microduck_rk.imu.ImuWorker',Imu),patch.object(cli,'read_command',side_effect=lambda p:([0.]*3+[command_head]+[0.]*9,0.,time.monotonic())),patch.object(cli.signal,'signal'):
                if command_head:
                    with self.assertRaisesRegex(ValueError,'head-home'):cli.run(a)
                elif fail or cleanup_fail:
                    with self.assertRaisesRegex(RuntimeError,fail or 'gate write failure'):cli.run(a)
                else:cli.run(a)
        return events
    def test_actual_run_masks_head_targets_but_keeps_raw_previous_action_observation(self):
        raw=[.1]*14;e=self.execute(raw_actions=raw)
        targets=[x[1]for x in e if isinstance(x,tuple)and x[0]=='target']
        obs=[x[1]for x in e if isinstance(x,tuple)and x[0]=='observation']
        self.assertGreaterEqual(len(targets),2)
        self.assertEqual(targets[0][5:10],[0.]*5)
        self.assertAlmostEqual(targets[0][0],.01)
        self.assertEqual(obs[1][34:48],raw)
    def test_actual_run_head_command_refused_before_torque_enable(self):
        e=self.execute(command_head=.01);self.assertNotIn('torque_on',e);self.assertNotIn('write',e);self.assertIn('power_off',e)

    def test_invalid_run_duration_refused_before_any_hardware(self):
        for seconds in [float('nan'),float('inf'),0,-1]:
            with tempfile.TemporaryDirectory() as td,patch('microduck_rk.power.PowerSystem') as factory:
                with self.assertRaises(ValueError):cli.run(SimpleNamespace(stop_file=td+'/STOP',seconds=seconds))
                factory.assert_not_called()
    def test_actual_first_cycle_executes_and_checks_power_before_write(self):
        e=self.execute();self.assertIn('write',e);self.assertIn('power_enable',e);self.assertLess(e.index('power_enable'),e.index('torque_on'));self.assertLess(e.index('power_check'),e.index('write'));self.assertIn('power_off',e)
    def test_failed_gate_shutdown_still_cleans_motors_and_does_not_report_success(self):
        e=self.execute(cleanup_fail=True);self.assertIn('motors_close',e)
    def test_policy_failure_cuts_power_before_motor_cleanup(self):
        e=self.execute('policy failed');self.assertNotIn('write',e);self.assertIn('power_off',e);self.assertLess(e.index('power_off'),e.index('torque_off'))

    def test_powered_commission_uses_supervisor_and_cleans_on_failure(self):
        self.assertTrue(hasattr(cli,'powered_servo_command'),'commission actual supply lifecycle missing')
        events=[]
        class P:
            def __init__(s,*a):events.append('open')
            def start(s):events.append('start')
            def enable(s):events.append('supply_on')
            def check(s):return {}
            def close(s):events.append('supply_off')
        class M:
            def __init__(s,*a):pass
            def commission(s):events.append('commission');raise RuntimeError('EEPROM write failure')
            def torque_off(s):events.append('torque_off')
            def close(s):events.append('close')
        a=SimpleNamespace(power_config='p',calibration='c',serial='s',mode='commission')
        with patch('microduck_rk.power.PowerConfig.load',return_value=SimpleNamespace()),patch('microduck_rk.power.PowerSystem',P),patch.object(cli.Calibration,'load',return_value=load(data())),patch('microduck_rk.dynamixel.Dynamixels',M):
            with self.assertRaisesRegex(RuntimeError,'EEPROM'):cli.powered_servo_command(a)
        self.assertLess(events.index('supply_on'),events.index('commission'));self.assertIn('supply_off',events)

    def test_bench_capture_refuses_missing_disconnect_confirmation_or_long_duration(self):
        self.assertTrue(hasattr(cli,'bench_power_capture'),'bounded isolated-load calibration path missing')
        for confirm,seconds in [(False,1),(True,6),(True,float('nan'))]:
            with self.subTest(confirm=confirm,seconds=seconds),patch('microduck_rk.power.PowerSystem') as factory:
                with self.assertRaises(ValueError):cli.bench_power_capture(SimpleNamespace(confirm_servos_disconnected=confirm,seconds=seconds,i2c='/dev/test',stop_file='/tmp/not-present-test'))
                factory.assert_not_called()
    def test_bench_capture_never_touches_dynamixel_and_closes_on_load_limit(self):
        self.assertTrue(hasattr(cli,'bench_power_capture'))
        events=[]
        class P:
            def __init__(s,c):self.assertFalse(c.data['measurements_verified'])
            def start(s):pass
            def enable(s):events.append('on')
            def activate_control(s):pass
            def check(s):return {'power':{'servo':{'current_A':5.1}}}
            def close(s):events.append('off')
        with tempfile.TemporaryDirectory() as td,patch('microduck_rk.power.PowerSystem',P),patch('microduck_rk.dynamixel.Dynamixels',side_effect=AssertionError('bench must not access motors')):
            with self.assertRaisesRegex(RuntimeError,'5A'):cli.bench_power_capture(SimpleNamespace(confirm_servos_disconnected=True,seconds=1.,i2c='/dev/test',stop_file=td+'/STOP'))
        self.assertEqual(events,['on','off'])
if __name__=='__main__':unittest.main()


