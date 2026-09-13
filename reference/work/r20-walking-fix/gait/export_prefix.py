"""Freeze the solved first true step for early independent free-root evaluation."""
from screen_stances import *
import math, bisect

raw=json.loads((OUT/'guarded_cycle_keypoints_v1.json').read_text())
end=next(i for i,k in enumerate(raw['keypoints']) if k['phase']=='right_landing_still_unloaded')
K=raw['keypoints'][:end+1]
snap=OUT/'first_step_keypoints_v1.json'
assert not snap.exists(), 'Immutable prefix already exists'
snap.write_text(json.dumps(dict(status='FROZEN_FIRST_STEP_PREFIX_NOT_COMPLETE_GAIT',keypoints=K,guard_sources=raw['guard_sources']),indent=2)+'\n')
names=[j['joint'] for j in J];key=[];segments=[];t=0.
for i,b0 in enumerate([K[0]]+K):
 b=json.loads(json.dumps(b0))
 if i:
  a=key[-1];dq=max(abs(b['q_HOME_delta_deg'][n]-a['q_HOME_delta_deg'][n]) for n in names)
  dt=max(float(b.get('minimum_hold_s',0)),.12,1.875*dq/10,math.sqrt(10*math.sqrt(3)/3*dq/40))
  t+=dt;segments.append(dict(id=f'{i-1:04d}',start_s=a['time_s'],end_s=t,q0=a['q_HOME_delta_deg'],q1=b['q_HOME_delta_deg'],phase=b['phase'],contact_mode=b['contact_mode'],support_links=b['support_links']))
 b['time_s']=t;key.append(b)
times=[k['time_s'] for k in key]
ts=sorted(set([round(float(x),12)for x in np.arange(0,t,.025)]+[round(x,12)for x in times]))
samples=[]
for ti in ts:
 i=min(max(bisect.bisect_right(times,ti)-1,0),len(key)-2);a,b=key[i:i+2];dt=b['time_s']-a['time_s'];u=np.clip((ti-a['time_s'])/dt,0,1);s=10*u**3-15*u**4+6*u**5;ds=(30*u*u-60*u**3+30*u**4)/dt;dds=(60*u-180*u*u+120*u**3)/dt**2
 q={n:(1-s)*a['q_HOME_delta_deg'][n]+s*b['q_HOME_delta_deg'][n]for n in names}
 targets={l:np.array(a['foot_target_transforms_mm'][l])for l in feet}
 for l in feet:targets[l][:3,3]=(1-s)*targets[l][:3,3]+s*np.array(b['foot_target_transforms_mm'][l])[:3,3]
 support=b['support_link'];T=transforms(J,q);B=targets[support]@np.linalg.inv(T[support])
 samples.append(dict(time_s=ti,q_HOME_delta_deg=q,joint_velocity_deg_s={n:ds*(b['q_HOME_delta_deg'][n]-a['q_HOME_delta_deg'][n])for n in names},joint_acceleration_deg_s2={n:dds*(b['q_HOME_delta_deg'][n]-a['q_HOME_delta_deg'][n])for n in names},base_transform_m=to_m(B),support_link=support,support_links=b['support_links'],contact_mode=b['contact_mode'],desired_load_fraction_by_link={l:(1-s)*a['desired_load_fraction_by_link'][l]+s*b['desired_load_fraction_by_link'][l]for l in feet},phase=b['phase'],segment_id=segments[i]['id'],source_linear_q_parameter=float(s)))
sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in [snap,Path(__file__),OUT/'build_guarded_cycle.py',OUT/'screen_stances.py',ROOT/'work/r20-walking-fix/dynamics/quasistatic.py']};sources.update(raw['guard_sources'])
p=OUT/'first_step_trajectory_v1.json'
p.write_text(json.dumps(dict(schema='R19_DIAGNOSTIC_Q_BASE_V1',status='FROZEN_EARLY_CONTROLLER_TEST_PREFIX_NOT_COMPLETE_GAIT',physical_approved=False,duration_s=t,maximum_sample_period_s=.025,units=dict(time='s',joint='HOME-delta degree',base_transform_translation='m'),time_law='Each q0/q1 line uses shared quintic scalar. Identical to eventual four-step exporter limits: <=10deg/s and <=40deg/s2. All exact knots retained.',initial_q_HOME_delta_deg=samples[0]['q_HOME_delta_deg'],initial_base_transform_m=samples[0]['base_transform_m'],keypoints=key,segments=segments,samples=samples,sources=sources),indent=2)+'\n')
print(json.dumps(dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),duration_s=t,sample_count=len(samples),keypoints=len(key))))
