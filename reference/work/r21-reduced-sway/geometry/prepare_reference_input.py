"""Bind exact timed q segments and verify every sample uses the same scalar path."""
from pathlib import Path
import json,hashlib,argparse,re
import numpy as np
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--trajectory',required=True);ap.add_argument('--segments',required=True);ap.add_argument('--label',required=True);a=ap.parse_args();assert re.fullmatch('[a-z0-9_]+',a.label);S={};sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def read(rel):
 p=ROOT/rel;S[rel]=sha(p);d=json.loads(p.read_text())
 for r,h in d.get('sources',{}).items():assert sha(ROOT/r)==h,(r,'CHANGED');S[r]=h
 return d
D=read(a.trajectory);E=read(a.segments)['trajectories']['forward'];assert E['trajectory']==a.trajectory and E['trajectory_sha256']==S[a.trajectory];segs=E['segments'];ss=D['samples'];names=sorted(ss[0]['q_HOME_delta_deg']);ids={r['id']:r for r in segs};assert len(ids)==len(segs);assert len(ss)>1 and len(segs)>0
assert abs(segs[0]['start_s'])<1e-12 and abs(segs[-1]['end_s']-D['duration_s'])<1e-9
for i,s in enumerate(segs):
 assert s['start_s']<s['end_s'] and sorted(s['q0'])==names==sorted(s['q1'])
 if i:
  prev=segs[i-1];assert abs(s['start_s']-prev['end_s'])<1e-9;assert max(abs(s['q0'][n]-prev['q1'][n])for n in names)<1e-9
maxerr=0.;sampleq=[];tprev=-1.;phases={}
for i,s in enumerate(ss):
 assert s['time_s']>tprev;tprev=s['time_s'];seg=ids[s['segment_id']];assert seg['start_s']-1e-9<=s['time_s']<=seg['end_s']+1e-9;v=s['source_linear_q_parameter'];assert -1e-12<=v<=1+1e-12
 err=max(abs(s['q_HOME_delta_deg'][n]-((1-v)*seg['q0'][n]+v*seg['q1'][n]))for n in names);maxerr=max(maxerr,err);assert err<1e-8
 phases.setdefault(s['phase'],[]).append(i);sampleq.append([s['q_HOME_delta_deg'][n]for n in names])
assert abs(ss[0]['time_s'])<1e-12 and abs(ss[-1]['time_s']-D['duration_s'])<1e-9
# Six spread source samples per phase plus each joint's global extrema; the
# separate continuous scan covers every point of every joint-space segment.
selected={0,len(ss)-1};Q=np.array(sampleq)
for idx in phases.values():selected.update(idx[i]for i in np.linspace(0,len(idx)-1,min(6,len(idx)),dtype=int))
for j in range(len(names)):selected.update([int(Q[:,j].argmin()),int(Q[:,j].argmax())])
poses=[];seen=set()
for i in sorted(selected):
 s=ss[i];key=tuple(s['q_HOME_delta_deg'][n]for n in names)
 if key in seen:continue
 seen.add(key);poses.append(dict(label=f'{i:05d}_{s["phase"]}',time_s=s['time_s'],q=s['q_HOME_delta_deg'],source_sample_index=i))
S[str(Path(__file__).resolve().relative_to(ROOT))]=sha(Path(__file__).resolve());out=HERE/(a.label+'_input.json');assert not out.exists();result=dict(status='EXACT_REFERENCE_Q_PATH_INPUT_VERIFIED_NOT_A_COLLISION_PASS',trajectory=a.trajectory,trajectory_sha256=S[a.trajectory],source_sample_count=len(ss),sample_scalar_path_max_error_deg=maxerr,finite_pose_policy='Six spread original samples per phase plus all joint extrema, duplicate q eliminated. All q segments separately checked continuously.',poses=poses,segments=segs,sources=S)
out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print('VERIFIED',len(ss),'samples',len(segs),'segments',len(poses),'finite poses',maxerr)
