"""Compose the frozen head and full-section hip-rail revisions without editing them."""
from pathlib import Path
import json,hashlib,copy
ROOT=Path(__file__).resolve().parents[2];WORK=ROOT/'work/r20-walking-fix';OUT=WORK/'assembly_final'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
sources={}
def read(p):
 p=WORK/p;sources[str(p.relative_to(ROOT))]=sha(p);return json.loads(p.read_text())
head=read('head_mount/assembly_selection.json');hm=read('head_mount/candidate_manifest.json');hip=read('hip_relief/candidate_v4/candidate_manifest.json');mass=read('hip_relief/candidate_v4/mass_inertia_delta.json');sources.update(hip['sources']);sources.update(hm['sources'])
assert len(head['items'])==557 and len(hip['parts'])==1
new=hip['parts'][0];oldname=new['replaces_name'];assert oldname=='R11_hip_l_rail_2';old=next(r for r in head['items']if r['name']==oldname)
row=copy.deepcopy(old);row.update(new);row.update(label_zh='左髋侧摆连接杆 · 避让与工具通道修订',source_group='R20_hip_rail_offset',source_manifest='work/r20-walking-fix/hip_relief/candidate_v4/candidate_manifest.json',replaces_name=oldname,manufacturing_approved=False,mass_is_not_computed_from_viewer_geometry=True)
assert row['link_frame']==old['link_frame']
selection=copy.deepcopy(head);selection['items']=[row if r['name']==oldname else r for r in head['items']];selection.update(status='R20_HEAD_AND_HIP_RAIL_ENGINEERING_REVISION_VALIDATION_PENDING',physical_approved=False,manufacturing_approved=False,nominal_mass_kg=mass['after_nominal_kg'])
manifest=dict(status=selection['status'],parts=hm['parts']+[row],removed_names=hm['removed_names'],physical_approved=False,manufacturing_approved=False,sources=sources.copy())
sources[str(Path(__file__).relative_to(ROOT))]=sha(__file__);manifest['sources']=sources.copy()
assert len(selection['items'])==len({r['name']for r in selection['items']})==557
for p,h in sources.items():assert sha(ROOT/p)==h,(p,'SOURCE_CHANGED')
for r in selection['items']:
 for key,hk in [('mesh','mesh_sha256'),('step','step_sha256')]:
  if r.get(key)and r.get(hk):assert sha(ROOT/r[key])==r[hk],(r['name'],key,'SOURCE_CHANGED')
OUT.mkdir(exist_ok=True)
for fn,data in [('assembly_selection.json',selection),('candidate_manifest.json',manifest)]:
 p=OUT/fn;p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');print(fn,sha(p),flush=True)
index=dict(status='COMPOSED_SOURCE_SELECTION_ONLY_NOT_GEOMETRY_APPROVAL',parts=557,nominal_mass_kg=mass['after_nominal_kg'],baseline_head_items=557,replaced_material=oldname,new_material=row['name'],all_other556_rows_exactly_retained=all(r==next(x for x in head['items']if x['name']==r['name'])for r in selection['items']if r['name']!=row['name']),kinematic_joints_exactly_retained=selection['joints']==head['joints'],files=[dict(path=str((OUT/fn).relative_to(ROOT)),sha256=sha(OUT/fn))for fn in ['assembly_selection.json','candidate_manifest.json']],sources=sources)
(OUT/'composition_check.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n')
