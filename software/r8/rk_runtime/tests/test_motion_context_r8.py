import copy,json,math,tempfile,unittest
from pathlib import Path
from microduck_rk.motion_context import MotionContextGuard,validate_live_frame
from microduck_rk.motion_limits import limits_sha256
from microduck_interaction.schema import ROBOT_PROFILE
from microduck_interaction.executor import Arbiter
class ContextTests(unittest.TestCase):
 def samples(self,g,start=0):
  for i in range(27):g.observe([0.]*15,[0.]*15,[0.,0.,0.],[0.,0.,-1.],start+i*.02,start+i*.02,0.)
 def test_measured_stable_window_required_and_restarted_by_motion(self):
  g=MotionContextGuard([0.]*15);self.assertFalse(g.observe([0.]*15,[0.]*15,[0]*3,[0,0,-1],0.,0.,0.));self.samples(g,.02);self.assertTrue(g.ready)
  g.activate();q=[0.]*15;q[5]=math.radians(.6)
  with self.assertRaises(RuntimeError):g.observe(q,[0.]*15,[0]*3,[0,0,-1],.58,.58,0.)
 def test_velocity_not_target_or_position_alone_controls_ready(self):
  g=MotionContextGuard([0.]*15);dq=[0.]*15;dq[7]=.031
  for i in range(30):self.assertFalse(g.observe([0.]*15,dq,[0]*3,[0,0,-1],i*.02,i*.02,0.))
 def test_stale_duplicate_future_or_missing_actual_rejected(self):
  for mt,now in [(0.,.101),(1.,0.),(float('nan'),0.)]:
   with self.assertRaises((ValueError,RuntimeError)):MotionContextGuard([0.]*15).observe([0.]*15,[0.]*15,[0]*3,[0,0,-1],mt,now,0.)
  g=MotionContextGuard([0.]*15);self.samples(g)
  with self.assertRaises(RuntimeError):g.observe([0.]*15,[0.]*15,[0]*3,[0,0,-1],.52,.54,0.)
 def test_locked_mode_rejects_head_mouth_commands_and_masks_policy_outputs(self):
  g=MotionContextGuard([0.]*15);self.samples(g);g.activate()
  for i in range(3,7):
   c=[0.]*13;c[i]=.01
   with self.assertRaises(ValueError):g.validate_commands(c,0.)
  with self.assertRaises(ValueError):g.validate_commands([0.]*13,.01)
  a,m=g.filter_actions([1.]*14,.1);self.assertEqual(a[5:9],[0.]*4);self.assertEqual(m,0.);self.assertEqual(a[:5],[1.]*5)
 def test_supported_double_requires_confirmation_and_holds_legs(self):
  with self.assertRaises(ValueError):MotionContextGuard([0.]*15,'supported_double')
  g=MotionContextGuard([0.]*15,'supported_double',True);self.samples(g);g.activate()
  c=[0.]*13;c[3]=math.radians(5);g.validate_commands(c,.1)
  c[0]=.001
  with self.assertRaises(ValueError):g.validate_commands(c,0.)
  a,m=g.filter_actions([1.]*14,.1);self.assertEqual(a[:5]+a[9:],[0.]*10);self.assertEqual(a[5:9],[1.]*4)
  q=[0.]*15;q[0]=.02
  with self.assertRaises(RuntimeError):g.observe(q,[0.]*15,[0]*3,[0,0,-1],.54,.54,0.)
 def test_live_state_binds_calibration_age_profile_and_context(self):
  state={'source':'live_dynamixel_sflp','robot_profile':ROBOT_PROFILE,'calibration_sha256':'c','motion_limits_sha256':limits_sha256(),'monotonic_s':1.,'armed':True,'motion_context':{'mode':'head_home_locked','ready':True,'head_home_stable':True}}
  frame={'commands':[.01]+[0.]*12,'mouth_rad':0.}
  validate_live_frame(frame,state,'c',1.05)
  for key,val in [('armed',False),('monotonic_s',.8),('source','simulated'),('calibration_sha256','bad'),('motion_limits_sha256','old')]:
   bad=copy.deepcopy(state);bad[key]=val
   with self.assertRaises(ValueError):validate_live_frame(frame,bad,'c',1.05)
  frame['commands'][3]=.01
  with self.assertRaises(ValueError):validate_live_frame(frame,state,'c',1.05)
 def test_context_rejection_preserves_sequence_and_stops_audio_before_start(self):
  def reject(f):raise ValueError('head lock')
  a=Arbiter(context_check=reject,clock=lambda:1.);sid=a.start_session('test')['session_id']
  with self.assertRaises(ValueError):a.submit(sid,1,ROBOT_PROFILE,{'duration_s':.2})
  self.assertEqual(a.session['sequence'],-1)
  class Audio:
   duration=.1
   def start(self):raise AssertionError('must reject before playback')
  with self.assertRaises(ValueError):a.attach_audio(sid,1,Audio())
  self.assertEqual(a.session['sequence'],-1)
