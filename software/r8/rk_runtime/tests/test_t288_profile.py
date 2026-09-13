"""New T288 identity and independent motor qualification boundary regressions."""
import copy,unittest
from test_mixed_drive import data,load,Registers
from microduck_rk.actuators import spec_for_id,spec_for_model,profile_sha256
from microduck_rk import prepare_training as pt

class T288ProfileTests(unittest.TestCase):
 def test_two_yaws_require_1220_and_head_mouth_stay1210(self):
  self.assertEqual([spec_for_id(i).model_number for i in (20,10,32,33,34)],[1220,1220,1210,1210,1210]);self.assertEqual(spec_for_model(1220).name,'XC330-T288-T')
 def test_old_T181_yaw_refused_before_any_eeprom_write(self):
  r=Registers();r.reg[20][0]=1210
  with self.assertRaisesRegex(RuntimeError,'model'):r.commission()
  self.assertTrue(all(e[2]==64 and e[4]==0 for e in r.events if e[0]=='w'))
 def test_T181_yaw_refused_at_enable(self):
  r=Registers();r.reg[10][0]=1210
  with self.assertRaisesRegex(RuntimeError,'model'):r.enable([0]*15)
  self.assertFalse(any(e[0]=='w'for e in r.events))
 def test_three_BAM_identities_are_distinct(self):
  self.assertEqual(pt.MODEL_NAMES,{1020:'xm430',1210:'xc330',1220:'xc330_t288'})
 def test_capability_report_required_for_motion_and_direct_enable(self):
  d=data();d.pop('motor_capability_qualification',None)
  with self.assertRaisesRegex(ValueError,'qualification'):load(d,True)
  r=Registers();r.cal.data.pop('motor_capability_qualification',None)
  with self.assertRaisesRegex(ValueError,'qualification'):r.enable([0]*15)
  self.assertFalse(r.events)
 def test_insufficient_duration_voltage_temperature_or_torque_refused(self):
  for key,val in [('duration_s',7199),('terminal_voltage_V',10.8),('ambient_C',25),('maximum_case_C',71),('verified',False),('report','')]:
   d=data();d['motor_capability_qualification'][key]=val
   with self.subTest(key=key),self.assertRaisesRegex(ValueError,'qualification'):load(d,True)
  for sid,v in [('20',.12),('20',.1299),('21',.82),('21',.8999)]:
   d=data();d['motor_capability_qualification']['axes'][sid]['demonstrated_lower_bound_Nm']=v
   with self.subTest(sid=sid),self.assertRaisesRegex(ValueError,'qualification'):load(d,True)
 def test_wrong_qualification_model_or_current_envelope_rejected(self):
  for key,val in [('model_number',1210),('tested_current_ceiling_raw',1)]:
   d=data();d['motor_capability_qualification']['axes']['20'][key]=val
   with self.subTest(key=key),self.assertRaisesRegex(ValueError,'qualification'):load(d,True)
