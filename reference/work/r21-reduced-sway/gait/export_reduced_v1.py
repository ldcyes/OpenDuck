"""Two exact repeats of a physically translated two-step candidate; no state resets."""
from reduced_core_v2 import *
import argparse
SOURCES.bind(__file__)
parser=argparse.ArgumentParser();parser.add_argument('--prefix',action='store_true');args=parser.parse_args()
def foot_stats(T,F):
 v=apply_points(F['vertices'],T);p=apply_points(F['sole'],T);normal=T[:3,:3]@np.array([0,0,1.]);angle=np.rad2deg(np.arccos(np.clip(normal[2],-1,1)))
 return dict(min_material_z_mm=float(v[:,2].min()),sole_z_min_mm=float(p[:,2].min()),sole_z_max_mm=float(p[:,2].max()),sole_tilt_deg=float(angle),center_world_mm=p.mean(0).tolist())
import bisect,math
P=OUT/('reduced_prefix_keypoints_v1.json'if args.prefix else'reduced_cycle_keypoints_v2.json');D=SOURCES.json(P);assert D['status']==('FROZEN_TRUE_RIGHT_STEP_PREFIX_NOT_A_COMPLETE_GAIT'if args.prefix else'GUARDED_TWO_TRUE_STEPS_EXACT_CYCLE_CANDIDATE_NOT_APPROVED')
TAG='prefix_v1'if args.prefix else'4steps_v1'
K=D['keypoints'];NAMES=[j['joint']for j in J];VMAX=10.;AMAX=40.;key=[];segments=[];cursor=0.

def moved(k,cycle):
 r=json.loads(json.dumps(k));r['cycle_index']=cycle;r['phase']=f'cycle{cycle+1}_'+r['phase'];r['source_cycle_checkpoint_index']=K.index(k)
 r['base_transform_m'][0][3]+=cycle*.01
 for t in r['foot_target_transforms_mm'].values():t[0][3]+=cycle*10
 r['time_s']=None;return r

def append(b):
 global cursor
 if not key:b['time_s']=0.;key.append(b);return
 a=key[-1];dq=max(abs(b['q_HOME_delta_deg'][n]-a['q_HOME_delta_deg'][n])for n in NAMES);dt=max(float(b.get('minimum_hold_s',0)),.12,1.875*dq/VMAX,math.sqrt(10*math.sqrt(3)/3*dq/AMAX));dt*=1.5 if'left_step_advance'in b['phase']else 1.;cursor+=dt;b['time_s']=cursor;i=len(key)-1
 segments.append(dict(id=f'{i:04d}',phase=b['phase'],start_s=a['time_s'],end_s=cursor,q0=a['q_HOME_delta_deg'],q1=b['q_HOME_delta_deg'],support_link=b['support_link'],support_links=b['support_links'],contact_mode=b['contact_mode'],desired_load_fraction_start=a['desired_load_fraction_by_link'],desired_load_fraction_end=b['desired_load_fraction_by_link'],source_keypoint_indices=[i,i+1],cycle_index=b['cycle_index'],source_cycle_checkpoint_index=b['source_cycle_checkpoint_index'],peak_joint_speed_deg_s=1.875*dq/dt,peak_joint_acceleration_deg_s2=10*math.sqrt(3)/3*dq/dt**2))
 key.append(b)
for cycle in ([0]if args.prefix else[0,1]):
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
# Preserve at least each matched R20 phase duration; only lengthen when local
# speed/acceleration limits need more time. This prevents a fewer-knot solver
# from implicitly accelerating the user-visible walking cycle.
base_segments=SOURCES.json('work/r20-walking-fix/dynamics/retimed_segments_v2.json')['trajectories']['forward']['segments']
base_durations={}
for ss in base_segments:base_durations[ss['phase']]=base_durations.get(ss['phase'],0.)+ss['end_s']-ss['start_s']
phase_timing=[];cursor=0.;key[0]['time_s']=0.
for phase,group in itertools.groupby(segments,key=lambda s:s['phase']):
 group=list(group);old=sum(s['end_s']-s['start_s']for s in group);target=base_durations.get(phase,old);factor=max(1.,target/old);phase_timing.append(dict(phase=phase,kinematic_minimum_s=old,R20_phase_s=target,final_duration_s=old*factor,stretch_factor=factor))
 for ss in group:
  dt=(ss['end_s']-ss['start_s'])*factor;ss['start_s']=cursor;cursor+=dt;ss['end_s']=cursor;ss['peak_joint_speed_deg_s']/=factor;ss['peak_joint_acceleration_deg_s2']/=factor**2;key[ss['source_keypoint_indices'][1]]['time_s']=cursor
