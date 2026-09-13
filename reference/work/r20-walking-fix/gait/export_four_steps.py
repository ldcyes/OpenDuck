"""Two exact repeats of a physically translated two-step candidate; no state resets."""
from screen_stances import *
from kinematic_inputs import foot_stats,margin
from kinematic_inputs import SOURCES as KINEMATIC_SOURCES
import bisect,math
P=OUT/'guarded_cycle_keypoints_v1.json';D=json.loads(P.read_text());assert D['status']=='GUARDED_TWO_TRUE_STEPS_EXACT_CYCLE_CANDIDATE_NOT_APPROVED'
K=D['keypoints'];NAMES=[j['joint']for j in J];VMAX=10.;AMAX=40.;key=[];segments=[];cursor=0.

def moved(k,cycle):
 r=json.loads(json.dumps(k));r['cycle_index']=cycle;r['phase']=f'cycle{cycle+1}_'+r['phase'];r['source_cycle_checkpoint_index']=K.index(k)
 r['base_transform_m'][0][3]+=cycle*.01
 for t in r['foot_target_transforms_mm'].values():t[0][3]+=cycle*10
 r['time_s']=None;return r

def append(b):
 global cursor
 if not key:b['time_s']=0.;key.append(b);return
 a=key[-1];dq=max(abs(b['q_HOME_delta_deg'][n]-a['q_HOME_delta_deg'][n])for n in NAMES);dt=max(float(b.get('minimum_hold_s',0)),.12,1.875*dq/VMAX,math.sqrt(10*math.sqrt(3)/3*dq/AMAX));cursor+=dt;b['time_s']=cursor;i=len(key)-1
 segments.append(dict(id=f'{i:04d}',phase=b['phase'],start_s=a['time_s'],end_s=cursor,q0=a['q_HOME_delta_deg'],q1=b['q_HOME_delta_deg'],support_link=b['support_link'],support_links=b['support_links'],contact_mode=b['contact_mode'],desired_load_fraction_start=a['desired_load_fraction_by_link'],desired_load_fraction_end=b['desired_load_fraction_by_link'],source_keypoint_indices=[i,i+1],cycle_index=b['cycle_index'],source_cycle_checkpoint_index=b['source_cycle_checkpoint_index'],peak_joint_speed_deg_s=1.875*dq/dt,peak_joint_acceleration_deg_s2=10*math.sqrt(3)/3*dq/dt**2))
 key.append(b)
for cycle in [0,1]:
 for i,k in enumerate(K):
  r=moved(k,cycle)
  if not key:
   append(r);h=moved(k,cycle);h['phase']+='_hold';append(h)
  elif i==0:
   # Start matches the preceding translated end exactly, in both q and world.
   assert max(abs(r['q_HOME_delta_deg'][n]-key[-1]['q_HOME_delta_deg'][n])for n in NAMES)<1e-12
   assert np.max(abs(np.array(r['base_transform_m'])-np.array(key[-1]['base_transform_m'])))<1e-9
   for l in feet:assert np.max(abs(np.array(r['foot_target_transforms_mm'][l])-np.array(key[-1]['foot_target_transforms_mm'][l])))<1e-8
   append(r)
  else:append(r)
TIMES=[r['time_s']for r in key];sampletimes=sorted(set([round(float(t),12)for t in np.arange(0,cursor,.025)]+[round(t,12)for t in TIMES]+[round(cursor,12)]));samples=[];metrics=[]
for ti,t in enumerate(sampletimes):
 i=min(max(bisect.bisect_right(TIMES,t)-1,0),len(key)-2);a,b=key[i],key[i+1];dt=b['time_s']-a['time_s'];u=min(1.,max(0.,(t-a['time_s'])/dt));v=10*u**3-15*u**4+6*u**5;dv=(30*u*u-60*u**3+30*u**4)/dt;ddv=(60*u-180*u*u+120*u**3)/dt**2
 q={n:a['q_HOME_delta_deg'][n]*(1-v)+b['q_HOME_delta_deg'][n]*v for n in NAMES};qdot={n:(b['q_HOME_delta_deg'][n]-a['q_HOME_delta_deg'][n])*dv for n in NAMES};qddot={n:(b['q_HOME_delta_deg'][n]-a['q_HOME_delta_deg'][n])*ddv for n in NAMES};targets={l:np.array(a['foot_target_transforms_mm'][l],float)for l in feet}
 for l in feet:targets[l][:3,3]=np.array(a['foot_target_transforms_mm'][l])[:3,3]*(1-v)+np.array(b['foot_target_transforms_mm'][l])[:3,3]*v
 T=transforms(J,q);support=b['support_link'];B=targets[support]@np.linalg.inv(T[support]);load={l:a['desired_load_fraction_by_link'][l]*(1-v)+b['desired_load_fraction_by_link'][l]*v for l in feet};st=EV.evaluate(q,to_m(B),support);C=np.array(st['COM_world_m'])*1000;fs={l:foot_stats(B@T[l],f)for l,f in feet.items()};err={l:float(np.max(np.linalg.norm(apply_points(f['sole'],B@T[l])-apply_points(f['sole'],targets[l]),axis=1)))for l,f in feet.items()};mode=b['contact_mode']
 samples.append(dict(time_s=t,q_HOME_delta_deg=q,joint_velocity_deg_s=qdot,joint_acceleration_deg_s2=qddot,base_transform_m=to_m(B),support_link=support,support_links=b['support_links'],contact_mode=mode,desired_load_fraction_by_link=load,phase=b['phase'],segment_id=segments[i]['id'],source_keypoint_indices=[i,i+1],source_linear_q_parameter=v))
 metrics.append(dict(time_s=t,phase=b['phase'],contact_mode=mode,feet=fs,foot_target_max_errors_mm=err,static_designated_support=st,desired_load_fraction_by_link=load))
 if ti%500==0:print('EXPORT',ti,len(sampletimes),flush=True)
