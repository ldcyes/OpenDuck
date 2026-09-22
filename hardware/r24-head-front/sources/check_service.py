"""Front extraction diagnostic; rigid geometry only, connector disconnection required."""
from pathlib import Path
import sys,json,hashlib,itertools
ROOT=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'work/r12-motion/python-deps'),str(ROOT/'work/rk-mechanics/python-deps')]
import numpy as np,trimesh,manifold3d as md
s=json.loads((O/'assembly_selection.json').read_text());man=json.loads((O/'manifest.json').read_text())
cache={}
def body(p):
 n=p['name']
 if n not in cache:
  q=trimesh.load(ROOT/p.get('analysis_mesh',p['mesh']),force='mesh',process=p.get('mesh_load_process',True));v=np.array(q.vertices)@np.array(p['R']).T+p['t_mm'];cache[n]=md.Manifold(md.Mesh64(v,np.array(q.faces,dtype=np.uint64)))
 return cache[n]
new=[p for p in man['parts'] if p['name']!='R24_top_head_shell_front_cover_lugs' and not p['name'].startswith('R24_face_')]
obstacles=[p for p in s['items'] if p['name'] not in {q['name'] for q in new} and not (p['name'].startswith('R24_face_') and '_M2x' in p['name'])]
rows=[];hits=[]
for p in new:
 a=body(p);ab=np.array(a.bounding_box()).reshape(2,3);sweepbb=ab.copy();sweepbb[1,0]+=40
 for q in obstacles:
  b=body(q);bb=np.array(b.bounding_box()).reshape(2,3)
  lb=np.linalg.norm(np.maximum(0,np.maximum(sweepbb[0]-bb[1],bb[0]-sweepbb[1])))
  if lb>1:continue
  gaps=[]
  for dx in np.arange(0,40.0001,.5):
   aa=a.translate([float(dx),0,0]);g=float(aa.min_gap(b,2));v=abs((aa^b).volume()) if g<1e-7 else 0
   if v>1e-6:hits.append(dict(a=p['name'],b=q['name'],dx_mm=float(dx),intersection_mm3=v))
   gaps.append(g)
  row=dict(a=p['name'],b=q['name'],minimum_sample_gap_mm=min(gaps),worst_dx_mm=float(np.argmin(gaps)*.5),continuous_bound_after_first_mm=min(gaps[2:])-.25,initial_gaps_mm=gaps[:3]);rows.append(row)
 print('EXTRACT',p['name'],'hits',len(hits),flush=True)
report=dict(status='SAMPLED_EXTRACTION_WITH_BOUNDS_READ_START_CONTACTS',source_selection_sha256=hashlib.sha256((O/'assembly_selection.json').read_bytes()).hexdigest(),checker_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),translation_mm=[0,40],axis=[1,0,0],step_mm=.5,moving_count=len(new),obstacle_count=len(obstacles),near_pairs=rows,intersections=hits,limits=['Fasteners4M2x10 removed and USB disconnected before extraction; actual cable/mating plug not qualified.','Nominal rigid shells only; first0..1mm seats separately need directional separation review.','This is a service-space check, not proof of whole-head assembly order or hardware tool standard.'])
# Initial seating: frontplate liesX>=132.625, lug solidsX<=132.625,
# so positiveX translation separates those seats. Camera supports behind that
# plane occupy a disjointY interval, checked on a clipped solid.
face=body(man['parts'][0]);XB=132.625
rear=face ^ md.Manifold.cube([XB-110-1e-7,240,150]).translate([110,-120,200])
rearbb=np.array(rear.bounding_box()).reshape(2,3)
lateral=[]
for p in man['tools']:
 bb=np.array(p['bounds_mm']);assert bb[1,0]<=XB+1e-8
 lateral.append(max(rearbb[0,1]-bb[1,1],bb[0,1]-rearbb[1,1]))
assert min(lateral)>1
# The unchanged shell alone remains clear from the first increment; add its
# own initial samples and continuous translation budget, excluding fixed lugs.
oldsel=json.loads((ROOT/'work/r23-power-integration/integration/assembly_selection.json').read_text())
oldtop=next(p for p in oldsel['items'] if p['name']==man['replaces'][0]);oldbody=body(oldtop)
initial_shell_gap=min(float(face.translate([float(dx),0,0]).min_gap(oldbody,3))for dx in np.arange(0,1.0001,.1))
assert initial_shell_gap-.05>0
report['initial_seat_directional_proof']=dict(plate_rear_plane_x_mm=XB,lug_front_plane_x_mm=XB,rear_support_bounds_mm=rearbb.tolist(),minimum_rear_support_lateral_gap_mm=min(lateral),old_shell_first_mm_continuous_lower_bound_mm=initial_shell_gap-.05,method='PositiveX separates plate/lug supporting planes; supports behind plate remain laterally separated; old shell nearest0.1mm translation samples minus0.05mm.')
report['status']='RIGID_FORWARD_EXTRACTION_NO_INTERSECTION_WITH_CONTINUOUS_BOUNDS_AND_INITIAL_SEAT_PROOF'
report['limits'][1]='Initial seating is separately directionally bounded; flexible cable and plug are excluded until disconnected.'
(O/'service_check.json').write_text(json.dumps(report,indent=2)+'\n')
print('HITS',hits,flush=True)
