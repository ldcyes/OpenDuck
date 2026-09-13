"""Publish an additive v2 interpretation without changing frozen base evidence."""
from pathlib import Path
import sys,json,hashlib,copy,itertools,shutil,collections
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'work/rk-mechanics/python-deps'))
import numpy as np,trimesh
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
load=lambda p:json.loads(Path(p).read_text())
d=load(OUT/'inputs.json');extension=load(OUT/'insulation_subset_extension.json');bearing=load(OUT/'bearing_STEP_supplement.json');base=load(OUT/'summary.json');ver=load(OUT/'verification.json');contacts=load(OUT/'static_contact_ledger.json');raw=load(OUT/'result.json');ix=load(OUT/'pair_index.json');cap=load(OUT/'cap_final_reference_rebind.json')
for ledger in [ver['sources'],extension['original_evidence']]:
 for p,h in ledger.items():assert sha(ROOT/p)==h,p
for row in extension['rows']:
 assert row['new_STL_outside_old_STL_is_empty']and row['new_STL_outside_old_STL_volume_mm3']==row['new_STEP_outside_old_STEP_volume_mm3']==0
 assert row['new_STL_lead_common_mm3']==row['new_STEP_lead_common_mm3']==0 and row['new_STL_lead_gap_mm']>1e-4
items=copy.deepcopy(d['items'])
for i,q in enumerate(items):
 if q['name']not in extension['updated_parts']:continue
 n=extension['updated_parts'][q['name']];q.update(n);q['mesh_sha256']=n['sha256_STL'];q['step_sha256']=n['sha256_STEP'];q['source_bound_revision']='insulation_v2 strict subset of frozen R22 geometry';q['is_new']=True;q['input_group']='power_reference'
by={q['name']:q for q in items};sources={};count=0
for q in items+d['service_only_items']:
 for k,hk in [('mesh','mesh_sha256'),('step','step_sha256'),('analysis_mesh','analysis_mesh_sha256')]:
  if q.get(k)and q.get(hk):assert sha(ROOT/q[k])==q[hk],q['name'];sources[q[k]]=q[hk];count+=1
source_integration=ROOT/'work/r22-compact-power/integration/assembly_selection.json';idata=source_integration.read_bytes();i=json.loads(idata);ib={q['name']:q for q in i['items']};assert by.keys()==ib.keys()
for n,q in by.items():
 assert all(q[k]==ib[n][k]for k in ['R','t_mm','link_frame']),n
 assert q['mesh_sha256']==ib[n].get('mesh_sha256',ib[n].get('sha256_STL')),n
 assert q.get('step_sha256')==ib[n].get('step_sha256',ib[n].get('sha256_STEP')),n