assert max(abs(samples[-1]['q_HOME_delta_deg'][n]-samples[0]['q_HOME_delta_deg'][n])for n in NAMES)<1e-10
assert np.linalg.norm((np.array(samples[-1]['base_transform_m'])-np.array(samples[0]['base_transform_m']))[:3,3]-[.02,0,0])<1e-9
single=[r for r in metrics if r['contact_mode']!='double'];assert single
summary=dict(sample_count=len(samples),duration_s=cursor,cycle_count=2,swing_event_count=4,steps_by_foot=dict(ankle_left=2,ankle_right=2),net_root_and_both_feet_translation_mm=[20,0,0],max_analytic_joint_speed_deg_s=max(s['peak_joint_speed_deg_s']for s in segments),max_analytic_joint_acceleration_deg_s2=max(s['peak_joint_acceleration_deg_s2']for s in segments),max_sampled_single_support_static_utilization=max(r['static_designated_support']['max_utilization']for r in single),minimum_sampled_single_support_COP_margin_mm=min(r['static_designated_support']['COP_margin_mm']for r in single),max_sampled_foot_target_point_error_mm=max(max(r['foot_target_max_errors_mm'].values())for r in metrics),minimum_actual_TPU_mesh_z_mm=min(f['min_material_z_mm']for r in metrics for f in r['feet'].values()),max_actual_foot_plane_tilt_deg=max(f['sole_tilt_deg']for r in metrics for f in r['feet'].values()),max_sample_gap_s=max(np.diff(sampletimes)),keypoint_count=len(key),moving_and_hold_segments=len(segments))
sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in [P,Path(__file__),ROOT/'work/r20-walking-fix/gait/build_guarded_cycle.py',ROOT/'work/r20-walking-fix/gait/reserved_endpoints.json',ROOT/'work/r20-walking-fix/gait/screen_stances.py',ROOT/'work/r20-walking-fix/dynamics/quasistatic.py',ROOT/'work/r19-walking-simulation/physics/model_contract_v2.json',ROOT/'work/r19-walking-simulation/physics/current_robot_v2.xml',ROOT/'work/r19-walking-simulation/path_support/kinematic_inputs.py',ROOT/'work/r18-leg-hip-covers/review/motion_core.py']};sources.update(D['guard_sources']);sources.update(KINEMATIC_SOURCES)
report=dict(schema='R19_DIAGNOSTIC_Q_BASE_V1',status='R20_FOUR_FORWARD_STEPS_GUARDED_QUASISTATIC_CANDIDATE',physical_approved=False,geometry_approved=False,dynamic_approved=False,duration_s=cursor,maximum_sample_period_s=.025,units=dict(time='s',joint='HOME-delta degree',base_transform_translation='m'),root_policy='Reference root reconstructed from designated stance foot. Actual dynamic root must remain free; no pose resets at cycle boundaries.',time_law='Per q0/q1 segment a common quintic 10u^3-15u^4+6u^5, with analytic peak speed<=10deg/s and acceleration<=40deg/s². All exact knots are retained in samples so linear resampling never shortcuts across different q line segments.',initial_q_HOME_delta_deg=samples[0]['q_HOME_delta_deg'],initial_base_transform_m=samples[0]['base_transform_m'],net_planned_translation_mm=[20,0,0],summary=summary,keypoints=key,samples=samples,sources=sources)
p=OUT/'trajectory_4steps_v1.json';p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');trajsha=hashlib.sha256(p.read_bytes()).hexdigest()
(OUT/'trajectory_segments_v1.json').write_text(json.dumps(dict(status='EXACT_SHARED_SCALAR_Q_SEGMENTS',trajectories=dict(forward=dict(trajectory=str(p.relative_to(ROOT)),trajectory_sha256=trajsha,dynamic_motion_segment_count=len(segments),segments=segments))),ensure_ascii=False,indent=2)+'\n')
(OUT/'trajectory_support_v1.json').write_text(json.dumps(dict(status='FINITE_AND_INTERPOLATED_RIGID_FOOT_AND_STATIC_DIAGNOSTIC',trajectory_sha256=trajsha,summary=summary,samples=metrics,sources=sources),ensure_ascii=False,indent=2)+'\n')
# Both hypothetical single-support evaluations on every unique numerical q keypoint.
ss=[]
for r in K:ss.append(dict(phase=r['phase'],contact_mode=r['contact_mode'],q_HOME_delta_deg=r['q_HOME_delta_deg'],base_transform_m=r['base_transform_m'],hypothetical_single_support_by_link={l:EV.evaluate(r['q_HOME_delta_deg'],r['base_transform_m'],l)for l in feet}))
(OUT/'keypoint_both_support_static_v1.json').write_text(json.dumps(dict(status='TWO_SINGLE_SUPPORT_HYPOTHESES_NOT_DOUBLE_SUPPORT_LOAD_SOLUTION',rows=ss,sources=sources),ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True);print('TRAJECTORY_SHA',trajsha,flush=True)
