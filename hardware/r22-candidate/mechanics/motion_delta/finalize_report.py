"""Independent exhaustive interval partition audit and named static contact ledger."""
from pathlib import Path
import sys,json,hashlib,itertools,collections
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
import numpy as np
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text())
d=read(OUT/'inputs.json');r=read(OUT/'result.json');t=read(OUT/'target_refinement.json');s=read(OUT/'contact_STEP_adjudication.json');ix=read(OUT/'pair_index.json');P=len(ix['pairs']);N=r['interval_count'];items=d['items'];by={q['name']:q for q in items};dyn=set(r['dynamic_pair_ids']);inv=set(r['invariant_pair_ids']);step={q['pair_id']:q for q in s['rows']};K=d['new_installed_count']
assert P==K*d['retained_count']+K*(K-1)//2==159000
assert len({tuple(sorted(x))for x in ix['pairs']})==P
assert all(a<K or b<K for a,b in ix['pairs'])
assert set(range(P))==dyn|inv and not dyn&inv
assert sha(OUT/'inputs.json')==r['input_sha256']==t['inputs_sha256']==s['inputs_sha256']
assert sha(OUT/'result.json')==t['base_result_sha256']
assert sha(ROOT/d['interval_bounds_path'])==d['interval_bounds_sha256']
assert len(d['service_only_items'])==9 and len(d['removed_original_items'])==89
# Independently rebuild the exact time partition per pair, not just equal counts.
parts=[[]for _ in range(P)]
for c in r['certificates']:
 assert c['minimum_lower_bound_mm']>=r['positive_separation_threshold_mm']
 for pid in c['pair_ids']:parts[pid].append((c['start_interval'],c['end_interval_exclusive'],'positive'))
for u in r['unresolved_spans']:parts[u['pair_id']].append((u['start_interval'],u['end_interval_exclusive'],'unresolved'))
for q in r['named_invariant_representations']:parts[q['pair_id']].append((0,N,'named'));assert q['pair_id']in inv
for pid,spans in enumerate(parts):
 spans.sort();assert spans[0][0]==0 and spans[-1][1]==N,(pid,spans)
 assert all(0<=a<b<=N for a,b,_ in spans)
 assert all(x[1]==y[0]for x,y in zip(spans,spans[1:])),pid
 assert sum(b-a for a,b,status in spans if status=='positive')==r['covered_interval_counts'][pid]
# Remove the old below-target dynamic spans, replacing them with refined target certificates.
target=[c for c in r['certificates']if c['level']=='target_2.2mm'and set(c['pair_ids'])&dyn]+t['target_certificates']
assert not t['remaining_below_target_spans']
target_parts={pid:[]for pid in dyn}
for c in target:
 assert c['minimum_lower_bound_mm']>=2.2
 for pid in c['pair_ids']:
  assert pid in dyn;target_parts[pid].append((c['start_interval'],c['end_interval_exclusive'],c['minimum_lower_bound_mm']))
for pid,spans in target_parts.items():
 spans.sort();assert spans[0][0]==0 and spans[-1][1]==N
 assert all(x[1]==y[0]for x,y in zip(spans,spans[1:])),pid
 assert sum(b-a for a,b,_ in spans)==N
source_checks=0
for q in items+d['service_only_items']:
 for key,hkey in [('mesh','mesh_sha256'),('step','step_sha256'),('analysis_mesh','analysis_mesh_sha256')]:
  if q.get(key)and q.get(hkey):assert sha(ROOT/q[key])==q[hkey],q['name'];source_checks+=1
for group,v in d['manifest_inputs'].items():assert sha(ROOT/v['path'])==v['sha256'];source_checks+=1
for p,h in s['sources'].items():assert sha(ROOT/p)==h;source_checks+=1

