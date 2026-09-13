"""VLA result age is enforced at final local acceptance, not only before HTTP."""
import unittest
from microduck_interaction.executor import Arbiter
from microduck_rk.motion_limits import limits_sha256
from microduck_rk.actuators import ROBOT_PROFILE
class VLATransactionTests(unittest.TestCase):
 def setUp(self):
  self.t=10.1;self.a=Arbiter(clock=lambda:self.t);self.sid=self.a.start_session('vla',2)['session_id']
  self.ctx={'capture_monotonic_s':10.,'deadline_monotonic_s':10.75,'calibration_sha256':'a'*64,'motion_limits_sha256':limits_sha256(),'motion_context':'head_home_locked'}
 def send(self):return self.a.submit(self.sid,0,ROBOT_PROFILE,{'vx':.01,'duration_s':.2},vla_context=self.ctx)
 def test_missing_provenance_refused_even_for_zero_intent(self):
  with self.assertRaises(ValueError):self.a.submit(self.sid,0,ROBOT_PROFILE,{'duration_s':.2})
 def test_local_transport_delay_cannot_redate_old_observation(self):
  self.t=10.76
  with self.assertRaises(ValueError):self.send()
  self.assertEqual(self.a.status()['last_sequence'],-1)
 def test_lease_and_close_grace_end_at_observation_deadline(self):
  self.t=10.70;self.send();self.assertIsNotNone(self.a.frame());self.t=10.751;self.assertIsNone(self.a.frame())
 def test_context_mismatch_rejected_before_sequence_consumption(self):
  self.ctx['motion_limits_sha256']='b'*64
  with self.assertRaises(ValueError):self.send()
  self.assertEqual(self.a.status()['last_sequence'],-1)
 def test_zero_VLA_cannot_use_unarmed_runtime_bootstrap_exception(self):
  from microduck_rk.motion_context import validate_live_frame
  state={'source':'live_dynamixel_sflp','robot_profile':ROBOT_PROFILE,'calibration_sha256':'a'*64,'motion_limits_sha256':limits_sha256(),'armed':False,'monotonic_s':10.1,'motion_context':{'mode':'head_home_locked','ready':True,'head_home_stable':True}}
  with self.assertRaises(ValueError):validate_live_frame({'commands':[0.]*13,'mouth_rad':0.,'vla_context':self.ctx},state,'a'*64,10.1)
 def test_current_runtime_context_change_revokes_active_VLA_frames(self):
  from microduck_rk.motion_context import validate_live_frame
  state={'source':'live_dynamixel_sflp','robot_profile':ROBOT_PROFILE,'calibration_sha256':'a'*64,'motion_limits_sha256':limits_sha256(),'armed':True,'monotonic_s':10.1,'motion_context':{'mode':'head_home_locked','ready':True,'head_home_stable':True}}
  self.a.context_check=lambda frame:validate_live_frame(frame,state,'a'*64,self.t)
  self.send();self.assertIsNotNone(self.a.frame());state['motion_context']['mode']='supported_double'
  with self.assertRaises(ValueError):self.a.frame()
if __name__=='__main__':unittest.main()
