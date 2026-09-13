from pathlib import Path
import pcbnew as p,json,math,hashlib
R=Path(__file__).parent;ROOT=R.parents[2];SRC=ROOT/'work/r13-electronics/inherited/Entry_5V_R8';N='Microduck_Entry_5V_R22'
old=p.LoadBoard(str(SRC/'Microduck_Entry_5V_R8.kicad_pcb'));b=p.LoadBoard(str(R/(N+'.kicad_pcb')))
previous=json.loads((SRC/'Board_Interface_R8_Entry.json').read_text());items={r['ref']:r for r in previous['components']};oldfps={fp.GetReference():fp for fp in old.GetFootprints()}
def mat(fp):
 a=math.radians(-fp.GetOrientationDegrees());c,s=math.cos(a),math.sin(a);side=-1 if fp.GetLayer()==p.B_Cu else 1
 return [[c,-s*side],[s,c*side]]
out=[];con=[]
vertical={'J3':2,'J5':8,'J6':3,'J7':3,'J8':5}
for fp in b.GetFootprints():
 ref=fp.GetReference();of=oldfps[ref];a=mat(fp);d=mat(of);t=[[sum(a[i][k]*d[j][k]for k in range(2))for j in range(2)]for i in range(2)]
 nx,ny=[p.ToMM(z)for z in [fp.GetPosition().x,fp.GetPosition().y]];ox,oy=[p.ToMM(z)for z in [of.GetPosition().x,of.GetPosition().y]]
 tz=1 if fp.GetLayer()==of.GetLayer() else -1;tr=[nx-t[0][0]*ox-t[0][1]*oy,ny-t[1][0]*ox-t[1][1]*oy,0 if tz==1 else 1.6]
 bb=fp.GetBoundingBox(False,False);q=dict(items[ref]);q.update(xy_mm=[nx,ny],rotation_deg=fp.GetOrientationDegrees(),side='B'if fp.GetLayer()==p.B_Cu else'F',bbox_footprint_including_fab_mm=[p.ToMM(bb.GetX()),p.ToMM(bb.GetY()),p.ToMM(bb.GetRight()),p.ToMM(bb.GetBottom())],native_footprint_id=str(fp.GetFPID().GetLibNickname())+':'+str(fp.GetFPID().GetLibItemName()),source_ref=ref,source_xy_mm=[ox,oy],source_side='B'if of.GetLayer()==p.B_Cu else'F',source_rotation_deg=of.GetOrientationDegrees(),source_pcb_to_r22_pcb_rotation=[[t[0][0],t[0][1],0],[t[1][0],t[1][1],0],[0,0,tz]],source_pcb_to_r22_pcb_translation_mm=tr)
 if 'shape' in q:
  q['shape_coordinate_frame']='source PCB; apply source_pcb_to_r22 transform above'
  if q['shape'].get('length_max_mm'):q['height_from_surface_mm']=q['shape']['length_max_mm']
 q['mpn']=fp.GetField('MPN').GetText()
 if ref in vertical:
  count=vertical[ref];angle=math.radians(-fp.GetOrientationDegrees());co,si=math.cos(angle),math.sin(angle)
  def current_xy(x,y):return [nx+co*x-si*y,ny+si*x+co*y]
  corners=[current_xy(x,y)for x in[-(count+2)/2,(count+2)/2]for y in[-1.9,1.0]]
  q.update(physical_package_replaced=True,height_from_surface_mm=4.25,source_body_must_not_be_reused=True,new_package_geometry=dict(coordinate_frame='R22 native PCB; board rear z0/front z1.6',kind='JST BM top-entry header; body and solder reinforcement separate',body_bbox_xyz_minmax_mm=[min(pt[0]for pt in corners),max(pt[0]for pt in corners),min(pt[1]for pt in corners),max(pt[1]for pt in corners),1.6,5.85],header_height_from_surface_mm=4.25,mated_height_from_surface_budget_mm=6.5,manufacturer_body_xy_mm=[count+2,2.9],source='JST SH datasheet pages1 and3; BMxxB-SRSS-TB; local KiCad BM footprint Fab'))
 out.append(q)
 if ref.startswith('J'):
  original=next(c for c in previous['connector_mating_envelopes']if c['ref']==ref) if 'connector_mating_envelopes'in previous else None
  # Use manufacturer's 6.25mm mated SH length, same original conservative union.
  candidates=[v for v in previous.values()if isinstance(v,list)]
  original=next(c for lst in candidates for c in lst if isinstance(c,dict)and c.get('ref')==ref and'mating_engineering_bbox_xyz_minmax_mm'in c)
  ob=original['mating_engineering_bbox_xyz_minmax_mm'];corners=[]
  for x in ob[:2]:
   for y in ob[2:4]:corners.append([t[0][0]*x+t[0][1]*y+tr[0],t[1][0]*x+t[1][1]*y+tr[1]])
  dx,dy,dz=original['wire_exit_pcb'];qq=dict(original);qq.update(mating_engineering_bbox_xyz_minmax_mm=[min(z[0]for z in corners),max(z[0]for z in corners),min(z[1]for z in corners),max(z[1]for z in corners),ob[4],ob[5]],wire_exit_pcb=[t[0][0]*dx+t[0][1]*dy,t[1][0]*dx+t[1][1]*dy,dz]);con.append(qq)
  if ref in vertical:
   count=vertical[ref];points=[current_xy(x,y)for x in[-(count+3+.6)/2,(count+3+.6)/2]for y in[-.45-2.5,-.45+2.5]]
   qq.update(header=f'BM{count:02d}B-SRSS-TB(LF)(SN)',mating_engineering_bbox_xyz_minmax_mm=[min(pt[0]for pt in points),max(pt[0]for pt in points),min(pt[1]for pt in points),max(pt[1]for pt in points),1.6,8.1],wire_exit_pcb=[0,0,1],mated_height_from_surface_budget_mm=6.5,manufacturer_mated_height_mm=6.3,note='Actual BM top-entry header, same SHR housing and SSH contact family;6.5mm assembly-height budget,5mm straight lead,5mm bend radius and8mm unplug translation. XY uses header-body center offset of0.45mm from native footprint origin.')
