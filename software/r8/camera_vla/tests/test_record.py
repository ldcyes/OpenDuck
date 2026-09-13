import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from microduck_vision.record import demonstration_row
from microduck_interaction.schema import command_values,validate_intent
from test_bridge import state
def sample():
 i=validate_intent({'vx':0.,'mouth':.2,'duration_s':.2});s=state();s.update(source='live_dynamixel_sflp',sent_commands=command_values(i),sent_mouth_rad=.05,sent_monotonic_s=10.03,source_command_monotonic_s=10.02)
 s['motion_context']['mode']='supported_double'
 status={'robot_profile':s['robot_profile'],'motion_limits_sha256':s['motion_limits_sha256'],'intent_since_monotonic_s':10.01,'intent_deadline_monotonic_s':10.2,'active_source':'manual','intent_active':True,'dry_run':False,'executor_healthy':True,'intent':i}
 return s,status
def record(s,status):return demonstration_row(b'\xff\xd8x\xff\xd9',s,status,capture_s=10.,now_s=10.05,sequence=1,task='向前')
class RecordTests(unittest.TestCase):
 def test_labels_sent_not_requested_mouth(self):
  s,t=sample();row=record(s,t);self.assertEqual(row['executed_intent']['mouth'],.05);self.assertFalse(row['successful'])
 def test_vla_not_human_teacher(self):
  s,t=sample();t['active_source']='vla'
  with self.assertRaises(ValueError):record(s,t)
 def test_dry_run_not_real_teacher(self):
  s,t=sample();t['dry_run']=True
  with self.assertRaises(ValueError):record(s,t)
 def test_changed_intent_discarded(self):
  s,t=sample();t['intent']['vx']=.02
  with self.assertRaises(ValueError):record(s,t)
 def test_old_command_discarded(self):
  s,t=sample();s['source_command_monotonic_s']=9.
  with self.assertRaises(ValueError):record(s,t)
 def test_equal_old_intent_is_not_relabelled_as_new_manual_command(self):
  s,t=sample();t['intent_since_monotonic_s']=10.025
  with self.assertRaises(ValueError):record(s,t)
 def test_status_intent_that_expired_in_transit_is_rejected(self):
  s,t=sample();t['intent_deadline_monotonic_s']=10.04
  with self.assertRaises(ValueError):record(s,t)
if __name__=='__main__':unittest.main()
