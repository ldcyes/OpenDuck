from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'work/r12-motion/python-deps'),str(ROOT/'work/rk-mechanics/python-deps')]
import trimesh,numpy as np,manifold3d as md
from scipy.spatial import cKDTree
m=json.loads((O/'manifest.json').read_text());s=json.loads((ROOT/'work/r23-power-integration/integration/assembly_selection.json').read_text())
a=next(p for p in s['items'] if p['name']==m['replaces'][0]);b=m['parts'][2]
old=trimesh.load(ROOT/a['mesh'],force='mesh');new=trimesh.load(ROOT/b['mesh'],force='mesh',process=False)
# Independent source-triangle identity away from conservative local front modification ROI.
# All edits are allowed only atX>=123.5; compare oriented triangle multisets exactly to1e-8mm.
from collections import Counter
def key(t):
 v=[tuple(np.round(v,8)) for v in t];return min(tuple(v[i:]+v[:i]) for i in range(3))
def audit(x):
 ta=old.triangles;tb=new.triangles;A=Counter(key(t)for t in ta if t[:,0].max()<x);B=Counter(key(t)for t in tb if t[:,0].max()<x)
 return A,B,A-B,B-A
A,B,missing,extra=audit(123.5)
ALLA=Counter(key(t) for t in old.triangles);ALLB=Counter(key(t) for t in new.triangles)
def changed_bounds(c):
 t=np.array(list(c));return [t.reshape(-1,3).min(0).tolist(),t.reshape(-1,3).max(0).tolist()] if len(t) else None
print('ALL_CHANGED',sum((ALLA-ALLB).values()),sum((ALLB-ALLA).values()),changed_bounds(ALLA-ALLB),changed_bounds(ALLB-ALLA),flush=True)
print('TRIANGLES',len(old.faces),len(new.faces),'outside ROI',sum(A.values()),sum(B.values()),'missing',sum(missing.values()),'extra',sum(extra.values()),flush=True)
# These may be re-triangulations within old planes. Preserve result rather than infer equivalence.
report=dict(status='EXACT_ORIENTED_TRIANGLES' if not missing and not extra else 'TRIANGLE_RETRIANGULATION_NEEDS_SURFACE_CHECK',roi='X>=123.5mm contains every declared lug; all other surfaces require retention',old_outside_triangles=sum(A.values()),new_outside_triangles=sum(B.values()),missing_count=sum(missing.values()),extra_count=sum(extra.values()),removed_or_retriangulated_triangle_bounds_mm=changed_bounds(ALLA-ALLB),added_or_retriangulated_triangle_bounds_mm=changed_bounds(ALLB-ALLA),original_mesh=a['mesh'],original_sha256=a['mesh_sha256'],new_mesh=b['mesh'],new_sha256=b['mesh_sha256'])
if missing or extra:
 for label,ctr,target in [('old_missing',missing,new),('new_extra',extra,old)]:
  triangles=np.array(list(ctr));points=np.concatenate([triangles.reshape(-1,3),triangles.mean(1)])
  try:
   _,dist,_=trimesh.proximity.closest_point(target,points)
   report[label]=dict(point_count=len(points),maximum_surface_distance_mm=float(dist.max()),bounds_mm=[triangles.reshape(-1,3).min(0).tolist(),triangles.reshape(-1,3).max(0).tolist()],method='vertices and centroids diagnostic, not continuous surface proof')
   print(label,report[label],flush=True)
  except Exception as e:report[label]=dict(error=str(e))
(O/'shell_surface_audit.json').write_text(json.dumps(report,indent=2)+'\n')
# Continuous 2D coverage of changed triangles, outside four explicit lug bounding boxes.
# This avoids3D coplanar Boolean volume cancellation entirely.
from scipy.spatial import ConvexHull
import itertools,math
boxes=[np.array(p['bounds_mm']) for p in m['tools']]
old_changed=np.array(list(ALLA-ALLB));new_changed=np.array(list(ALLB-ALLA))
def coverage(triangles,target):
 tv=target.triangles;normal=target.face_normals;rows=[]
 for ti,t in enumerate(triangles):
  if any(np.all(t>=bb[0]-1e-7) and np.all(t<=bb[1]+1e-7)for bb in boxes):continue
  o=t[0];u=t[1]-o;u/=np.linalg.norm(u);n=np.cross(t[1]-o,t[2]-o);n/=np.linalg.norm(n);v=np.cross(n,u);basis=np.array([u,v]).T
  cs=md.CrossSection([(t-o)@basis],md.FillRule.EvenOdd)
  hit=(normal@n>1-1e-8)&(np.max(np.abs((tv-o)@n),axis=1)<1e-5)
  cuts=[md.CrossSection([(tt-o)@basis],md.FillRule.EvenOdd) for tt in tv[hit]]
  for bb in boxes:
   corners=np.array(list(itertools.product(*zip(bb[0],bb[1]))));dist=(corners-o)@n;points=[]
   for i,j in itertools.combinations(range(8),2):
    if sum(corners[i]!=corners[j])!=1:continue
    if abs(dist[i])<1e-7:points.append(corners[i])
    if dist[i]*dist[j]<0:points.append(corners[i]+(corners[j]-corners[i])*dist[i]/(dist[i]-dist[j]))
   if len(points)>=3:
    p=np.unique(np.round((np.array(points)-o)@basis,10),axis=0)
    if len(p)>=3:
     try:cuts.append(md.CrossSection([p[ConvexHull(p).vertices]],md.FillRule.EvenOdd))
     except Exception:pass
  if cuts:cs=cs-md.CrossSection.batch_boolean(cuts,md.OpType.Add)
  area=cs.area();rows.append(dict(triangle_index=ti,uncovered_area_mm2=area))
 return dict(nontrivial_triangles=len(rows),maximum_uncovered_area_mm2=max((r['uncovered_area_mm2']for r in rows),default=0),total_uncovered_area_mm2=sum(r['uncovered_area_mm2']for r in rows),rows=rows)
report['old_surface_coverage']=coverage(old_changed,new)
report['new_surface_coverage']=coverage(new_changed,old)
report['local_edit_boxes_mm']=[b.tolist() for b in boxes]
report['coplanar_distance_tolerance_mm']=1e-5
report['method']='Oriented identical triangles at1e-8mm plus bidirectional continuous planar polygon coverage of changed triangles outside four declared lug boxes. No3D Boolean volume proof.'
report['status']='SURFACE_PRESERVATION_OUTSIDE_DECLARED_LUG_BOXES' if max(report['old_surface_coverage']['maximum_uncovered_area_mm2'],report['new_surface_coverage']['maximum_uncovered_area_mm2'])<1e-5 else 'LOCAL_SURFACE_AUDIT_UNRESOLVED'
(O/'shell_surface_audit.json').write_text(json.dumps(report,indent=2)+'\n')
print('COVERAGE',report['status'],report['old_surface_coverage']['maximum_uncovered_area_mm2'],report['new_surface_coverage']['maximum_uncovered_area_mm2'],flush=True)
