import base64, copy, sys, time, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from microduck_vision.protocol import PROFILE, make_observation, ReplyGate, state_vector, validate_observation,context_binding,limits_sha256

def state(now=10.):
 return {'source':'live_dynamixel_sflp','motion_limits_sha256':limits_sha256(),'motion_context':{'mode':'head_home_locked','ready':True,'active':True,'head_home_stable':True},'robot_profile':PROFILE,'monotonic_s':now,'positions':[0.]*15,'velocities':[0.]*15,'gyro':[0.]*3,'gravity':[0.,0.,-1.],'imu_age_s':.001,'commissioned':True,'armed':True,'calibration_sha256':'a'*64}
def obs():
 return make_observation(b'\xff\xd8sample\xff\xd9',state(),capture_s=10.,now_s=10.01,sequence=1,task='向前一点',live=True)
def response(o):
 return {'schema':1,'request_id':o['request_id'],'sequence':o['sequence'],'robot_profile':PROFILE,**context_binding(o['state']),'plan':{'robot_profile':PROFILE,'say':'','intent':{'vx':.01,'duration_s':.2}}}

class ProtocolTests(unittest.TestCase):
 def test_actual_state_contract(self):
  o=obs(); self.assertEqual(len(state_vector(o)),21); self.assertEqual(state_vector(o)[-3:],[0.,0.,-1.]); validate_observation(o)
 def test_stale_state_rejected(self):
  with self.assertRaises(ValueError): make_observation(b'\xff\xd8x\xff\xd9',state(9.),capture_s=10.,now_s=10.,sequence=1,task='x',live=True)
 def test_future_state_rejected(self):
  with self.assertRaises(ValueError): make_observation(b'\xff\xd8x\xff\xd9',state(10.2),capture_s=10.,now_s=10.,sequence=1,task='x',live=True)
 def test_nonfinite_feedback_rejected(self):
  s=state(); s['positions'][0]=float('nan')
  with self.assertRaises(ValueError): make_observation(b'\xff\xd8x\xff\xd9',s,capture_s=10.,now_s=10.,sequence=1,task='x',live=True)
 def test_unarmed_live_rejected(self):
  s=state(); s['armed']=False
  with self.assertRaises(ValueError): make_observation(b'\xff\xd8x\xff\xd9',s,capture_s=10.,now_s=10.,sequence=1,task='x',live=True)
 def test_bad_image_rejected(self):
  with self.assertRaises(ValueError): make_observation(b'notjpeg',state(),capture_s=10.,now_s=10.,sequence=1,task='x',live=False)
 def test_stale_camera_rejected(self):
  with self.assertRaises(ValueError): make_observation(b'\xff\xd8x\xff\xd9',state(),capture_s=9.,now_s=10.,sequence=1,task='x',live=False)
 def test_reply_one_use(self):
  o=obs(); g=ReplyGate(); self.assertEqual(g.accept(o,response(o),10.1)['intent']['vx'],.01)
  with self.assertRaises(ValueError):g.accept(o,response(o),10.1)
 def test_delayed_reply_rejected(self):
  o=obs()
  with self.assertRaises(ValueError): ReplyGate().accept(o,response(o),10.9)
 def test_swapped_frame_rejected(self):
  o=obs(); r=response(o); r['request_id']='wrong'
  with self.assertRaises(ValueError): ReplyGate().accept(o,r,10.1)
 def test_wrong_calibration_rejected(self):
  o=obs(); r=response(o); r['calibration_sha256']='b'*64
  with self.assertRaises(ValueError): ReplyGate().accept(o,r,10.1)
 def test_plan_cannot_write_joints(self):
  o=obs(); r=response(o); r['plan']['intent']['joint_targets']=[0]*15
  with self.assertRaises(ValueError): ReplyGate().accept(o,r,10.1)
 def test_slow_high_level_plan_still_bounded(self):
  o=obs(); r=response(o); r['plan']['intent']['duration_s']=2.
  with self.assertRaises(ValueError): ReplyGate().accept(o,r,10.1)
 def test_image_state_skew(self):
  with self.assertRaises(ValueError): make_observation(b'\xff\xd8x\xff\xd9',state(),capture_s=9.8,now_s=10.01,sequence=1,task='x',live=False)

if __name__=='__main__':unittest.main()
