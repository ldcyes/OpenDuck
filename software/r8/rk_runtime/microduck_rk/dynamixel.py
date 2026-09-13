from .actuators import validate_motor_qualification
"""U2D2 + fixed R8 XM430/XC330 protocol 2.0; no DXL IMU ID200 is queried."""
import math
from .voltage_limits import WINDOW
from .motion_limits import validate_mouth_acceptance
from .contract import IDS
from .actuators import spec_for_id, spec_for_model, current_raw, validate_joint_configuration


def signed(x,bits):
    return x-(1<<bits) if x&(1<<(bits-1)) else x


class Dynamixels:
    def __init__(self,path,calibration,baud=1000000):
        import dynamixel_sdk as sdk
        self.sdk=sdk; self.cal=calibration
        self.port=sdk.PortHandler(path); self.packet=sdk.PacketHandler(2.)
        if not self.port.openPort() or not self.port.setBaudRate(baud):
            raise RuntimeError('U2D2 port/baud could not be opened')
        self.group=sdk.GroupSyncRead(self.port,self.packet,126,21)
        self.health=sdk.GroupSyncRead(self.port,self.packet,70,1)
        for i in IDS:
            if not self.group.addParam(i): raise RuntimeError('duplicate servo ID')
            self.health.addParam(i)
        self.writer=sdk.GroupSyncWrite(self.port,self.packet,116,4)

    def _check(self,result,error=0):
        if result!=self.sdk.COMM_SUCCESS or error:
            raise RuntimeError(f'Dynamixel: {self.packet.getTxRxResult(result)} / {self.packet.getRxPacketError(error)}')

    def read_register(self,i,address,size):
        value,result,error=getattr(self.packet,f'read{size}ByteTxRx')(self.port,i,address)
        self._check(result,error); return value

    def write_register(self,i,address,size,value):
        result,error=getattr(self.packet,f'write{size}ByteTxRx')(self.port,i,address,value)
        self._check(result,error)

    def torque_off(self):
        self._enable_prepared=False
        failures=[]
        for i in IDS:
            try: self.write_register(i,64,1,0)
            except Exception as exc: failures.append(f'{i}: {exc}')
        return failures

    def close(self):
        self.port.closePort()

    def _require_startup_firmware(self,i):
        firmware=self.read_register(i,6,1);minimum=spec_for_id(i).minimum_firmware
        if firmware<minimum:
            raise RuntimeError(f'ID{i}: firmware {firmware}; {spec_for_id(i).name} requires firmware >={minimum}. '
                               'Upgrade with official ROBOTIS tools before commissioning or motion; inspect remains available.')

    def _precheck(self):
        validate_joint_configuration(self.cal.joints)
        for j in self.cal.joints:
            i=j['id'];torque=self.read_register(i,64,1)
            if torque!=0:raise RuntimeError(f'ID{i} reg64={torque}, expected torque off')
            model=self.read_register(i,0,2);want=spec_for_id(i).model_number
            if model!=want:raise RuntimeError(f'ID{i}: model {model}, expected {want} ({spec_for_id(i).name})')
            self._require_startup_firmware(i)

    def _settings(self,j):
        # Hardware voltage/temperature shutdown supplements the 50 Hz software guard.
        return [(11,1,5),(38,2,current_raw(j['id'],j['current_limit_ma'])),
                (9,1,0),(20,4,0),(10,1,0),(31,1,70),(32,2,round(WINDOW['firmware_max_V']*10)),(34,2,round(WINDOW['firmware_min_V']*10)),(63,1,53)]

    def verify(self):
        self._precheck()
        for j in self.cal.joints:
            i=j['id']
            for address,size,want in [(60,1,0)]+self._settings(j):
                got=self.read_register(i,address,size)
                if got!=want:
                    raise RuntimeError(f'ID{i} reg{address}={got}, expected {want}; run commission with torque off')
            if self.read_register(i,70,1):raise RuntimeError(f'ID{i}: hardware error latched')

    def commission(self):
        validate_joint_configuration(self.cal.joints)
        failures=self.torque_off()
        if failures:raise RuntimeError('; '.join(failures))
        # All models, firmware and torque state must pass before any EEPROM mutation.
        self._precheck()
        for j in self.cal.joints:
            i=j['id']
            if self.read_register(i,60,1)!=0:self.write_register(i,60,1,0)
            if self.read_register(i,60,1)!=0:raise RuntimeError(f'ID{i}: reg60 failed zero readback; commissioning stopped')
            for address,size,value in self._settings(j):
                if self.read_register(i,address,size)!=value:self.write_register(i,address,size,value)
        self.verify()

    def inspect(self):
        result=[]
        for i in IDS:
            model=self.read_register(i,0,2);firmware=self.read_register(i,6,1)
            spec=spec_for_model(model)
            startup=self.read_register(i,60,1) if spec and firmware>=spec.minimum_firmware else None
            result.append({'id':i,'model':model,'firmware':firmware,'startup_configuration':startup,'mode':self.read_register(i,11,1),
                           'torque':self.read_register(i,64,1),'raw_tick':signed(self.read_register(i,132,4),32),
                           'volts':self.read_register(i,144,2)/10.,'temperature':self.read_register(i,146,1)})
        return result

    def read(self):
        self._check(self.group.txRxPacket())
        ticks=[]; velocity=[]; current=[]; current_raw_values=[]; volts=[]; temps=[]
        for i,j in zip(IDS,self.cal.joints):
            if not self.group.isAvailable(i,126,21): raise RuntimeError(f'missing servo {i}')
            ticks.append(signed(self.group.getData(i,132,4),32))
            velocity.append(signed(self.group.getData(i,128,4),32)*.229*2*math.pi/60*j['direction'])
            raw=signed(self.group.getData(i,126,2),16);current_raw_values.append(raw)
            current.append(raw*spec_for_id(i).current_mA_per_raw)
            volts.append(self.group.getData(i,144,2)/10.)
            temps.append(self.group.getData(i,146,1))
        return {'positions':self.cal.positions(ticks),'velocities':velocity,'current_ma':current,'current_raw':current_raw_values,'volts':volts,'temps':temps,'raw_ticks':ticks}

    def write(self,positions):
        ticks=self.cal.ticks(positions); self.writer.clearParam()
        try:
            for i,t in zip(IDS,ticks):
                if not self.writer.addParam(i,list(t.to_bytes(4,'little'))): raise RuntimeError('goal construction failed')
            self._check(self.writer.txPacket())
        finally:
            self.writer.clearParam()

    def check_health(self):
        self._check(self.health.txRxPacket())
        for i in IDS:
            if not self.health.isAvailable(i,70,1) or self.health.getData(i,70,1):
                raise RuntimeError(f'servo {i}: missing response or hardware alarm')

    def prepare_enable(self):
        """Slow verified RAM setup stays TorqueOff, before actual HOME stability sampling."""
        self._enable_prepared=False
        validate_mouth_acceptance(self.cal.data)
        validate_motor_qualification(self.cal.data)
        self.verify()
        try:
            for j in self.cal.joints:
                i=j['id']
                self.write_register(i,98,1,0)  # Clear watchdog error before setting goals.
                self.write_register(i,80,2,0); self.write_register(i,82,2,0)
                self.write_register(i,84,2,j['p_gain'])
                self.write_register(i,102,2,current_raw(i,j['current_limit_ma']))
                self.write_register(i,108,4,0); self.write_register(i,112,4,0)
            self._enable_prepared=True
        except BaseException:
            self.torque_off()
            raise

    def enable(self,initial,check_ready=None):
        if not getattr(self,'_enable_prepared',False):self.prepare_enable()
        self._enable_prepared=False  # Prepared state cannot be reused after a partial attempt.
        try:
            if check_ready:check_ready()
            self.write(initial)  # Adopt actual measured pose before torque is enabled.
            for i in IDS:
                if check_ready:check_ready()
                self.write_register(i,64,1,1)
                if check_ready:check_ready()
                self.write_register(i,98,1,5)  # 100ms bus watchdog; not a physical power cutoff.
            if check_ready:check_ready()
        except BaseException:
            # Partial enable must release every responding joint, including earlier IDs.
            self.torque_off()
            raise
