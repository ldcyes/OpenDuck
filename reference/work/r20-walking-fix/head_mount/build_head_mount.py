"""Retain the four original cooling lugs as the only front compression member."""
from head_common import *
import re

bind(__file__);bind(OUT/'head_common.py')
parts=[];joints=[]
for i,(y,z) in enumerate(HOLES,1):
    pp,j=hardware('X',[102.74454072117805,y,z],2,22,3.8,2,1.5,1,4,1.6,5,.3,17.3,f'R20_CM4_stack_{i}_M2')
    j.update(id=f'CM4_STACK_{i}',nominal_thread_pitch_mm=.4,minimum_catalog_thread_length_mm=16,
             front_contact_host='R10_HEAD_R8_CM4_6061_finned_heatsink',rear_contact_host='R11_CM4_rear_cradle_and_diagonal_arms')
    joints.append(j)
    for n,s in pp:
        q=export(n,s,notes='M2x22 DIN912/ISO4762 length; through stack. Thread/root envelope, not a helical manufacturing toolpath. Mating thread intersection only has a named bounded interface.');parts.append(q)
for i,(x,y,z) in enumerate(FEET,1):
    pp,j=hardware('Z',[x,y,225.5],2.5,10,4.5,2.5,2,1.2,5,2,6,.5,6,f'R20_CM4_foot_{i}_M2p5')
    j.update(id=f'CM4_FOOT_{i}',nominal_thread_pitch_mm=.45,
             front_contact_host='R11_CM4_rear_cradle_and_diagonal_arms',rear_contact_host='R13_head_shell_carrier_Entry_ports')
    joints.append(j)
    for n,s in pp:
        q=export(n,s,notes='M2.5x10 through existing 3mm cradle foot and 3mm head frame; one top washer, rear hex nut. Thread envelope only.');parts.append(q)

# The old carrier item is a solid box. Restore only its four *existing* native NPTHs.
contract=load('outputs/Microduck_RK_R8_制造设计/电气/CM4_Carrier_R8/Board_Interface_R8_CM4_Carrier.json')
kicad=bind('outputs/Microduck_RK_R8_制造设计/电气/CM4_Carrier_R8/Microduck_CM4_Carrier_R8.kicad_pcb')
text=kicad.read_text()
assert '(thickness 1.6)' in text
assert contract['board_mm']==[58,45,1.6] and contract['hole_diameter_mm']==2.7
def balanced_blocks(txt,tag):
    start=0
    while True:
        a=txt.find('('+tag+' ',start)
        if a<0:return
        depth=0;quoted=False;escape=False
        for end in range(a,len(txt)):
            ch=txt[end]
            if ch=='"' and not escape:quoted=not quoted
            if not quoted:
                if ch=='(':depth+=1
                if ch==')':depth-=1
            if depth==0 and end>a:
                yield txt[a:end+1];start=end+1;break
            escape=(ch=='\\' and not escape)
npths=[]
for block in balanced_blocks(text,'footprint'):
    if 'np_thru_hole' not in block:continue
    ref=re.search(r'\(property "Reference" "([^"]+)"',block).group(1)
    xy=re.search(r'\(at ([\d.\-]+) ([\d.\-]+)',block)
    pad=next(balanced_blocks(block,'pad'))
    diameter=float(re.search(r'\(drill ([\d.]+)\)',pad).group(1))
    npths.append(dict(ref=ref,xy_mm=[float(xy[1]),float(xy[2])],diameter_mm=diameter))
assert len(npths)==4 and all(p['diameter_mm']==2.7 for p in npths)
assert sorted(p['xy_mm'] for p in npths)==sorted(contract['holes_xy_mm'])
old=BY['R10_HEAD_CM4carrier_PCB']
m=trimesh.load(bind(old['mesh'],old['mesh_sha256']),force='mesh')
world=np.asarray(m.vertices)@np.asarray(old['R']).T+old['t_mm']
lo,hi=world.min(0),world.max(0)
assert np.max(abs((hi-lo)-[1.6,58,45]))<1e-5
# The precise millimetre contract is used, not the old single-precision box rounding.
carrier=c.box([112.54454072117805,-2.347290277481079,281.0042672753334],[1.6,58,45])
for y,z in HOLES:carrier=c.cut(carrier,c.cyl([112.54454072117805,y,z],1.35,3,'X'))
q=export('R20_CM4carrier_PCB_existing_NPTH_geometry',carrier,folder='board_representation',material='Existing 1.6mm PCB; source-derived representation only',density=1.85,notes='No PCB circuit/outline/mounting axis change. Replaces the obsolete hole-less box using current KiCad four2.7NPTH and1.6general thickness. Previous1.51mm exportedpreview is not used as installed thickness.')
q['replaces_name']='R10_HEAD_CM4carrier_PCB';q['mass_change_g']=0.;q['mass_basis']='Board population already in electrical_CM4_SOM_carrier_cooling; no added PCB mass.'
q['source_NPTHs']=npths

assembly=[]
for p in parts+[q]:
    item=copy.deepcopy(BY['R11_CM4_front_clamp_bar_1'] if p in parts else old)
    item.update(name=p['name'],label_zh=('头部紧固件 · ' if p in parts else '现有核心板载板 · 已有安装孔实体')+p['name'],
       category='10_fasteners_insulation' if p in parts else '06_electronics',category_zh='紧固件与绝缘件' if p in parts else '电路板与元器件参考',
       source_group='R20_head_mount',source_manifest=rel(OUT/'head_mount_delta.json'),mesh=p['mesh'],mesh_sha256=p['mesh_sha256'],step=p['step'],step_sha256=p['step_sha256'],
       R=np.eye(3).tolist(),t_mm=[0.,0.,0.],geometry_scale=[1,1,1],kind='nominal_purchased_hardware' if p in parts else 'source_derived_existing_PCB_NPTH_material',
       reference_only=p in parts,material=p['material'],replaces_name=p.get('replaces_name'),manufacturing_approved=False,
       notes_zh=[p['notes']],visible_default=True)
    assembly.append(item)

delta=dict(status='HEAD_MOUNT_GEOMETRY_CANDIDATE_REQUIRES_INTERFACE_AND_COLLISION_AUDIT',physical_approved=False,manufacturing_approved=False,
    baseline_selection=SEL_PATH,baseline_selection_sha256=sha(ROOT/SEL_PATH),removed_names=REMOVED,
    replacements=[dict(old_name=q['replaces_name'],new_name=q['name'],reason='Add the four existing source-confirmed NPTHs to displayed PCB material; no physical PCB change')],
    parts=parts,board_representation=q,added_or_replacement_items=assembly,joints=joints,
    unchanged=['Original heatsink/4mounting ears','4mm front PEEK','1.5mm B2B PEEK','5mm rear PEEK','Core and carrier locations','Original four mounting axes','Rear cradle/frame holes','Exterior shape'],
    limits=['Purchased fasteners are dimensioned nominal assemblies, not CNC thread models or supplier-qualified lots.',
      'No original PCB/reference mass is added again. Fastener mass/reserve allocation is delivered separately.',
      'The hidden vendor maximum box remains an independent conservative reference, not solid core material.',
      'R18/R19 originals are not overwritten.'],sources=SOURCES)
dump(OUT/'head_mount_delta.json',delta)
print('BUILT',len(parts),'hardware + 1 board representation',flush=True)
