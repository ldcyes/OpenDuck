"""Physical-limit and voltage boundaries; synthetic tests, no physical approval."""
import copy,json,math,tempfile,unittest
from pathlib import Path
from microduck_interaction.schema import validate_intent,command_values,ROBOT_PROFILE
from microduck_interaction.executor import Arbiter,CommandWriter
from microduck_rk.safety import read_command,Guard
from test_mixed_drive import data,load,Registers
import test_power_r8 as power_tests

class HeadLimitsTests(unittest.TestCase):
    def test_each_signed_head_boundary_and_mouth_boundary(self):
        for i,(lo,hi) in enumerate(((-20,5),(-15,15),(-15,15),(-8,8))):
            for sign,degree in ((-1,lo),(1,hi)):
                h=[0.]*4;h[i]=math.radians(degree)
                validate_intent({'duration_s':.2,'head':h})
                h[i]+=sign*1e-8
                with self.subTest(i=i,sign=sign),self.assertRaises(ValueError):validate_intent({'duration_s':.2,'head':h})
        validate_intent({'duration_s':.2,'mouth':math.radians(12)})
        for v in (-1e-8,math.radians(12)+1e-8):
            with self.assertRaises(ValueError):validate_intent({'duration_s':.2,'mouth':v})
    def test_invalid_submission_preserves_sequence_and_deadline(self):
        a=Arbiter(clock=lambda:1.);s=a.start_session('test',2.)['session_id'];a.submit(s,1,ROBOT_PROFILE,{'duration_s':.2})
        before=(a.intent_until,a.session['sequence'])
        with self.assertRaises(ValueError):a.submit(s,2,ROBOT_PROFILE,{'duration_s':3.,'head':[0,.3,0,0]})
        self.assertEqual(before,(a.intent_until,a.session['sequence']))
    def test_audio_endpoints_reject_old_travel(self):
        with self.assertRaises(ValueError):Arbiter(mouth_open=.3)
        with self.assertRaises(ValueError):Arbiter(mouth_closed=-.01)
        # Safe closure is the mechanical zero, never a held-open audio idle.
        with self.assertRaises(ValueError):Arbiter(mouth_closed=.05)
    def test_writer_validates_before_atomic_replace_and_reader_rejects_old_contract(self):
        from microduck_rk.motion_limits import limits_sha256
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'cmd.json';frame={'monotonic_s':1.,'commands':[0.]*13,'mouth_rad':0.}
            with CommandWriter(p) as w:
                w.write(frame);good=p.read_bytes();self.assertEqual(json.loads(good)['motion_limits_sha256'],limits_sha256())
                for bad in ({**frame,'mouth_rad':.3},{**frame,'commands':[0,0,0,0,.3,0,0,0,0,0,0,0,0]}):
                    with self.assertRaises(ValueError):w.write(bad)
                    self.assertEqual(p.read_bytes(),good)
            read_command(p)
            d=json.loads(good);d['motion_limits_sha256']='old';p.write_text(json.dumps(d))
            with self.assertRaises(ValueError):read_command(p)
    def test_calibration_head_caps_home_offset_and_closed_endpoint(self):
        from microduck_rk.motion_limits import limits_sha256
        d=data();d['motion_limits_sha256']=limits_sha256()
        # Head contract is delta from the measured home, not absolute encoder zero.
        for j,(lo,hi) in zip(d['joints'][5:9],((-20,5),(-15,15),(-15,15),(-8,8))):
            j['home_rad']=.3491;j['min_rad']=.3491+math.radians(lo);j['max_rad']=.3491+math.radians(hi)
        d['joints'][9].update(home_rad=0,min_rad=0,max_rad=math.radians(12))
        load(d,True)
        for key,value in [('motion_limits_sha256','old')]:
            bad=copy.deepcopy(d);bad[key]=value
            with self.assertRaises(ValueError):load(bad,True)
        bad=copy.deepcopy(d);bad['joints'][6]['max_rad']+=.001
        with self.assertRaises(ValueError):load(bad,True)
        bad=copy.deepcopy(d);bad['joints'][9]['min_rad']=-.001
        with self.assertRaises(ValueError):load(bad,True)
    def test_provider_prompt_uses_exact_shared_radians(self):
        from microduck_interaction.providers import SYSTEM_PROMPT
        from microduck_rk.motion_limits import limits_sha256
        self.assertIn(limits_sha256(),SYSTEM_PROMPT)
        self.assertIn(str(math.radians(12)),SYSTEM_PROMPT)
        self.assertNotIn('[0.35,0.35,0.5,0.35]',SYSTEM_PROMPT)

    def test_neck_positive_old_command_rejected_before_any_write(self):
        from microduck_rk.motion_limits import validate_frame
        c=[0.]*13;c[3]=math.radians(5)
        validate_frame({'commands':c,'mouth_rad':0.,'monotonic_s':1.})
        for bad in (5.00001,20.):
            c[3]=math.radians(bad)
            with self.assertRaises(ValueError):validate_frame({'commands':c,'mouth_rad':0.,'monotonic_s':1.})
    def test_superseded_motion_binding_cannot_authorize_new_contract(self):
        from microduck_rk.motion_limits import validate_frame
        old='95537db9f31118c35f96116ee7822112518de5f5ea8ab57d92bb728a6c95f343'
        with self.assertRaises(ValueError):validate_frame({'commands':[0.]*13,'mouth_rad':0.,'monotonic_s':1.,'motion_limits_sha256':old},True)