TIMES=[r['time_s']for r in key];sampletimes=sorted(set([round(float(t),12)for t in np.arange(0,cursor,.025)]+[round(t,12)for t in TIMES]+[round(cursor,12)]));samples=[];metrics=[]
for ti,t in enumerate(sampletimes):
 i=min(max(bisect.bisect_right(TIMES,t)-1,0),len(key)-2);a,b=key[i],key[i+1];dt=b['time_s']-a['time_s'];u=min(1.,max(0.,(t-a['time_s'])/dt));v=10*u**3-15*u**4+6*u**5;dv=(30*u*u-60*u**3+30*u**4)/dt;ddv=(60*u-180*u*u+120*u**3)/dt**2
 q={n:a['q_HOME_delta_deg'][n]*(1-v)+b['q_HOME_delta_deg'][n]*v for n in NAMES};qdot={n:(b['q_HOME_delta_deg'][n]-a['q_HOME_delta_deg'][n])*dv for n in NAMES};qddot={n:(b['q_HOME_delta_deg'][n]-a['q_HOME_delta_deg'][n])*ddv for n in NAMES};targets={l:np.array(a['foot_target_transforms_mm'][l],float)for l in feet}
 for l in feet:targets[l][:3,3]=np.array(a['foot_target_transforms_mm'][l])[:3,3]*(1-v)+np.array(b['foot_target_transforms_mm'][l])[:3,3]*v
 T=transforms(J,q);support=b['support_link'];B=targets[support]@np.linalg.inv(T[support]);load={l:a['desired_load_fraction_by_link'][l]*(1-v)+b['desired_load_fraction_by_link'][l]*v for l in feet};st=EV.evaluate(q,to_m(B),support);C=np.array(st['COM_world_m'])*1000;fs={l:foot_stats(B@T[l],f)for l,f in feet.items()};err={l:float(np.max(np.linalg.norm(apply_points(f['sole'],B@T[l])-apply_points(f['sole'],targets[l]),axis=1)))for l,f in feet.items()};mode=b['contact_mode']
 samples.append(dict(time_s=t,q_HOME_delta_deg=q,joint_velocity_deg_s=qdot,joint_acceleration_deg_s2=qddot,base_transform_m=to_m(B),support_link=support,support_links=b['support_links'],contact_mode=mode,desired_load_fraction_by_link=load,phase=b['phase'],segment_id=segments[i]['id'],source_keypoint_indices=[i,i+1],source_linear_q_parameter=v))
 metrics.append(dict(time_s=t,phase=b['phase'],contact_mode=mode,body_rpy_deg=Rotation.from_matrix(B[:3,:3]).as_euler('xyz',degrees=True).tolist(),head_point_world_mm=head_point(B,T).tolist(),feet=fs,foot_target_max_errors_mm=err,static_designated_support=st,desired_load_fraction_by_link=load))
 if ti%500==0:print('EXPORT',ti,len(sampletimes),flush=True)
if not args.prefix:
 assert max(abs(samples[-1]['q_HOME_delta_deg'][n]-samples[0]['q_HOME_delta_deg'][n])for n in NAMES)<1e-10
 assert np.linalg.norm((np.array(samples[-1]['base_transform_m'])-np.array(samples[0]['base_transform_m']))[:3,3]-[.02,0,0])<1e-9
