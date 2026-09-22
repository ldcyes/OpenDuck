from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parents[2];O=Path(__file__).parent
sys.path[:0]=[str(ROOT/'work/r12-motion/python-deps'),str(ROOT/'work/rk-mechanics/python-deps')]
import numpy as np,trimesh,manifold3d as md
S=json.loads((O/'assembly_selection.json').read_text());parts=S['items'];cache={}
def body(p):
 if p['name']not in cache:
  m=trimesh.load(ROOT/p.get('analysis_mesh',p['mesh']),force='mesh',process=p.get('mesh_load_process',True));m.vertices=m.vertices@np.array(p['R']).T+np.array(p['t_mm']);cache[p['name']]=md.Manifold(md.Mesh64(np.array(m.vertices),np.array(m.faces,dtype=np.uint64)))
 return cache[p['name']]
rows=[]
for i,x in enumerate([17,47],1):
 # Comb is wired/closed on bench before bridge mounting. Non-present later assemblies excluded by explicit stage.
 for stage,lo,axis in [('comb_on_bench',[x,-68,212.52],'z'),('head_subassembly_before_neck_and_skins',[x,-57.48,201],'y')]:
  screw=f'R25_neck_upper_retainer_{i}_M2x6'if axis=='z'else f'R25_neck_upper_mount_{i}_M2x18'
  tool=md.Manifold.cylinder(35,1.5,1.5,48)
  if axis=='y':tool=tool.rotate([-90,0,0])
  tool=tool.translate(lo);bb=np.array(tool.bounding_box()).reshape(2,3);hits=[];tested=0
  for p in parts:
   n=p['name']
   if n==screw:continue
   if stage=='comb_on_bench' and not(n.startswith('R25_neck_upper_') and '6061'not in n and '_mount_'not in n):continue
   if stage=='head_subassembly_before_neck_and_skins' and p['link_frame']not in ['jaw_soft','mouth_link','yaw_roll_motion']:continue
   if stage=='head_subassembly_before_neck_and_skins' and ('shell' in n.lower()or 'face_camera' in n or 'eye_'in n or 'R24_face_'in n):continue
   b=body(p);bnd=np.array(b.bounding_box()).reshape(2,3)
   if np.any(bb[1]<bnd[0])or np.any(bnd[1]<bb[0]):continue
   v=abs((tool^b).volume());tested+=1
   if v>1e-5:hits.append(dict(name=n,intersection_mm3=v))
  if stage=='comb_on_bench':
   contract=json.loads((O/'flex/compact_bundle_home/manifest.json').read_text())
   routes=json.loads((O/'tails/manifest.json').read_text())['routes']
   for r in routes:
    a=r['segments'][-1]['end']if r['port']in ['P5','P6']else r['segments'][0]['start']
    w=md.Manifold.cylinder(62,r['od_mm']/2,r['od_mm']/2,48).translate(a);v=abs((tool^w).volume())
    if v>1e-5:hits.append(dict(name='unformed_wire_'+r['port'],intersection_mm3=v))
  rows.append(dict(stage=stage,screw=screw,driver_shaft_diameter_mm=3,driver_exterior_length_mm=35,intersections=hits,tested_near_pairs=tested))
  print(rows[-1],flush=True)
(O/'tool_access.json').write_text(json.dumps(dict(selection_sha256=hashlib.sha256((O/'assembly_selection.json').read_bytes()).hexdigest(),checks=rows,physical_approved=False,limits=['Assembly sequence required: tighten retainers on straight unformed wires first, then form/terminate tails, then mount guide on head subassembly before connecting neck and closing skins. No assembled in-place access asserted.','Bit fit and real driver handles require first article.']),indent=2)+'\n')