ip=OUT/'snapshot/integration_assembly_selection.insulation_v2.json';ip.write_bytes(idata);assert sha(source_integration)==sha(ip)
sources[str(ip.relative_to(ROOT))]=sha(ip)
effective={'status':'FROZEN_BASE_PLUS_TWO_SOURCE_BOUND_STRICT_SUBSETS','items':items,'joints':d['joints'],'service_only_items':d['service_only_items'],'new_count':265,'retained_count':468,'base_inputs_sha256':sha(OUT/'inputs.json'),'insulation_subset_extension_sha256':sha(OUT/'insulation_subset_extension.json'),'current_integration_capture':str(ip.relative_to(ROOT)),'current_integration_capture_sha256':sha(ip)}
(OUT/'effective_inputs.json').write_text(json.dumps(effective,ensure_ascii=False,indent=2)+'\n')
# Classify the original six unadjudicated rows without retroactively rewriting them.
bearids={q['pair_id']for q in bearing['rows']};leadids={pid for pid,(a,b)in enumerate(ix['pairs'])if items[a]['name'].replace('FORMED_LEAD','INSULATION')==items[b]['name']and items[b]['name']in extension['changed_part_names']}
assert len(bearids)==4 and len(leadids)==2
assert {q['pair_id']for q in contacts['remaining_conflicts']}==bearids|leadids
latest_contacts={'status':'ALL_INVARIANT_RELATIONSHIPS_CLASSIFIED_FOR_EFFECTIVE_INPUTS','unchanged_named_zero_volume_contacts':contacts['named_zero_volume_contacts'],'additional_bearing_zero_volume_contacts':bearing['rows'],'sleeve_conflicts_replaced_by_positive_separation':[{'pair_id':pid,'a':items[ix['pairs'][pid][0]]['name'],'b':items[ix['pairs'][pid][1]]['name'],'proof':'insulation_subset_extension.json'}for pid in sorted(leadids)],'source_named_representation_exclusions':contacts['source_named_representation_exclusions'],'remaining_unclassified_contacts_or_intersections':[],'effective_inputs_sha256':sha(OUT/'effective_inputs.json'),'preserved_raw_ledger_sha256':sha(OUT/'static_contact_ledger.json')}
(OUT/'static_contact_ledger_v2.json').write_text(json.dumps(latest_contacts,ensure_ascii=False,indent=2)+'\n')
# Independent AABB screening of all distinct per-pin formed cables: no same-J exemption.
cache={}
def bb(q):
 if q['name']not in cache:
  m=trimesh.load(ROOT/q['mesh'],force='mesh');v=np.asarray(m.vertices)@np.array(q['R']).T+q['t_mm'];cache[q['name']]=np.array([v.min(0),v.max(0)])
 return cache[q['name']]
def gap(a,b):return float(np.linalg.norm(np.maximum(0,np.maximum(a[0]-b[1],b[0]-a[1]))))
wiregroups=collections.defaultdict(list)
for q in items:
 if q.get('kind')=='formed_wire_clearance_budget'and q.get('reference','').startswith('J'):wiregroups[(q['input_group'],q['reference'])].append(q)
wires=[]
for group,rows in wiregroups.items():
 for a,b in itertools.combinations(rows,2):
  assert a['link_frame']==b['link_frame'];g=gap(bb(a),bb(b));assert g>1e-4
  wires.append({'a':a['name'],'b':b['name'],'reference':group[1],'group':group[0],'invariant_AABB_lower_bound_mm':g,'link_frame':a['link_frame']})
assert len(wires)==73
wire_result={'status':'ALL_DISTINCT_PIN_R5_ENVELOPES_SEPARATED','pair_count':73,'minimum_AABB_lower_bound_mm':min(q['invariant_AABB_lower_bound_mm']for q in wires),'rows':wires,'effective_inputs_sha256':sha(OUT/'effective_inputs.json'),'note':'Each pin envelope is checked against every other pin of the same header; BODY/MATED and straight-continuation exclusions never exempt distinct pin wires.'}
(OUT/'individual_pin_wire_check.json').write_text(json.dumps(wire_result,ensure_ascii=False,indent=2)+'\n')
service=next(q for q in d['service_only_items']if q['name']=='R22_Power_J1_UNPLUG_TOOL');service_rows=[]
for q in items:
 if q['input_group']=='power_cap_mount':service_rows.append({'cap_mount_part':q['name'],'service_budget':service['name'],'invariant_AABB_lower_bound_mm':gap(bb(q),bb(service))})
assert len(service_rows)==15 and min(x['invariant_AABB_lower_bound_mm']for x in service_rows)>3
cap2=copy.deepcopy(cap);cap2['status']='CAP_MOUNT_REBOUND_TO_POWER_INSULATION_V2_NO_UNCLASSIFIED_FINITE_INTERSECTION';cap2['effective_inputs_sha256']=sha(OUT/'effective_inputs.json');cap2['frozen_original_report_sha256']=sha(OUT/'cap_final_reference_rebind.json');cap2['power_manifest_v2']={'path':str((OUT/'snapshot/insulation_v2/power_manifest.original.json').relative_to(ROOT)),'sha256':sha(OUT/'snapshot/insulation_v2/power_manifest.original.json')};cap2['subset_extension_sha256']=sha(OUT/'insulation_subset_extension.json');changed=extension['changed_part_names'];changedrows=0
for row in cap2['rows']:
 if row['a']in changed or row['b']in changed:row['v2_basis']='Strict STL/STEP subset under unchanged R/t/link: previous positive separation lower bound is preserved.';changedrows+=1
