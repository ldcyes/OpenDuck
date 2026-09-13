"""TI INA226/ADS1115 real-register adapters. No simulated live measurements."""
import math,time

class PowerFault(RuntimeError):pass

def signed16(v):return v-65536 if v&0x8000 else v

class WordI2c:
    """16-bit big-endian registers using atomic repeated-start I2C messages."""
    def __init__(self,path,address):
        from smbus2 import SMBus,i2c_msg
        self.bus=SMBus(path);self.address=address;self.msg=i2c_msg
    def read16(self,reg):
        w=self.msg.write(self.address,[reg]);r=self.msg.read(self.address,2)
        self.bus.i2c_rdwr(w,r);b=bytes(r)
        if len(b)!=2:raise PowerFault('short I2C word')
        return int.from_bytes(b,'big')
    def write16(self,reg,value):self.bus.i2c_rdwr(self.msg.write(self.address,[reg,value>>8,value&255]))
    def close(self):self.bus.close()

class Ina226:
    CONFIG=0x4327 # AVG4, 1.1ms bus +1.1ms shunt, continuous.
    CAL=0x0a00 #0.00512/(0.001 A*0.002 ohm)
    def __init__(self,bus,cal,clock=time.monotonic,sleep=time.sleep):
        self.bus=bus;self.cal=cal;self.clock=clock;self.sleep=sleep
    def initialize(self):
        if self.bus.read16(0xfe)!=0x5449 or self.bus.read16(0xff)&0xfff0!=0x2260:raise PowerFault('INA226 identity mismatch')
        self.bus.write16(0,self.CONFIG);self.bus.write16(5,self.CAL)
        self.verify()
    def verify(self):
        if self.bus.read16(0)!=self.CONFIG or self.bus.read16(5)!=self.CAL:raise PowerFault('INA226 config/calibration reset or readback mismatch')
    def sample(self):
        started=self.clock();self.verify()
        while True:
            flags=self.bus.read16(6)
            if flags&4:raise PowerFault('INA226 overflow')
            if flags&8:break
            if self.clock()-started>.025:raise PowerFault('INA226 conversion not fresh')
            self.sleep(.001)
        shunt=signed16(self.bus.read16(1));bus=self.bus.read16(2);current=signed16(self.bus.read16(4));power=self.bus.read16(3)
        if abs(shunt)>=32760 or abs(current)>=32760 or bus&0x8000:raise PowerFault('INA226 ADC/current saturated')
        return {'monotonic_s':started,'bus_V':bus*.00125*self.cal['bus_gain']+self.cal['bus_offset_V'],
          'current_A':current*.001*self.cal['current_gain']+self.cal['current_offset_A'],
          'power_register_W':power*.025,'shunt_V':shunt*.0000025,
          'raw':{'shunt':shunt,'bus':bus,'current':current,'power':power}}

class Ads1115:
    def __init__(self,bus,clock=time.monotonic,sleep=time.sleep):self.bus=bus;self.clock=clock;self.sleep=sleep;self.last_raw=None
    def voltage(self,channel):
        if type(channel)is not int or not 0<=channel<=3:raise ValueError('ADS1115 channel')
        # OS1, single ended, PGA +/-4.096V, single shot,128SPS, comparator disabled.
        cfg=0x8000|((channel+4)<<12)|(1<<9)|(1<<8)|(4<<5)|3
        self.bus.write16(1,cfg);started=self.clock();self.sleep(.009)
        while True:
            got=self.bus.read16(1)
            if got&0x7fff!=cfg&0x7fff:raise PowerFault('ADS1115 config/mux mismatch')
            if got&0x8000:break
            if self.clock()-started>.030:raise PowerFault('ADS1115 conversion timeout')
            self.sleep(.001)
        raw=signed16(self.bus.read16(0));self.last_raw=raw
        if abs(raw)>=32760:raise PowerFault('ADS1115 saturated')
        return raw*.000125

def ntc_temperature(voltage,excitation,pullup,r25,beta):
    if not all(math.isfinite(v) for v in (voltage,excitation,pullup,r25,beta)) or min(excitation,pullup,r25,beta)<=0:
        raise PowerFault('invalid NTC parameters')
    ratio=voltage/excitation
    if ratio<=.02 or ratio>=.98:raise PowerFault('NTC open/short/out-of-range')
    r=pullup*ratio/(1-ratio)
    return 1/(1/298.15+math.log(r/r25)/beta)-273.15


class NamedGpioGate:
    """libgpiod2 character-device API; locate exactly one of each DT line name."""
    def __init__(self):
        import glob,gpiod
        self.g=gpiod;self.requests=[];self.req=None;self.ok=None
        names=['MICRODUCK_RUN_REQ','MICRODUCK_RUN_OK'];found={n:[] for n in names}
        for path in sorted(glob.glob('/dev/gpiochip*')):
            chip=gpiod.Chip(path)
            try:
                for offset in range(chip.get_info().num_lines):
                    name=chip.get_line_info(offset).name
                    if name in found:found[name].append((path,offset))
            finally:chip.close()
        if any(len(found[n])!=1 for n in names):raise PowerFault('require unique DT GPIO line names: '+str(found))
        try:
            for name in names:
                path,offset=found[name][0];chip=gpiod.Chip(path)
                try:
                    output=name==names[0]
                    kw={'direction':gpiod.line.Direction.OUTPUT if output else gpiod.line.Direction.INPUT,'active_low':False}
                    if output:kw['output_value']=gpiod.line.Value.INACTIVE
                    request=chip.request_lines(consumer='microduck-r8-power',config={offset:gpiod.LineSettings(**kw)})
                finally:chip.close()
                self.requests.append(request)
                if output:self.req=(request,offset)
                else:self.ok=(request,offset)
        except BaseException:
            self.close();raise
    def set_request(self,value):
        if self.req is None:raise PowerFault('RUN_REQ GPIO unavailable')
        self.req[0].set_value(self.req[1],self.g.line.Value.ACTIVE if value else self.g.line.Value.INACTIVE)
    def permitted(self):
        if self.ok is None:raise PowerFault('RUN_OK GPIO unavailable')
        return self.ok[0].get_value(self.ok[1])==self.g.line.Value.ACTIVE
    def close(self):
        try:
            if self.req:self.set_request(False)
        finally:
            for request in reversed(self.requests):request.release()
            self.requests=[];self.req=None;self.ok=None


def raw_diagnostics(i2c_device):
    """Capture actual registers for external reference calibration; RUN stays low."""
    gate=None;buses=[]
    try:
        gate=NamedGpioGate();gate.set_request(False)
        for address in (0x40,0x41,0x42,0x48):buses.append(WordI2c(i2c_device,address))
        nominal={'current_gain':1.,'current_offset_A':0.,'bus_gain':1.,'bus_offset_V':0.}
        ina=[Ina226(b,nominal)for b in buses[:3]]
        for s in ina:s.initialize()
        current=[s.sample()for s in ina];adc=Ads1115(buses[3]);v=[];raw=[]
        for ch in range(4):v.append(adc.voltage(ch));raw.append(adc.last_raw)
        return {'calibrated':False,'motion_approved':False,'run_req':False,'source':'live hardware registers; nominal datasheet scale only',
          'battery':current[0],'servo':current[1],'brake':current[2],'raw_adc':raw,'adc_nominal_volts':v,
          'ntc_ratios':([x/v[3]for x in v[:3]]if 3.1<=v[3]<=3.5 else None),'monotonic_s':time.monotonic()}
    finally:
        try:
            if gate:gate.close()
        finally:
            for b in buses:b.close()