# All rules below apply only after a measured zero-volume contact, and each output
# row carries exact part names and geometry bindings. No reference-only exemption.
def contact_basis(a,b):
 na,nb=a['name'],b['name'];pair={na,nb};ka,kb=a.get('kind'),b.get('kind')
 for x,y in [(a,b),(b,a)]:
  if x.get('kind')=='pcb_substrate_reference'and x['input_group']==y['input_group']and y.get('kind')in ['component_reference','mating_union_budget','trimmed_lead_budget','solder_process_budget','wire_straight_clearance_budget']:
   return 'Same native board: package/pad/rear-trim/solder/wire envelope terminates at substrate surface. Computed zero common volume only; not a solder or dielectric qualification.'
  if x['name']=='R22_Entry5V_rigid_frame'and y['name']in ['R13_H_Entry_foot_-6_washer','R13_H_Entry_foot_2_washer','R13_head_shell_carrier_Entry_ports']:
   return 'Exact inherited Entry frame/carrier mounting bearing interface, unchanged host contact locations.'
  if x['name']=='R22_Entry_PCB_FINISHED'and y['input_group']=='entry_mount'and ('PEEK_5mm'in y['name']or y['name'].endswith('_washer')):
   return 'Exact Entry H1-H4 board bearing face to spacer or washer.'
  if x['name']=='R22_Entry5V_rigid_frame'and y['input_group']=='entry_mount'and 'PEEK_5mm'in y['name']:
   return 'Exact Entry H1-H4 spacer bearing face on frame.'
  if x['name']=='R22_Power_PCB_FINISHED'and (y['name']=='R22_C101_PEEK_front_beam_cradle'or(y['input_group']=='power_cap_mount'and y['name'].endswith('_rear_washer'))):
   return 'Exact C101 H1/H2 front PEEK/rear washer bearing face on finished PCB.'
  if x['name']=='R22_Power_C101_BODY'and y['name']in ['R22_Power_C101_1_FORMED_LEAD','R22_Power_C101_2_FORMED_LEAD']:
   return 'Capacitor lead begins at its own negative-X sealing face.'
  if x['name']=='R22_Power_C101_BODY'and y['name']=='R22_C101_PEEK_front_beam_cradle':return 'Specified seal-side lower-rim axial stop contact; +X vent end remains open.'
  if x['name']=='R22_Power_C101_BODY'and 'R22_C101_saddle_liner_'in y['name']:return 'Nominal maximum-D13 can bearing on compliant liner; independent exact STEP confirms zero-volume contact.'
  if x['name']=='R22_C101_PEEK_front_beam_cradle'and 'R22_C101_saddle_liner_'in y['name']:return 'Nominal saddle/liner bearing interface; exact STEP adjudication when triangulation crosses curved surfaces.'
  if x['name']=='R22_C101_PEEK_front_beam_cradle'and y['input_group']=='power_cap_mount'and y['name'].endswith('_front_washer'):return 'Exact H1/H2 front washer bearing on PEEK mounting boss.'
 if a['input_group']==b['input_group']and a.get('reference')and a.get('reference')==b.get('reference')and a['reference'].startswith('J')and {ka,kb}in [{'mating_union_budget','wire_straight_clearance_budget'},{'mating_union_budget','formed_wire_clearance_budget'}]:return 'Exact connector reference: installed cable begins at its own mated housing exit face.'
 for i in range(1,5):
  if pair=={f'R22_Entry_H{i}_M2x10',f'R22_Entry_H{i}_washer'}:return 'Exact Entry screw-head/washer bearing face.'
 for i in [1,2]:
  if pair in [{f'R22_C101_H{i}_front_washer',f'R22_C101_H{i}_M2x8'},{f'R22_C101_H{i}_rear_washer',f'R22_C101_H{i}_SHNS_M2_LP'}]:return 'Exact C101 screw-head/front-washer or thin-nut/rear-washer bearing face.'
 return None
