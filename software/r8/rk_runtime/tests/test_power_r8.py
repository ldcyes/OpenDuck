import copy,importlib,importlib.util,json,tempfile,unittest
from pathlib import Path
class Clock:
    def __init__(self):self.t=1.
    def __call__(self):return self.t
    def sleep(self,t):self.t+=t
class Gate:
    def __init__(self):self.req=False;self.ok=True;self.events=[];self.closed=False
    def set_request(self,v):
        if self.closed:raise RuntimeError('GPIO already released')
        self.req=v;self.events.append(v)
    def permitted(self):return self.ok
    def close(self):self.set_request(False);self.closed=True
class PowerTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('microduck_rk.power'),'power lifecycle not implemented')
        self.p=importlib.import_module('microduck_rk.power');self.c=Clock();self.g=Gate()
    def sample(self,bv=15.,sv=10.8,bi=1.,si=1.,br=0.):
        return {'monotonic_s':self.c(),'battery':{'bus_V':bv,'current_A':bi},'servo':{'bus_V':sv,'current_A':si},'brake':{'bus_V':sv,'current_A':br}}
    def advance(self,m,seconds,**kwargs):
        end=self.c()+seconds
        while self.c()<end-1e-12:
            self.c.sleep(min(.02,end-self.c()));m.update_power(self.sample(**kwargs));m.update_temperature(self.temps())
    def temps(self,battery=25,module=30,brake=25):return {'monotonic_s':self.c(),'temperatures_C':dict(battery=battery,module=module,brake=brake),'excitation_V':3.3}
    def monitor(self):
        m=self.p.PowerSupervisor(self.g,clock=self.c);m.update_power(self.sample());m.update_temperature(self.temps());return m
    def arm(self,m):m.enable(lambda:self.c.sleep(.001));m.check();self.assertTrue(self.g.req)
    def test_default_gate_low_and_explicit_enable_only(self):
        m=self.monitor();self.assertFalse(self.g.req);self.arm(m);m.close();self.assertFalse(self.g.req)
    def test_no_temperature_no_sensor_no_power_enable(self):
        for absent in ['power','temperature']:
            m=self.p.PowerSupervisor(self.g,clock=self.c)
            if absent!='power':m.update_power(self.sample())
            if absent!='temperature':m.update_temperature(self.temps())
            with self.assertRaises(RuntimeError):m.enable(lambda:None)
            self.assertFalse(self.g.req)
    def test_allow_servo_off_before_start_then_wait_for_measured_rail(self):
        m=self.monitor();m.update_power(self.sample(sv=0))
        def spin():self.c.sleep(.01);m.update_power(self.sample(sv=10.4))
        m.enable(spin);self.assertTrue(self.g.req)
    def test_startup_timeout_latches_off(self):
        m=self.monitor();m.update_power(self.sample(sv=0))
        def spin():self.c.sleep(.01);m.update_power(self.sample(sv=0));m.update_temperature(self.temps())
        with self.assertRaises(RuntimeError):m.enable(spin)
        self.assertFalse(self.g.req)
        with self.assertRaises(RuntimeError):m.enable(spin)
    def test_permission_drop_lowers_request(self):
        m=self.monitor();self.arm(m);self.g.ok=False
        with self.assertRaisesRegex(RuntimeError,'RUN_OK'):m.check()
        self.assertFalse(self.g.req)
    def test_stale_or_nonfinite_or_future_samples_latch_off(self):
        for kind in ['stale','future','nan','missing']:
            self.g=Gate();m=self.monitor();self.arm(m)
            if kind=='stale':self.c.sleep(.11)
            elif kind=='future':x=self.sample();x['monotonic_s']+=.1;m.update_power(x)
            elif kind=='nan':m.update_power(self.sample(bi=float('nan')))
            else:m.update_power({'monotonic_s':self.c()})
            with self.assertRaises(RuntimeError):m.check()
            self.assertFalse(self.g.req)
    def test_current_debounce_uses_elapsed_time_and_cannot_rearm(self):
        m=self.monitor();self.arm(m);m.update_power(self.sample(bi=11.6));m.check()
        self.advance(m,.101,bi=11.6)
        with self.assertRaisesRegex(RuntimeError,'battery current'):m.check()
        self.assertFalse(self.g.req)
        m.update_power(self.sample())
        with self.assertRaises(RuntimeError):m.enable(lambda:None)
    def test_immediate_overcurrent_overvoltage_and_thermal(self):
        for what,kw in [('p',{'bi':13}),('p',{'si':11.5}),('p',{'sv':11.66}),('p',{'bv':12}),('t',{'battery':50}),('t',{'module':75}),('t',{'brake':65})]:
            self.g=Gate();m=self.monitor();self.arm(m)
            if what=='p':m.update_power(self.sample(**kw))
            else:m.update_temperature(self.temps(**kw))
            with self.assertRaises(RuntimeError):m.check()
            self.assertFalse(self.g.req)
    def test_moderate_regeneration_permitted_but_extreme_rejected(self):
        m=self.monitor();self.arm(m);m.update_power(self.sample(si=-2));m.check()
        m.update_power(self.sample(si=-12))
        with self.assertRaises(RuntimeError):m.check()
    def test_sensor_worker_fault_cannot_leave_request_high(self):
        m=self.monitor();self.arm(m);m.sensor_fault(OSError('missing ADC'))
        self.assertFalse(self.g.req)
        with self.assertRaisesRegex(RuntimeError,'missing ADC'):m.check()
    def test_main_loop_heartbeat_watchdog(self):
        m=self.monitor();self.arm(m);self.advance(m,.101)
        with self.assertRaisesRegex(RuntimeError,'heartbeat'):m.watchdog()
        self.assertFalse(self.g.req)
    def test_unverified_template_and_wrong_platform_rejected(self):
        d=json.loads((Path(__file__).parents[1]/'config/power.template.json').read_text())
        for key,value in [('measurements_verified',False),('platform',{'module':'ZERO3W'})]:
            x=copy.deepcopy(d);x[key]=value
            with tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp)/'p.json';p.write_text(json.dumps(x))
                with self.assertRaises(ValueError):self.p.PowerConfig.load(p)

    def test_powered_preflight_has_deadline_without_false_100ms_trip(self):
        m=self.monitor();m.enable(lambda:None,preflight=True);self.advance(m,.2);m.watchdog()
        m.activate_control();self.advance(m,.101)
        with self.assertRaisesRegex(RuntimeError,'heartbeat'):m.watchdog()
    def test_actual_threaded_worker_failure_cuts_gate(self):
        import time,types,math
        from unittest.mock import patch
        self.assertTrue(hasattr(self.p,'PowerSystem'),'real sensor workers missing')
        class Sensor:
            def __init__(s,*args,**kwargs):s.fail=False
            def initialize(s):pass
            def sample(s):
                if s.fail:raise OSError('removed INA226')
                return {'monotonic_s':time.monotonic(),'bus_V':15. if s is system.current[0] else 10.8,'current_A':1.}
        class ADC:
            last_raw=13200
            def __init__(s,*a):pass
            def voltage(s,ch):return 3.3 if ch==3 else 1.65
        class Bus:
            def close(s):pass
        data={'i2c_device':'/dev/test-only','ina226':{'battery':{},'servo':{},'brake':{}},'adc':{'gain':1.,'offset_V':0.}}
        cfg=types.SimpleNamespace(data=data,temperature=lambda *a:25)
        with patch('microduck_rk.power_io.Ina226',Sensor),patch('microduck_rk.power_io.Ads1115',ADC),patch('microduck_rk.power_io.WordI2c',lambda *a:Bus()),patch('microduck_rk.power_io.NamedGpioGate',return_value=self.g):
            system=self.p.PowerSystem(cfg)
            try:
                system.start();system.enable();system.check();self.assertTrue(self.g.req)
                system.current[0].fail=True
                end=time.monotonic()+.3
                while self.g.req and time.monotonic()<end:time.sleep(.005)
                self.assertFalse(self.g.req)
                with self.assertRaisesRegex(RuntimeError,'removed INA226'):system.check()
            finally:system.close();system.close()
        self.assertFalse(self.g.req)
    def test_missing_third_ina_prevents_enable(self):
        m=self.monitor();s=self.sample();del s['brake'];m.update_power(s)
        with self.assertRaisesRegex(RuntimeError,'brake'):m.enable(lambda:None)
        self.assertFalse(self.g.req)
    def test_brake_event_trip_lowers_gate_and_history_survives_close(self):
        m=self.monitor();self.arm(m);self.advance(m,.22,br=10.)
        self.assertFalse(self.g.req)
        with self.assertRaisesRegex(RuntimeError,'event'):m.check()
        before=m.energy.snapshot(self.c())['rolling30_J'];m.close()
        self.assertAlmostEqual(m.energy.snapshot(self.c())['rolling30_J'],before)
    def test_physical_factory_requires_address42_before_any_enable(self):
        import types
        from unittest.mock import patch
        class Bus:
            def __init__(s,path,address):s.address=address;s.closed=False
            def close(s):s.closed=True
        class Sensor:
            def __init__(s,b,*a):s.b=b
            def initialize(s):
                if s.b.address==0x42:raise OSError('missing0x42')
        cfg=types.SimpleNamespace(data={'i2c_device':'/dev/test-only','ina226':{'battery':{},'servo':{},'brake':{}}})
        with patch('microduck_rk.power_io.WordI2c',Bus),patch('microduck_rk.power_io.Ina226',Sensor),patch('microduck_rk.power_io.Ads1115',lambda *a:object()),patch('microduck_rk.power_io.NamedGpioGate',return_value=self.g):
            p=self.p.PowerSystem(cfg)
            with self.assertRaisesRegex(OSError,'0x42'):p.start()
            self.assertNotIn(True,self.g.events);self.assertTrue(all(b.closed for b in p.buses))
    def test_brake_bus_sense_disconnected_blocks_start_and_stops_motion(self):
        m=self.monitor();s=self.sample();s['brake']['bus_V']=0.;m.update_power(s)
        def spin():
            self.c.sleep(.02);s=self.sample();s['brake']['bus_V']=0.;m.update_power(s);m.update_temperature(self.temps())
        with self.assertRaisesRegex(RuntimeError,'startup timeout'):m.enable(spin)
        self.assertFalse(self.g.req)
        self.g=Gate();m=self.monitor();self.arm(m);self.c.sleep(.02);s=self.sample();s['brake']['bus_V']=0.;m.update_power(s)
        with self.assertRaisesRegex(RuntimeError,'brake sense'):m.check()
        self.assertFalse(self.g.req)
if __name__=='__main__':unittest.main()