single=[r for r in metrics if r['contact_mode']!='double'];assert single
summary=dict(sample_count=len(samples),duration_s=cursor,cycle_count=0 if args.prefix else 2,swing_event_count=1 if args.prefix else 4,steps_by_foot=dict(ankle_left=0 if args.prefix else 2,ankle_right=1 if args.prefix else 2),net_root_and_both_feet_translation_mm=None if args.prefix else[20,0,0],max_analytic_joint_speed_deg_s=max(s['peak_joint_speed_deg_s']for s in segments),max_analytic_joint_acceleration_deg_s2=max(s['peak_joint_acceleration_deg_s2']for s in segments),max_sampled_single_support_static_utilization=max(r['static_designated_support']['max_utilization']for r in single),minimum_sampled_single_support_COP_margin_mm=min(r['static_designated_support']['COP_margin_mm']for r in single),max_sampled_foot_target_point_error_mm=max(max(r['foot_target_max_errors_mm'].values())for r in metrics),minimum_actual_TPU_mesh_z_mm=min(f['min_material_z_mm']for r in metrics for f in r['feet'].values()),max_actual_foot_plane_tilt_deg=max(f['sole_tilt_deg']for r in metrics for f in r['feet'].values()),max_sample_gap_s=max(np.diff(sampletimes)),keypoint_count=len(key),moving_and_hold_segments=len(segments))
summary['matched_phase_timing']=phase_timing;summary['reference_roll_range_deg']=[float(min(r['body_rpy_deg'][0]for r in metrics)),float(max(r['body_rpy_deg'][0]for r in metrics))];summary['reference_top_shell_marker_y_range_mm']=[float(min(r['head_point_world_mm'][1]for r in metrics)),float(max(r['head_point_world_mm'][1]for r in metrics))]
sources={**SOURCES.entries,**D['sources'],**D['guard_sources']}
report=dict(schema='R19_DIAGNOSTIC_Q_BASE_V1',status='R21_REDUCED_SWAY_RIGHT_STEP_PREFIX'if args.prefix else'R21_REDUCED_SWAY_FOUR_FORWARD_STEPS_CANDIDATE',physical_approved=False,geometry_approved=False,dynamic_approved=False,duration_s=cursor,maximum_sample_period_s=.025,units=dict(time='s',joint='HOME-delta degree',base_transform_translation='m'),root_policy='Reference root reconstructed from designated stance foot. Actual dynamic root must remain free; no pose resets at cycle boundaries.',time_law='Per q0/q1 segment a common quintic 10u^3-15u^4+6u^5, with analytic peak speed<=10deg/s and acceleration<=40deg/s². All exact knots are retained in samples so linear resampling never shortcuts across different q line segments.',initial_q_HOME_delta_deg=samples[0]['q_HOME_delta_deg'],initial_base_transform_m=samples[0]['base_transform_m'],net_planned_translation_mm=None if args.prefix else[20,0,0],preparation_status='Prepared stance initialization only; no autonomous HOME-to-stance repositioning is implied',summary=summary,keypoints=key,samples=samples,sources=sources)
p=OUT/f'trajectory_{TAG}.json';p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');trajsha=hashlib.sha256(p.read_bytes()).hexdigest()
(OUT/f'trajectory_segments_{TAG}.json').write_text(json.dumps(dict(status='EXACT_SHARED_SCALAR_Q_SEGMENTS',trajectories=dict(forward=dict(trajectory=str(p.relative_to(ROOT)),trajectory_sha256=trajsha,dynamic_motion_segment_count=len(segments),segments=segments))),ensure_ascii=False,indent=2)+'\n')
(OUT/f'trajectory_support_{TAG}.json').write_text(json.dumps(dict(status='FINITE_AND_INTERPOLATED_RIGID_FOOT_AND_STATIC_DIAGNOSTIC',trajectory_sha256=trajsha,summary=summary,samples=metrics,sources=sources),ensure_ascii=False,indent=2)+'\n')
# Both hypothetical single-support evaluations on every unique numerical q keypoint.
ss=[]
for r in K:ss.append(dict(phase=r['phase'],contact_mode=r['contact_mode'],q_HOME_delta_deg=r['q_HOME_delta_deg'],base_transform_m=r['base_transform_m'],hypothetical_single_support_by_link={l:EV.evaluate(r['q_HOME_delta_deg'],r['base_transform_m'],l)for l in feet}))
(OUT/f'keypoint_both_support_static_{TAG}.json').write_text(json.dumps(dict(status='TWO_SINGLE_SUPPORT_HYPOTHESES_NOT_DOUBLE_SUPPORT_LOAD_SOLUTION',rows=ss,sources=sources),ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True);print('TRAJECTORY_SHA',trajsha,flush=True)
