"""Full selected population at HOME; unclassified contact remains open."""
from pathlib import Path
import sys,json,hashlib,itertools,time
ROOT=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'work/r12-motion/python-deps'),str(ROOT/'work/rk-mechanics/python-deps')]
import numpy as np,trimesh,manifold3d as md
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
s=json.loads((O/'assembly_selection.json').read_text());man=json.loads((O/'manifest.json').read_text());cache={};items=s['items'];V=[];F=[];B=[]
for i,p in enumerate(items):
 path=ROOT/p.get('analysis_mesh',p['mesh']);assert sha(path)==p.get('analysis_mesh_sha256',p['mesh_sha256'])
 m=trimesh.load(path,force='mesh',process=p.get('mesh_load_process',True));v=np.array(m.vertices)@np.array(p['R']).T+np.array(p['t_mm']);V.append(v);F.append(np.array(m.faces));B.append([v.min(0),v.max(0)])
 if i%200==0:print('load',i,flush=True)
B=np.array(B);K=s['new_installed_count'];rows=[];errors=[]
def body(i):
 if i not in cache:
  a=md.Manifold(md.Mesh64(V[i].astype(float),F[i].astype(np.uint64)))
  if a.status()!=md.Error.NoError:raise ValueError((items[i]['name'],str(a.status())))
  cache[i]=a
 return cache[i]
for i in range(K):
 for j in range(i+1,len(items)):
  d=np.maximum(0,np.maximum(B[i,0]-B[j,1],B[j,0]-B[i,1]));lower=np.linalg.norm(d)
  if lower>3:continue
  try:
   a,b=body(i),body(j);gap=float(a.min_gap(b,3));vol=abs((a^b).volume())if gap<1e-5 else 0
   rows.append(dict(a=items[i]['name'],b=items[j]['name'],same_link=items[i]['link_frame']==items[j]['link_frame'],gap_mm=gap,intersection_mm3=vol))
  except Exception as e:errors.append(dict(a=items[i]['name'],b=items[j]['name'],error=str(e)))
 print('check',i,items[i]['name'],flush=True)
pairs=K*(len(items)-K)+K*(K-1)//2
report=dict(status='HOME_SCREEN_READ_NAMED_CONTACTS_NOT_MOTION_PROOF',selection_sha256=sha(O/'assembly_selection.json'),new_object_count=K,all_object_count=len(items),requested_pair_count=pairs,near_rows=rows,errors=errors,physical_approved=False)
(O/'static_check.json').write_text(json.dumps(report,indent=2)+'\n')
print('PAIRS',pairs,'near',len(rows),'errors',len(errors),flush=True)
for r in rows:
 if r['intersection_mm3']>1e-6:print('INTERSECTION',r,flush=True)
