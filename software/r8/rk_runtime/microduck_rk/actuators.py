"""Fixed R8 manufacturing profile. Values come from ROBOTIS model manuals.

Current units describe each actuator's register. They are not interchangeable
supply-current measurements and must not be summed as battery current.
"""
from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_FLOOR
import hashlib
import json
import math

ROBOT_PROFILE = 'Microduck-RK-R8-RK3576-XM430-XC330'
IDS = (20,21,22,23,24,30,31,32,33,34,10,11,12,13,14)
LEG_IDS = frozenset((21,22,23,24,11,12,13,14))
T288_IDS = frozenset((20,10))
XM430_IDS = LEG_IDS | frozenset((30,31))  # neck_pitch and head_pitch carry the enlarged head

@dataclass(frozen=True)
class ActuatorSpec:
    name: str
    model_number: int
    current_mA_per_raw: float
    minimum_firmware: int
    maximum_configured_mA: int
    current_register_max: int
    voltage_min: float
    voltage_max: float

XM430 = ActuatorSpec('XM430-W350-T',1020,2.69,45,2000,1193,10.,14.8)
XC330 = ActuatorSpec('XC330-T181-T',1210,1.,46,300,910,6.5,12.)
XC330_T288 = ActuatorSpec('XC330-T288-T',1220,1.,46,300,910,6.5,12.)
QUALIFICATION = {'revision':'R8-T288-independent-capability-2','XM430_Nm':.90,'T288_Nm':.13,
                 'terminal_voltage_V':10.3,'ambient_C':40.,'duration_s':7200.}

def spec_for_id(servo_id):
    if type(servo_id) is not int or servo_id not in IDS:
        raise ValueError('unknown servo ID in R8 drive profile')
    return XM430 if servo_id in XM430_IDS else (XC330_T288 if servo_id in T288_IDS else XC330)

def spec_for_model(model):
    return next((s for s in (XM430,XC330,XC330_T288) if s.model_number==model),None)

def current_raw(servo_id,milliamps):
    spec=spec_for_id(servo_id)
    if isinstance(milliamps,bool) or not isinstance(milliamps,(int,float)) or not math.isfinite(milliamps):
        raise ValueError('current_limit_ma must be a finite physical current')
    if not spec.current_mA_per_raw <= milliamps <= spec.maximum_configured_mA:
        raise ValueError(f'{spec.name}: current limit outside R8 engineering cap')
    # Decimal avoids rounding a requested cap up to the next hardware count.
    raw=int((Decimal(str(milliamps))/Decimal(str(spec.current_mA_per_raw))).to_integral_value(rounding=ROUND_FLOOR))
    if not 1<=raw<=spec.current_register_max:raise ValueError('current register out of range')
    return raw

def validate_joint_configuration(joints):
    if not isinstance(joints,list) or [j.get('id') for j in joints]!=list(IDS):
        raise ValueError('R8 drive profile requires the exact 15 ordered IDs')
    for j in joints:
        s=spec_for_id(j['id'])
        if type(j.get('model_number')) is not int or j.get('model_number')!=s.model_number or j.get('operating_mode')!=5:
            raise ValueError(f'ID{j["id"]}: R8 requires {s.name} model {s.model_number}, mode 5')
        current_raw(j['id'],j.get('current_limit_ma'))

def profile_sha256():
    profile={'robot':ROBOT_PROFILE,'supply_V':10.8,'motor_capability_requirements':QUALIFICATION,'servos':[{**asdict(spec_for_id(i)),'id':i} for i in IDS]}
    return hashlib.sha256(json.dumps(profile,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def configuration_sha256(joints):
    validate_joint_configuration(joints)
    values=[{'id':j['id'],'model':j['model_number'],'mode':j['operating_mode'],
             'requested_mA':j['current_limit_ma'],'raw_current_limit':current_raw(j['id'],j['current_limit_ma']),
             'p_gain':j.get('p_gain')} for j in joints]
    return hashlib.sha256(json.dumps({'profile':profile_sha256(),'joints':values},sort_keys=True,separators=(',',':')).encode()).hexdigest()


def validate_motor_qualification(data):
    """Independent motor capacity evidence, not permission to load fragile assemblies.

    Actual mounted current/gains/dynamics remain separately calibrated. A qualified
    torque is never converted into a Goal Current or automatically commanded.
    """
    q=data.get('motor_capability_qualification')
    def bad():raise ValueError('independent motor capability qualification incomplete or incompatible')
    def number(v):return not isinstance(v,bool) and isinstance(v,(int,float)) and math.isfinite(v)
    if not isinstance(q,dict) or q.get('verified')is not True or q.get('independent_fixture')is not True:bad()
    if not isinstance(q.get('report'),str)or not q['report'].strip():bad()
    if not all(number(q.get(n))for n in ('duration_s','terminal_voltage_V','ambient_C','maximum_case_C')):bad()
    if q['duration_s']<QUALIFICATION['duration_s']or abs(q['terminal_voltage_V']-10.3)>1e-6 or not 40<=q['ambient_C']<=50:bad()
    if not number(data.get('temperature_max')) or not q['ambient_C']<=q['maximum_case_C']<=data['temperature_max']<=70:bad()
    required=XM430_IDS|T288_IDS;axes=q.get('axes');js={j['id']:j for j in data['joints']}
    if not isinstance(axes,dict)or set(axes)!={str(i)for i in required}:bad()
    for i in required:
        r=axes[str(i)];s=spec_for_id(i);target=QUALIFICATION['XM430_Nm' if i in XM430_IDS else 'T288_Nm']
        if not isinstance(r,dict)or type(r.get('model_number'))is not int or r['model_number']!=s.model_number:bad()
        v=r.get('demonstrated_lower_bound_Nm')
        if not number(v)or v<target:bad()
        ceiling=r.get('tested_current_ceiling_raw')
        if type(ceiling)is not int or not current_raw(i,js[i]['current_limit_ma'])<=ceiling<=s.current_register_max:bad()
