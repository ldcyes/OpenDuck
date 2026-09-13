"""R8 boundary regression: test-only register transport, no simulated hardware path."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from microduck_rk.motion_limits import limits_sha256, HEAD_RANGES, MOUTH_MAX,policy_action_scales
from microduck_rk.contract import Calibration, IDS,JOINT_NAMES,POLICY_SLOTS
from power_fixture import power_sha,platform_sha256
from microduck_rk.dynamixel import Dynamixels

R8='Microduck-RK-R8-RK3576-XM430-XC330'
XM_IDS={21,22,23,24,11,12,13,14,30,31}
ROOT=Path(__file__).parents[1]

def data():
    d=json.loads((ROOT/'config/calibration.template.json').read_text())
    d.update(schema=2,robot=R8,calibrated=True,imu_mount_verified=True,dynamics_verified=True,
             thermal_verified=True,power_verified=True,measurement_report='TEST ONLY',
             thermal_report='TEST ONLY',power_report='TEST ONLY',imu_sensor_to_trunk_wxyz=[1,0,0,0],
             action_scale=.1,voltage_hard=10.2,voltage_soft=10.3,voltage_max=11.8,temperature_max=60)
    d['power_configuration_sha256']=power_sha();d['hardware_platform_sha256']=platform_sha256()
    for j in d['joints']:
        j.update(model_number=1020 if j['id'] in XM_IDS else(1220 if j['id']in (20,10)else 1210),operating_mode=5,current_limit_ma=300,
                 p_gain=100,zero_tick=2048,direction=1,min_rad=-1,max_rad=1,home_rad=0,max_step_rad=.03)
    d['motion_limits_sha256']=limits_sha256()
    for j,(lo,hi) in zip(d['joints'][5:9],HEAD_RANGES):j.update(min_rad=lo,max_rad=hi)
    d['joints'][9].update(min_rad=0,max_rad=MOUTH_MAX)
    d['mouth_load_acceptance']={'verified':True,'structural_limit_Nm':.05,'observed_peak_upper_bound_Nm':.04,
      'tested_goal_current_raw':300,'tested_p_gain':100,'tested_max_step_rad':.03,
      'tested_range_rad':[0,MOUTH_MAX],'tested_voltage_range_V':[10.2,11.8],
      'tested_temperature_max_C':70,'full_travel_and_blocked_load_verified':True,
      'report':'SYNTHETIC TEST ONLY: no actual300mA torque claim'}
    from microduck_rk.actuators import current_raw
    d['motor_capability_qualification']={'verified':True,'independent_fixture':True,'report':'SYNTHETIC TEST ONLY',
      'duration_s':7200,'terminal_voltage_V':10.3,'ambient_C':40,'maximum_case_C':55,
      'axes':{str(j['id']):{'model_number':j['model_number'],'demonstrated_lower_bound_Nm':.90 if j['id']in XM_IDS else .13,
      'tested_current_ceiling_raw':current_raw(j['id'],j['current_limit_ma'])}for j in d['joints']if j['model_number']in (1020,1220)}}
    return d

def load(d,motion=False):
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp)/'cal.json';p.write_text(json.dumps(d))
        return Calibration.load(p,motion=motion)

class Registers(Dynamixels):
    def __init__(self):
        self.cal=Calibration(data(),'a'*64)
        self.events=[]
        self.reg={j['id']:{0:j['model_number'],6:45 if j['id'] in XM_IDS else 46,9:0,10:0,11:5,
              20:0,31:70,32:118,34:100,38:111 if j['id'] in XM_IDS else 300,
              60:0,63:53,64:0,70:0,132:2048,144:111,146:25} for j in self.cal.joints}
    def read_register(self,i,a,n):
        self.events.append(('r',i,a,n))
        if a==60 and self.reg[i][6]<(45 if self.reg[i][0]==1020 else 46):
            raise AssertionError('unsupported startup register read')
        return self.reg[i][a]
    def write_register(self,i,a,n,v):
        self.events.append(('w',i,a,n,v));self.reg[i][a]=v
    def write(self,p):self.events.append(('target',tuple(p)))

class MixedDriveTests(unittest.TestCase):
    def test_motion_refuses_missing_or_wrong_cm4_power_binding(self):
        for key,value in [('power_configuration_sha256',None),('hardware_platform_sha256','old-RK3566')]:
            d=data();d[key]=value
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'power|platform'):load(d,True)

    def test_profiles_module_exists(self):
        self.assertIsNotNone(importlib.util.find_spec('microduck_rk.actuators'))
    def test_r8_calibration_accepted_for_inspect_and_motion_after_gates(self):
        self.assertEqual(load(data()).data['robot'],R8)
        self.assertEqual(load(data(),True).data['robot'],R8)
    def test_old_robot_calibration_refused_even_without_motion(self):
        d=data();d['robot']='Microduck-RK-R1-XC330-T181';d['schema']=1
        with self.assertRaises(ValueError):load(d)
    def test_wrong_joint_model_refused_without_motion(self):
        for i in (0,1,9,14):
            d=data();d['joints'][i]['model_number']=1210 if d['joints'][i]['model_number']==1020 else 1020
            with self.subTest(i=i),self.assertRaises(ValueError):load(d)
    def test_finite_current_and_gain_limits(self):
        for v in (True,math.nan,math.inf,-1,0,.1,2000.1):
            d=data();d['joints'][1]['current_limit_ma']=v
            with self.subTest(v=v),self.assertRaises(ValueError):load(d)
        d=data();d['joints'][0]['current_limit_ma']=301
        with self.assertRaises(ValueError):load(d)
    def test_incomplete_physical_acceptance_refuses_motion(self):
        for key in ('calibrated','imu_mount_verified','dynamics_verified','thermal_verified','power_verified'):
            d=data();d[key]=False
            with self.subTest(key=key),self.assertRaises(ValueError):load(d,True)
    def test_voltage_and_temperature_limits_protect_both_models(self):
        for field,value in [('voltage_hard',9.9),('voltage_max',12.1),('voltage_max',10.4),('temperature_max',71)]:
            d=data();d[field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):load(d,True)
    def test_commission_writes_mixed_raw_current_and_enables_no_torque(self):
        r=Registers()
        for reg in r.reg.values():reg[38]=0;reg[60]=3;reg[64]=1
        r.commission()
        self.assertEqual(r.events[:15],[('w',i,64,1,0) for i in IDS])
        for i in IDS:
            self.assertEqual(r.reg[i][38],111 if i in XM_IDS else 300)
            self.assertEqual(r.reg[i][60],0);self.assertEqual(r.reg[i][64],0)
        self.assertFalse(any(e[0]=='w' and e[2]==64 and e[4] for e in r.events))
    def test_all_models_prechecked_before_any_eeprom_mutation(self):
        r=Registers();r.reg[IDS[-1]][0]=1210
        with self.assertRaisesRegex(RuntimeError,'model'):r.commission()
        self.assertEqual([e for e in r.events if e[0]=='w'],[('w',i,64,1,0) for i in IDS])
    def test_firmware_gate_by_model_and_precheck_before_eeprom(self):
        for i,fw in [(20,45),(21,44)]:
            r=Registers();r.reg[i][6]=fw
            with self.subTest(i=i),self.assertRaisesRegex(RuntimeError,'firmware'):r.commission()
            self.assertEqual([e for e in r.events if e[0]=='w'],[('w',i,64,1,0) for i in IDS])
        Registers().verify()  # XM43045 / XC33046 are each valid.
    def test_enable_rejects_wrong_model_before_any_write(self):
        r=Registers();r.reg[14][0]=1210
        with self.assertRaises(RuntimeError):r.enable([0]*15)
        self.assertFalse(any(e[0]=='w' for e in r.events))
    def test_enable_current_is_quantized_and_goals_precede_torque(self):
        r=Registers();r.enable([0]*15)
        for i in IDS:self.assertEqual(r.reg[i][102],111 if i in XM_IDS else 300)
        target=next(k for k,e in enumerate(r.events) if e[0]=='target')
        self.assertTrue(all(k>target for k,e in enumerate(r.events) if e[0]=='w' and e[2]==64 and e[4]==1))
    def test_inspect_only_reads_startup_for_known_supported_models(self):
        r=Registers();r.reg[20][6]=45;r.reg[21][6]=44;r.reg[22][0]=9999
        out=r.inspect()
        self.assertTrue(all(out[i]['startup_configuration'] is None for i in (0,1,2)))
        self.assertFalse(any(e[0]=='w' for e in r.events))
    def test_signed_present_current_converted_by_model(self):
        r=Registers();r.sdk=SimpleNamespace(COMM_SUCCESS=0)
        r.group=SimpleNamespace(txRxPacket=lambda:0,isAvailable=lambda *a:True,
          getData=lambda i,a,n:{126:0xffff,128:0,132:2048,144:111,146:25}[a])
        r._check=lambda *a:None
        measured=r.read()
        for i,v in zip(IDS,measured['current_ma']):self.assertAlmostEqual(v,-2.69 if i in XM_IDS else -1)
        self.assertEqual(measured['current_raw'],[-1]*15)
    def test_reg60_nonzero_and_failed_readback_still_stop(self):
        r=Registers();r.reg[14][60]=1
        with self.assertRaisesRegex(RuntimeError,'reg60'):r.enable([0]*15)
        self.assertFalse(any(e[0]=='w' for e in r.events))
    def test_overvoltage_immediate_stop(self):
        from microduck_rk.safety import Guard
        with self.assertRaisesRegex(RuntimeError,'overvoltage'):Guard(data()).check(0,[11.9]*15,[30]*15,[0,0,-1],0)
    def test_initial_sensors_check_current_before_enable(self):
        from microduck_rk.safety import check_joint_currents
        check_joint_currents([0]*15,load(data()))
        x=[0]*15;x[1]=400
        with self.assertRaises(RuntimeError):check_joint_currents(x,load(data()))


    def test_prepared_enable_rechecks_permission_and_cleans_partial_torque(self):
        r=Registers();r.prepare_enable();before=len(r.events)
        calls=[]
        def ready():
            calls.append(1)
            if any(r.reg[i][64] for i in IDS):raise RuntimeError('expired final actual HOME sample')
        with self.assertRaisesRegex(RuntimeError,'expired'):r.enable([0]*15,check_ready=ready)
        self.assertGreaterEqual(len(calls),2)
        self.assertTrue(all(r.reg[i][64]==0 for i in IDS))
        self.assertFalse(any(e[0]=='r' for e in r.events[before:]))

    def test_enable_failure_attempts_torque_off_for_all_ids(self):
        r=Registers();original=r.write_register
        def fail(i,a,n,v):
            if i==21 and a==64 and v==1:raise RuntimeError('simulated failed enable')
            original(i,a,n,v)
        r.write_register=fail
        with self.assertRaises(RuntimeError):r.enable([0]*15)
        self.assertTrue(all(r.reg[i][64]==0 for i in IDS))

if importlib.util.find_spec('microduck_rk.actuators'):
    from microduck_rk.actuators import spec_for_id, current_raw, profile_sha256
    class UnitTests(unittest.TestCase):
        def test_quantization_never_exceeds_requested_ma(self):
            s=spec_for_id(21)
            for v in [2.69,3,300,1000,1500,2000]:self.assertLessEqual(current_raw(21,v)*s.current_mA_per_raw,v+1e-12)
            self.assertEqual(current_raw(21,300),111);self.assertEqual(current_raw(20,300),300)
        def test_neck_and_head_pitch_require_xm430_and_refuse_previous_profile(self):
            for servo_id in (30,31):
                self.assertEqual(spec_for_id(servo_id).model_number,1020)
                self.assertEqual(current_raw(servo_id,300),111)
                d=data();next(j for j in d['joints'] if j['id']==servo_id)['model_number']=1210
                with self.subTest(servo_id=servo_id),self.assertRaises(ValueError):load(d)
        def test_unknown_id_rejected(self):
            with self.assertRaises(ValueError):spec_for_id(99)
        def test_drive_hash_changes_when_current_changes(self):
            c=load(data());a=c.drive_sha256;c.joints[1]['current_limit_ma']=301
            self.assertNotEqual(a,c.drive_sha256)
        def test_manifest_profile_and_drive_binding(self):
            from microduck_rk.policy import validate_manifest
            c=load(data()); m={'motion_limits_sha256':limits_sha256(),'hardware_platform_sha256':platform_sha256(),'power_configuration_sha256':power_sha(),'robot':R8,'drive_profile_sha256':profile_sha256(),
              'drive_configuration_sha256':c.drive_sha256,'calibration_sha256':c.sha256,
              'policy_sha256':'b'*64,'observation_size':61,'action_size':14,'motion_approved':True,
              'motion_context':'head_home_locked','action_scale_by_joint':policy_action_scales([JOINT_NAMES[i]for i in POLICY_SLOTS],.1,'head_home_locked'),'action_filter':'motion_context_joint_scale_mask','action_clip':None,'action_scale':.1,
              'previous_action':'raw_unfiltered_network_output','imu_observation':'projected_gravity',
              'control_hz':50,'home_rad':c.home,'validation_report':'TEST ONLY','dynamics_sha256':'c'*64}
            validate_manifest(m,c,'b'*64)
            for key in ('motion_context','action_scale_by_joint','action_filter','previous_action','motion_limits_sha256','robot','drive_profile_sha256','drive_configuration_sha256','hardware_platform_sha256','power_configuration_sha256'):
                bad=dict(m);bad[key]='R3'
                with self.subTest(key=key),self.assertRaises(ValueError):validate_manifest(bad,c,'b'*64)
        def test_training_requires_mixed_input_set(self):
            from microduck_rk.prepare_training import prepare
            with self.assertRaisesRegex(ValueError,'mixed|R8'):
                prepare(SimpleNamespace())
