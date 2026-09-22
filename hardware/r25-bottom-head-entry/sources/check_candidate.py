from pathlib import Path
import json,sys,itertools,time
ROOT=Path(__file__).resolve().parents[2];O=Path(__file__).parent
sys.path[:0]=[str(ROOT/'work/r12-motion/python-deps'),str(ROOT/'work/rk-mechanics/python-deps')]
import numpy as np,trimesh,manifold3d as md
load=lambda p:json.loads(Path(p).read_text());S=load(ROOT/'work/r24-head-front/assembly_selection.json');N=load(O/'mechanics/manifest.json');parts=N['parts'].copy();removed=N['replaces'].copy()
if (O/'tails/manifest.json').exists():
 j=load(O/'tails/manifest.json');parts+=j['parts'];removed+=j['replaces']
if (O/'flex/compact_bundle_home/manifest.json').exists():
 j=load(O/'flex/compact_bundle_home/manifest.json');parts+=j['parts'];removed+=j.get('replaces',[x for p in j['parts']for x in p.get('replaces',[])])
old=[p for p in S['items']if p['name']not in removed];Nn=len(parts);items=parts+old
if not(O/'tails/manifest.json').exists():items=[p for p in items if not any(t in p['name']for t in ['R23_NECK_UPPER_','R23_HEAD_SERVO_UPPER_','R23_NECK_FREE'])]
cache=[]
for p in items:
 path=ROOT/p.get('analysis_mesh',p['mesh']);m=trimesh.load(path,force='mesh',process=p.get('mesh_load_process',True));R=np.array(p.get('R',np.eye(3)));t=np.array(p.get('t_mm',[0,0,0]));m.vertices=m.vertices@R.T+t
 s=md.Manifold(md.Mesh64(np.array(m.vertices),np.array(m.faces,dtype=np.uint64)));cache.append((m.bounds,s))
hits=[];count=0;bad=[]
for i in range(Nn):
 a,ma=cache[i]
 for k in range(i+1,len(items)):
  b,mb=cache[k]
  if np.any(a[1]<b[0]-1e-7)or np.any(b[1]<a[0]-1e-7):continue
  count+=1
  if ma.status()!=md.Error.NoError or mb.status()!=md.Error.NoError:bad.append([items[i]['name'],items[k]['name']]);continue
  v=(ma^mb).volume()
  if abs(v)>1e-5:
   q=dict(a=items[i]['name'],b=items[k]['name'],volume_mm3=v);hits.append(q);print(q,flush=True)
S['items']=items;S['new_installed_count']=Nn;S['status']='R25_CANDIDATE_NOT_RELEASED';(O/'candidate_selection.json').write_text(json.dumps(S,indent=2)+'\n')
(O/'candidate_check.json').write_text(json.dumps(dict(tested=count,hits=hits,invalid=bad),indent=2)+'\n');print('DONE',count,len(hits),len(bad),flush=True)
