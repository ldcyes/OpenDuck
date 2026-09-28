"""Conditional mouth spring torque subtraction; frozen no-spring R29 evidence is read-only."""
from __future__ import annotations
import hashlib,itertools,json,re,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
BASE=ROOT/'work/r29-r26-dynamics'
sys.path[:0]=[str(ROOT/'work/python-deps'),str(ROOT/'work/r12-motion/python-deps'),str(ROOT/'work/rk-mechanics/python-deps'),str(ROOT/'work/r20-walking-fix/dynamics')]
from scipy.spatial.transform import Rotation  # noqa: E402
from quasistatic import StaticEvaluator  # noqa: E402
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
RUNTIME=ROOT/'work/openduck-publish/repository/software/r8/rk_runtime/microduck_rk/motion_limits.py'
MODEL=BASE/'current_robot_r26_mouth10_films_contact4.xml'
CONTRACT=BASE/'model_contract_r26_mouth10_films_contact4.json'
match=re.search(r'^MOUTH_STRUCTURAL_TORQUE_NM\s*=\s*([0-9.]+)',RUNTIME.read_text(),re.M)
assert match
LIMIT=float(match.group(1));assert LIMIT==.05
wire_mm=.7;diameter_mm=11.5;turns=3;E_N_mm2=200_000.0;spring_count=2;preload_Nm=.020
stiffness_Nm_rad=spring_count*E_N_mm2*wire_mm**4/(64*diameter_mm*turns)/1000
assert abs(stiffness_Nm_rad-.0434964)<1e-6
spring=lambda qdeg:-(preload_Nm+stiffness_Nm_rad*np.deg2rad(qdeg))
paths=[Path(__file__),RUNTIME,MODEL,CONTRACT]
cases=[]
for name in ('R29_final_nominal','R29_final_halfdt','R29_final_friction05','R29_final_contact9'):
    tp=BASE/name/'trajectory.json';rp=BASE/name/'report.json';bp=BASE/name/'interval_joint_bounds.json';paths.extend([tp,rp,bp])
    samples=read(tp)['samples'];report=read(rp);bounds=read(bp)
    t=np.array([s['time_s'] for s in samples]);angle=np.array([s['q_HOME_delta_deg']['mouth_candidate'] for s in samples]);old=np.array([s['joint_torque_Nm']['mouth_candidate'] for s in samples]);assist=preload_Nm+stiffness_Nm_rad*np.deg2rad(angle)
    assert np.max(np.abs(old))<.08
    new=old+assist
    motor=next(x for x in report['actuators']if x['joint']=='mouth_candidate')
    all_lo=min(x['q_min_HOME_deg']['mouth_candidate'] for x in bounds['intervals'])
    all_hi=max(x['q_max_HOME_deg']['mouth_candidate'] for x in bounds['intervals'])
    cases.append(dict(case=name,motor_peak_all_integration_steps_without_spring_Nm=motor['peak_Nm'],
       motor_RMS_all_integration_steps_without_spring_Nm=motor['RMS_Nm'],
       saved_samples=len(samples),saved_sample_signed_torque_without_spring_range_Nm=[float(old.min()),float(old.max())],
       saved_sample_signed_torque_with_hypothetical_spring_range_Nm=[float(new.min()),float(new.max())],
       saved_sample_peak_absolute_with_spring_Nm=float(np.max(np.abs(new))),
       saved_samples_exceeding_0p05_with_spring=int(np.sum(np.abs(new)>LIMIT)),
       saved_sample_over_limit_duration_s=float(np.trapezoid((np.abs(new)>LIMIT).astype(float),t)),
       saved_sample_mouth_angle_range_deg=[float(angle.min()),float(angle.max())],
       all_integration_step_mouth_angle_bound_deg=[float(all_lo),float(all_hi)],
       minimum_spring_assist_in_all_integration_states_Nm=float(preload_Nm+stiffness_Nm_rad*np.deg2rad(all_lo)),
       maximum_spring_assist_in_all_integration_states_Nm=float(preload_Nm+stiffness_Nm_rad*np.deg2rad(all_hi))))
# Static level-base gravity curve at actual head HOME.
ev=StaticEvaluator(MODEL,CONTRACT);dof=ev.m.joint('mouth_candidate').dofadr
T=np.eye(4);T[2,3]=.25
curve=[]
for deg in range(11):
    q={n:0. for n in ev.names};q['mouth_candidate']=float(deg);ev.set_state(q,T)
    bare=float(ev.d.qfrc_bias[dof].item())
    curve.append(dict(mouth_open_deg=deg,motor_static_without_spring_Nm=bare,
      spring_closing_torque_Nm=float(spring(deg)),motor_static_with_spring_Nm=bare-spring(deg)))