class VoltageContractTests(unittest.TestCase):
    setUp=power_tests.PowerTests.setUp;sample=power_tests.PowerTests.sample;advance=power_tests.PowerTests.advance;temps=power_tests.PowerTests.temps;monitor=power_tests.PowerTests.monitor;arm=power_tests.PowerTests.arm
    # Reuse fixture helpers without rerunning the existing tests.
    def test_new_startup_threshold_and_running_10_3_acceptance(self):
        m=self.monitor();m.update_power(self.sample(sv=10.39))
        spins=[]
        def spin():spins.append(1);self.c.sleep(.02);m.update_power(self.sample(sv=10.40))
        m.enable(spin);self.assertEqual(spins,[1])
        for _ in range(15):self.advance(m,.02,sv=10.30);m.check()
        self.assertTrue(self.g.req)
    def test_bus_soft_40ms_and_hard_threshold_are_separate(self):
        m=self.monitor();self.arm(m);m.update_power(self.sample(sv=10.29));m.check()
        self.advance(m,.039,sv=10.29);m.check();self.advance(m,.001,sv=10.29)
        with self.assertRaisesRegex(RuntimeError,'servo voltage low'):m.check()
        self.g=type(self.g)();m=self.monitor();self.arm(m);m.update_power(self.sample(sv=10.10))
        with self.assertRaises(RuntimeError):m.check()
        self.assertFalse(self.g.req)
    def test_10_3_servo_readback_normal_10_2_stops_and_firmware_10_0(self):
        g=Guard(data())
        for t in (0,.2,.4):g.check(t,[10.3]*15,[30]*15,[0,0,-1],t)
        with self.assertRaises(RuntimeError):g.check(.5,[10.2]*15,[30]*15,[0,0,-1],.5)
        from types import SimpleNamespace
        r=Registers();r.sdk=SimpleNamespace(COMM_SUCCESS=0);r._check=lambda *a:None
        r.group=SimpleNamespace(txRxPacket=lambda:0,isAvailable=lambda *a:True,
          getData=lambda i,a,n:{126:0,128:0,132:2048,144:102,146:25}[a])
        with self.assertRaises(RuntimeError):g.check(.6,r.read()['volts'],[30]*15,[0,0,-1],.6)
        r=Registers();r.commission()
        self.assertTrue(all(row[34]==100 and row[32]==118 for row in r.reg.values()))
