"""Freeze R26's two new covers against every other installed rigid item."""
from pathlib import Path
import json,copy,hashlib
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent/'mechanics/motion_delta'
sp=ROOT/'work/r26-cover-first/assembly_selection.json';s=json.loads(sp.read_text());assert len(s['items'])==1224 and len(s['joints'])==15
newnames=set(s['new_part_names']);assert newnames=={'R26_L_thigh_short_cover','R26_R_thigh_short_cover'}
new=[copy.deepcopy(p)for p in s['items']if p['name']in newnames]
old=[copy.deepcopy(p)for p in s['items']if p['name']not in newnames and p['link_frame']!='MULTI_LINK_FLEX_HARNESS']
for p in new:p['is_new']=True
for p in old:p['is_new']=False
assert len(new)==2 and len(old)==1191
s.update(status='R26_DIRECT_TWO_COVER_RIGID_INTERVAL_CHECK',items=new+old,new_installed_count=2,retained_count=1191,
 interval_bounds_path='work/r21-reduced-sway/dynamics/full_v3/nominal/interval_joint_bounds.json',
 interval_bounds_sha256=hashlib.sha256((ROOT/'work/r21-reduced-sway/dynamics/full_v3/nominal/interval_joint_bounds.json').read_bytes()).hexdigest(),
 physical_approved=False,manufacturing_approved=False,
 limits=['Only pairs involving new R26 covers are directly checked; retained-retained pairs inherit R25 ledger.',
 '31 flexible free-neck items are excluded; floor and physical tolerance/deformation are not modeled.'])
OUT.mkdir(parents=True,exist_ok=True)
(OUT/'inputs.json').write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n')
(OUT/'input_binding.json').write_text(json.dumps({'r26_selection':'work/r26-cover-first/assembly_selection.json','r26_selection_sha256':hashlib.sha256(sp.read_bytes()).hexdigest(),'installed_rigid_items':1193,'new_covers':sorted(newnames),'excluded_flexible_items':31,'interval_bounds_sha256':s['interval_bounds_sha256']},indent=2)+'\n')
print('R26_RIGID_INPUTS',len(s['items']),len(new),len(old))
