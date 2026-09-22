"""R24 removable face: source-outline print derivative, new captive-nut lugs."""
from pathlib import Path
import sys,json,hashlib,copy,math
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
sys.path[:0]=[str(ROOT/'work/r12-motion/python-deps'),str(ROOT/'work/rk-mechanics/python-deps'),str(ROOT/'work/r13-electronics/mechanics')]
import numpy as np,trimesh,manifold3d as md
import common as c
sys.path.insert(0,str(ROOT/'work/r23-power-integration/integration'))
from mesh_print_export import export_indexed
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
rel=lambda p:str(Path(p).relative_to(ROOT))
load=lambda p:json.loads(Path(p).read_text())
S=load(ROOT/'work/r23-power-integration/integration/assembly_selection.json');oldtop=next(p for p in S['items'] if p['name']=='R23_top_head_shell_31wire_window')
ref=load(ROOT/'work/r12-motion/facial_reference_manifest.json')['items'][0]
sources={rel(ROOT/'work/r23-power-integration/integration/assembly_selection.json'):sha(ROOT/'work/r23-power-integration/integration/assembly_selection.json'),ref['mesh']:sha(ROOT/ref['mesh']),oldtop['mesh']:sha(ROOT/oldtop['mesh']),rel(Path(__file__)):sha(__file__), 'work/r8-design/integration/reference/OS05A10_dimensions.jpg':sha(ROOT/'work/r8-design/integration/reference/OS05A10_dimensions.jpg')}
sources[rel(ROOT/'work/r23-power-integration/integration/mesh_print_export.py')]=sha(ROOT/'work/r23-power-integration/integration/mesh_print_export.py')
CY=-.19194;CZ=269.007;XF=135.025;XB=132.625;SEAT=129.;PCB=135.1;LENS=151.1
parts=[];tools=[];contacts=[];native={}
def box(lo,hi):return md.Manifold.cube(np.array(hi)-lo).translate(lo)
def cube(mid,size):return box(np.array(mid)-np.array(size)/2,np.array(mid)+np.array(size)/2)
def cx(x,y,z,r,L):return md.Manifold.cylinder(L,r,r,64,True).rotate([0,90,0]).translate([x,y,z])
def cone(x0,x1,y,z,r0,r1):return md.Manifold.cylinder(x1-x0,r0,r1,96).rotate([0,90,0]).translate([x0,y,z])
def mm(mesh):return md.Manifold(md.Mesh64(np.array(mesh.vertices,dtype=float),np.array(mesh.faces,dtype=np.uint64)))
def mload(p):
 m=trimesh.load(ROOT/p['mesh'],force='mesh');m.apply_transform(np.block([[np.array(p.get('R',np.eye(3))),np.array(p.get('t_mm',p.get('t',[0,0,0]))).reshape(3,1)],[np.array([[0.,0.,0.,1.]])]]));return mm(m)
def meshof(s):
 q=s.to_mesh64();return trimesh.Trimesh(np.asarray(q.vert_properties)[:,:3],np.asarray(q.tri_verts),process=False)
def emit(name,s,kind,material='PA2200 PA12 SLS, density scenario',rho=.93,reference=False,installed=True):
 assert s.status()==md.Error.NoError and len(s.decompose())==1 and s.volume()>0,(name,s.status(),len(s.decompose()))
 native[name]=s
 m=meshof(s);assert m.is_watertight and m.is_winding_consistent,name
 d=OUT/'geometry';d.mkdir(exist_ok=True);p=d/(name+'.stl');m.export(p);r=trimesh.load(p,force='mesh');extra={}
 if kind.startswith('printed_') or not(r.is_watertight and r.is_winding_consistent and len(r.split())==1):
  bad=OUT/'diagnostics';bad.mkdir(exist_ok=True);p.replace(bad/p.name)
  extra=export_indexed(m,d,name);p=extra.pop('mesh_path');master=extra.pop('manufacturing_path')
  extra.update(manufacturing_master=rel(master),manufacturing_master_sha256=sha(master))
 else:assert abs(r.volume-m.volume)<.08,(name,r.volume,m.volume)
 q=dict(name=name,mesh=rel(p),mesh_sha256=sha(p),R=np.eye(3).tolist(),t_mm=[0.,0.,0.],link_frame='jaw_soft',material=material,density_assumption_g_cm3=rho,volume_mm3=float(m.volume),mass_from_CAD_g=float(m.volume)*rho/1000,center_mm=m.center_mass.tolist(),unit_density_inertia_mm5=m.moment_inertia.tolist(),bounds_mm=m.bounds.tolist(),solid_count=1,mesh_watertight=True,kind=kind,reference_only=reference,manufacturing_mesh_only=True,derivation_sources=dict(sources),visible_default=True,is_new=True,input_group='R24_head_front',r23_domain='R24_head_front',physical_approved=False,manufacturing_approved=False)
 q.update(extra);(parts if installed else tools).append(q);return q
