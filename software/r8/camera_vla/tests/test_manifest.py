import hashlib,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from microduck_vision.smolvla_adapter import check_manifest,STATE_NAMES
from microduck_vision.protocol import PROFILE,ACTION_NAMES,CAMERA_PROFILE,limits_sha256
class ManifestTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
  profile={'motion_limits_sha256':limits_sha256(),'motion_context':'head_home_locked','camera_profile':CAMERA_PROFILE,'robot_profile':PROFILE,'state_names':STATE_NAMES,'action_names':ACTION_NAMES,'camera_key':'observation.images.front','camera_rotation_applied_deg':180,'calibration_sha256':'a'*64,'fps':5,'width':640,'height':480}
  (self.root/'config.json').write_text('{}');(self.root/'model.safetensors').write_bytes(b'TEST FILE BINDING ONLY; NOT MODEL WEIGHTS');(self.root/'microduck_training_profile.json').write_text(json.dumps(profile))
  self.manifest={**profile,'approved_for_simulation':True,'checkpoint_files_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.iterdir()}}
 def tearDown(self):self.temp.cleanup()
 def test_file_binding(self):self.assertEqual(check_manifest(self.manifest,self.root)['fps'],5)
 def test_changed_file_refused(self):
  (self.root/'model.safetensors').write_bytes(b'changed')
  with self.assertRaises(ValueError):check_manifest(self.manifest,self.root)
 def test_deployment_orientation_mismatch(self):
  self.manifest['camera_rotation_applied_deg']=0
  with self.assertRaises(ValueError):check_manifest(self.manifest,self.root)
 def test_wrong_state_projection_input(self):
  self.manifest['state_names']=['q']*36
  with self.assertRaises(ValueError):check_manifest(self.manifest,self.root)
 def test_unreviewed_refused(self):
  self.manifest['approved_for_simulation']=False
  with self.assertRaises(ValueError):check_manifest(self.manifest,self.root)
 def test_obsolete_motion_and_camera_profile_refused(self):
  for key,value in [('motion_limits_sha256','b'*64),('camera_profile','IMX219'),('motion_context','old')]:
   bad=dict(self.manifest);bad[key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):check_manifest(bad,self.root)
 def test_context_change_requires_new_training_profile(self):
  self.manifest['motion_context']='supported_double'
  with self.assertRaises(ValueError):check_manifest(self.manifest,self.root)
if __name__=='__main__':unittest.main()
