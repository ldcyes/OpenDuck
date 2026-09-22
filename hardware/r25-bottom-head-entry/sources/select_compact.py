from pathlib import Path
import json,hashlib,copy
ROOT=Path(__file__).resolve().parents[2];O=Path(__file__).parent
load=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
S=load(ROOT/'work/r24-head-front/assembly_selection.json');M=load(O/'mechanics/manifest.json');T=load(O/'tails/manifest.json')
fp=O/'flex/compact_bundle_home/manifest.json';assert fp.exists(),'Await source-bound new-center physical-length HOME'
F=load(fp);parts=M['parts']+T['parts']+F['parts'];replaces=M['replaces']+T['replaces']+F['replaces'];assert len(set(replaces))==len(replaces)
for p in parts:
 p['is_new']=True;p['input_group']='R25_bottom_entry'
 for k in ['mesh','step','analysis_mesh']:
  if p.get(k):p[k+'_sha256']=sha(ROOT/p[k])
old=[copy.deepcopy(p)for p in S['items']if p['name']not in replaces]
for p in old:p['is_new']=False
S.update(items=parts+old,new_installed_count=len(parts),installed_count=len(parts+old),status='R25_BOTTOM_HEAD_ENTRY_ENGINEERING_CANDIDATE',replaces=replaces,physical_approved=False,manufacturing_approved=False)
S['sources']={str(p.relative_to(ROOT)):sha(p)for p in [ROOT/'work/r24-head-front/assembly_selection.json',O/'mechanics/manifest.json',O/'tails/manifest.json',fp,Path(__file__)]}
# Relocate the non-installed VMQ manufacturing reference without counting it in assembly.
import numpy as np
R=np.array(M['transform']['R']);t=np.array(M['transform']['t_mm'])
for p in S.get('service_items',[]):
 if p['name'].startswith('R23_neck_upper_'):
  p['name']=p['name'].replace('R23_','R25_',1);p['t_mm']=(R@np.array(p['t_mm'])+t).tolist();p['R']=(R@np.array(p['R'])).tolist()
# Current counters and aliases must describe R25, not inherited R23/R24 history.
S['retained_count']=len(old)
S['new_service_count']=sum(p['name'].startswith('R25_') for p in S['service_items'])
S['service_only_items']=copy.deepcopy(S['service_items'])
S['historical_manifest_inputs']=S.pop('manifest_inputs',[])
S['manifest_inputs']=[dict(path=str(p.relative_to(ROOT)),sha256=sha(p))for p in [O/'mechanics/manifest.json',O/'tails/manifest.json',fp]]
S['historical_removed_baseline']=S.pop('removed_baseline',[])
base_rows={p['name']:p for p in load(ROOT/'work/r24-head-front/assembly_selection.json')['items']}
S['removed_baseline']=[dict(name=n,source_mesh_sha256=base_rows[n]['mesh_sha256'],reason='Explicit R25 replacement or retired side wire guard')for n in replaces]
S['historical_removed_service_references']=S.pop('removed_service_references',[])
S['removed_service_references']=[dict(name='R23_neck_upper_VMQ_finished_free_insert',replacement='R25_neck_upper_VMQ_finished_free_insert',reason='Same free-state manufacturing reference relocated to bottom guide')]
(O/'assembly_selection.json').write_text(json.dumps(S,ensure_ascii=False,indent=2)+'\n')
Q=copy.deepcopy(S);Q['items']=[p for p in S['items']if p['link_frame']!='MULTI_LINK_FLEX_HARNESS'];Q['new_installed_count']=sum(bool(p['is_new'])for p in Q['items']);previous=load(O/'rigid_inputs.json');assert previous['items']==Q['items'],'Rigid geometry changed: recheck required'
# Existing rigid certificate remains source-bound to its frozen unchanged inputs.
(O/'rigid_geometry_identity.json').write_text(json.dumps(dict(previous_rigid_sha256=sha(O/'rigid_inputs.json'),new_selection_sha256=sha(O/'assembly_selection.json'),items_identical=True,interval_bounds_identical=previous['interval_bounds_sha256']==Q['interval_bounds_sha256']),indent=2)+'\n')
print('SELECTED',len(S['items']),len(parts))