# Finite adverse static grid: supported head limits plus body roll from the recorded gait.
# This is not a continuous range proof, nor a moving-head joint trajectory.
head={'neck_pitch':(-20.,0.,5.),'head_pitch':(-15.,0.,15.),'head_yaw':(-15.,0.,15.),'head_roll':(-8.,0.,8.)}
poses=[]
for base_roll,neck,pitch,yaw,roll,mouth in itertools.product((-18.3,0.,18.3),*head.values(),(0.,2.,5.,8.,10.)):
    T[:3,:3]=Rotation.from_euler('x',base_roll,degrees=True).as_matrix()
    q={n:0. for n in ev.names};q.update(neck_pitch=neck,head_pitch=pitch,head_yaw=yaw,head_roll=roll,mouth_candidate=mouth)
    ev.set_state(q,T)
    bare=float(ev.d.qfrc_bias[dof].item());resid=bare-spring(mouth)
    poses.append(dict(base_roll_deg=base_roll,neck_pitch_deg=neck,head_pitch_deg=pitch,head_yaw_deg=yaw,head_roll_deg=roll,mouth_open_deg=mouth,
                      motor_static_without_spring_Nm=bare,motor_static_with_spring_Nm=resid))
adverse=max(poses,key=lambda x:abs(x['motor_static_with_spring_Nm']))
result=dict(status='CONDITIONAL_ANALYTICAL_SPRING_TORQUE_FEASIBILITY_ONLY',physical_approved=False,manufacturing_approved=False,
            active_runtime_guard_Nm=LIMIT,
            spring_design_assumption=dict(springs=spring_count,wire_diameter_mm=wire_mm,mean_coil_diameter_mm=diameter_mm,active_turns_each=turns,
               assumed_elastic_modulus_N_mm2=E_N_mm2,pair_closing_preload_at_0deg_Nm=preload_Nm,pair_stiffness_Nm_rad=stiffness_Nm_rad,
               passive_torque_formula='-0.020 - stiffness_Nm_rad * q_rad',
               vendor_rate_formula='single spring M_per_rad_Nmm = E_N_mm2 * d_mm^4 / (64 * D_mm * n)',
               manufacturer_handbook_url='https://www.federnshop.com/download/pdf/Gutekunst-Federn-1x1-2013-E.pdf',
               manufacturer_handbook_section='Gutekunst Metal Springs 1x1, section 1.4.4, PDF pages 20-21',
               CAD_anchors_rated_material_stress_fatigue_unverified=True),
            four_frozen_trace_analytical_subtractions=cases,static_gravity_curve_head_HOME=curve,
            adverse_static_grid=dict(head_ranges_deg=head,base_roll_samples_deg=[-18.3,0,18.3],mouth_samples_deg=[0,2,5,8,10],grid_samples=len(poses),worst_residual_pose=adverse,
                 maximum_absolute_static_motor_torque_with_spring_Nm=abs(adverse['motor_static_with_spring_Nm'])),
            limitations=['Analytical subtraction uses preexisting no-spring motor-torque samples; it is not a new integrated controller run.',
                         'Saved actuator torques are sampled every 20 ms, so full integration-step spring-compensated peaks remain unproved.',
                         'Finite static head/body-roll grid does not prove the continuous combined-pose envelope or dynamic head/mouth motion.',
                         'The spring has no frozen CAD anchors, spring-leg clearance, manufacturer-rated preload, material stress, or fatigue evidence yet.',
                         'Original R29 no-spring blocked status and 0.05 Nm active software guard remain unchanged.'],
            sources={str(p.relative_to(ROOT)):sha(p) for p in paths})
path=OUT/'analytical_torque.json';path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(path=str(path.relative_to(ROOT)),sha256=sha(path),stiffness_Nm_rad=stiffness_Nm_rad,
 cases=[dict(case=x['case'],saved_peak_Nm=x['saved_sample_peak_absolute_with_spring_Nm'],over_guard=x['saved_samples_exceeding_0p05_with_spring']) for x in cases],
 static_home_range_Nm=[min(x['motor_static_with_spring_Nm'] for x in curve),max(x['motor_static_with_spring_Nm'] for x in curve)],
 adverse_static_abs_Nm=abs(adverse['motor_static_with_spring_Nm']),adverse_pose=adverse),ensure_ascii=False))
