"""Actual run-loop failure boundaries; all hardware transports are test-only."""
import math,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from test_mixed_drive import data,load
from microduck_rk import __main__ as cli
from microduck_rk.motion_context import MotionContextGuard,live_context_reader
from microduck_rk.motion_limits import limits_sha256
from microduck_rk.actuators import ROBOT_PROFILE
from microduck_interaction.executor import Arbiter,Executor,atomic_json

class RuntimeContextFailureTests(unittest.TestCase):
 def run_case(self,mode='head_home_locked',fault=None):
  events=[];targets=[];state={'armed':False,'reads':0};cal=load(data(),motion=True)
  class Clock:
   t=100.
   def monotonic(s):return s.t
   def sleep(s,v):s.t+=v
  clock=Clock()
  class Motors:
   def __init__(s,*a):pass
   def verify(s):pass
   def prepare_enable(s):
    if fault=='slow_prepare':clock.sleep(.15)
    events.append('prepared')
    state['prepared_at']=clock.monotonic()
   def read(s):
    clock.sleep(.001) # A completed transport read has a later receipt timestamp.
    if state['armed']:state['reads']+=1
    q=cal.home[:];dq=[0.]*15
    if state['armed']and state['reads']>=2:
     if fault=='head':q[5]+=.01
     if fault=='mouth':q[9]+=.01
     if fault=='leg':q[0]+=.01
     if mode=='supported_double'and fault is None:q[5]+=.02;dq[5]=.2
    return {'positions':q,'velocities':dq,'current_ma':[0.]*15,'volts':[10.8]*15,'temps':[25.]*15}
   def enable(s,q,check_ready=None):
    if check_ready:check_ready()
    state['armed']=True;events.append('torque_on')
    if fault=='slow_prepare':assert clock.monotonic()-state['prepared_at']>=.5
   def check_health(s):pass
   def write(s,q):targets.append(q[:]);events.append('write')
   def torque_off(s):events.append('torque_off');return []
   def close(s):events.append('motors_close')
  class Power:
   def __init__(s,*a):pass
   def start(s):pass
   def enable(s):events.append('run_high')
   def activate_control(s):
    if fault=='slow_prepare':assert state['armed'],'control heartbeat began before bounded torque enable'
    events.append('control_active')
   def check(s):
    if fault=='run_lost'and state['armed']and state['reads']>=2:raise RuntimeError('RUN_OK hardware permission lost')
    return {'state':'ON'}
   def close(s):events.append('run_low')
  class Bus:
   def __init__(s,*a):pass
   def close(s):pass
  class Imu:
   def __init__(s,*a):pass
   def start(s):pass
   def wait_ready(s):pass
   def read(s):
    gravity=[0.,0.,-1.]
    if fault=='tilt'and state['armed']and state['reads']>=1:gravity=[math.sin(math.radians(6)),0.,-math.cos(math.radians(6))]
    return {'gyro':[0.,0.,0.],'gravity':gravity,'age_s':0.,'quat':[1.,0.,0.,0.]}
   def close(s):pass
  class Policy:
   def __init__(s,*a):pass
   def benchmark(s):return {'p99_ms':0.}
   def run(s,obs):
    if fault=='interrupt'and state['reads']>=2:raise KeyboardInterrupt('test signal')
    if fault=='slow_policy':clock.sleep(.021)
    return [.1]*14
  def command(_):
   c=[0.]*13;mouth=0.
   if mode=='supported_double':c[3]=.02;mouth=.1
   stamp=clock.monotonic()-(.301 if fault=='lease'and state['armed']and state['reads']>=2 else 0.)
   return c,mouth,stamp
  with tempfile.TemporaryDirectory()as td:
   a=SimpleNamespace(stop_file=td+'/STOP',seconds=.045,calibration='c',robot_profile=cal.data['robot'],arm=True,policy='p',manifest='m',power_config='pc',i2c='/dev/test',address=0x6a,serial='s',command='cmd',telemetry=td+'/state.json',log=td+'/log',motion_context=mode,confirm_supported_double=mode=='supported_double')
   error=None
   original_publish=cli.publish_telemetry
   def publish(*a,**kw):
    original_publish(*a,**kw)
    if fault=='stale_prearm'and not state['armed']and kw.get('motion_context',{}).get('ready'):clock.sleep(.101)
   with patch.object(cli,'publish_telemetry',side_effect=publish),patch('microduck_rk.power.PowerConfig.load',return_value=SimpleNamespace(sha256=cal.data['power_configuration_sha256'],data={'i2c_device':'/dev/test'})),patch('microduck_rk.power.PowerSystem',Power),patch.object(cli.Calibration,'load',return_value=cal),patch('microduck_rk.policy.Policy',Policy),patch('microduck_rk.dynamixel.Dynamixels',Motors),patch('microduck_rk.imu.LinuxI2c',Bus),patch('microduck_rk.imu.Lsm6dsv16x',lambda *a:None),patch('microduck_rk.imu.ImuWorker',Imu),patch.object(cli,'read_command',side_effect=command),patch.object(cli.signal,'signal'),patch.object(cli,'time',clock):
    try:cli.run(a)
    except (RuntimeError,ValueError,KeyboardInterrupt)as exc:error=exc
   import json
   telemetry=json.loads(Path(a.telemetry).read_text())
  return events,targets,error,telemetry
 def test_stale_final_prearm_telemetry_cannot_enable_torque(self):
  e,t,err,telemetry=self.run_case(fault='stale_prearm')
  self.assertIsInstance(err,RuntimeError);self.assertIn('stale',str(err))
  self.assertNotIn('torque_on',e);self.assertIn('run_low',e)
 def test_slow_configuration_precedes_the_measured_stability_window(self):
  e,t,err,telemetry=self.run_case(fault='slow_prepare')
  self.assertIsNone(err);self.assertLess(e.index('prepared'),e.index('torque_on'));self.assertLess(e.index('torque_on'),e.index('control_active'))
 def stopped(self,mode,fault,pattern):
  e,t,err,telemetry=self.run_case(mode,fault)
  self.assertIsInstance(err,RuntimeError);self.assertIn(pattern,str(err));self.assertEqual(len(t),1)
  self.assertLess(e.index('run_low'),e.index('torque_off'))
  self.assertFalse(telemetry['armed']);self.assertFalse(telemetry['motion_context']['ready'])
 def test_actual_armed_head_or_mouth_displacement_stops_before_next_write(self):
  for fault in ['head','mouth']:
   with self.subTest(fault=fault):self.stopped('head_home_locked',fault,'posture/velocity')
 def test_actual_supported_mode_allows_head_motion_but_masks_all_ten_legs(self):
  e,t,err,telemetry=self.run_case('supported_double')
  self.assertIsNone(err);self.assertGreaterEqual(len(t),2)
  for q in t:
   self.assertEqual(q[:5]+q[10:],[0.]*10)
   for v in q[5:9]:self.assertAlmostEqual(v,.01)
  self.assertGreater(t[0][9],0.);self.assertFalse(telemetry['armed'])
 def test_actual_supported_leg_displacement_stops_before_next_write(self):self.stopped('supported_double','leg','posture/velocity')
 def test_actual_supported_trunk_tilt_stops_before_next_write(self):self.stopped('supported_double','tilt','posture/velocity')
 def test_actual_RUN_permission_loss_exits_and_revokes_final_telemetry(self):self.stopped('head_home_locked','run_lost','RUN_OK')
 def test_actual_command_expiry_does_not_renew_zero_lease(self):self.stopped('head_home_locked','lease','lease expired')
 def test_actual_interrupt_cuts_RUN_before_motor_cleanup(self):
  e,t,err,telemetry=self.run_case(fault='interrupt');self.assertIsInstance(err,KeyboardInterrupt)
  self.assertEqual(len(t),1);self.assertLess(e.index('run_low'),e.index('torque_off'));self.assertFalse(telemetry['armed'])
 def test_actual_late_policy_result_never_reaches_servo_write(self):
  e,t,err,telemetry=self.run_case(fault='slow_policy');self.assertIsInstance(err,RuntimeError)
  self.assertIn('missed 20ms deadline',str(err));self.assertEqual(t,[]);self.assertFalse(telemetry['armed'])
 def test_preflight_motion_resets_the_full_stability_window(self):
  g=MotionContextGuard([0.]*15)
  for i in range(25):g.observe([0.]*15,[0.]*15,[0]*3,[0,0,-1],i*.02,i*.02,0.)
  q=[0.]*15;q[9]=.01;g.observe(q,[0.]*15,[0]*3,[0,0,-1],.50,.50,0.)
  for i in range(25):self.assertFalse(g.observe([0.]*15,[0.]*15,[0]*3,[0,0,-1],.52+i*.02,.52+i*.02,0.))
  self.assertTrue(g.observe([0.]*15,[0.]*15,[0]*3,[0,0,-1],1.02,1.02,0.))
 def test_running_audio_and_command_lease_stop_when_actual_context_is_revoked(self):
  class Audio:
   duration=.5;error=None;playing=False;cancelled=False
   def start(s):s.playing=True
   def alive(s,now):return s.playing
   def level(s,now):return .5 if s.playing else 0.
   def cancel(s):s.playing=False;s.cancelled=True
  with tempfile.TemporaryDirectory()as td:
   statepath=Path(td)/'state.json';logpath=Path(td)/'dry.jsonl'
   state={'source':'live_dynamixel_sflp','robot_profile':ROBOT_PROFILE,'calibration_sha256':'c','motion_limits_sha256':limits_sha256(),'monotonic_s':time.monotonic(),'armed':True,'motion_context':{'mode':'supported_double','ready':True,'head_home_stable':True}}
   atomic_json(statepath,state);a=Arbiter(context_check=live_context_reader(statepath,'c'));sid=a.start_session('test',3.)['session_id'];audio=Audio();a.attach_audio(sid,0,audio)
   ex=Executor(a,str(Path(td)/'cmd'),dry_run=True,dry_log=str(logpath))
   try:
    ex.start();end=time.monotonic()+.2
    while not logpath.read_text()and time.monotonic()<end:time.sleep(.005)
    self.assertTrue(logpath.read_text());state['armed']=False;state['monotonic_s']=time.monotonic();atomic_json(statepath,state)
    ex.thread.join(timeout=.3);self.assertFalse(ex.thread.is_alive());self.assertIsInstance(ex.error,ValueError)
    self.assertTrue(audio.cancelled);self.assertIsNone(a.session)
   finally:ex.close()

if __name__=='__main__':unittest.main()
