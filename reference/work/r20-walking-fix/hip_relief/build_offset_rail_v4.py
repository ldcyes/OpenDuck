"""Retain all source end interfaces and reroute the full-diameter mid-span."""
from pathlib import Path
import sys,json,hashlib,copy,math
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent/'candidate_v4';OUT.mkdir(exist_ok=True)
sys.path[:0]=[str(ROOT/'work/python-deps'),str(ROOT/'work/r12-motion/python-deps'),str(ROOT/'work/rk-mechanics/python-deps'),str(ROOT/'work/r13-electronics/mechanics'),str(ROOT/'work/r18-leg-hip-covers/review')]
import numpy as np
import common as c
import trimesh,manifold3d as md
from motion_core import transforms,relative_motion_budget,certify_segment
from OCP.BRepTools import BRepTools
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.StlAPI import StlAPI_Writer
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCone
from OCP.gp import gp_Ax2,gp_Pnt,gp_Dir
SOURCES={}
def bind(p,h=None):
 p=Path(p);p=p if p.is_absolute()else ROOT/p;s=hashlib.sha256(p.read_bytes()).hexdigest();assert h is None or s==h;SOURCES[str(p.relative_to(ROOT))]=s;return p
def read(p):return json.loads(bind(p).read_text())
sel=read('work/r20-walking-fix/head_mount/assembly_selection.json');by={r['name']:r for r in sel['items']};old_name='R11_hip_l_rail_2';new_name='R20_left_hip_rail_offset';saddle_name='left_hip_roll_fixed'
record=next(r for r in read('work/r11-integration/mechanics/serial_cad_v4/manifest.json')['parts']if r['name']==old_name);oldrow=by[old_name];oldshape=c.read(bind(oldrow['step'],oldrow['step_sha256']));oldmesh=trimesh.load(bind(oldrow['mesh'],oldrow['mesh_sha256']),force='mesh');ports=record['interfaces'];oldpath=record['paths'][0]['full_rail_points_mm'];path=copy.deepcopy(oldpath)
for i in [3,4]:
 path[i][0]=8.5;path[i][2]+=4.
path.insert(5,copy.deepcopy(oldpath[4]))
path[2][2]+=8.
raised=copy.deepcopy(oldpath[1]);raised[2]+=8.;path.insert(2,raised)
def portplate(p):
 return c.tf(c.box((0,0,1.5),(2*p['half_pitch_mm']+8,10,3)),np.array([p['u'],p['v'],p['normal_out']]).T,p['point_mm'])
def holes(s,p):
 hp=p['half_pitch_mm'];hr=p['diameter_mm']/2;cr=p['countersink_diameter_mm']/2;R=np.array([p['u'],p['v'],p['normal_out']]).T;t=np.array(p['point_mm'])
 for u in [-hp,hp]:
  s=c.cut(s,c.tf(c.cylinder((u,0,3),hr,14,(0,0,1)),R,t));cone=BRepPrimAPI_MakeCone(gp_Ax2(gp_Pnt(u,0,3),gp_Dir(0,0,-1)),cr,hr,cr-hr).Shape();s=c.cut(s,c.tf(cone,R,t))
 return s
