"""Only bounded high-level intents cross the model/robot boundary."""
import json
import math

from microduck_rk.actuators import ROBOT_PROFILE
from microduck_rk.motion_limits import INTENT_LIMITS as LIMITS


def number(value, name, low, high):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not low <= value <= high or not math.isfinite(value):
        raise ValueError(f'{name}: finite number in [{low}, {high}] required')
    return float(value)


def object_keys(value, allowed, name):
    if not isinstance(value,dict) or any(k not in allowed for k in value):
        raise ValueError(f'{name}: object with only {sorted(allowed)} required')


def strict_json(text):
    def pairs(items):
        out={}
        for k,v in items:
            if k in out: raise ValueError(f'duplicate JSON field: {k}')
            out[k]=v
        return out
    def bad(v): raise ValueError(f'nonfinite JSON token: {v}')
    return json.loads(text,object_pairs_hook=pairs,parse_constant=bad)


def validate_intent(raw):
    object_keys(raw,set(LIMITS)|{'duration_s'},'intent')
    if 'duration_s' not in raw: raise ValueError('intent.duration_s required')
    out={'duration_s':number(raw['duration_s'],'duration_s',.02,3.)}
    for k,bound in LIMITS.items():
        if isinstance(bound,tuple):
            values=raw.get(k,[0.]*len(bound))
            if not isinstance(values,list) or len(values)!=len(bound):raise ValueError(f'{k}: expected {len(bound)} values')
            out[k]=[number(v,f'{k}[{i}]',*(b if isinstance(b,tuple) else (-b,b))) for i,(v,b) in enumerate(zip(values,bound))]
        else:
            out[k]=number(raw.get(k,0.),k,0. if k=='mouth' else -bound,bound)
    return out


def validate_plan(raw, robot_profile=ROBOT_PROFILE):
    object_keys(raw,{'robot_profile','say','intent'},'plan')
    if raw.get('robot_profile')!=robot_profile:raise ValueError('robot_profile mismatch')
    say=raw.get('say','')
    if not isinstance(say,str) or len(say)>1000:raise ValueError('say: string <=1000 characters required')
    return {'robot_profile':robot_profile,'say':say,'intent':validate_intent(raw.get('intent'))}


def command_values(intent):
    return [intent['vx'],intent['vy'],intent['yaw']]+intent['head']+[0.,0.]+intent['body']+[0.]