# Source profile at a material-bearing plane. Offset only perimeter inward0.35mm.
orig=trimesh.load(ROOT/ref['mesh'],force='mesh');section=orig.section(plane_normal=[1,0,0],plane_origin=[134,0,0]);polys=[v[:-1,1:] for v in section.discrete]
area=lambda p:abs(np.sum(p[:,0]*np.roll(p[:,1],-1)-p[:,1]*np.roll(p[:,0],-1)))/2
coords=max(polys,key=area);cs=md.CrossSection([coords],md.FillRule.EvenOdd).offset(-.35,md.JoinType.Miter);face=cs.extrude(XF-XB).transform(np.array([[0,0,1,XB],[1,0,0,0],[0,1,0,0]]))
print('BASE',cs.area(),face.status(),face.volume(),flush=True)
face=face-cx(134,CY,CZ,25.,8)
# Lower shell is fixed: relieve the front bottom seam for print tolerance.
face=face-box([100,-120,200],[160,120,227.5])
# New shell lugs: transverse flanges join actual current side wall, fixed front seat.
MOUNTS=[(-80,251),(80,251),(-74,285),(74,285)];top=mload(oldtop);added=[]
for i,(y,z) in enumerate(MOUNTS,1):
 sy=1 if y>0 else-1
 lug=box([124.625,min(y-4,sy*95),z-5],[XB,max(y+4,sy*95),z+5])
 # Exact sidewall intersection is needed; do not rely on bounding boxes.
 assert (lug^top).volume()>1,(i,'lug does not join existing shell')
 lug=lug-cx(129,y,z,1.2,18)
 # Side-load a square antirotation pocket from head interior; rear and front walls retained.
 # NutAF4, thickness1.6; pocket4.3 high/1.9 axial, access from smaller|Y| edge.
 yend=y-sy*7
 pocket=box([127.025,min(y-2.5,yend),z-2.15],[128.925,max(y+2.5,yend),z+2.15])
 lug=lug-pocket
 emit(f'R24_Lug_{i}_addition_proof',lug,'derivation_tool',installed=False)
 top=top+lug;added.append(lug)
 face=face-cx(134,y,z,1.2,8)
# Camera rear-corner stand-offs & diagonal ribs; rear camera housing seats atX129.
# Eye bolts use separate four cardinal positions; no scaled old camera posts survive.
for sy in [-1,1]:
 for sz in [-1,1]:
  y=CY+sy*10.5;z=CZ+sz*10.5
  post=cx(127,y,z,2.3,4)-cx(127,y,z,.9,8)
  # thick planar diagonal strip through corner support out to radius29mm, behind module.
  aa=np.array([CY+sy*10.5,CZ+sz*10.5]);bb=np.array([CY+sy*21.3,CZ+sz*21.3]);d=(bb-aa)/np.linalg.norm(bb-aa);n=np.array([-d[1],d[0]])*2.3
  p=md.CrossSection([[aa+n,bb+n,bb-n,aa-n]],md.FillRule.EvenOdd).extrude(3).transform(np.array([[0,0,1,125.],[1,0,0,0],[0,1,0,0]]))
  pillar=cx((128+XB)/2,bb[0],bb[1],3.5,XB-128+.04)
  print('RIB',sy,sz,face.status(),post.status(),p.status(),pillar.status(),flush=True)
  face=face+post+p+pillar
  face=face-cx(127,y,z,.9,10)
EYES=[(CY-29,CZ),(CY+29,CZ),(CY,CZ-29),(CY,CZ+29)]
bezel=(cx((XF+XF+2.4)/2,CY,CZ,33,2.4)-cx(XF+1.2,CY,CZ,25,5))+(cone(XF+2.2,149.025,CY,CZ,31.5,18)-cone(XF+2.1,149.125,CY,CZ,28,14))
for y,z in EYES:
 face=face-cx(132,y,z,1.2,12)
 bezel=bezel-cx(141,y,z,1.2,25)
 bezel=bezel-cx((XF+2.4+160)/2,y,z,2.2,160-(XF+2.4))
