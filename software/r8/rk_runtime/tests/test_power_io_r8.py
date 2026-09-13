import importlib,importlib.util,math,unittest
class Clock:
    def __init__(self):self.t=0.
    def __call__(self):return self.t
    def sleep(self,t):self.t+=t
class Registers:
    def __init__(self):self.r={0xfe:0x5449,0xff:0x2260,6:8,1:0,2:8640,3:432,4:1000};self.w=[];self.ready=True
    def read16(self,r):return self.r.get(r,0)
    def write16(self,r,v):self.w.append((r,v));self.r[r]=v
class PowerIoTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('microduck_rk.power_io'),'real R8 power I/O not implemented')
        self.p=importlib.import_module('microduck_rk.power_io');self.clock=Clock();self.bus=Registers()
        self.cal={'current_gain':1.,'current_offset_A':0.,'bus_gain':1.,'bus_offset_V':0.}
    def ina(self):return self.p.Ina226(self.bus,self.cal,clock=self.clock,sleep=self.clock.sleep)
    def test_true_ina_units_and_negative_regeneration(self):
        s=self.ina();s.initialize();self.assertIn((5,0xa00),self.bus.w)
        self.bus.r[4]=(-1500)&65535;self.bus.r[1]=(-1200)&65535
        x=s.sample();self.assertAlmostEqual(x['current_A'],-1.5);self.assertAlmostEqual(x['bus_V'],10.8)
        self.assertAlmostEqual(x['power_register_W'],10.8);self.assertAlmostEqual(x['shunt_V'],-.003)
    def test_ina_missing_or_wrong_identity(self):
        self.bus.r[0xfe]=0
        with self.assertRaisesRegex(RuntimeError,'identity'):self.ina().initialize()
    def test_ina_conversion_stale_is_not_zero_sample(self):
        s=self.ina();s.initialize();self.bus.r[6]=0
        with self.assertRaisesRegex(RuntimeError,'conversion'):s.sample()
    def test_ina_reset_calibration_or_overflow_rejected(self):
        for register,value in [(5,0),(6,12)]:
            with self.subTest(register=register):
                s=self.ina();s.initialize();self.bus.r[register]=value
                with self.assertRaises(RuntimeError):s.sample()
    def test_ina_bus_and_shunt_saturation_rejected(self):
        for register,value in [(1,32767),(2,0x8000),(4,0x7fff)]:
            with self.subTest(register=register):
                s=self.ina();s.initialize();self.bus.r[register]=value
                with self.assertRaises(RuntimeError):s.sample()
                self.bus.r[register]=0
    def test_ads_single_shot_selects_three_channels_and_uses_4096_range(self):
        class ADC(Registers):
            def write16(b,r,v):
                super().write16(r,v)
                if r==1:b.r[0]=13200
        b=ADC();s=self.p.Ads1115(b,clock=self.clock,sleep=self.clock.sleep)
        for ch in range(3):
            self.assertAlmostEqual(s.voltage(ch),1.65)
            self.assertEqual((b.w[-1][1]>>12)&7,ch+4)
            self.assertEqual((b.w[-1][1]>>9)&7,1)
            self.assertEqual((b.w[-1][1]>>8)&1,1)
    def test_ads_stuck_busy_and_wrong_mux_rejected(self):
        class ADC(Registers):
            def read16(b,r):return super().read16(r)&0x7fff if r==1 else super().read16(r)
        with self.assertRaisesRegex(RuntimeError,'conversion'):self.p.Ads1115(ADC(),clock=self.clock,sleep=self.clock.sleep).voltage(1)
        class Wrong(Registers):
            def write16(b,r,v):super().write16(r,v^0x1000)
        with self.assertRaisesRegex(RuntimeError,'config'):self.p.Ads1115(Wrong(),clock=self.clock,sleep=self.clock.sleep).voltage(0)
    def test_ntc_25C_analytical_and_open_short(self):
        self.assertAlmostEqual(self.p.ntc_temperature(1.65,3.3,10000,10000,3380),25)
        for v in [0,3.3,float('nan'),-.1,3.4]:
            with self.subTest(v=v),self.assertRaises(RuntimeError):self.p.ntc_temperature(v,3.3,10000,10000,3380)
        r=10000*math.exp(3380*(1/333.15-1/298.15));v=3.3*r/(10000+r)
        self.assertAlmostEqual(self.p.ntc_temperature(v,3.3,10000,10000,3380),60)

