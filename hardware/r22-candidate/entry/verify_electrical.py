from pathlib import Path
import pcbnew as p,json,csv,hashlib,xml.etree.ElementTree as E,collections
R=Path(__file__).parent;ROOT=R.parents[2];SRC=ROOT/'work/r13-electronics/inherited/Entry_5V_R8';N='Microduck_Entry_5V_R22';OLD='Microduck_Entry_5V_R8'
new=p.LoadBoard(str(R/(N+'.kicad_pcb')));old=p.LoadBoard(str(SRC/(OLD+'.kicad_pcb')))
def footprints(b):return{fp.GetReference():fp for fp in b.GetFootprints()}
def pads(b):
 out=[]
 for fp in b.GetFootprints():
  for pd in fp.Pads():
   if pd.GetNumber().isdigit()and(pd.IsOnLayer(p.F_Cu)or pd.IsOnLayer(p.B_Cu)):out.append((fp.GetReference(),pd.GetNumber(),pd.GetNetname()))
 return sorted(out)
def netlist(path):
 d={}
 for net in E.parse(path).getroot().findall('./nets/net'):
  for node in net.findall('node'):
   if not node.attrib['ref'].startswith('#'):d[(node.attrib['ref'],node.attrib['pin'])]=net.attrib['name']
 return d
of,nf=footprints(old),footprints(new);op,np=pads(old),pads(new);on=netlist(R/'verification/source_schematic.xml');nn=netlist(R/'verification/new_schematic.xml')
assert set(of)==set(nf)and len(nf)==58
assert op==np,'Native numbered copper pad net membership changed'
assert on==nn,'Schematic pin/net map changed'
for ref,pin,net in np:
 if(ref,pin)in nn:assert nn[(ref,pin)]==net,(ref,pin,net,nn[(ref,pin)])
changes=[];bom=[]
vertical={'J3':2,'J5':8,'J6':3,'J7':3,'J8':5};mpn_changes=[]
for ref,fp in sorted(nf.items()):
 prev=of[ref];assert prev.GetValue()==fp.GetValue()
 if ref in vertical:
  assert fp.GetField('MPN').GetText()==f'BM{vertical[ref]:02d}B-SRSS-TB(LF)(SN)'
  mpn_changes.append(dict(ref=ref,source_MPN=prev.GetField('MPN').GetText(),r22_MPN=fp.GetField('MPN').GetText(),reason='Host clearance requires top-entry; same SH-family SHR housing/SSH contact, all pin/net functions retained'))
 else:assert prev.GetField('MPN').GetText()==fp.GetField('MPN').GetText()
 oldid=str(prev.GetFPID().GetLibNickname())+':'+str(prev.GetFPID().GetLibItemName());newid=str(fp.GetFPID().GetLibNickname())+':'+str(fp.GetFPID().GetLibItemName())
 if oldid!=newid:changes.append(dict(ref=ref,source_footprint=oldid,new_footprint=newid,reason='JST BM top-entry manufacturer package, physical pin numbering retained'if ref in vertical else'TI DGS0010A official 1.45x0.30mm pad,4.4mm row span; physical package/MPN/pin numbering retained'))
 pos=fp.GetPosition();bom.append([ref,fp.GetValue(),fp.GetField('MPN').GetText(),newid,'B'if fp.GetLayer()==p.B_Cu else'F',p.ToMM(pos.x),p.ToMM(pos.y),fp.GetOrientationDegrees(),fp.GetField('Datasheet').GetText()])
with(R/'assembly/BOM_R22_Entry.csv').open('w',newline='')as f:
 w=csv.writer(f);w.writerow(['reference','value','MPN','footprint','side','x_mm','y_mm','rotation_deg','datasheet']);w.writerows(bom)
with(R/'assembly/Pin_to_Net_R22_Entry.csv').open('w',newline='')as f:
 w=csv.writer(f);w.writerow(['reference','physical_pin','net']);w.writerows([(*key,val)for key,val in sorted(nn.items())])
with(R/'verification/pin_equivalence.csv').open('w',newline='')as f:
 w=csv.writer(f);w.writerow(['ref','pin','source_net','r22_net','equal']);w.writerows([(*key,on[key],nn[key],True)for key in sorted(on)])
sch=(R/(N+'.kicad_sch')).read_text();source_sch=(SRC/(OLD+'.kicad_sch')).read_text();reverse=sch.replace('Microduck_Entry_R8:TI_DGS0010A_Manufacturer_1p45x0p30','Package_SO:MSOP-10_3x3mm_P0.5mm')
for count in set(vertical.values()):reverse=reverse.replace(f'BM{count:02d}B-SRSS-TB(LF)(SN)',f'SM{count:02d}B-SRSS-TB(LF)(SN)').replace(f'JST_SH_BM{count:02d}B-SRSS-TB_1x{count:02d}-1MP_P1.00mm_Vertical',f'JST_SH_SM{count:02d}B-SRSS-TB_1x{count:02d}-1MP_P1.00mm_Horizontal')
assert reverse==source_sch
report=dict(footprints=58,numbered_copper_pad_instances=len(np),schematic_physical_pins=len(nn),native_pad_net_multiset_equal=True,schematic_pin_net_map_equal=True,unchanged_MPN_count=53,all_values_and_all_IC_MPN_identical=True,explicit_connector_MPN_substitutions=mpn_changes,schematic_change_limited_to_seven_footprint_properties_and_five_connector_MPN_properties=True,footprint_changes=changes,logic_connectors=8,power_wire_joints=8,shunt='WSL27262L000FEA;2mOhm;4 terminals',logic_fuse='0448002.MR;2A',module='LMZM33603RLRR;5.10V;3A maximum IC rating',load_budget='2.7A design load;3A budget ceiling;no physical load or temperature validation',pcb_sha256=hashlib.sha256((R/(N+'.kicad_pcb')).read_bytes()).hexdigest(),source_pcb_sha256=hashlib.sha256((SRC/(OLD+'.kicad_pcb')).read_bytes()).hexdigest(),source_schematic_sha256=hashlib.sha256((SRC/(OLD+'.kicad_sch')).read_bytes()).hexdigest())
(R/'verification/electrical_equivalence.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False))
