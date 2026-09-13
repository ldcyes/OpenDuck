"""Immutable R22 delta inputs; never change original native or mechanics files."""
from pathlib import Path
import json,hashlib,shutil,datetime
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
sources={};new=[];manifests={}
for group in ['entry_reference','entry_mount','power_reference','power_cap_mount']:
 p=OUT.parent/group/'manifest.json';raw=p.read_bytes();d=json.loads(raw);target=OUT/'snapshot'/group;target.mkdir(parents=True,exist_ok=True)
 (target/'manifest.original.json').write_bytes(raw);sources[str(p.relative_to(ROOT))]=sha(p)
 for q0 in d['parts']:
  q=dict(q0);q['input_group']=group;q['is_new']=True;q['original_mesh']=q['mesh'];q['original_step']=q.get('step');q['mesh_sha256']=q.get('mesh_sha256',q.get('sha256_STL'));q['step_sha256']=q.get('step_sha256',q.get('sha256_STEP'))
  for k,hkey in [('mesh','mesh_sha256'),('step','step_sha256')]:
   if not q.get(k):continue
   src=ROOT/q[k];assert sha(src)==q[hkey],src;dst=target/('STL'if k=='mesh'else'STEP')/src.name;dst.parent.mkdir(exist_ok=True);shutil.copyfile(src,dst);assert sha(dst)==q[hkey];q[k]=str(dst.relative_to(ROOT))
  new.append(q)
 manifests[group]=dict(path=str((target/'manifest.original.json').relative_to(ROOT)),sha256=sha(target/'manifest.original.json'),parts=len(d['parts']))
selection_path=ROOT/'work/r20-walking-fix/assembly_final/assembly_selection.json';sel=json.loads(selection_path.read_text());sources[str(selection_path.relative_to(ROOT))]=sha(selection_path)
entry_mount=json.loads((OUT/'snapshot/entry_mount/manifest.original.json').read_text());replaced=set(entry_mount['replaces']);removed=[];old=[]
for q0 in sel['items']:
 q=dict(q0)
 if q['name'].startswith('Entry_5V_R8_')or q['name']in replaced or q['name']=='REFERENCE_R11_TDK_assembled_envelopes':removed.append({'name':q['name'],'mesh_sha256':q['mesh_sha256'],'reason':'old Entry native/mount replacement'if q['name']!='REFERENCE_R11_TDK_assembled_envelopes'else'old TDK compound replaced by individual new merged-board references'});continue
 q['is_new']=False;q['input_group']='retained_R20';old.append(q)
service=[q for q in new if q.get('kind')=='service_clearance_budget'];installed=[q for q in new if q not in service]
assert len({q['name']for q in installed+old})==len(installed+old)
override_path=ROOT/'work/r19-walking-simulation/review/xc330_analysis/override_manifest.json';od=json.loads(override_path.read_text());sources[str(override_path.relative_to(ROOT))]=sha(override_path)
for p,h in od['sources'].items():assert sha(ROOT/p)==h;sources[p]=h
for ov in od['overrides']:
 q=next(q for q in old if q['name']==ov['name'])
 assert q['mesh_sha256']==ov['original_mesh_sha256']and q['R']==ov['original_R']and q['t_mm']==ov['original_t_mm']and q['link_frame']==ov['original_link_frame']
 q['analysis_mesh']=ov['analysis_mesh'];q['analysis_mesh_sha256']=ov['analysis_mesh_sha256'];assert sha(ROOT/q['analysis_mesh'])==q['analysis_mesh_sha256'];sources[q['analysis_mesh']]=q['analysis_mesh_sha256']
bp=ROOT/'work/r21-reduced-sway/dynamics/full_v3/nominal/interval_joint_bounds.json';sources[str(bp.relative_to(ROOT))]=sha(bp)
copy=OUT/'snapshot/interval_joint_bounds.json';shutil.copyfile(bp,copy)
for p,h in sources.items():assert sha(ROOT/p)==h,p
result={'status':'IMMUTABLE_NEW_GEOMETRY_AND_EXACT_RETAINED_BASELINE_BINDINGS','captured_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'items':installed+old,'new_names':[q['name']for q in installed],'service_only_items':service,'removed_original_items':removed,'joints':sel['joints'],'original_baseline_count':len(sel['items']),'new_installed_count':len(installed),'retained_count':len(old),'manifest_inputs':manifests,'interval_bounds_path':str(copy.relative_to(ROOT)),'interval_bounds_sha256':sha(copy),'upstream_source_captures':sources,'limits':['No old-old pairs are requested.','Service/unplug volumes excluded from walking material and retained in a separate ledger.','Other reference/installed wire volumes remain included; no blanket reference exemption.','Power capacitor mount retains its own earlier reference record, but is now checked against the captured final126part Power reference.']}
(OUT/'inputs.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print({k:result[k]for k in ['new_installed_count','retained_count','captured_at_utc']},'services',len(service),'removed',len(removed),flush=True)
