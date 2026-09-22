"""Source-bound optical/tool checks and continuously bounded mouth opening."""
from pathlib import Path
import sys,json,hashlib,math
ROOT=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'work/r12-motion/python-deps'),str(ROOT/'work/rk-mechanics/python-deps')]
import numpy as np,trimesh,manifold3d as md
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
s=json.loads((O/'rigid_inputs.json').read_text());m=json.loads((O/'mechanics/manifest.json').read_text());parts=s['items'];by={p['name']:p for p in parts};cache={};vertices={}
def body(p):
 n=p['name']
 if n not in cache:
  path=ROOT/p.get('analysis_mesh',p['mesh']);assert sha(path)==p.get('analysis_mesh_sha256',p['mesh_sha256'])
  q=trimesh.load(path,force='mesh',process=p.get('mesh_load_process',True));v=np.array(q.vertices)@np.array(p['R']).T+np.array(p['t_mm']);vertices[n]=v
  cache[n]=md.Manifold(md.Mesh64(v.astype(float),np.array(q.faces).astype(np.uint64)));assert cache[n].status()==md.Error.NoError,n
 return cache[n]
def cylinder(x0,x1,y,z,r):return md.Manifold.cylinder(x1-x0,r,r,64).rotate([0,90,0]).translate([x0,y,z])
def boxgap(a,b):
 a=np.array(a.bounding_box()).reshape(2,3);b=np.array(b.bounding_box()).reshape(2,3)
 return float(np.linalg.norm(np.maximum(0,np.maximum(a[0]-b[1],b[0]-a[1]))))
def toolscan(tool,population,exclude=()):
 hits=[];gap=1e9;near=[]
 for p in population:
  if p['name'] in exclude:continue
  q=body(p);lb=boxgap(tool,q)
  if lb>3:gap=min(gap,lb);continue
  d=float(tool.min_gap(q,3));v=abs((tool^q).volume())if d<1e-7 else 0;gap=min(gap,d)
  near.append(dict(name=p['name'],gap_mm=d,common_mm3=v))
  if v>1e-6:hits.append(near[-1])
 return dict(minimum_capped_gap_mm=gap,intersections=hits,near=near)
new=[p for p in parts if p['is_new']]
mouth=[p for p in parts if p['link_frame']=='mouth_link']
j=next(j for j in s['joints'] if j['joint']=='mouth_candidate');pivot=np.array(j['pivot_trunk_mm']);axis=np.array(j['axis_trunk']);axis/=np.linalg.norm(axis)
x,y,z=axis;K=np.array([[0,-z,y],[z,0,-x],[-y,x,0]]);delta=.25
motion=[];all_hits=[];baseline=json.loads((ROOT/'work/r24-head-front/assembly_selection.json').read_text());oldmap={p['name']:p for p in baseline['items']}
for p in mouth:
 b=body(p);v=vertices[p['name']];w=v-pivot;r=float(np.linalg.norm(w-np.outer(w@axis,axis),axis=1).max());budget=2*r*math.sin(math.radians(delta/2)/2)+1e-5
 candidates=[(a,body(a)) for a in new];mins={a['name']:1e9 for a in new};angles={};hits=[]
 for angle in np.arange(0,25.00001,delta):
  t=math.radians(float(angle));R=np.eye(3)+math.sin(t)*K+(1-math.cos(t))*(K@K);b2=b.transform(np.column_stack((R,pivot-R@pivot)))
  for a,a2 in candidates:
   name=a['name'];lb=boxgap(a2,b2)
   if lb>5:gap=lb
   else:gap=float(a2.min_gap(b2,5))
   if gap<mins[name]:mins[name]=gap;angles[name]=float(angle)
   if gap<1e-7:
    vol=abs((a2^b2).volume())
    if vol>1e-6:
     inherited=0.
     oldname={'R25_lower_head_shell_bottom_entry':'R12_lower_head_shell','R25_top_head_shell_closed_side':'R24_top_head_shell_front_cover_lugs'}.get(name)
     if oldname:inherited=abs((body(oldmap[oldname])^b2).volume())
     hits.append(dict(a=name,b=p['name'],angle_deg=float(angle),common_mm3=vol,baseline_intersection_mm3=inherited,new_or_increased=vol>inherited+1e-5))
 for a in new:
  name=a['name'];motion.append(dict(a=name,b=p['name'],sample_lower_bound_mm=mins[name],worst_sample_deg=angles.get(name),maximum_between_sample_displacement_mm=budget,continuous_lower_bound_mm=mins[name]-budget))
 all_hits.extend(hits)
 print('MOUTH',p['name'],'min bound',min(mins.values())-budget,'hits',len(hits),'new',sum(h['new_or_increased']for h in hits),flush=True)
report=dict(source_selection_sha256=sha(O/'rigid_inputs.json'),mouth_range_deg=[0,25],intersections=all_hits,new_or_increased_intersections=[h for h in all_hits if h['new_or_increased']],sample_step_deg=delta,pairs=motion,minimum_continuous_lower_bound_mm=min(r['continuous_lower_bound_mm']for r in motion),physical_approved=False,manufacturing_approved=False)
(O/'mouth_check.json').write_text(json.dumps(report,indent=2)+'\n')
print('MIN_BOUND',report['minimum_continuous_lower_bound_mm'],flush=True)
