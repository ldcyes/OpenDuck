"""Single R8 software ceiling; provisional geometry, never a motion approval.
Head entries are deltas from measured HOME. Mouth zero is the closed target.
Tightening this file changes its SHA and invalidates old command/calibration/policy data.
"""
import hashlib,json,math
HEAD_NAMES=('neck_pitch','head_pitch','head_yaw','head_roll')
HEAD_DEGREES=((-20.,5.),(-15.,15.),(-15.,15.),(-8.,8.))
HEAD_RANGES=tuple(tuple(math.radians(x) for x in pair) for pair in HEAD_DEGREES)
# Absolute magnitudes retained only for symmetric non-head sampling helpers.
HEAD_CAPS=tuple(max(abs(lo),abs(hi)) for lo,hi in HEAD_RANGES)
MOUTH_MAX=math.radians(12.)
MOUTH_STRUCTURAL_TORQUE_NM=.05
INTENT_LIMITS={'vx':.15,'vy':.10,'yaw':.5,'head':HEAD_RANGES,'body':(.03,.15,.15),'mouth':MOUTH_MAX}
COMMAND_CAPS=(.15,.10,.5)+HEAD_CAPS+(0.,0.,.03,.15,.15,0.)
COMMAND_RANGES=tuple((-x,x) for x in COMMAND_CAPS[:3])+HEAD_RANGES+tuple((-x,x) for x in COMMAND_CAPS[7:])
SUPPORT_CONTEXT_CONTRACT={'default':'head_home_locked','stable_s':.5,'sample_max_age_s':.1,'sample_max_gap_s':.1,'position_tolerance_rad':math.radians(.5),'velocity_tolerance_rad_s':.03,'supported_gyro_max_rad_s':.05,'supported_tilt_max_deg':5.,'supported_contact_automatically_proven':False}
CONTRACT={'support_context':SUPPORT_CONTEXT_CONTRACT,'revision':'R8-V11-head-envelope-provisional-20260906-3','head_names':HEAD_NAMES,'head_delta_degrees':HEAD_DEGREES,
 'mouth_absolute_degrees':(0.,12.),'mouth_structural_torque_limit_Nm':MOUTH_STRUCTURAL_TORQUE_NM,'mouth_load_acceptance_required':True,'head_reference':'measured_home_rad','command_ranges':COMMAND_RANGES,'geometry_basis':'V11 synchronized head envelope; final skin recheck pending',
 'physical_sweep_approved':False,'single_support_dynamic_approved':False}
def limits_sha256():return hashlib.sha256(json.dumps(CONTRACT,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def valid_number(x):return not isinstance(x,bool) and isinstance(x,(int,float)) and math.isfinite(x)
def validate_frame(frame,require_binding=False):
    if not isinstance(frame,dict):raise ValueError('command frame object required')
    digest=frame.get('motion_limits_sha256')
    if (require_binding or digest is not None) and digest!=limits_sha256():raise ValueError('command motion limits contract mismatch')
    c=frame.get('commands');m=frame.get('mouth_rad');t=frame.get('monotonic_s')
    if not isinstance(c,(list,tuple)) or len(c)!=13 or any(not valid_number(x) or not lo<=x<=hi for x,(lo,hi) in zip(c,COMMAND_RANGES)):
        raise ValueError('command outside R8 motion limits contract')
    if not valid_number(m) or not 0<=m<=MOUTH_MAX or not valid_number(t):raise ValueError('mouth/lease outside R8 motion limits contract')
    return {**frame,'commands':list(c),'motion_limits_sha256':limits_sha256()}
def validate_joint_range(j):
    name=j['name']
    if name in HEAD_NAMES:
        lo,hi=HEAD_RANGES[HEAD_NAMES.index(name)]
        if j['min_rad']<j['home_rad']+lo-1e-12 or j['max_rad']>j['home_rad']+hi+1e-12:raise ValueError(name+': measured range exceeds head contract')
    elif name=='mouth':
        if j['home_rad']!=0 or j['min_rad']!=0 or not 0<j['max_rad']<=MOUTH_MAX:raise ValueError('mouth requires closed zero and range inside0..12degrees')


def validate_mouth_acceptance(d):
    """Require measured actuator-setting coverage; never infer torque from milliamps.

    Reported peak bound must include measurement uncertainty and the tested transient/
    blocked-load behavior. This validates declared evidence, not its physical truth.
    """
    from .actuators import current_raw
    a=d.get('mouth_load_acceptance')
    if not isinstance(a,dict) or a.get('verified') is not True or a.get('full_travel_and_blocked_load_verified') is not True:
        raise ValueError('mouth requires measured load acceptance')
    if a.get('structural_limit_Nm')!=MOUTH_STRUCTURAL_TORQUE_NM:
        raise ValueError('mouth structural torque limit must be0.05Nm')
    peak=a.get('observed_peak_upper_bound_Nm')
    if not valid_number(peak) or not 0<peak<=MOUTH_STRUCTURAL_TORQUE_NM:
        raise ValueError('mouth measured peak torque bound exceeds structure limit or is absent')
    if not isinstance(a.get('report'),str) or not a['report'].strip():
        raise ValueError('mouth requires a physical load measurement report reference')
    j=next((j for j in d.get('joints',[]) if j.get('name')=='mouth' and j.get('id')==34),None)
    if j is None:raise ValueError('mouth ID34 configuration missing')
    raw=a.get('tested_goal_current_raw');gain=a.get('tested_p_gain')
    if type(raw) is not int or not 1<=raw<=300 or current_raw(34,j['current_limit_ma'])>raw:
        raise ValueError('mouth configured goal current exceeds measured setting')
    if type(gain) is not int or gain!=j.get('p_gain'):
        raise ValueError('mouth P gain differs from measured setting')
    step=a.get('tested_max_step_rad');temp=a.get('tested_temperature_max_C')
    if not valid_number(step) or not j['max_step_rad']<=step<=.15:
        raise ValueError('mouth command step exceeds measured setting')
    if not valid_number(temp) or not d['temperature_max']<=temp<=70:
        raise ValueError('mouth temperature acceptance does not cover configured stop')
    for key,lo,hi in [('tested_range_rad',j['min_rad'],j['max_rad']),
                      ('tested_voltage_range_V',d['voltage_hard'],d['voltage_max'])]:
        r=a.get(key)
        if not isinstance(r,(list,tuple)) or len(r)!=2 or not all(valid_number(v) for v in r) or not r[0]<=lo<hi<=r[1]:
            raise ValueError('mouth '+key+' does not cover configured envelope')


def policy_action_scales(names,scale,mode):
    if mode not in ('head_home_locked','supported_double'):raise ValueError('unknown policy motion context')
    return {name:(0. if ((name in HEAD_NAMES)==(mode=='head_home_locked')) else scale) for name in names}
