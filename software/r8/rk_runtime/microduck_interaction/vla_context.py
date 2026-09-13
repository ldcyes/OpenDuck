"""Robot-clock provenance for high-level VLA intents, checked at local acceptance."""
import re
from .schema import number,object_keys,command_values
from microduck_rk.motion_limits import limits_sha256

def validate_context(c,now,intent):
    object_keys(c,{'capture_monotonic_s','deadline_monotonic_s','calibration_sha256','motion_limits_sha256','motion_context'},'VLA context')
    capture=number(c.get('capture_monotonic_s'),'capture',0.,1e15)
    deadline=number(c.get('deadline_monotonic_s'),'observation deadline',0.,1e15)
    if not 0<deadline-capture<=1. or not capture<=now<deadline:raise ValueError('VLA observation expired or future at local acceptance')
    if c.get('motion_limits_sha256')!=limits_sha256()or not re.fullmatch('[a-f0-9]{64}',str(c.get('calibration_sha256',''))):raise ValueError('VLA calibration/motion binding invalid')
    from microduck_rk.motion_context import MotionContextGuard
    mode=c.get('motion_context')
    MotionContextGuard([0.]*15,mode,supported_confirmed=mode=='supported_double').validate_commands(command_values(intent),intent['mouth'])
    return dict(c)