# Reserve the entire forward extraction corridor, not just the installed pose.
# Clip actual old head shell triangles toX>=face rear and project their occupied
# surface alongX. NonZero with CCW contours unions overlaps; offset1mm for seam.
projection_polys=[]
for shell in [oldtop,next(p for p in S['items'] if p['name']=='R12_lower_head_shell')]:
 sm=meshof(mload(shell))
 for tri in sm.triangles:
  polygon=list(tri);out=[]
  for i,a in enumerate(polygon):
   b=polygon[(i+1)%len(polygon)];ain=a[0]>=XB;bin=b[0]>=XB
   if ain:out.append(a)
   if ain!=bin:out.append(a+(b-a)*(XB-a[0])/(b[0]-a[0]))
  if len(out)<3:continue
  yz=np.array(out)[:,1:];signed=np.sum(yz[:,0]*np.roll(yz[:,1],-1)-yz[:,1]*np.roll(yz[:,0],-1))/2
  if abs(signed)<1e-10:continue
  projection_polys.append(yz if signed>0 else yz[::-1])
reserve=md.CrossSection(projection_polys,md.FillRule.NonZero).offset(1.,md.JoinType.Round)
cut=reserve.extrude(70).transform(np.array([[0,0,1,115],[1,0,0,0],[0,1,0,0]]))
face=face-cut
faceq=emit('R24_Microduck_front_face_camera_carrier',face,'printed_camera_front_face')
bezelq=emit('R24_black_camera_eye_bezel',bezel,'printed_eye_bezel','Black PA2200 PA12 SLS, density scenario')
topq=emit('R24_top_head_shell_front_cover_lugs',top,'printed_shell_derivative');topq['replaces']=[oldtop['name']]
# Nominal camera geometry, split by material, explicitly NOT precise vendor CAD.
cam=cube([132.05,CY,CZ],[6.1,25,25])
for sy in[-1,1]:
 for sz in[-1,1]:cam=cam-cx(132,CY+sy*10.5,CZ+sz*10.5,1.,12)
camq=emit('R24_REFERENCE_OS05A10_module_body',cam,'purchased_camera_envelope','Purchased OS05A10 dimensional envelope',0,True)
lensq=emit('R24_REFERENCE_OS05A10_lens',cx((PCB+LENS)/2,CY,CZ,7,LENS-PCB),'purchased_camera_envelope','Purchased OS05A10 lens envelope',0,True)
camq['mass_owner']=lensq['mass_owner']='existing camera_module_and_included_cable15g; do not sum density'
# Metal fasteners are actual solid representations with modeled bore/socket.
def hexshape(x,y,z,af,L):
 pts=[[af/math.sqrt(3)*math.cos(t),af/math.sqrt(3)*math.sin(t)]for t in np.arange(6)*math.pi/3]
 return md.CrossSection([pts]).extrude(L).transform(np.array([[0,0,1,x-L/2],[1,0,0,y],[0,1,0,z]]))
def metal(name,s):return emit(name,s,'purchased_fastener_envelope','Stainless steel fastener dimensional acceptance envelope',7.9)
def screw(name,y,z,seat,L,d):
 hd=3.8 if d==2 else 3.;h=d
 q=cx(seat-L/2,y,z,d/2,L)+cx(seat+h/2,y,z,hd/2,h)
 q=q-hexshape(seat+h-.4,y,z,1.5,1.)
 return metal(name,q)
for i,(y,z) in enumerate(MOUNTS,1):
 screw(f'R24_face_{i}_M2x10',y,z,XF,10,2)
 nut=hexshape(127.925,y,z,4,1.6)-cx(127.925,y,z,.8,4)
 nq=metal(f'R24_face_{i}_M2_captive_nut',nut);nq['host_thread_engagement']=[f'R24_face_{i}_M2x10']
 contacts.append([f'R24_face_{i}_M2x10',f'R24_face_{i}_M2_captive_nut','same M2 modeled thread engagement'])
