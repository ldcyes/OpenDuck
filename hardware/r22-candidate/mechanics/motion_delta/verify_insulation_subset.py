"""Independent source-bound STEP AND STL subset extension of frozen motion evidence."""
from pathlib import Path
import sys,json,hashlib,shutil
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'work/r12-motion/python-deps'),str(ROOT/'work/rk-mechanics/python-deps'),str(ROOT/'work/r13-electronics/mechanics')]
import numpy as np,trimesh,manifold3d as md
from common import read,cut,common,volume,BRepExtrema_DistShapeShape
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
load=lambda p:json.loads(Path(p).read_text())
old=load(OUT/'snapshot/power_reference/manifest.original.json');src=OUT.parent/'power_reference/manifest.json';raw=src.read_bytes();new=json.loads(raw);target=OUT/'snapshot/insulation_v2';target.mkdir(exist_ok=True);(target/'power_manifest.original.json').write_bytes(raw)
ob={q['name']:q for q in old['parts']};nb={q['name']:q for q in new['parts']};assert ob.keys()==nb.keys()and len(ob)==126
expected={f'R22_Power_C101_{i}_INSULATION'for i in [1,2]};changed={n for n in ob if ob[n]!=nb[n]};assert changed==expected,changed
before=OUT.parent/'insulation_v2/manifest_before.json';assert sha(before)==sha(OUT/'snapshot/power_reference/manifest.original.json')
sources={str(src.relative_to(ROOT)):sha(src),str(before.relative_to(ROOT)):sha(before),str((OUT.parent/'insulation_v2/subset_proof.json').relative_to(ROOT)):sha(OUT.parent/'insulation_v2/subset_proof.json')};rows=[];updated={}
def mesh(q):
 p=ROOT/q['mesh'];assert sha(p)==q['sha256_STL'];m=trimesh.load(p,force='mesh');s=md.Manifold(md.Mesh64(np.array(m.vertices,dtype=np.float64),np.array(m.faces,dtype=np.uint64)));assert s.status()==md.Error.NoError;return s
for name in sorted(changed):
 a,b=ob[name],dict(nb[name]);assert all(a[k]==b[k]for k in ['R','t_mm','link_frame']);assert all(b[k]==nb[next(n for n in nb if n==name.replace('INSULATION','FORMED_LEAD'))][k]for k in ['R','t_mm','link_frame'])
 for key,hkey,sub in [('step','sha256_STEP','STEP'),('mesh','sha256_STL','STL')]:
  p=ROOT/b[key];assert sha(p)==b[hkey];sources[str(p.relative_to(ROOT))]=sha(p);dest=target/sub/p.name;dest.parent.mkdir(exist_ok=True);shutil.copyfile(p,dest);b['original_'+key]=b[key];b[key]=str(dest.relative_to(ROOT));assert sha(dest)==b[hkey]
 # Old paths deliberately use immutable captured files, never the live original.
 for key,sub in [('mesh','STL'),('step','STEP')]:a={**a,key:str((OUT/'snapshot/power_reference'/sub/Path(a[key]).name).relative_to(ROOT))}
 lead=ob[name.replace('INSULATION','FORMED_LEAD')];lead={**lead,'mesh':str((OUT/'snapshot/power_reference/STL'/Path(lead['mesh']).name).relative_to(ROOT)),'step':str((OUT/'snapshot/power_reference/STEP'/Path(lead['step']).name).relative_to(ROOT))}
 for q in [a,b,lead]:
  for k,h in [('mesh','sha256_STL'),('step','sha256_STEP')]:assert sha(ROOT/q[k])==q[h];sources[q[k]]=q[h]
 oldmesh,newmesh,leadmesh=map(mesh,[a,b,lead]);outside=newmesh-oldmesh;mc=newmesh^leadmesh;mg=float(newmesh.min_gap(leadmesh,1.))
 os,ns,ls=[read(ROOT/q['step'])for q in [a,b,lead]];sv=abs(volume(cut(ns,os)));lv=abs(volume(common(ns,ls)));dist=BRepExtrema_DistShapeShape(ns,ls);dist.Perform();assert dist.IsDone()
 row={'name':name,'old_bindings':{k:a[k]for k in ['mesh','sha256_STL','step','sha256_STEP','R','t_mm','link_frame']},'new_bindings':{k:b[k]for k in ['mesh','sha256_STL','step','sha256_STEP','R','t_mm','link_frame']},'old_mesh_volume_mm3':oldmesh.volume(),'new_mesh_volume_mm3':newmesh.volume(),'new_STL_outside_old_STL_is_empty':outside.is_empty(),'new_STL_outside_old_STL_volume_mm3':abs(outside.volume()),'new_STEP_outside_old_STEP_volume_mm3':sv,'new_STL_lead_common_mm3':abs(mc.volume()),'new_STL_lead_gap_mm':mg,'new_STEP_lead_common_mm3':lv,'new_STEP_lead_gap_mm':dist.Value(),'new_native_mesh_bounds_mm':list(newmesh.bounding_box())}
 assert row['new_STL_outside_old_STL_is_empty']and row['new_STL_outside_old_STL_volume_mm3']==0 and sv<1e-10,row
 assert row['new_STL_lead_common_mm3']<1e-10 and lv<1e-10 and mg>1e-4 and dist.Value()>1e-4,row
 rows.append(row);updated[name]=b;print(row,flush=True)
for p,h in sources.items():assert sha(ROOT/p)==h,p
base=load(OUT/'inputs.json');pairs=load(OUT/'pair_index.json')['pairs'];dyn=set(load(OUT/'result.json')['dynamic_pair_ids']);affected=[pid for pid,(a,b)in enumerate(pairs)if base['items'][a]['name']in changed or base['items'][b]['name']in changed]
result={'status':'NEW_SLEEVES_STRICT_SUBSETS_OF_FROZEN_STL_AND_STEP_WITH_POSITIVE_LEAD_CLEARANCE','rows':rows,'changed_part_names':sorted(changed),'unchanged_power_objects':124,'same_name_R_t_link_verified':True,'affected_delta_pair_count':len(affected),'affected_dynamic_pair_count':sum(p in dyn for p in affected),'affected_dynamic_pair_ids':[p for p in affected if p in dyn],'motion_inheritance':'For A_new subset A_old and B unchanged/subset, inf distance(A_new,B_new)>=inf distance(A_old,B_old) at every common rigid pose. Captured STL set differences are empty, and R/t/link identities match; therefore every original/refined2.2mm certificate for affected pairs remains valid with identical lower bounds. No sampled-motion substitution.','original_dynamic_minimum_lower_bound_mm':load(OUT/'summary.json')['minimum_certified_dynamic_lower_bound_mm'],'updated_parts':updated,'sources':sources,'original_evidence':{str((OUT/p).relative_to(ROOT)):sha(OUT/p)for p in ['inputs.json','result.json','target_refinement.json','contact_STEP_adjudication.json','verification.json']},'checker_sha256':sha(__file__),'limits':['Extends the frozen geometry evidence only; old raw conflicts remain honestly recorded in their original sources.','The independently verified STL containment is required because the motion distances were calculated on triangulations, not merely on nominal STEP.','Subset monotonicity does not certify lead insulation electrical/thermal performance or fabrication tolerances.']}
(OUT/'insulation_subset_extension.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
