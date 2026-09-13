import copy,unittest
from test_bridge import obs,response,state
from microduck_vision.protocol import PROFILE,ReplyGate,make_observation,validate_submission_state
from microduck_rk.actuators import ROBOT_PROFILE
from microduck_rk.motion_limits import limits_sha256
from microduck_vision.dataset import validate_episode,dataset_profile
from test_dataset import episode
class R8BindingTests(unittest.TestCase):
 def test_profile_is_actual_R8(self):self.assertEqual(PROFILE,ROBOT_PROFILE)
 def test_missing_or_old_motion_contract_refused(self):
  for val in (None,'a'*64):
   s=state();s['motion_limits_sha256']=val
   with self.subTest(val=val),self.assertRaises(ValueError):make_observation(b'\xff\xd8x\xff\xd9',s,capture_s=10.,now_s=10.01,sequence=1,task='x',live=True)
 def test_inactive_context_refused(self):
  s=state();s['motion_context']={'mode':'head_home_locked','ready':False,'active':True,'head_home_stable':False}
  with self.assertRaises(ValueError):make_observation(b'\xff\xd8x\xff\xd9',s,capture_s=10.,now_s=10.01,sequence=1,task='x',live=True)
 def test_reply_cannot_move_head_under_HOME_lock(self):
  o=obs();r=response(o);r['plan']['intent']['head']=[.01,0,0,0]
  with self.assertRaises(ValueError):ReplyGate().accept(o,r,10.1)
 def test_dataset_cannot_mix_contexts(self):
  rows=episode();rows[1]['observation']['state']['motion_context']={'mode':'supported_double','ready':True,'active':True,'head_home_stable':True};rows[1]['executed_intent']={'head':[.01,0,0,0],'duration_s':.2}
  with self.assertRaises(ValueError):validate_episode(rows)
 def test_current_state_rechecked_after_slow_inference(self):
  o=obs();plan=ReplyGate().accept(o,response(o),10.6)
  with self.assertRaises(ValueError):validate_submission_state(o,plan,state(),10.6)
  latest=state(10.59);validate_submission_state(o,plan,latest,10.6)
  for key,value in [('calibration_sha256','b'*64),('armed',False),('motion_context',{'mode':'supported_double','ready':True,'active':True,'head_home_stable':True})]:
   bad=copy.deepcopy(latest);bad[key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):validate_submission_state(o,plan,bad,10.6)
 def test_reply_motion_hash_and_mode_are_bound(self):
  for key,val in [('motion_limits_sha256','b'*64),('motion_context','supported_double')]:
   o=obs();r=response(o);r[key]=val
   with self.subTest(key=key),self.assertRaises(ValueError):ReplyGate().accept(o,r,10.1)
 def test_wrong_camera_profile_refused(self):
  o=obs();o['image']['camera_profile']='old-IMX219'
  from microduck_vision.protocol import validate_observation
  with self.assertRaises(ValueError):validate_observation(o)
 def test_actual_runtime_telemetry_publisher_is_consumable(self):
  import json,tempfile
  from pathlib import Path
  from microduck_rk.telemetry import publish
  st=state()
  with tempfile.TemporaryDirectory()as td:
   path=Path(td)/'state.json'
   publish(path,{'positions':st['positions'],'velocities':st['velocities']},{'gyro':st['gyro'],'gravity':st['gravity'],'age_s':.001},'a'*64,PROFILE,True,10.,motion_context=st['motion_context'])
   result=make_observation(b'\xff\xd8x\xff\xd9',json.loads(path.read_text()),capture_s=10.,now_s=10.01,sequence=0,task='actual publisher boundary',live=True)
   self.assertEqual(result['state']['motion_limits_sha256'],limits_sha256());self.assertEqual(result['state']['positions'],st['positions'])
if __name__=='__main__':unittest.main()
