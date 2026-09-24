"""First-order proportion/drive screening, NOT a new dynamics qualification."""
from pathlib import Path
import copy
import hashlib
import json
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'work/r11-integration/loads'))
from kinematics import Kinematics
sources = {}
def read(path):
    raw = (ROOT/path).read_bytes()
    sources[path] = hashlib.sha256(raw).hexdigest()
    return json.loads(raw)

A = read('work/r25-bottom-head-entry/assembly_selection.json')
G = read('work/r26-proportion-study/baseline_measurements.json')
M = read('work/r25-bottom-head-entry/mass_delta.json')
S = read('work/r21-reduced-sway/gait/support_pair_v4.json')['stance']
reports = [read(f'work/r21-reduced-sway/dynamics/full_v3/{case}/report.json')
           for case in ['nominal','friction_0p5','half_timestep','contact9']]
model = Kinematics(A)
q = np.deg2rad([S['initial_q_HOME_delta_deg'][n] for n in model.names])
_, old_pivots, _ = model.forward(q)
pose_pivots = dict(zip(model.names, old_pivots))
peak = {}
for axis in reports[0]['actuators']:
    name = axis['joint']
    readings = [next(x for x in r['actuators'] if x['joint']==name) for r in reports]
    peak[name] = dict(peak_Nm=max(abs(x['peak_Nm']) for x in readings),
                      RMS_Nm=max(x['RMS_Nm'] for x in readings),
                      unqualified_limit_Nm=axis['cap_Nm'])

cases = []
for label, extension in [('A_cover_first',0),('B_sagittal_10_percent',.10),('C_sagittal_15_percent',.15)]:
    candidate = copy.deepcopy(A)
    joints = {j['joint']:j for j in candidate['joints']}
    for side in ['left','right']:
        hip,knee,ankle = [np.array(joints[side+'_'+n]['pivot_trunk_mm']) for n in ['hip_pitch','knee','ankle']]
        delta1 = (knee-hip)*np.array([extension,0,extension])
        delta2 = (ankle-knee)*np.array([extension,0,extension])
        joints[side+'_knee']['pivot_trunk_mm'] = (knee+delta1).tolist()
        joints[side+'_ankle']['pivot_trunk_mm'] = (ankle+delta1+delta2).tolist()
    mod = Kinematics(candidate)
    _, pv, _ = mod.forward(q)
    pv = dict(zip(mod.names,pv))
    shift = (pose_pivots['left_ankle']-pv['left_ankle'])*1000
    right_shift=(pose_pivots['right_ankle']-pv['right_ankle'])*1000
    h,k,a = [np.array(joints['left_'+n]['pivot_trunk_mm']) for n in ['hip_pitch','knee','ankle']]
    upper,lower = float(np.linalg.norm(k-h)),float(np.linalg.norm(a-k))
    torque_screen = {}
    # Deliberately only sensitivity: proportional load and moment-arm assumption.
    # It does not redistribute contact, account for extra links, or certify capacity.
    factor = M['mass_kg']/reports[0]['mass_kg']*(1+extension)
    for name,v in peak.items():
        if not name.startswith(('left_','right_')): continue
        demand = v['peak_Nm']*factor
        torque_screen[name] = dict(sensitivity_peak_Nm=demand,
            capacity_required_for_15_percent_reserve_Nm=demand/.85,
            ratio_to_old_unqualified_limit=demand/v['unqualified_limit_Nm'])
    cases.append(dict(name=label, sagittal_extension_fraction=extension,
        upper_axis_distance_mm=upper,lower_axis_distance_mm=lower,
        sum_axis_distances_mm=upper+lower,
        HOME_height_proxy_mm=G['HOME_height_mm']+extension*G['lengths']['left']['home_hip_to_ankle_vertical_mm'],
        R21_same_angles_height_proxy_mm=G['R21_preparation_pose_on_R25_height_mm']+shift[2],
        left_foot_reanchor_delta_mm=shift.tolist(), right_foot_reanchor_delta_mm=right_shift.tolist(),
        joints=candidate['joints'],mass_and_arm_sensitivity_factor=factor,
        torque_sensitivity=torque_screen))

cover=next(x for x in G['parts'] if x['name']=='R18P_L_thigh_photo_triangle')
motor=next(x for x in G['parts'] if x['name']=='left_hip_pitch_motor')
cb=np.array(cover['home_bounds_mm']); mb=np.array(motor['home_bounds_mm'])
knee=next(j for j in A['joints'] if j['joint']=='left_knee')['pivot_trunk_mm']
out=dict(status='DESIGN_SCREEN_ONLY_NOT_FABRICATION_OR_GAIT_APPROVAL',physical_approved=False,
    sources=sources, baseline_mass_kg=M['mass_kg'], historical_dynamics_mass_kg=reports[0]['mass_kg'],
    mass_increase_percent=(M['mass_kg']/reports[0]['mass_kg']-1)*100,
    cover=dict(xz_span_mm=(cb[1]-cb[0])[[0,2]].tolist(),
               below_knee_axis_mm=float(knee[2]-cb[0,2]),
               lateral_inner_cover_to_motor_AABB_mm=float(cb[0,1]-mb[1,1]),
               proposed_lower_edge_knee_minus_10_mm=float(knee[2]-10),
               possible_vertical_edge_raise_mm=float(knee[2]-10-cb[0,2]),
               note='AABB projection measurements, not collision clearance or visible-pixel occlusion.'),
    historical_four_case_loads=peak,candidates=cases,
    limits=['Mass-and-arm multiplication is neither an upper bound nor a replacement for inverse dynamics.',
            'New stance must solve both feet, contact distribution, mass/COM/inertia and collisions together.',
            'Height proxies keep the same joint angles, motor housings and foot offsets; no new CAD exists.',
            'Factory stall torque is not a continuous output rating.',
            'Old model actuator caps are unqualified assumptions, not measured low-battery capabilities.'])
(OUT/'candidate_screen.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k not in ['sources','candidates','historical_four_case_loads']},ensure_ascii=False,indent=2))
print([(c['name'],round(c['sum_axis_distances_mm'],2),round(c['HOME_height_proxy_mm'],2),round(c['R21_same_angles_height_proxy_mm'],2)) for c in cases])
