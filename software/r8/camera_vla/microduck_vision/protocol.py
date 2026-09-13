"""Versioned observation contract; all clock checks use the robot's monotonic clock."""
import base64
import math
import re
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'rk_runtime'))
from microduck_rk.actuators import ROBOT_PROFILE as PROFILE
from microduck_rk.motion_limits import limits_sha256
from microduck_rk.motion_context import MotionContextGuard
CAMERA_PROFILE = 'Waveshare-OS05A10-5MP-USB-A-33123-640x480'

def validate_intent_context(intent,mode):
    from microduck_interaction.schema import command_values,validate_intent
    intent=validate_intent(intent)
    MotionContextGuard([0.]*15,mode,supported_confirmed=mode=='supported_double').validate_commands(command_values(intent),intent['mouth'])
    return intent

def context_binding(state):
    return {k:state[k] for k in ('calibration_sha256','motion_limits_sha256')} | {'motion_context':state['motion_context']['mode']}

def validate_live_state(s):
    c=s.get('motion_context',{})
    if s.get('source')!='live_dynamixel_sflp' or not(s['commissioned'] and s['armed']) or c.get('ready')is not True or c.get('active')is not True:
        raise ValueError('live VLA requires actual active, ready motion context')
    if c['mode']=='head_home_locked' and c.get('head_home_stable')is not True:raise ValueError('actual head HOME lock unavailable')

def validate_submission_state(observation,plan,latest,now_s):
    validate_state(latest);validate_live_state(latest)
    if not number(now_s)or not 0<=now_s-latest['monotonic_s']<=.1:raise ValueError('current runtime state stale or future')
    if context_binding(latest)!=context_binding(observation['state']):raise ValueError('runtime identity/context changed during inference')
    validate_intent_context(plan['intent'],latest['motion_context']['mode'])

def submission_context(o,max_age_s=.75):
    return {**context_binding(o['state']),'capture_monotonic_s':o['capture_monotonic_s'],
            'deadline_monotonic_s':o['capture_monotonic_s']+max_age_s}

STATE_FIELDS = [('positions',15),('velocities',15),('gyro',3),('gravity',3)]
ACTION_NAMES = ['vx','vy','yaw','neck_pitch','head_pitch','head_yaw','head_roll','body_z','body_roll','body_pitch','mouth']
MAX_JPEG = 512_000

def number(v):
    return type(v) in (int,float) and math.isfinite(v)

def validate_state(s):
    if not isinstance(s,dict) or s.get('robot_profile') != PROFILE:
        raise ValueError('wrong robot profile')
    if s.get('motion_limits_sha256')!=limits_sha256():raise ValueError('motion contract mismatch')
    if not isinstance(s.get('motion_context'),dict) or s['motion_context'].get('mode')not in ('head_home_locked','supported_double'):raise ValueError('motion context missing')
    for key,n in STATE_FIELDS:
        a=s.get(key)
        if not isinstance(a,list) or len(a)!=n or not all(number(v) for v in a):
            raise ValueError('invalid measured '+key)
    if not number(s.get('monotonic_s')) or not number(s.get('imu_age_s')) or not 0 <= s['imu_age_s'] <= .03:
        raise ValueError('invalid/stale IMU or clock')
    if type(s.get('commissioned')) is not bool or type(s.get('armed')) is not bool:
        raise ValueError('missing commissioning/armed state')
    if not re.fullmatch('[a-f0-9]{64}',str(s.get('calibration_sha256',''))):
        raise ValueError('invalid calibration hash')

def make_observation(jpeg,state,*,capture_s,now_s,sequence,task,live=False,rotation_deg=180):
    validate_state(state)
    if not all(number(v) for v in (capture_s,now_s)) or not 0 <= now_s-capture_s <= .15:
        raise ValueError('camera delivery is stale or in future')
    if not 0 <= now_s-state['monotonic_s'] <= .1 or abs(capture_s-state['monotonic_s'])>.1:
        raise ValueError('measured state is stale or not aligned to image')
    if live:validate_live_state(state)
    o={'schema':1,'request_id':uuid.uuid4().hex,'robot_profile':PROFILE,'sequence':sequence,
       'capture_monotonic_s':capture_s,'task':task,'state':state,'simulated':not live,
       'image':{'mime':'image/jpeg','camera':'front','camera_profile':CAMERA_PROFILE,'rotation_applied_deg':rotation_deg,'jpeg_base64':base64.b64encode(jpeg).decode()}}
    validate_observation(o)
    return o

