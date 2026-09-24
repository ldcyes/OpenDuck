"""Bind R26 gait replay to measured source traces and prior rigid interval proof."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(rel):return json.loads((ROOT/rel).read_text())
paths={
'r26_selection':'work/r26-cover-first/assembly_selection.json',
'r26_geometry':'work/r26-cover-first/mechanics/geometry_checks.json',
'r26_integration':'work/r26-cover-first/verification.json',
'r26_mass':'work/r26-cover-first/mass_delta.json',
'r21_trace':'work/r21-reduced-sway/dynamics/full_v3/nominal/dynamic_trace_for_CAD.json',
'r21_interval':'work/r21-reduced-sway/dynamics/full_v3/nominal/interval_joint_bounds.json',
'r21_report':'work/r21-reduced-sway/dynamics/full_v3/nominal/report.json',
'r21_acceptance':'work/r21-reduced-sway/dynamics/full_v3/nominal/acceptance.json',
'r25_rigid_selection':'work/r25-bottom-head-entry/rigid_inputs.json',
'r25_pairs':'work/r25-bottom-head-entry/motion/rigid_final/pair_index.json',
'r25_result':'work/r25-bottom-head-entry/motion/rigid_final/result.json',
'r25_named_contacts':'work/r25-bottom-head-entry/motion_contact_review.json',
'r25_flex':'work/r25-bottom-head-entry/flex/motion9_y68/report.json',
}
d={k:load(v)for k,v in paths.items()};s=d['r26_selection'];old=d['r25_rigid_selection'];geom=d['r26_geometry'];vi=d['r26_integration'];trace=d['r21_trace'];interval=d['r21_interval'];prior=d['r25_result'];pairs=d['r25_pairs'];review=d['r25_named_contacts'];mass=d['r26_mass'];dynamic=d['r21_report']
assert geom['status']=='PASS_NATIVE_COVER_AND_EXPORT_CHECKS' and vi['status']=='PASS_TWO_COVER_GEOMETRY_DELTA' and not vi['errors']
assert all(row['native_new_minus_old_mm3']==0 for row in vi['independent_subset_checks'])
assert s['joints']==old['joints'] and len(s['joints'])==15
rigid={x['name']:x for x in old['items']};current={x['name']:x for x in s['items']}
old_covers=set(s['replaces']);new_covers=set(s['new_part_names']);assert len(old_covers)==len(new_covers)==2
assert set(rigid)-old_covers==set(current)-new_covers-set(n for n in current if n.startswith('R25_NECK_FREE_'))
for name,row in rigid.items():
 if name in old_covers:continue
 now=current[name]
 for key in ['link_frame','R','t_mm','mesh','mesh_sha256','step','step_sha256']:
  assert row.get(key)==now.get(key),(name,key)
assert len(trace['samples'])==9774 and abs(trace['time_s']-195.44175)<1e-4
assert interval['interval_count']==len(trace['samples'])-1==prior['interval_count']
assert interval['sources'][paths['r21_trace'].replace('dynamic_trace_for_CAD.json','trajectory.json')]==sha(ROOT/'work/r21-reduced-sway/dynamics/full_v3/nominal/trajectory.json') if paths['r21_trace'].replace('dynamic_trace_for_CAD.json','trajectory.json') in interval['sources'] else True
assert old['interval_bounds_path']==paths['r21_interval'] and old['interval_bounds_sha256']==sha(ROOT/paths['r21_interval'])
assert prior['full_partition_verified'] and prior['dynamic_pair_count']==len(prior['dynamic_pair_ids'])
assert review['dynamic_unresolved_count']==0 and not review['unresolved']
ids={x['name']:x['id']for x in pairs['items']};dynamic_ids=set(prior['dynamic_pair_ids']);cover_pairs={}
for name in sorted(old_covers):
 i=ids[name];matched={j for j,pair in enumerate(pairs['pairs'])if i in pair};assert len(matched)==57 and matched<=dynamic_ids
 assert not any(x['pair_id'] in matched for x in prior['unresolved_spans'])
 cover_pairs[name]=dict(total=len(matched),dynamic_interval_pairs=len(matched),unresolved=0)
assert len(pairs['pairs'])==prior['pair_count']
# The old R21 mass model is materially different from R26; retain its results as inherited replay evidence only.
R21_mass=dynamic['mass_kg'];R26_mass=mass['mass_kg'];delta=(R26_mass-R21_mass)*1000
assert R26_mass>R21_mass and abs(delta)>100
assert dynamic['simulated_duration_s']>=trace['time_s']-1e-6
qkeys={j['joint']for j in s['joints']}
for sample in trace['samples']:
 assert set(sample['q_HOME_delta_deg'])==qkeys
 assert len(sample['base_transform_m'])==4
phases=[]
for sample in trace['samples']:
 if not phases or phases[-1]['name']!=sample['phase']:
  phases.append(dict(name=sample['phase'],start_s=sample['time_s'],end_s=sample['time_s']))
 else:phases[-1]['end_s']=sample['time_s']
report=dict(status='R26_FOUR_STEP_KINEMATIC_REPLAY_AND_INHERITED_RIGID_COLLISION_DELTA_CHECKED',
 actual_trace_samples=len(trace['samples']),actual_trace_duration_s=trace['time_s'],intervals=len(trace['samples'])-1,
 step_count=4,walk_source='R21 integrated free-base numerical trace; R26 dynamics NOT re-solved',
 R21_dynamic_model_mass_kg=R21_mass,R26_estimated_mass_kg=R26_mass,mass_gap_g=delta,
 unchanged_rigid_parts=len(rigid)-2,modified_cover_count=2,flexible_neck_items_excluded_from_rigid_check=31,
 prior_rigid_pair_count=prior['pair_count'],prior_dynamic_pair_count=prior['dynamic_pair_count'],
 prior_named_invariant_contacts=len(review['named_invariant_rows']),prior_dynamic_unresolved=review['dynamic_unresolved_count'],
 old_cover_pair_coverage=cover_pairs,new_cover_native_subset_volume_mm3=[x['native_new_minus_old_mm3']for x in vi['independent_subset_checks']],
 collision_argument='Each new cover is a native-solid subset of the old cover on the same rigid link. All other R25 rigid shapes, transforms and joints are unchanged. For the same recorded q(t), shortening cannot introduce a new rigid collision among the 1193-part rigid selection; earlier named contacts remain.',
 phases=phases,
 inherited_R21_simulation=dict(acceptance_status=d['r21_acceptance']['status'],maximum_torque_limit_excess_Nm=dynamic['maximum_torque_limit_excess_Nm'],original_mass_kg=R21_mass),
 unresolved=['R26 mass, power and low-voltage sustained torque were not re-integrated; old R21 acceptance does not transfer to R26 dynamics.',
 '31 flexible free-neck wires are absent from the rigid interval checker and remain motion/tolerance unqualified.',
 'Inherited named contacts and previously recorded mouth/lower-shell movement conflict are not resolved by thigh-cover trimming.',
 'No elastic deformation, as-printed tolerance, floor variability, or physical loaded walking acceptance.'],
 physical_approved=False,manufacturing_approved=False,
 sources={v:sha(ROOT/v)for v in paths.values()}|{str(Path(__file__).relative_to(ROOT)):sha(__file__)})
(OUT/'analysis.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:report[k]for k in ['status','actual_trace_samples','actual_trace_duration_s','prior_dynamic_pair_count','mass_gap_g','old_cover_pair_coverage']},ensure_ascii=False,indent=2))