shape=c.union(c.union(portplate(ports[0]),c.rod(path,5)),portplate(ports[1]));shape=holes(holes(shape,ports[0]),ports[1]);p=c.properties(shape);assert p['valid_BRep']and p['solid_count']==1
rec=c.export(new_name,shape,OUT/'CAD','7075-T651 CNC candidate',2.8,'hip_l',notes='φ10 rod section and original two 3mm end plates retained; two internal bend centers shifted to HOME X8.5mm. Geometry candidate pending full assembly review and load/DFM qualification.',interfaces=ports)
sp=OUT/'CAD'/rec['STEP'];mp=OUT/'CAD'/rec['STL'];reread=c.read(sp);BRepTools.Clean_s(reread);BRepMesh_IncrementalMesh(reread,.008,False,.05,False).Perform();writer=StlAPI_Writer();writer.ASCIIMode=False;assert writer.Write(reread,str(mp));mesh=trimesh.load(mp,force='mesh')
# OCC produced one exactly zero-area repeated-index triangle at a source elbow.
# Retain the raw bytes; remove only zero-area faces, without moving any vertex,
# filling a boundary or fusing disconnected material.
rawp=OUT/'CAD'/'raw_OCC_mesher.stl';rawp.write_bytes(mp.read_bytes());before_volume=float(mesh.volume);zero_faces=np.flatnonzero(mesh.area_faces==0);removed_faces=mesh.faces[zero_faces].tolist()
if len(zero_faces):mesh.update_faces(mesh.area_faces>0);mesh.export(mp)
mesh=trimesh.load(mp,force='mesh');assert mesh.is_watertight and mesh.is_winding_consistent and mesh.volume>0 and abs(mesh.volume-before_volume)<1e-9
cleanup=dict(raw_mesh=str(rawp.relative_to(ROOT)),raw_mesh_sha256=hashlib.sha256(rawp.read_bytes()).hexdigest(),removed_exactly_zero_area_face_count=len(zero_faces),removed_face_vertex_indices=removed_faces,vertex_coordinates_modified=False,hole_filling_performed=False,volume_change_mm3=float(mesh.volume-before_volume))
rec.update(step=str(sp.relative_to(ROOT)),mesh=str(mp.relative_to(ROOT)),step_sha256=hashlib.sha256(sp.read_bytes()).hexdigest(),mesh_sha256=hashlib.sha256(mp.read_bytes()).hexdigest(),mesh_closed_positive=True,mesh_volume_mm3=float(mesh.volume),mesh_vs_STEP_relative_volume_error=abs(mesh.volume-p['volume_mm3'])/p['volume_mm3'],link_frame='hip_l',R=np.eye(3).tolist(),t_mm=[0,0,0],geometry_scale=[1,1,1],replaces_name=old_name,old_path_HOME_mm=oldpath,new_path_HOME_mm=path,centerline_changed_indices=[3,4],retained_axial_terminal_old_path_segment=[4,5],midspan_raise_Z_mm=4.,retained_rod_diameter_mm=10.,blend_sphere_radius_mm=5.03)
assert rec['mesh_vs_STEP_relative_volume_error']<.002
rec['centerline_changed_indices']=[2,3,4,5];rec['centerline_changed_index_basis']='zero-based new_path_HOME_mm, full source mapping follows';rec['proximal_long_stem_raise_Z_mm']=8.;rec['retained_axial_proximal_old_path_segment']=[0,1];rec['old_to_new_path_mapping']=[dict(old_point_index=i,new_point_index=j,operation=op,old_HOME_mm=oldpath[i],new_HOME_mm=path[j],delta_HOME_mm=(np.array(path[j])-oldpath[i]).tolist())for i,j,op in [(0,0,'retained'),(1,1,'retained'),(1,2,'inserted_raised_copy'),(2,3,'raised_original'),(3,4,'offset_and_raised_original'),(4,5,'inserted_offset_and_raised_copy'),(4,6,'retained'),(5,7,'retained')]];rec['mesher_degenerate_face_cleanup']=cleanup;rec['mesh_cleanup_evidence']=cleanup;rec['sha256_STL']=rec['mesh_sha256'];bind(sp);bind(mp);bind(rawp)
# Both exact original port plates, including all hole and countersink boundaries,
# remain identical throughout the plate itself. Do not extend this protected
# domain into the intentionally changed rear rod approach.
interface=[]
for port in ports:
 R=np.array([port['u'],port['v'],port['normal_out']]).T;t=np.array(port['point_mm']);region=portplate(port)
 oldmat=c.common(oldshape,region);newmat=c.common(shape,region);removed=abs(c.volume(c.cut(oldmat,newmat)));added=abs(c.volume(c.cut(newmat,oldmat)));assert max(removed,added)<1e-5,(port['name'],removed,added)
 interface.append(dict(name=port['name'],source_holes_HOME_mm=port['holes_mm'],normal_out=port['normal_out'],plate_thickness_mm=3.,through_diameter_mm=3.4,countersink_diameter_mm=6.3,countersink_angle_deg=90.,minimum_plate_under_countersink_mm=1.55,minimum_outer_edge_to_through_hole_mm=2.3,minimum_outer_edge_to_countersink_mm=.85,protected_plate_removed_mm3=removed,protected_plate_added_mm3=added))