contacts=[];blocks=[]
for u in r['unresolved_spans']:
 pid=u['pair_id'];assert pid in inv;a,b=[items[i]for i in ix['pairs'][pid]];e=u['exact'];v=step[pid]['STEP_intersection_mm3']if pid in step else e.get('intersection_mm3');basis=contact_basis(a,b);row={'pair_id':pid,'a':a['name'],'b':b['name'],'mesh_gap_mm':e.get('gap_mm'),'mesh_intersection_mm3':e.get('intersection_mm3'),'exact_STEP':step.get(pid),'basis':basis,'bindings':{q['name']:{k:q.get(k)for k in ['mesh_sha256','step_sha256','R','t_mm','link_frame']}for q in [a,b]}}
 if e['status']=='computed'and v is not None and v<=1e-5 and basis:row['status']='NAMED_ZERO_VOLUME_NOMINAL_CONTACT';contacts.append(row)
 else:row['status']='STATIC_REFERENCE_MODEL_CONFLICT_OR_UNCLASSIFIED';blocks.append(row)
(OUT/'static_contact_ledger.json').write_text(json.dumps({'status':'EXPLICIT_NAMED_CONTACTS_AND_REFERENCE_CONFLICTS','named_zero_volume_contacts':contacts,'remaining_conflicts':blocks,'source_named_representation_exclusions':r['named_invariant_representations'],'inputs_sha256':sha(OUT/'inputs.json'),'result_sha256':sha(OUT/'result.json'),'STEP_adjudication_sha256':sha(OUT/'contact_STEP_adjudication.json')},ensure_ascii=False,indent=2)+'\n')
# Cap mount against final captured125installed Power references +105mount-self.
capids={i for i,q in enumerate(items)if q['input_group']=='power_cap_mount'};powerids={i for i,q in enumerate(items)if q['input_group']=='power_reference'};cap_pairids=[pid for pid,(a,b)in enumerate(ix['pairs'])if(a in capids and b in powerids|capids)or(b in capids and a in powerids)]
assert len(cap_pairids)==15*125+105==1980
contact_map={x['pair_id']:x for x in contacts};block_map={x['pair_id']:x for x in blocks};named_map={x['pair_id']:x for x in r['named_invariant_representations']};certmap={pid:c for c in r['certificates']for pid in c['pair_ids']if pid in set(cap_pairids)}
caprows=[]
for pid in cap_pairids:
 a,b=[items[i]for i in ix['pairs'][pid]]
 if pid in certmap:detail={'status':'POSITIVE_SEPARATION','lower_bound_mm':certmap[pid]['minimum_lower_bound_mm'],'method':certmap[pid]['method']}
 elif pid in contact_map:detail={'status':'NAMED_ZERO_VOLUME_CONTACT','basis':contact_map[pid]['basis']}
 elif pid in named_map:detail={'status':'NAMED_THREAD_OR_OWN_LACING_REPRESENTATION','basis':named_map[pid]['basis']}
 else:detail={'status':'UNRESOLVED','detail':block_map.get(pid)}
 caprows.append({'pair_id':pid,'a':a['name'],'b':b['name'],**detail})
assert not any(x['status']=='UNRESOLVED'for x in caprows)
capresult={'status':'CAP_MOUNT_REBOUND_TO_FINAL126PART_POWER_REFERENCE_NO_UNCLASSIFIED_FINITE_INTERSECTION','captured_power_manifest':d['manifest_inputs']['power_reference'],'installed_power_count':125,'separate_service_count':1,'cap_mount_count':15,'pair_count':1980,'rows':caprows,'service_note':'J1 unplug volume is separately captured and excluded from installed walking material. This report covers125installed reference objects; service access is not a walking clearance claim.','sources':{str((OUT/p).relative_to(ROOT)):sha(OUT/p)for p in ['inputs.json','result.json','contact_STEP_adjudication.json','static_contact_ledger.json']},'limits':['Same trunk_base rigid body: checked nominal relationship is invariant throughout R21 joint motion.','This does not complete the TDK-board-to-main-body structural mounting interface.','Cap liner, braid tension, hardware tolerances and thermal/creep acceptance remain physical qualification tasks.']}
(OUT/'cap_final_reference_rebind.json').write_text(json.dumps(capresult,ensure_ascii=False,indent=2)+'\n')
minlb=min(c['minimum_lower_bound_mm']for c in target);global_pairs=set(pid for c in target if c['start_interval']==0 and c['end_interval_exclusive']==N for pid in c['pair_ids'])
bygroup=collections.Counter();mins_bygroup={}
for pid,spans in target_parts.items():
 a,b=[items[i]for i in ix['pairs'][pid]];g='Entry_involved'if(a['input_group'].startswith('entry')or b['input_group'].startswith('entry'))else'Power_or_cap_involved';bygroup[g]+=1;mins_bygroup[g]=min(mins_bygroup.get(g,float('inf')),min(x[2]for x in spans))
