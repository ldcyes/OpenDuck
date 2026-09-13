"""Twelve source-material leg/battery distances for numerical gait constraints.

Input: q HOME deltas in degrees. Output: capped distances in mm (not signed
penetration depth). This is a narrow solver guard; whole-assembly review is
still required for the accepted path and source selection.
"""
from pathlib import Path
import itertools,sys,json,time
ROOT=Path(__file__).resolve().parents[3]
sys.dont_write_bytecode=True
sys.path[:0]=[str(ROOT/'work/r12-motion/python-deps'),str(ROOT/'work/rk-mechanics/python-deps'),str(ROOT/'work/r18-leg-hip-covers/review')]
import numpy as np
import trimesh,manifold3d as md
from motion_core import Sources,transforms,relative_transform,apply_points
SELECTION='work/r18-leg-hip-covers/legs/reference_design/candidate_v8/motion_diagnostic/diagnostic_selection.json'

class LegBatteryGuard:
 def __init__(self,selection_path=SELECTION):
  self.selection_path=selection_path;self.sources=Sources();self.sources.bind(__file__)
  for p in [ROOT/'work/r18-leg-hip-covers/review/motion_core.py',md.__file__,trimesh.__file__]:self.sources.bind(p)
  selection=self.sources.json(selection_path);self.joints=selection['joints'];self.by={x['name']:x for x in selection['items']}
  shells=['R17_battery_front_relocated_limiter_hosts','R13_battery_rear_internal_passages']
  legs=[p for side in ['left','right']for p in [f'{side}_knee_motor',f'{side}_knee_fixed',f'R11_upper_leg_{side}_dual_rail']]
  self.pairs=list(itertools.product(legs,shells));self.objects={}
  for name in legs+shells:
   row=self.by[name];p=self.sources.bind(row['mesh'],row['mesh_sha256'])
   if row.get('step'):self.sources.bind(row['step'],row['step_sha256'])
   if row.get('geometry_scale',[1,1,1])!=[1,1,1]:raise ValueError(('SOURCE_GEOMETRY_SCALE',name))
   mesh=trimesh.load(p,force='mesh');R=np.asarray(row['R']);t=np.asarray(row['t_mm'])
   if not np.allclose(R.T@R,np.eye(3),atol=1e-6,rtol=0):raise ValueError(('NONRIGID_SOURCE',name))
   V=np.asarray(mesh.vertices)@R.T+t
   solid=md.Manifold(md.Mesh64(V.astype(np.float64),np.asarray(mesh.faces,np.uint64)))
   if solid.status()!=md.Error.NoError or solid.volume()<=0:raise ValueError(('INVALID_SOURCE_MATERIAL',name))
   bounds=np.array([V.min(0),V.max(0)]);corners=np.array(list(itertools.product(*zip(bounds[0],bounds[1]))))
   self.objects[name]=dict(vertices=V,solid=solid,corners=corners)
  self.sources.verify()
 def inspect(self,q,cap_mm=5.,include_volume=True):
  if not np.isfinite(cap_mm)or cap_mm<=0:raise ValueError('INVALID_CAP')
  T=transforms(self.joints,q);bounds={}
  for name,o in self.objects.items():
   v=apply_points(o['corners'],T[self.by[name]['link_frame']]);bounds[name]=np.array([v.min(0),v.max(0)])
  rows=[]
  for a,b in self.pairs:
   aa,bb=bounds[a],bounds[b];lower=float(np.linalg.norm(np.maximum(0,np.maximum(aa[0]-bb[1],bb[0]-aa[1]))));common=None
   if lower>=cap_mm:gap=float(cap_mm);method='AABB_CERTIFIED_AT_LEAST_CAP'
   else:
    rel=relative_transform(T[self.by[a]['link_frame']],T[self.by[b]['link_frame']]);A=self.objects[a]['solid'];B=self.objects[b]['solid'].transform(rel[:3]);gap=float(A.min_gap(B,cap_mm));method='SOURCE_MATERIAL_DISTANCE_CAPPED'
    if include_volume:common=abs(float((A^B).volume()))if gap<1e-7 else 0.
   rows.append(dict(a=a,b=b,gap_mm=gap,common_mm3=0. if lower>=cap_mm else common,method=method,cap_mm=cap_mm))
  return rows
 def gaps(self,q,cap_mm=5.):return np.array([r['gap_mm']for r in self.inspect(q,cap_mm,False)])
 def constraints(self,q,target_mm=2.2,cap_mm=5.):
  if cap_mm<=target_mm:raise ValueError('CAP_MUST_EXCEED_TARGET')
  return self.gaps(q,cap_mm)-target_mm

if __name__=='__main__':
 g=LegBatteryGuard();data=json.loads((ROOT/'work/r19-walking-simulation/path_support/gait_collision_evidence/manifest.json').read_text());q=data['pairs'][0]['q_HOME_delta_deg'];start=time.time()
 for _ in range(10):g.gaps(q)
 print('Average guard seconds',(time.time()-start)/10)
 print(json.dumps(g.inspect(q),indent=2))