for i,(y,z) in enumerate(EYES,1):
 screw(f'R24_eye_{i}_M2x8',y,z,XF+2.4,8,2)
 metal(f'R24_eye_{i}_washer',cx(XB-.15,y,z,2.5,.3)-cx(XB-.15,y,z,1.1,1))
 nq=metal(f'R24_eye_{i}_M2_nut',hexshape(XB-.3-.8,y,z,4,1.6)-cx(XB-1.1,y,z,.8,4));nq['host_thread_engagement']=[f'R24_eye_{i}_M2x8']
 contacts.append([f'R24_eye_{i}_M2x8',nq['name'],'same M2 modeled thread engagement'])
for i,(sy,sz) in enumerate([(a,b)for a in[-1,1]for b in[-1,1]],1):
 y=CY+sy*10.5;z=CZ+sz*10.5
 screw(f'R24_camera_{i}_M1p6x14',y,z,PCB,14,1.6)
 metal(f'R24_camera_{i}_washer',cx(124.85,y,z,2,.3)-cx(124.85,y,z,.9,1))
 nq=metal(f'R24_camera_{i}_M1p6_nut',hexshape(124.05,y,z,3.2,1.3)-cx(124.05,y,z,.65,4));nq['host_thread_engagement']=[f'R24_camera_{i}_M1p6x14']
 contacts.append([f'R24_camera_{i}_M1p6x14',nq['name'],'same M1.6 modeled thread engagement'])
# Face outline metric and exact printed-shell inclusion partition.
oldm=mload(oldtop);added_union=md.Manifold.batch_boolean(added,md.OpType.Add)
report=dict(status='CANDIDATE_REQUIRES_COLLISION_OPTICAL_ASSEMBLY_REVIEW',parts=parts,tools=tools,replaces=[oldtop['name']],sources=sources,
 design=dict(face_x_mm=[XB,XF],source_profile_plane_x_mm=134,outline_inset_mm=.35,lower_seam_trim_plane_z_mm=227.5,forward_extraction_projected_shell_clearance_mm=1.0,eye_axis_yz_mm=[CY,CZ],eye_front_x_mm=149.025,camera_lens_front_nominal_x_mm=LENS,camera_rear_seat_x_mm=SEAT,face_mount_yz_mm=MOUNTS,eye_mount_yz_mm=EYES,camera_mount_pitch_mm=21,nominal_camera_reference_only=True,unused_ToF_position='integral blank: no fictitious sensor'),
 shell_derivation=dict(status='BOOLEAN_DIFFERENCE_NUMERICALLY_INVALID_USE_INDEPENDENT_SOURCE_SURFACE_AUDIT',old_volume_mm3=oldm.volume(),new_volume_mm3=top.volume(),removed_volume_mm3=(oldm-top).volume(),addition_outside_declared_lugs_mm3=((top-oldm)-added_union).volume()),named_thread_contacts=contacts,native_seating_checks=[dict(a=a,b=b,intersection_mm3=abs((native[a]^native[b]).volume())) for a,b in [('R24_Microduck_front_face_camera_carrier','R24_black_camera_eye_bezel')]+[('R24_Microduck_front_face_camera_carrier',f'R24_face_{i}_M2x10') for i in range(1,5)]],physical_approved=False,manufacturing_approved=False)
assert all(r['intersection_mm3']<1e-8 for r in report['native_seating_checks'])
(OUT/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
new=copy.deepcopy(S);new['items']=[*parts,*[dict(p,is_new=False)for p in S['items']if p['name']!=oldtop['name']]];new['new_installed_count']=len(parts);new['retained_count']=len(new['items'])-len(parts);new['sources']={**S['sources'],**sources,rel(OUT/'manifest.json'):sha(OUT/'manifest.json')}
for p in parts:new['sources'][p['mesh']]=p['mesh_sha256']
new.update(status='R24_CANDIDATE_FRONT_COVER_OVERLAY',physical_approved=False,manufacturing_approved=False)
(OUT/'assembly_selection.json').write_text(json.dumps(new,ensure_ascii=False,indent=2)+'\n')
# Collision run excludes flexible HOME shapes, whose independent pose scope is separate.
r=copy.deepcopy(new);r['items']=[p for p in r['items'] if p['link_frame']!='MULTI_LINK_FLEX_HARNESS'];r['retained_count']=len(r['items'])-len(parts)
(OUT/'rigid_inputs.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
print('R24 BUILD',len(parts),'new objects',len(new['items']),'installed; shell delta',top.volume()-oldm.volume(),'mm3',flush=True)
