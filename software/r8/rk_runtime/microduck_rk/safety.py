import json
import math
from pathlib import Path
from .contract import finite,IDS
from .motion_limits import validate_frame

# Legacy R1 diagnostic retained for old test evidence; R8 run NEVER calls it.
POWER_GROUPS={'J6':[22,23,24],'J7':[12,13,14],'J8':[31,32,33],'J9':[20,21,30],'J10':[10,11,34]}


def check_power_groups(currents):
    finite(currents,15,'servo supply currents mA')
    by_id=dict(zip(IDS,map(abs,currents)))
    if sum(by_id.values())>5000: raise RuntimeError('reported servo supply current >5A prototype total target')
    for name,ids in POWER_GROUPS.items():
        if sum(by_id[i] for i in ids)>2000: raise RuntimeError(f'{name}: reported current >2A branch target')


def check_joint_currents(currents,calibration):
    """Per-actuator indication only; mixed motor/input currents are not rail current."""
    from .actuators import current_raw, spec_for_id
    finite(currents,15,'servo indicated currents mA')
    for measured,j in zip(currents,calibration.joints):
        limit=current_raw(j['id'],j['current_limit_ma'])*spec_for_id(j['id']).current_mA_per_raw
        # Allow one hardware count, not an unbounded percentage, for readback quantization.
        if abs(measured)>limit+spec_for_id(j['id']).current_mA_per_raw:
            raise RuntimeError(f'ID{j["id"]}: indicated current exceeds configured limit')


class Guard:
    def __init__(self,config):
        self.config=config; self.low_since=None

    def check(self,now,volts,temps,gravity,command_time):
        finite(volts,15,'voltages'); finite(temps,15,'temperatures'); finite(gravity,3,'gravity')
        if not math.isfinite(command_time) or not 0<=now-command_time<=.3:
            raise RuntimeError('operator command lease expired (>300ms)')
        if max(volts)>=self.config.get('voltage_max',11.8):
            raise RuntimeError('servo overvoltage')
        if min(volts)<=self.config['voltage_hard']:
            raise RuntimeError('hard undervoltage')
        if min(volts)<self.config['voltage_soft']:
            if self.low_since is None: self.low_since=now
            if now-self.low_since>=.2: raise RuntimeError('undervoltage sustained 200ms')
        else:
            self.low_since=None
        if max(temps)>=self.config['temperature_max']:
            raise RuntimeError('servo temperature limit')
        if gravity[2]>-.5:
            raise RuntimeError('trunk tilt exceeds 60 degrees; recovery policies disabled for R8 bringup')


def read_command(path):
    d=validate_frame(json.loads(Path(path).read_text()),require_binding=True)
    return d['commands'],d['mouth_rad'],d['monotonic_s']


def mouth_step(requested,previous,minimum,maximum,max_step,dt=.02):
    finite([requested,previous,minimum,maximum,max_step,dt],6,'mouth command')
    if not minimum<=requested<=maximum or not minimum<=previous<=maximum:
        raise ValueError('mouth target outside measured travel')
    if max_step<=0 or dt<=0: raise ValueError('invalid mouth step/time')
    step=min(.5*dt,max_step)  # Independent non-policy mouth, maximum 0.5 rad/s.
    return previous+max(-step,min(step,requested-previous))
