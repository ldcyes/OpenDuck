"""Mouth structure boundary; every accepted fixture here is synthetic, not approval."""
import copy,math,unittest
from test_mixed_drive import data,load,Registers

def approval():
    return {'verified':True,'structural_limit_Nm':.05,'observed_peak_upper_bound_Nm':.04,
      'tested_goal_current_raw':300,'tested_p_gain':100,'tested_max_step_rad':.03,
      'tested_range_rad':[0,math.radians(12)],'tested_voltage_range_V':[10.2,11.8],
      'tested_temperature_max_C':70,'full_travel_and_blocked_load_verified':True,
      'report':'SYNTHETIC TEST ONLY - does not establish an actual300mA torque'}
def approved_data():
    d=data();d['mouth_load_acceptance']=approval();return d
class MouthLoadTests(unittest.TestCase):
    def test_missing_acceptance_refuses_motion_but_allows_inspection(self):
        d=approved_data();del d['mouth_load_acceptance'];load(d,False)
        with self.assertRaisesRegex(ValueError,'mouth'):load(d,True)
    def test_peak_bound_flags_report_and_structure_limit_are_enforced(self):
        for key,value in [('verified',False),('full_travel_and_blocked_load_verified',False),('report',''),
          ('structural_limit_Nm',.14),('observed_peak_upper_bound_Nm',.050001),
          ('observed_peak_upper_bound_Nm',math.nan),('observed_peak_upper_bound_Nm',True),('observed_peak_upper_bound_Nm',0)]:
            d=approved_data();d['mouth_load_acceptance'][key]=value
            with self.subTest(key=key,value=value),self.assertRaisesRegex(ValueError,'mouth'):load(d,True)
    def test_approval_covers_actual_current_gain_step_range_voltage_temperature(self):
        for key,value in [('tested_goal_current_raw',299),('tested_goal_current_raw',True),
          ('tested_p_gain',99),('tested_max_step_rad',.029),('tested_range_rad',[0,.1]),
          ('tested_voltage_range_V',[10.3,11.8]),('tested_voltage_range_V',[10.2,11.7]),('tested_temperature_max_C',59)]:
            d=approved_data();d['mouth_load_acceptance'][key]=value
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'mouth'):load(d,True)
    def test_enable_cannot_bypass_load_gate_even_with_direct_calibration_object(self):
        r=Registers();r.cal.data.pop('mouth_load_acceptance',None)
        with self.assertRaisesRegex(ValueError,'mouth'):r.enable([0]*15)
        self.assertFalse(r.events,'Must reject before register reads/writes or Torque On')
    def test_valid_lower_tested_setting_reaches_actual_goal_current_register(self):
        r=Registers();r.cal.data['mouth_load_acceptance']=approval()
        r.cal.data['mouth_load_acceptance']['tested_goal_current_raw']=40
        r.cal.joints[9]['current_limit_ma']=40;r.commission();r.enable([0]*15)
        self.assertEqual(r.reg[34][38],40);self.assertEqual(r.reg[34][102],40)
    def test_single_motion_contract_explicitly_binds_mouth_structure(self):
        from microduck_rk.motion_limits import CONTRACT
        self.assertEqual(CONTRACT.get('mouth_structural_torque_limit_Nm'),.05)

    def test_bam_rejects_unbound_or_previous_mouth_contract(self):
        from test_mixed_training import bam
        from microduck_rk.prepare_training import validate_bam
        for value in (None,'old-contract'):
            b=bam(1210);b['r8_actuator']['motion_limits_sha256']=value
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'motion|load'):validate_bam(b,1210)