# Independently compare the complete new rod and all original native port hosts.
host_checks=[];tool_checks=[]
for port in ports:
 hr=by[port['host_item']];host=c.tf(c.read(bind(hr['step'],hr['step_sha256'])),hr['R'],hr['t_mm']);before_common=abs(c.volume(c.common(oldshape,host)));after_common=abs(c.volume(c.common(shape,host)));assert after_common<1e-7,(port['name'],'NEW_HOST_PENETRATION',after_common)
 host_checks.append(dict(host=port['host_item'],old_original_STEP_common_mm3=before_common,new_original_STEP_common_mm3=after_common))
 axis=np.array(port['normal_out'])
 for hole in port['holes_mm']:
  tool=c.cylinder(np.array(hole)+axis*(3.05+12.5),1.5,25,axis);common=abs(c.volume(c.common(shape,tool)));assert common<1e-7,(port['name'],'TOOL_BLOCKED',common)
  tool_checks.append(dict(port=port['name'],hole_HOME_mm=hole,axis_out=axis.tolist(),shaft_diameter_mm=3.,shaft_exposed_length_mm=25.,starts_beyond_outer_plate_face_mm=.05,new_rail_common_mm3=common))
(OUT/'host_and_tool_self_access.json').write_text(json.dumps(dict(status='PASS_ORIGINAL_PORT_HOST_MATERIAL_AND_D3_TOOL_SELF_ACCESS',full_assembly_tool_access_approved=False,hosts=host_checks,tool_corridors=tool_checks,sources=SOURCES),indent=2)+'\n')

# Continuous one-axis certification across the exact reference envelope plus
# a stated +/-3-degree tracking scenario. No finite point sweep is called proof.
srow=by[saddle_name];sm=trimesh.load(bind(srow['mesh'],srow['mesh_sha256']),force='mesh');bind(srow['step'],srow['step_sha256']);sv=np.array(sm.vertices)@np.array(srow['R']).T+srow['t_mm'];S=md.Manifold(md.Mesh64(np.array(sv,dtype=np.float64),np.array(sm.faces,dtype=np.uint64)));V=np.array(mesh.vertices);B=md.Manifold(md.Mesh64(V.copy(),np.array(mesh.faces,dtype=np.uint64)));assert S.status()==B.status()==md.Error.NoError
traj=read('work/r20-walking-fix/gait/trajectory_4steps_v1.json');rolls=[r['q_HOME_delta_deg']['left_hip_roll']for r in traj['keypoints']];low=min(rolls)-3.;high=max(rolls)+3.;q0={j['joint']:0. for j in sel['joints']};q1=q0.copy();q0['left_hip_roll']=low;q1['left_hip_roll']=high
budget=relative_motion_budget(sel['joints'],srow['link_frame'],'hip_l',sv,V,q0,q1);visited={}
def gap(u):
 if u not in visited:
  q={n:q0[n]+u*(q1[n]-q0[n])for n in q0};T=transforms(sel['joints'],q);rel=np.linalg.inv(T[srow['link_frame']])@T['hip_l'];bb=B.transform(rel[:3]);gg=float(S.min_gap(bb,8));iv=float((S^bb).volume())if gg<1e-6 else 0.;visited[u]=dict(parameter_u=u,left_hip_roll_deg=q['left_hip_roll'],gap_mm=gg,common_mm3=iv)
 return visited[u]['gap_mm']
certificate=certify_segment(gap,budget,target_mm=2.2,max_depth=16)
assert certificate['passed'],certificate
# The moving rod must also clear the actual motor source, not only its saddle.
mr=by['left_hip_roll_motor'];mm=trimesh.load(bind(mr['mesh'],mr['mesh_sha256']),force='mesh');mv=np.array(mm.vertices)@np.array(mr['R']).T+mr['t_mm'];MS=md.Manifold(md.Mesh64(mv.copy(),np.array(mm.faces,dtype=np.uint64)));assert MS.status()==md.Error.NoError
motor_budget=relative_motion_budget(sel['joints'],mr['link_frame'],'hip_l',mv,V,q0,q1);motor_visited={}
def motor_gap(u):
 if u not in motor_visited:
  q={n:q0[n]+u*(q1[n]-q0[n])for n in q0};T=transforms(sel['joints'],q);rel=np.linalg.inv(T[mr['link_frame']])@T['hip_l'];bb=B.transform(rel[:3]);gg=float(MS.min_gap(bb,3));motor_visited[u]=dict(parameter_u=u,left_hip_roll_deg=q['left_hip_roll'],gap_mm=gg)
 return motor_visited[u]['gap_mm']
