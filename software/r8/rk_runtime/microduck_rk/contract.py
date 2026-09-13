"""Physical units and the pinned upstream 61 -> 14 policy contract."""
import hashlib
import json
import math
from pathlib import Path
from .voltage_limits import WINDOW
from .motion_limits import limits_sha256, validate_joint_range, validate_mouth_acceptance
from .power import platform_sha256
from .actuators import ROBOT_PROFILE, validate_joint_configuration, configuration_sha256, validate_motor_qualification

JOINT_NAMES = ['left_hip_yaw', 'left_hip_roll', 'left_hip_pitch', 'left_knee', 'left_ankle',
               'neck_pitch', 'head_pitch', 'head_yaw', 'head_roll', 'mouth',
               'right_hip_yaw', 'right_hip_roll', 'right_hip_pitch', 'right_knee', 'right_ankle']
IDS = [20,21,22,23,24,30,31,32,33,34,10,11,12,13,14]
HOME = [0.,-.0873,-.4579,-.0049,.4530,.3491,.3491,0.,0.,0.,0.,.0873,.4579,.0049,-.4530]
POLICY_SLOTS = [i for i in range(15) if i != 9]


def finite(values, n, name):
    if not isinstance(values,(list,tuple)) or len(values) != n or not all(not isinstance(v,bool) and isinstance(v, (int,float)) and math.isfinite(v) for v in values):
        raise ValueError(f'{name}: expected {n} finite values')
    return list(values)


def observation(gyro, gravity, positions, velocities, previous, commands, home=HOME):
    finite(positions,15,'positions'); finite(velocities,15,'velocities'); finite(home,15,'home')
    return (finite(gyro,3,'gyro') + finite(gravity,3,'gravity') +
            [positions[i]-home[i] for i in POLICY_SLOTS] + [velocities[i] for i in POLICY_SLOTS] +
            finite(previous,14,'previous action') + finite(commands,13,'commands'))


def action_targets(action, mouth, home, scale):
    finite(action,14,'action'); finite(home,15,'home'); finite([mouth,scale],2,'target parameters')
    result = list(home)
    for i,a in zip(POLICY_SLOTS, action):
        result[i] += a * scale
    result[9] = mouth
    return result


class Calibration:
    def __init__(self, data, digest):
        self.data, self.sha256 = data, digest
        self.joints = data['joints']

    @classmethod
    def load(cls, path, motion=False):
        raw = Path(path).read_bytes(); d = json.loads(raw)
        if d.get('schema') != 2 or d.get('robot') != ROBOT_PROFILE:
            raise ValueError('wrong calibration schema/robot')
        if [j['name'] for j in d['joints']] != JOINT_NAMES or [j['id'] for j in d['joints']] != IDS:
            raise ValueError('calibration joint order/IDs differ from policy contract')
        validate_joint_configuration(d['joints'])
        if motion:
            if d.get('motion_limits_sha256')!=limits_sha256():raise ValueError('motion limits contract mismatch')
            if d.get('hardware_platform_sha256')!=platform_sha256():raise ValueError('CM4 hardware platform mismatch')
            power_sha=d.get('power_configuration_sha256')
            if not isinstance(power_sha,str) or len(power_sha)!=64 or any(c not in '0123456789abcdef' for c in power_sha):raise ValueError('measured power calibration configuration SHA required')
            validate_mouth_acceptance(d)
            validate_motor_qualification(d)
            flags=('calibrated','imu_mount_verified','dynamics_verified','thermal_verified','power_verified')
            if any(d.get(k) is not True for k in flags):
                raise ValueError('calibration incomplete: measured calibration, IMU, dynamics, thermal and power acceptance required')
            if any(not isinstance(d.get(k),str) or not d[k].strip() for k in ('measurement_report','thermal_report','power_report')):
                raise ValueError('calibration requires physical acceptance report references')
            finite(d['imu_sensor_to_trunk_wxyz'],4,'IMU mount')
            for j in d['joints']:
                finite([j[k] for k in ('zero_tick','direction','min_rad','max_rad','home_rad','max_step_rad')],6,j['name'])
                if j['direction'] not in [-1,1] or not (0 <= j['zero_tick'] <= 4095):
                    raise ValueError('invalid encoder calibration')
                if not (j['min_rad'] <= j['home_rad'] < j['max_rad'] if j['name']=='mouth' else j['min_rad'] < j['home_rad'] < j['max_rad']) or not 0 < j['max_step_rad'] <= .15:
                    raise ValueError('invalid joint range/step calibration')
                validate_joint_range(j)
                if type(j['p_gain']) is not int or not 0 < j['p_gain'] <= 16383:
                    raise ValueError('calibrated integer P gain required')
            finite([d['action_scale'],d['voltage_soft'],d['voltage_hard'],d['voltage_max'],d['temperature_max']],5,'limits')
            if (d['voltage_hard'],d['voltage_soft'],d['voltage_max']) != (WINDOW['servo_readback_stop_V'],WINDOW['servo_readback_soft_V'],WINDOW['firmware_max_V']):
                raise ValueError('R8 voltage limits must protect the common 10..12 V servo range')
            if not 0 < d['action_scale'] <= 1 or not 30 <= d['temperature_max'] <= 70:
                raise ValueError('invalid action/temperature limit')
        return cls(d, hashlib.sha256(raw).hexdigest())

    @property
    def drive_sha256(self):
        return configuration_sha256(self.joints)

    @property
    def home(self):
        return [j['home_rad'] for j in self.joints]

    def positions(self, ticks):
        finite(ticks,15,'encoder ticks')
        return [(t-j['zero_tick'])*j['direction']*2*math.pi/4096 for t,j in zip(ticks,self.joints)]

    def ticks(self, positions):
        finite(positions,15,'joint targets')
        out=[]
        for p,j in zip(positions,self.joints):
            if not j['min_rad'] <= p <= j['max_rad']:
                raise ValueError(f'{j["name"]}: target {p:.4f} outside measured travel')
            t=round(j['zero_tick']+p*j['direction']*4096/(2*math.pi))
            if not 0 <= t <= 4095:
                raise ValueError('R8 forbids multi-turn goals even though servo mode 5 supports them')
            out.append(t)
        return out

    def check_step(self, target, previous):
        finite(target,15,'target'); finite(previous,15,'previous target')
        for t,p,j in zip(target,previous,self.joints):
            if abs(t-p) > j['max_step_rad']:
                raise ValueError(f'{j["name"]}: command step exceeds calibrated limit')
        self.ticks(target)
