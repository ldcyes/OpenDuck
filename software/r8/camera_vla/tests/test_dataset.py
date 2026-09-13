import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from microduck_vision.dataset import validate_episode,dataset_profile
from microduck_vision.smolvla_adapter import decode_action
from test_bridge import obs
def episode():
 o=obs(); b=copy.deepcopy(o);b['request_id']='b'*32;b['capture_monotonic_s']+=.2;b['state']['monotonic_s']+=.2
 return [{'teacher':'human_teleoperation','successful':True,'observation':x,'executed_monotonic_s':x['capture_monotonic_s'],'executed_intent':{'vx':.01,'duration_s':.2}} for x in [o,b]]
class DatasetTests(unittest.TestCase):
 def test_verified_episode(self):self.assertEqual(len(validate_episode(episode())[0][1]),11)
 def test_failed_episode_excluded(self):
  rows=episode();rows[0]['successful']=False
  with self.assertRaises(ValueError):validate_episode(rows)
 def test_model_self_labels_excluded(self):
  rows=episode();rows[0]['teacher']='vla'
  with self.assertRaises(ValueError):validate_episode(rows)
 def test_gap_excluded(self):
  rows=episode();rows[1]['observation']['capture_monotonic_s']+=.2
  with self.assertRaises(ValueError):validate_episode(rows)
 def test_arm_action_rejected(self):
  with self.assertRaises(ValueError):decode_action([0.]*6)
 def test_joint_targets_rejected(self):
  with self.assertRaises(ValueError):decode_action([0.]*15)
 def test_mixed_rotation_rejected(self):
  rows=episode();rows[1]['observation']['image']['rotation_applied_deg']=0
  with self.assertRaises(ValueError):validate_episode(rows)
 def test_dataset_orientation_consistency(self):
  first=validate_episode(episode());other=episode()
  for row in other:row['observation']['image']['rotation_applied_deg']=0
  with self.assertRaises(ValueError):dataset_profile([first,validate_episode(other)])
 def test_dataset_calibration_consistency(self):
  first=validate_episode(episode());other=episode()
  for row in other:row['observation']['state']['calibration_sha256']='b'*64
  with self.assertRaises(ValueError):dataset_profile([first,validate_episode(other)])
 def test_profile_keeps_training_contract(self):
  p=dataset_profile([validate_episode(episode())]);self.assertEqual(len(p['state_names']),21);self.assertEqual(p['camera_rotation_applied_deg'],180)
 def test_physical_units_mapping(self):
  i=decode_action([.1,0,.2,.05,.1,.2,.1,.01,.02,.03,.2]);self.assertEqual(i['body'],[.01,.02,.03]);self.assertEqual(i['mouth'],.2)
if __name__=='__main__':unittest.main()