def validate_observation(o):
    expected={'schema','request_id','robot_profile','sequence','capture_monotonic_s','task','state','simulated','image'}
    if not isinstance(o,dict) or set(o)!=expected or type(o['schema']) is not int or o['schema']!=1 or o['robot_profile']!=PROFILE:
        raise ValueError('observation schema mismatch')
    if type(o['sequence']) is not int or o['sequence']<0 or type(o['simulated']) is not bool:
        raise ValueError('invalid sequence/mode')
    if not isinstance(o['task'],str) or not 1<=len(o['task'])<=1000 or not re.fullmatch('[a-f0-9]{32}',str(o['request_id'])):
        raise ValueError('invalid task/request ID')
    if not number(o['capture_monotonic_s']):raise ValueError('invalid capture time')
    validate_state(o['state'])
    if abs(o['capture_monotonic_s']-o['state']['monotonic_s'])>.1:raise ValueError('state/image skew')
    if not o['simulated']:validate_live_state(o['state'])
    im=o['image']
    if not isinstance(im,dict) or set(im)!={'mime','camera','camera_profile','rotation_applied_deg','jpeg_base64'} or im['mime']!='image/jpeg' or im['camera']!='front' or im['camera_profile']!=CAMERA_PROFILE:
        raise ValueError('invalid image schema')
    if type(im['rotation_applied_deg']) is not int or im['rotation_applied_deg'] not in (0,180):raise ValueError('unsupported image rotation')
    if not isinstance(im['jpeg_base64'],str) or len(im['jpeg_base64'])>700000:raise ValueError('image too large')
    try:jpeg=base64.b64decode(im['jpeg_base64'],validate=True)
    except Exception as exc:raise ValueError('bad base64') from exc
    if not 4<=len(jpeg)<=MAX_JPEG or not jpeg.startswith(b'\xff\xd8') or not jpeg.endswith(b'\xff\xd9'):
        raise ValueError('invalid JPEG envelope')
    return jpeg

def state_vector(o):
    validate_state(o['state'])
    # The base SmolVLA projection has 32 columns. Use21 measured features; velocities remain in telemetry.
    return [v for key in ('positions','gyro','gravity') for v in o['state'][key]]

class ReplyGate:
    def __init__(self,max_age_s=.75):
        if not number(max_age_s) or not .05<=max_age_s<=1.:raise ValueError('invalid age limit')
        self.max_age_s=max_age_s
        self.last_sequence=-1
    def accept(self,observation,reply,now_s):
        from microduck_interaction.schema import validate_plan
        validate_observation(observation)
        if not number(now_s) or not 0<=now_s-observation['capture_monotonic_s']<=self.max_age_s:
            raise ValueError('VLA reply arrived too late')
        keys={'schema','request_id','sequence','robot_profile','calibration_sha256','motion_limits_sha256','motion_context','plan'}
        if not isinstance(reply,dict) or set(reply)!=keys or type(reply['schema']) is not int or reply['schema']!=1:raise ValueError('reply schema')
        for key in ('request_id','sequence','robot_profile'):
            if reply[key]!=observation[key]:raise ValueError('reply '+key+' mismatch')
        if type(reply['sequence']) is not int or reply['sequence']<=self.last_sequence:raise ValueError('replayed/out-of-order reply')
        for key,value in context_binding(observation['state']).items():
            if reply[key]!=value:raise ValueError('reply identity/context changed: '+key)
        plan=validate_plan(reply['plan'],robot_profile=PROFILE)
        if plan['intent']['duration_s']>1.:raise ValueError('VLA action horizon exceeds 1 second')
        validate_intent_context(plan['intent'],observation['state']['motion_context']['mode'])
        self.last_sequence=reply['sequence']
        return plan
