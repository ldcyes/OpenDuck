"""Source-bound optical/tool checks and continuously bounded mouth opening."""
from pathlib import Path
import sys,json,hashlib,math
ROOT=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'work/r12-motion/python-deps'),str(ROOT/'work/rk-mechanics/python-deps')]
import numpy as np,trimesh,manifold3d as md
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
s=json.loads((O/'assembly_selection.json').read_text());m=json.loads((O/'manifest.json').read_text());parts=s['items'];by={p['name']:p for p in parts};cache={};vertices={}
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
CY=-.19194;CZ=269.007
# Vendor gives96deg DIAGONAL, not horizontal. 50deg cone encloses48deg+2deg axis allowance.
# Pupil4mm behind lens is an assumed acceptance budget, not a published datum.
pupil_x=151.1-.4-4.;radius=7.5;end=220.
cone=md.Manifold.cylinder(end-pupil_x,radius,radius+(end-pupil_x)*math.tan(math.radians(50)),128).rotate([0,90,0]).translate([pupil_x,CY,CZ])
optical=toolscan(cone,[p for p in parts if p['link_frame']=='jaw_soft' and 'OS05A10' not in p['name']])
optical.update(diagonal_fov_deg=96,half_angle_budget_deg=50,pupil_setback_budget_mm=4,axial_tolerance_mm=.4,decenter_budget_mm=.5,status='CONDITIONAL_ON_PUPIL_BUDGET_AND_REAL_IMAGE_TEST')
print('OPTICAL',optical['intersections'],flush=True)
# Front drivers: actual screw removed for insertion check; every other installed body retained.
tools=[]
for p in m['parts']:
 n=p['name']
 if not any(t in n for t in ('_M2x','_M1p6x')):continue
 v=body(p).bounding_box();y=(v[1]+v[4])/2;z=(v[2]+v[5])/2;front=v[3]
 # Model exterior shaft from screw top, not bit/thread engagement.
 tool=cylinder(front+.02,front+35,y,z,1.5 if '_M2x' in n else 1.2)
 pop=[q for q in parts if (not n.startswith('R24_camera_') or q['is_new'] and q['name'] not in ('R24_black_camera_eye_bezel','R24_top_head_shell_front_cover_lugs') and not q['name'].startswith(('R24_eye_','R24_face_')))]
 row=toolscan(tool,pop,[n]);row.update(screw=n,stage='camera on detached face before bezel' if n.startswith('R24_camera_') else 'installed front access',tool_shaft_diameter_mm=3 if '_M2x' in n else 2.4);tools.append(row)
 print('TOOL',n,len(row['intersections']),flush=True)
# New head material only + new front hardware versus ALL mouth-link objects.
# Existing unchanged shell is tested separately and does not contaminate delta approval.
new=[p for p in m['parts'] if p['name']!='R24_top_head_shell_front_cover_lugs']+m['tools']
mouth=[p for p in parts if p['link_frame']=='mouth_link']
j=next(j for j in s['joints'] if j['joint']=='mouth_candidate');pivot=np.array(j['pivot_trunk_mm']);axis=np.array(j['axis_trunk']);axis/=np.linalg.norm(axis)
x,y,z=axis;K=np.array([[0,-z,y],[z,0,-x],[-y,x,0]]);delta=.25
motion=[]
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
    if vol>1e-6:hits.append(dict(a=name,angle_deg=float(angle),common_mm3=vol))
 for a in new:
  name=a['name'];motion.append(dict(a=name,b=p['name'],sample_lower_bound_mm=mins[name],worst_sample_deg=angles.get(name),maximum_between_sample_displacement_mm=budget,continuous_lower_bound_mm=mins[name]-budget))
 print('MOUTH',p['name'],'min bound',min(mins.values())-budget,'hits',hits,flush=True)
 assert not hits,hits
# Interface fit points and face planar tolerance use native geometry checks; STL microscopic seat errors recorded separately.
report=dict(selection_sha256=sha(O/'assembly_selection.json'),checker_sha256=sha(__file__),optical=optical,front_driver_checks=tools,mouth=dict(range_deg=[0,25],sample_step_deg=delta,method='Nearest sample rigid displacement2r sin(delta/4) subtracted from exact or AABB sample lower bounds; all new geometry excluding unchanged shell; not motor operating approval',pair_count=len(motion),new_geometry_count=len(new),mouth_object_count=len(mouth),pairs=motion,minimum_continuous_lower_bound_mm=min(r['continuous_lower_bound_mm'] for r in motion)),physical_approved=False,manufacturing_approved=False)
(O/'detail_checks.json').write_text(json.dumps(report,indent=2)+'\n')
print('DONE',report['mouth']['minimum_continuous_lower_bound_mm'],flush=True)
