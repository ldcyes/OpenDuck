"""R25 underside entry, physical candidate; mm HOME. Never edits source revisions."""
from pathlib import Path
import sys,json,hashlib,copy
ROOT=Path(__file__).resolve().parents[2];O=Path(__file__).parent;D=O/'mechanics';D.mkdir(exist_ok=True)
sys.path[:0]=[str(ROOT/'work/r3-mechanics/python-deps'),str(ROOT/'work/r12-motion/python-deps'),str(ROOT/'work/rk-mechanics/python-deps'),str(ROOT/'work/r13-electronics/mechanics'),str(ROOT/'work/r23-power-integration/integration')]
import numpy as np,trimesh,manifold3d as md,common as c
from mesh_print_export import export_indexed
load=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();rel=lambda p:str(Path(p).relative_to(ROOT))
S=load(ROOT/'work/r24-head-front/assembly_selection.json');old={p['name']:p for p in S['items']};parts=[];replaces=[]
b=.51/np.hypot(.51,.86);a=.86/np.hypot(.51,.86);R=np.array([[1,0,0],[0,b,-a],[0,a,b]]);E=np.array([32.,-68.,198.]);T=E-R@np.array([58.,-57.,254.])
def world(p):return c.tf(c.read(ROOT/p['step']),p['R'],p['t_mm'])
def ex(n,s,p=None,mat='6061-T651 machined billet',rho=2.7):
 q=c.export(n,s,D,mat,rho,'jaw_soft','Bottom-entry candidate; physical load, tooling and motion qualification required.')
 q.update(step=rel(D/q['STEP']),mesh=rel(D/q['STL']),R=np.eye(3).tolist(),t_mm=[0,0,0],link_frame='jaw_soft',kind='manufacturing_candidate',reference_only=False,is_new=True,input_group='R25_bottom_entry',manufacturing_approved=False,physical_approved=False)
 rb=c.properties(c.read(ROOT/q['step']));assert rb['valid_BRep'] and rb['solid_count']==1,(n,rb)
 q['STEP_readback_verified']=True
 if p:
  q.update(kind=p.get('kind'),reference_only=p.get('reference_only',False),replaces=[p['name']],source_step=p['step'],source_step_sha256=sha(ROOT/p['step']))
  for key in ['physical_mass_g','mass_budget_g','mass_accounting','manufacturer_mass_g','physical_mass_source']: 
   if key in p:q[key]=p[key]
  replaces.append(p['name'])
 parts.append(q);return q
for n,p in old.items():
 if not n.startswith('R23_neck_upper_') or any(t in n for t in ['6061','saddle_']):continue
 ex(n.replace('R23_','R25_',1),c.tf(world(p),R,T),p,p.get('material','reference'),p.get('density_assumption_g_cm3') or 0)
def bx(lo,hi):return c.box((np.array(lo)+hi)/2,np.array(hi)-lo)
p=old['R23_neck_upper_6061_with_power_pair'];base=world(p)
# Keep original saddle, positive Y stop and all unchanged attachment bores.
foot=c.common(base,bx([40,-66,222.],[70,-40,225.5]))
# Relocate only the comb sideplate + power-pair supporting grooved carrier.
port=c.common(c.tf(base,R,T),bx([2,-78,198],[51,-59.99,210.01]))
port=c.cut(port,bx([13.8,-84,197],[50.2,-62,211]))
# Machined bridge goes around mounting screw head/tool planes at X17,47/Z201.
arm=c.square_rod([[38,-59.8,201],[38,-59.8,205],[48,-59.8,210],[48,-59.8,213],[48,-68,216],[52,-68,222],[52,-68,230],[65,-53,230],[65,-51.5,223]],2.)
host=c.union(c.union(foot,port),arm)
ex('R25_neck_upper_6061_bottom_bridge',host,p)
def mm(p):
 m=trimesh.load(ROOT/p.get('analysis_mesh',p['mesh']),force='mesh',process=p.get('mesh_load_process',True));m.apply_transform(np.block([[np.array(p['R']),np.array(p['t_mm']).reshape(3,1)],[np.array([[0,0,0,1]])]]));return md.Manifold(md.Mesh64(np.array(m.vertices),np.array(m.faces,dtype=np.uint64)))
def mb(lo,hi):return md.Manifold.cube(np.array(hi)-lo).translate(lo)
def emit(n,s,replace,mat='PA2200 PA12 SLS',rho=.93):
 assert s.status()==md.Error.NoError and len(s.decompose())==1,(n,s.status(),len(s.decompose()))
 m=s.to_mesh64();m=trimesh.Trimesh(np.asarray(m.vert_properties)[:,:3],np.asarray(m.tri_verts),process=False)
 q=export_indexed(m,D,n);p=q.pop('mesh_path');master=q.pop('manufacturing_path')
 q.update(name=n,mesh=rel(p),mesh_sha256=sha(p),manufacturing_master=rel(master),manufacturing_master_sha256=sha(master),R=np.eye(3).tolist(),t_mm=[0,0,0],link_frame='jaw_soft',kind='printed_bottom_entry',material=mat,density_assumption_g_cm3=rho,mass_from_CAD_g=m.volume*rho/1000,volume_mm3=m.volume,center_mm=m.center_mass.tolist(),is_new=True,input_group='R25_bottom_entry',replaces=replace,physical_approved=False,manufacturing_approved=False)
 parts.append(q);replaces.extend(replace);return q
r22=load(ROOT/'work/r22-compact-power/integration/assembly_selection.json');orig=next(p for p in r22['items']if p['name']=='R11_45_top_head_shell');top=mm(orig)
for p in load(ROOT/'work/r24-head-front/manifest.json')['tools']:
 if p['name'].startswith('R24_Lug_'):top=top+mm(p)
emit('R25_top_head_shell_closed_side',top,['R24_top_head_shell_front_cover_lugs'])
# Rectangular bottom guide aperture clears installed housing, pair lacing and mount screws.
# Remove shell only: existing skin screws/nuts and mouth parts untouched.
portcut=mb([2.5,-77,195],[51.5,-56,215])
lower=mm(old['R12_lower_head_shell']);newlower=lower-portcut-mb([45.5,-73,210],[54.5,-64.5,220])
emit('R25_lower_head_shell_bottom_entry',newlower,['R12_lower_head_shell'])
replaces.append('R23_TPU_head_31wire_edge_guard')
(D/'manifest.json').write_text(json.dumps(dict(status='CANDIDATE_PENDING_FULL_COLLISION_AND_MOTION',parts=parts,replaces=replaces,transform=dict(R=R.tolist(),t_mm=T.tolist(),upper_free_center_mm=E.tolist()),bottom_cut_box_mm=[[2.5,-77,195],[51.5,-56,215]],old_side_restoration_source=orig,physical_approved=False,manufacturing_approved=False),indent=2)+'\n')
print('MECHANICS',len(parts),len(replaces),flush=True)
