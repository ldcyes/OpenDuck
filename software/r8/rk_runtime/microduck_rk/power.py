"""CM4 R8 power configuration and latched, fail-closed supervisory state machine."""
import copy,hashlib,json,math,threading,time
from pathlib import Path
from .voltage_limits import WINDOW
from .power_io import PowerFault,ntc_temperature
PLATFORM={'module':'Radxa CM4 RK3576 V1.20','carrier':'Microduck R8 CM4','servo_nominal_V':10.8,'ina_addresses':[64,65,66],'ads_address':72,'shunt_ohm':.002,'current_lsb_A':.001,'ina_config':0x4327,'gpio_run_req':'MICRODUCK_RUN_REQ','gpio_run_ok':'MICRODUCK_RUN_OK','active_high':True,'ntc_MPN':'NTCLE100E3103GB0','voltage_window':WINDOW}
def platform_sha256():return hashlib.sha256(json.dumps(PLATFORM,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def numeric(x,name,low,high):
    if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or not low<=x<=high:raise ValueError(name+' outside measured configuration bounds')
    return x
class PowerConfig:
    def __init__(self,data,sha):self.data=data;self.sha256=sha
    @classmethod
    def load(cls,path):
        raw=Path(path).read_bytes();d=json.loads(raw)
        if d.get('schema')!=1 or d.get('platform')!=PLATFORM:raise ValueError('CM4 R8 power platform mismatch')
        if d.get('measurements_verified')is not True or not isinstance(d.get('measurement_report'),str) or not d['measurement_report'].strip():raise ValueError('physical power calibration report required')
        if not isinstance(d.get('i2c_device'),str) or not d['i2c_device'].startswith('/dev/') or 'REPLACE' in d['i2c_device']:raise ValueError('actual CM4 I2C device required')
        for name in ['battery','servo','brake']:
            c=d['ina226'][name]
            for k,lo,hi in [('current_gain',.8,1.2),('current_offset_A',-.2,.2),('bus_gain',.95,1.05),('bus_offset_V',-.1,.1)]:numeric(c.get(k),name+k,lo,hi)
        numeric(d['adc'].get('gain'),'ADC gain',.95,1.05);numeric(d['adc'].get('offset_V'),'ADC offset',-.1,.1)
        for name in ['battery','module','brake']:
            c=d['ntc'][name];pull=numeric(c.get('pullup_ohm'),name+'pullup',9900,10100)
            r25=numeric(c.get('ratio_at_25C'),name+'25C',.4,.6);r60=numeric(c.get('ratio_at_60C'),name+'60C',.1,.3)
            a=pull*r25/(1-r25);b=pull*r60/(1-r60);beta=math.log(a/b)/(1/298.15-1/333.15)
            numeric(a,name+'measured R25',9000,11000);numeric(beta,name+'measured beta',3500,4500)
        return cls(d,hashlib.sha256(raw).hexdigest())
    def temperature(self,name,voltage,excitation):
        c=self.data['ntc'][name];p=c['pullup_ohm'];r25=p*c['ratio_at_25C']/(1-c['ratio_at_25C']);r60=p*c['ratio_at_60C']/(1-c['ratio_at_60C'])
        beta=math.log(r25/r60)/(1/298.15-1/333.15)
        return ntc_temperature(voltage,excitation,p,r25,beta)

class RegenEnergy:
    """Sampled conservative step-maximum energy estimate, NOT a pulse hardware bound.
    No RUN transition resets history. Process restart loses pre-start observations.
    """
    def __init__(self):
        from collections import deque
        self.segments=deque();self.last_t=None;self.last_p=0.;self.event_J=0.;self.active=False;self.idle_since=None
    def _expire(self,now):
        cutoff=now-30.
        while self.segments and self.segments[0][1]<=cutoff:self.segments.popleft()
    def snapshot(self,now):
        self._expire(now)
        total=sum(p*(b-max(a,now-30.))for a,b,p in self.segments)
        return {'event_active':self.active,'event_J':self.event_J,'rolling30_J':total,'estimated_from_samples':True,'physical_pulse_upper_bound':False}
    def observe(self,sample):
        try:
            t=sample['brake'].get('monotonic_s',sample['monotonic_s']);v=sample['brake']['bus_V'];i=sample['brake']['current_A']
            if any(isinstance(x,bool)or not isinstance(x,(int,float))or not math.isfinite(x)for x in [t,v,i])or v<-.1 or i<-.02:raise PowerFault('invalid brake energy sensor sample/polarity')
        except (KeyError,TypeError)as exc:raise PowerFault('missing brake energy sensor sample')from exc
        if self.last_t is not None:
            dt=t-self.last_t
            if dt<0 or dt>.100000001:raise PowerFault('brake energy sample time gap/reversal')
            if dt==0:return
        else:dt=0.
        p=max(v,0.)*max(i,0.);active=i>.02
        if active and not self.active:self.active=True;self.event_J=0.;self.idle_since=None
        interval_power=max(p,self.last_p)
        if dt:
            self.segments.append((self.last_t,t,interval_power))
            if self.active:self.event_J+=interval_power*dt
        self.last_t=t;self.last_p=p
        s=self.snapshot(t)
        if self.event_J>=20.-1e-9:raise PowerFault('brake event energy estimate reached20J')
        if s['rolling30_J']>=60.-1e-9:raise PowerFault('brake rolling30s energy estimate reached60J')
        if self.active:
            if active:self.idle_since=None
            elif self.idle_since is None:self.idle_since=t
            elif t-self.idle_since>=1.-1e-9:self.active=False;self.event_J=0.;self.idle_since=None

class PowerSupervisor:
    """The only owner of RUN_REQ. Faults remain latched until process restart."""
    def __init__(self,gate,clock=time.monotonic):
        self.gate=gate;self.clock=clock;self.lock=threading.RLock();self.state='OFF';self.fault=None
        self.power=None;self.temperature=None;self.since={};self.heartbeat=None;self.warnings=[];self.preflight_deadline=None;self.control_active=True
        self.energy=RegenEnergy();self.gate.set_request(False)
    def update_power(self,sample):
        with self.lock:
            self.power=copy.deepcopy(sample)
            try:self.energy.observe(sample)
            except Exception as exc:self._trip(exc)
    def update_temperature(self,sample):
        with self.lock:self.temperature=copy.deepcopy(sample)
    def _trip(self,reason):
        self.fault=self.fault or str(reason);self.state='FAULT'
        try:self.gate.set_request(False)
        except Exception as exc:self.fault+='; RUN_REQ low failed: '+str(exc)
    def sensor_fault(self,error):
        with self.lock:self._trip('power sensor/backend fault: '+str(error))
    def _duration(self,key,active,seconds,now):
        if not active:self.since.pop(key,None);return False
        self.since.setdefault(key,now)
        return now-self.since[key]>=seconds-1e-9
    def _validate(self,require_rail):
        if self.fault:raise PowerFault(self.fault)
        now=self.clock();self.warnings=[]
        for s,age,name in [(self.power,.100,'power'),(self.temperature,.250,'temperature')]:
            if not isinstance(s,dict):raise PowerFault('missing '+name+' sensor sample')
            t=s.get('monotonic_s')
            if not isinstance(t,(int,float)) or not math.isfinite(t) or not 0<=now-t<=age:raise PowerFault(name+' sample stale/future')
        for name in ['battery','servo','brake']:
            row=self.power[name]
            for k in ['bus_V','current_A']:
                if isinstance(row[k],bool) or not math.isfinite(row[k]):raise PowerFault('invalid '+name+' '+k)
        bv=self.power['battery']['bus_V'];sv=self.power['servo']['bus_V']
        bi=abs(self.power['battery']['current_A']);si=abs(self.power['servo']['current_A'])
        if bv<=12.0 or bv>17.0 or self._duration('battery_uv',bv<12.4,.2,now):raise PowerFault('battery voltage stop')
        if bv<12.8:self.warnings.append('battery voltage low')
        if bi>=13.0 or self._duration('battery_oc',bi>=11.5,.1,now):raise PowerFault('battery current stop')
        if si>=11.5 or self._duration('servo_oc',si>=10.0,.2,now):raise PowerFault('servo current stop')
        if sv>WINDOW['run_max_V']:raise PowerFault('servo voltage high')
        if self.power['brake']['bus_V']>WINDOW['run_max_V']:raise PowerFault('brake sense voltage high')
        if require_rail and self.power['brake']['bus_V']<=WINDOW['brake_sense_min_V']:raise PowerFault('brake sense voltage low/disconnected')
        if require_rail and (sv<=WINDOW['run_W3_hard_V'] or self._duration('servo_uv',sv<WINDOW['run_W3_soft_V'],WINDOW['run_W3_soft_s'],now)):raise PowerFault('servo voltage low')
        exc=self.temperature['excitation_V']
        if not isinstance(exc,(int,float)) or not math.isfinite(exc) or not 3.1<=exc<=3.5:raise PowerFault('NTC excitation out of range')
        for name,warn,stop in [('battery',45,50),('module',65,75),('brake',55,65)]:
            v=self.temperature['temperatures_C'][name]
            if isinstance(v,bool) or not math.isfinite(v) or not -20<=v<stop:raise PowerFault(name+' temperature stop/invalid')
            if v>=warn:self.warnings.append(name+' temperature warning')
    def enable(self,spin=None,preflight=False):
        spin=spin or (lambda:time.sleep(.005))
        try:
            with self.lock:
                if self.fault:raise PowerFault(self.fault)
                if self.state!='OFF':raise PowerFault('power enable only from OFF; no automatic fault reset')
                self._validate(False);self.state='STARTING';self.heartbeat=self.clock();self.gate.set_request(True);deadline=self.clock()+.5
            while True:
                with self.lock:
                    self._validate(False)
                    if self.gate.permitted() and self.power['servo']['bus_V']>=WINDOW['startup_W3_min_V'] and self.power['brake']['bus_V']>WINDOW['brake_sense_min_V']:
                        self.state='ON';self.heartbeat=self.clock();self.control_active=not preflight;self.preflight_deadline=self.clock()+5.;return
                    if self.clock()>=deadline:raise PowerFault('RUN_OK/servo rail startup timeout')
                spin()
        except BaseException as exc:
            with self.lock:self._trip(exc)
            raise
    def check(self):
        with self.lock:
            try:
                self._validate(self.state=='ON')
                if self.state!='ON':raise PowerFault('power not ON')
                if not self.gate.permitted():raise PowerFault('RUN_OK hardware permission lost')
                self.heartbeat=self.clock()
                return {'state':self.state,'power':copy.deepcopy(self.power),'temperature':copy.deepcopy(self.temperature),'warnings':list(self.warnings),'run_ok':True,'brake_energy':self.energy.snapshot(self.clock())}
            except Exception as exc:self._trip(exc);raise PowerFault(self.fault) from exc
    def watchdog(self):
        with self.lock:
            try:
                if self.state=='ON':
                    self._validate(True)
                    if not self.gate.permitted():raise PowerFault('RUN_OK hardware permission lost')
                    if self.control_active and self.clock()-self.heartbeat>.100:raise PowerFault('control heartbeat stale')
                    if not self.control_active and self.clock()>self.preflight_deadline:raise PowerFault('powered preflight exceeded5s')
                elif self.fault:raise PowerFault(self.fault)
            except Exception as exc:self._trip(exc);raise PowerFault(self.fault) from exc
    def activate_control(self):
        with self.lock:
            self.check();self.control_active=True;self.heartbeat=self.clock()
    def close(self):
        with self.lock:
            self.gate.set_request(False)
            if self.state!='FAULT':self.state='CLOSED'


class PowerSystem:
    """Real fixed hardware factory. Injectable only by Python tests, no mock CLI mode."""
    def __init__(self,config):
        from .power_io import WordI2c,Ina226,Ads1115,NamedGpioGate
        self._closed=False;self.started_current=False;self.started_temperature=False;self.config=config;self.stop=threading.Event();self.threads=[];self.buses=[];self.gate=None;self.supervisor=None
        try:
            self.gate=NamedGpioGate();self.supervisor=PowerSupervisor(self.gate)
            for address in (0x40,0x41,0x42,0x48):self.buses.append(WordI2c(config.data['i2c_device'],address))
            self.current=[Ina226(self.buses[i],config.data['ina226'][n])for i,n in enumerate(['battery','servo','brake'])]
            self.adc=Ads1115(self.buses[3])
        except BaseException:self.close();raise
    def start(self):
        try:
            for sensor in self.current:sensor.initialize()
            for function in (self._current_worker,self._temperature_worker,self._watchdog_worker):
                t=threading.Thread(target=function,daemon=True);self.threads.append(t);t.start()
                if function==self._current_worker:self.started_current=True
                if function==self._temperature_worker:self.started_temperature=True
        except BaseException:self.close();raise
    def _current_worker(self):
        try:
            while not self.stop.is_set():
                begin=time.monotonic();rows=[s.sample()for s in self.current]
                self.supervisor.update_power({'monotonic_s':min(x['monotonic_s']for x in rows),'battery':rows[0],'servo':rows[1],'brake':rows[2]})
                self.stop.wait(max(0,.02-(time.monotonic()-begin)))
        except Exception as exc:self.supervisor.sensor_fault(exc)
        finally:
            for b in self.buses[:3]:b.close()
    def _temperature_worker(self):
        try:
            while not self.stop.is_set():
                begin=time.monotonic();volts=[];raw=[]
                for channel in range(4):volts.append(self.adc.voltage(channel));raw.append(self.adc.last_raw)
                gain=self.config.data['adc']['gain'];offset=self.config.data['adc']['offset_V'];v=[x*gain+offset for x in volts]
                if not 3.1<=v[3]<=3.5:raise PowerFault('NTC excitation out of range')
                temps={n:self.config.temperature(n,v[i],v[3])for i,n in enumerate(['battery','module','brake'])}
                self.supervisor.update_temperature({'monotonic_s':begin,'temperatures_C':temps,'excitation_V':v[3],'raw_adc':raw,'adc_volts':volts})
                self.stop.wait(max(0,.125-(time.monotonic()-begin)))
        except Exception as exc:self.supervisor.sensor_fault(exc)
        finally:self.buses[3].close()
    def _watchdog_worker(self):
        try:
            while not self.stop.wait(.01):self.supervisor.watchdog()
        except Exception as exc:self.supervisor.sensor_fault(exc)
    def wait_ready(self):
        end=time.monotonic()+1.
        while True:
            with self.supervisor.lock:
                if self.supervisor.fault:raise PowerFault(self.supervisor.fault)
                if self.supervisor.power is not None and self.supervisor.temperature is not None:return
            if time.monotonic()>end:raise PowerFault('power sensors startup timeout')
            time.sleep(.005)
    def enable(self):self.wait_ready();self.supervisor.enable(preflight=True)
    def activate_control(self):self.supervisor.activate_control()
    def check(self):return self.supervisor.check()
    def close(self):
        if self._closed:return
        self._closed=True
        try:
            if self.supervisor:self.supervisor.close()
            elif self.gate:self.gate.set_request(False)
        finally:
            self.stop.set()
            for t in self.threads:
                if t.ident is not None:t.join(timeout=.15)
            # Running I2C workers own their fd until completion; never recycle a fd under a blocked ioctl.
            for i,b in enumerate(self.buses):
                if (i<3 and not self.started_current) or (i==3 and not self.started_temperature):b.close()
            if self.gate:self.gate.close()