wire=[]
for q in out:
 if q['ref'].startswith('W'):
  x,y=q['xy_mm'];wire.append(dict(ref=q['ref'],xy_mm=[x,y],process_courtyard_xy_mm=[x-3.5,y-3.5,x+3.5,y+3.5],solder_lead_direction_pcb=[0,0,1],back_lead_max_mm=1,front_straight_before_bend_mm=8,minimum_bend_radius_mm=8 if q['ref']in['W1','W2','W3','W4'] else 5,independent_strain_relief_required=True))
report=dict(status='R22 DESIGN REVIEW CANDIDATE FROZEN; NATIVE ERC/DRC VERIFIED; NO PHYSICAL TESTS',board_mm=[52,42,1.6],mounts_xy_mm=[[3,3],[23,3],[3,39],[49,39]],mount_diameter_mm=2.2,front_height_from_surface_max_mm=13.0,back_height_max_mm=2.7,back_component_to_material_gap_min_budget_mm=.5,components=out,connector_mating_envelopes=con,wire_termination_envelopes=wire,stackup_mm=[dict(layer='F.Cu',thickness=.07),dict(layer='prepreg1',thickness=.185),dict(layer='In1.Cu GND',thickness=.035),dict(layer='core',thickness=1.00),dict(layer='In2.Cu signal',thickness=.035),dict(layer='prepreg2',thickness=.185),dict(layer='B.Cu',thickness=.07)],mask_each_mm=.01,source_interface_sha256=hashlib.sha256((SRC/'Board_Interface_R8_Entry.json').read_bytes()).hexdigest(),native_pcb_sha256=hashlib.sha256((R/(N+'.kicad_pcb')).read_bytes()).hexdigest(),thermal_note='No qualified ambient, enclosure airflow or measured temperature rise. Do not infer continuous3A thermal approval from four layers or DRC.')
(R/'Board_Interface_R22_Entry.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(len(out),'components;',len(con),'mated connectors;',len(wire),'wire joints')