class GpioTests(unittest.TestCase):
    def test_real_backend_requests_low_and_releases_low(self):
        import types
        from unittest.mock import patch
        from microduck_rk import power_io
        self.assertTrue(hasattr(power_io,'NamedGpioGate'),'named-line Linux GPIO backend missing')
        events=[];state={7:0,8:1}
        class Request:
            def set_value(self,n,v):state[n]=v;events.append((n,v))
            def get_value(self,n):return state[n]
            def release(self):events.append('release')
        class Chip:
            def __init__(self,p):pass
            def get_info(self):return types.SimpleNamespace(num_lines=10)
            def get_line_info(self,i):return types.SimpleNamespace(name={7:'MICRODUCK_RUN_REQ',8:'MICRODUCK_RUN_OK'}.get(i))
            def request_lines(self,**kw):
                for n,s in kw['config'].items():
                    if hasattr(s,'output_value'):state[n]=s.output_value;events.append((n,s.output_value))
                return Request()
            def close(self):pass
        gpio=types.SimpleNamespace(Chip=Chip,LineSettings=lambda **kw:types.SimpleNamespace(**kw),line=types.SimpleNamespace(Direction=types.SimpleNamespace(INPUT=0,OUTPUT=1),Value=types.SimpleNamespace(INACTIVE=0,ACTIVE=1)))
        with patch.dict('sys.modules',{'gpiod':gpio}),patch('glob.glob',return_value=['/dev/gpiochip0']):
            g=power_io.NamedGpioGate();self.assertEqual(state[7],0);self.assertTrue(g.permitted());g.set_request(True);self.assertEqual(state[7],1);g.close();self.assertEqual(state[7],0)
        self.assertEqual(events[0],(7,0))
    def test_missing_named_gpio_is_error(self):
        from unittest.mock import patch
        from microduck_rk import power_io
        self.assertTrue(hasattr(power_io,'NamedGpioGate'))
        with patch.dict('sys.modules',{'gpiod':object()}),patch('glob.glob',return_value=[]):
            with self.assertRaisesRegex(RuntimeError,'unique'):power_io.NamedGpioGate()

class DiagnosticTests(unittest.TestCase):
    def test_raw_diagnostic_never_asserts_run_and_is_not_calibrated(self):
        from unittest.mock import patch
        from microduck_rk import power_io as p
        self.assertTrue(hasattr(p,'raw_diagnostics'),'raw hardware calibration capture missing')
        requested=[]
        class Gate:
            def __init__(s):requested.append(False)
            def set_request(s,v):requested.append(v)
            def close(s):requested.append(False)
        class Bus:
            def close(s):pass
        class Ina:
            def __init__(s,*a):pass
            def initialize(s):pass
            def sample(s):return {'raw':{'current':100},'current_A':.1}
        class Adc:
            last_raw=13200
            def __init__(s,*a):pass
            def voltage(s,ch):return 3.3 if ch==3 else 1.65
        with patch.object(p,'NamedGpioGate',Gate),patch.object(p,'WordI2c',lambda *a:Bus()),patch.object(p,'Ina226',Ina),patch.object(p,'Ads1115',Adc):r=p.raw_diagnostics('/dev/test')
        self.assertNotIn(True,requested);self.assertFalse(r['calibrated']);self.assertFalse(r['motion_approved']);self.assertEqual(len(r['raw_adc']),4)
if __name__=='__main__':unittest.main()