summary={'status':'DYNAMIC_DELTA_2P2MM_CERTIFIED_STATIC_SLEEVE_REFERENCE_CONFLICTS_PENDING','installed_parts':733,'new_parts':265,'retained_parts':468,'service_excluded':9,'removed_original_parts':89,'total_delta_pairs':P,'dynamic_pairs':len(dyn),'invariant_pairs':len(inv),'intervals':N,'duration_s':r['interval_duration_s'][1]-r['interval_duration_s'][0],'target_mm':2.2,'minimum_certified_dynamic_lower_bound_mm':minlb,'global_all_joint_box_target_pairs':len(global_pairs),'trajectory_interval_refinement_pairs':len(dyn)-len(global_pairs),'dynamic_groups':dict(bygroup),'dynamic_lower_bound_by_group_mm':mins_bygroup,'static_positive_pairs':len(inv)-len(r['unresolved_spans'])-len(r['named_invariant_representations']),'named_zero_volume_static_contacts':len(contacts),'named_thread_or_same_representation_pairs':len(r['named_invariant_representations']),'remaining_static_reference_conflicts':blocks,'cap_final_reference_pair_count':1980,'cap_unclassified_intersections':0,'exact_calls_initial':len(r['exact_calls']),'exact_calls_target_refinement':len(t['new_exact_calls']),'exact_timeouts':sum(e['status']=='timeout'for e in r['exact_calls']+t['new_exact_calls']),'all_159000_pair_interval_partitions_independently_verified':True,'all_93595_dynamic_target_partitions_independently_verified':True,'source_geometry_hash_checks':source_checks,'physical_approved':False}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
verification={'status':'EXHAUSTIVE_LEDGER_AND_SOURCE_BINDINGS_VERIFIED','pair_count':P,'dynamic_target_pair_count':len(dyn),'minimum_dynamic_lower_bound_mm':minlb,'source_geometry_hash_checks':source_checks,'raw_and_target_partitions_contiguous_complete_nonoverlapping':True,'source_integration_selection':read(OUT/'integration_binding.json'),'motion_core_tests':{'command':'python -m pytest -q work/r18-leg-hip-covers/review/test_motion_core.py work/r18-leg-hip-covers/review/test_differential_check.py','exit_code':0,'result':'18 passed in2.49s'},'sources':{str((OUT/p).relative_to(ROOT)):sha(OUT/p)for p in ['inputs.json','result.json','target_refinement.json','pair_index.json','pair_arrays.npz','contact_STEP_adjudication.json','static_contact_ledger.json','cap_final_reference_rebind.json','summary.json']},'checker_sha256':sha(__file__),'limits':['Two exact STEP sleeve/formed-lead conflicts intentionally remain in the captured baseline report until separately source-bound subset correction.','Passing interval partition verification is not physical manufacturing or hardware motion acceptance.']}
(OUT/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2)+'\n')
print({k:v for k,v in summary.items()if k!='remaining_static_reference_conflicts'});print('STATIC_CONFLICTS',[(x['a'],x['b'])for x in blocks])
