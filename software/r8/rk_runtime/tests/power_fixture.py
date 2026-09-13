"""Explicit synthetic TEST ONLY values. Never an approved robot configuration."""
import hashlib,json,math
from pathlib import Path
from microduck_rk.power import platform_sha256

def power_data():
    d=json.loads((Path(__file__).parents[1]/'config/power.template.json').read_text())
    d.update(measurements_verified=True,measurement_report='SYNTHETIC TEST ONLY',i2c_device='/dev/test-only')
    for c in d['ina226'].values():c.update(current_gain=1.,current_offset_A=0.,bus_gain=1.,bus_offset_V=0.)
    d['adc']={'gain':1.,'offset_V':0.}
    r=math.exp(3977*(1/333.15-1/298.15))
    for c in d['ntc'].values():c.update(pullup_ohm=10000.,ratio_at_25C=.5,ratio_at_60C=r/(1+r))
    return d

def power_sha():return hashlib.sha256(json.dumps(power_data()).encode()).hexdigest()