motor_certificate=certify_segment(motor_gap,motor_budget,target_mm=2.2,max_depth=12)
(OUT/'motor_saddle_continuous_clearance.json').write_text(json.dumps(dict(status='TWO_SOURCE_PAIRS_COMPLETE_CONTINUOUS_ROLL_RESULTS',physical_approved=False,certified_roll_range_deg=[low,high],motor=dict(certificate=motor_certificate,visited=list(motor_visited.values())),saddle=dict(certificate=certificate,visited=list(visited.values())),sources=SOURCES),indent=2)+'\n')
assert motor_certificate['passed'],motor_certificate
oldmass=next(r for r in read('work/r17-module-mount/mass_COM_update.json')['rows']if r['name']==old_name);newmass=dict(name=new_name,link='hip_l',COM_home_mm=p['center_mm'],low_g=rec['mass_from_CAD_g'],nominal_g=rec['mass_from_CAD_g'],high_g=rec['mass_from_CAD_g'],measured=False,category='R20 rerouted full-section original interface rail',basis='Original STEP end interfaces, new valid single-solid CAD at inherited7075density2.8g/cm3; material and load assumptions not hardware-qualified.',I_COM_home_kg_m2=(np.array(p['unit_density_inertia_mm5'])*2.8e-12).tolist(),I_COM_home_per_kg_m2=(np.array(p['unit_density_inertia_mm5'])*1e-6/p['volume_mm3']).tolist(),COM_uncertainty_halfwidth_HOME_mm=[.5,.5,.5],sources={rec['step']:rec['step_sha256'],rec['mesh']:rec['mesh_sha256']})
bind(__file__);bind('work/r13-electronics/mechanics/common.py');bind('work/r13-electronics/mechanics/cad_backend.py');bind('work/r18-leg-hip-covers/review/motion_core.py')
item=copy.deepcopy(oldrow);item.update(name=new_name,label_zh='左髋连接杆 · φ10截面中段避让',source_group='R20_hip_relief',source_manifest='work/r20-walking-fix/hip_relief/candidate_v4/candidate_manifest.json',mesh=rec['mesh'],mesh_sha256=rec['mesh_sha256'],step=rec['step'],step_sha256=rec['step_sha256'],R=np.eye(3).tolist(),t_mm=[0,0,0],replaces_name=old_name,notes_zh=['保持两端孔位和φ10承力杆直径，内部两个转折点移至HOME X=8.5mm。','仅局部运动几何通过；整机、制造与强度仍需复核。'])
manifest=dict(status='LOCAL_HIP_RAIL_OFFSET_CANDIDATE_FULL_ASSEMBLY_REVIEW_PENDING',physical_approved=False,manufacturing_approved=False,removed_names=[old_name],parts=[item],cad_parts=[rec],sources=SOURCES)
for name,data in [('candidate_manifest.json',manifest),('interface_preservation.json',dict(status='EXACT_SOURCE_PORT_MATERIAL_PRESERVED',interfaces=interface,sources=SOURCES)),('local_continuous_clearance.json',dict(status='PASS_2P2MM_LOCAL_RIGID_MESH_CONTINUOUS_ROLL_BUDGET_ONLY',physical_approved=False,reference_roll_range_deg=[min(rolls),max(rolls)],tracking_scenario_each_side_deg=3,certified_roll_range_deg=[low,high],certificate=certificate,visited=sorted(visited.values(),key=lambda r:r['parameter_u']),sources=SOURCES)),('mass_inertia_delta.json',dict(status='CAD_NOMINAL_MASS_INERTIA_DELTA',physical_approved=False,remove_mass_rows=[old_name],add_mass_rows=[newmass],old_mass_row=oldmass,delta_nominal_g=newmass['nominal_g']-oldmass['nominal_g'],before_nominal_kg=4.193000872961529,after_nominal_kg=4.193000872961529+(newmass['nominal_g']-oldmass['nominal_g'])/1000,sources=SOURCES))]:
 (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(name=new_name,shape_volume_mm3=p['volume_mm3'],mass_g=newmass['nominal_g'],mass_delta_g=newmass['nominal_g']-oldmass['nominal_g'],minimum_observed_gap_mm=min(r['gap_mm']for r in visited.values()),continuous_pass=certificate['passed'],roll_range_deg=[low,high],interface=interface),indent=2),flush=True)