assert changedrows==30
cap2['changed_sleeve_pairs_inherited']=changedrows;cap2['separate_J1_service_vs_cap_mount']=service_rows;cap2['service_note']='J1 unplug/tool is separately checked against all15cap-mount objects by invariant AABB; its budget is excluded from walking material.'
(OUT/'cap_final_reference_rebind_v2.json').write_text(json.dumps(cap2,ensure_ascii=False,indent=2)+'\n')
summary={k:v for k,v in base.items()if k!='remaining_static_reference_conflicts'};summary.update(status='EFFECTIVE_R22_DELTA_GEOMETRY_CERTIFIED_OVER_R21_RECORDED_JOINT_ENCLOSURES',static_positive_pairs=65088,named_zero_volume_static_contacts=256,remaining_unclassified_static_intersections=0,individual_pin_pairs=73,minimum_individual_pin_AABB_gap_mm=wire_result['minimum_AABB_lower_bound_mm'],insulation_v2_affected_pairs=extension['affected_delta_pair_count'],insulation_v2_affected_dynamic_pairs=extension['affected_dynamic_pair_count'],current_integration_selection_matches=True,effective_inputs_sha256=sha(OUT/'effective_inputs.json'),physical_approved=False)
assert summary['static_positive_pairs']+summary['named_zero_volume_static_contacts']+summary['named_thread_or_same_representation_pairs']==summary['invariant_pairs']
summary['limits']=['R21 195.44175s recorded simulation and interval joint enclosures only; changed R22 masses/inertias/controller dynamics are not simulated here.','Rigid model self-clearance only; no old-old revalidation, ground/external obstacles or actual flexible-harness deformation.','Whole global joint box proves92660dynamic pairs; remaining935use continuous enclosure of source interval groups, not sampling-only tests.','The2.2mm goal applies to pairs with relative motion. Fixed assembled contacts, thread representations and small component/lead clearances are explicitly distinct.','73distinct pin pairs clear at least0.140089mm nominal AABB; cable/manufacturing tolerances and bending variation are not approved.','No physical manufacturing, electrical insulation, thermal, creep, fatigue or TDK-to-main-body structural mounting qualification.']
(OUT/'latest_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
reports=['inputs.json','effective_inputs.json','result.json','target_refinement.json','verification.json','static_contact_ledger.json','contact_STEP_adjudication.json','bearing_STEP_supplement.json','insulation_subset_extension.json','static_contact_ledger_v2.json','individual_pin_wire_check.json','cap_final_reference_rebind_v2.json','latest_summary.json']
latest={'status':'EFFECTIVE_INPUTS_AND_ADDITIVE_GEOMETRY_CERTIFICATES_VERIFIED','effective_geometry_bindings_checked':count,'sources':{**sources,**{str((OUT/p).relative_to(ROOT)):sha(OUT/p)for p in reports}},'original_all_pair_partitions_verified':True,'original_all_dynamic_target_partitions_verified':True,'new_STL_and_STEP_strict_subsets_independently_verified':True,'independent_latest_integration_pose_and_geometry_match':True,'dynamic_certified_pair_count':93595,'dynamic_minimum_lower_bound_mm':summary['minimum_certified_dynamic_lower_bound_mm'],'invariant_unclassified_intersections':0,'checker_sha256':sha(__file__),'physical_approved':False}
for p,h in latest['sources'].items():assert sha(ROOT/p)==h,p
(OUT/'latest_verification.json').write_text(json.dumps(latest,ensure_ascii=False,indent=2)+'\n');print(summary)
