"""Review all R26 interval outcomes; resolve only six named cover seats by native STEP."""
from pathlib import Path
import json,hashlib,sys,collections
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent;CHECK=OUT/'mechanics/motion_delta'
sys.path[:0]=[str(ROOT/p)for p in ['work/r11-integration/mechanics','work/rk-mechanics/python-deps','work/r12-motion/python-deps']]
import numpy as np,common as c
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();read=lambda p:json.loads(Path(p).read_text())
r=read(CHECK/'result.json');idx=read(CHECK/'pair_index.json');sel=read(CHECK/'inputs.json');old=read(ROOT/'work/r25-bottom-head-entry/motion/rigid_final/result.json');oldreview=read(ROOT/'work/r25-bottom-head-entry/motion_contact_review.json');rv=read(ROOT/'work/r26-cover-first/verification.json');trace=read(ROOT/'work/r21-reduced-sway/dynamics/full_v3/nominal/dynamic_trace_for_CAD.json');mouth=read(OUT/'mouth_interference.json')
assert r['status']=='EXHAUSTIVE_DELTA_INTERVAL_LEDGER_WITH_EXPLICIT_CONTACTS_AND_UNRESOLVED_ITEMS'
assert r['full_partition_verified'] and r['input_sha256']==sha(CHECK/'inputs.json') and r['checker_sha256']==sha(CHECK/'check_delta.py')
assert len(sel['items'])==1193 and len(sel['joints'])==15
assert r['pair_count']==len(idx['pairs'])==2383 and r['dynamic_pair_count']==2345 and r['invariant_pair_count']==38 and r['interval_count']==9773
assert all(a+b==9773 for a,b in zip(r['covered_interval_counts'],r['unresolved_or_named_interval_counts']))
dyn=set(r['dynamic_pair_ids']);assert not any(span['pair_id']in dyn for span in r['unresolved_spans'])
assert all(r['covered_interval_counts'][i]==9773 for i in dyn)
for rel,h in r['sources'].items():assert sha(ROOT/rel)==h,rel
assert not oldreview['unresolved'] and oldreview['dynamic_unresolved_count']==0 and old['full_partition_verified']
by={x['name']:x for x in sel['items']};static={tuple(sorted([x['cover'],x['other']])):x for x in rv['static_results']}
resolved=[];expected=set()
for side in ['L','R']:
 cover=f'R26_{side}_thigh_short_cover'
 for n in [f'R18P_{side}_thigh_CNC_bridge_saddle',f'R18P_{side}_thigh_skin_F1_washer_OD7',f'R18P_{side}_thigh_skin_F2_washer_OD7']:
  expected.add(tuple(sorted([cover,n])))
assert len(r['unresolved_spans'])==len(expected)==6
for span in r['unresolved_spans']:
 i,j=idx['pairs'][span['pair_id']];a,b=[sel['items'][k]for k in [i,j]];key=tuple(sorted([a['name'],b['name']]))
 assert key in expected and span['reason']=='INVARIANT_CONTACT_OR_UNRESOLVED' and span['start_interval']==0 and span['end_interval_exclusive']==9773
 assert span['exact']['status']=='computed' and abs(span['exact']['intersection_mm3'])<1e-8
 assert static[key]['status']=='NAMED_UNCHANGED_SEATING_INTERFACE' and static[key]['native_common_mm3']==0
 pa=ROOT/a['step'];pb=ROOT/b['step'];assert sha(pa)==a.get('step_sha256',a.get('sha256_STEP')) and sha(pb)==b.get('step_sha256',b.get('sha256_STEP'))
 sa=c.tf(c.read(pa),a['R'],a['t_mm']);sb=c.tf(c.read(pb),b['R'],b['t_mm']);common=abs(c.volume(c.common(sa,sb)))
 assert common<=1e-6,(key,common)
 resolved.append(dict(cover=a['name'],seat=b['name'],pair_id=span['pair_id'],mesh_common_mm3=span['exact']['intersection_mm3'],native_STEP_common_mm3=common,classification='NOMINAL_SEATING_ZERO_NATIVE_VOLUME'))
assert {tuple(sorted([x['cover'],x['seat']]))for x in resolved}==expected
bounds=[cert['minimum_lower_bound_mm']for cert in r['certificates']if any(i in dyn for i in cert['pair_ids'])]
assert bounds and min(bounds)>r['positive_separation_threshold_mm']
q=[s['q_HOME_delta_deg']['mouth_candidate']for s in trace['samples']]
assert max(q)<8.75 and min(q)>-8.75 and mouth['first_sampled_intersection_deg']==8.75
report=dict(status='R26_DIRECT_RIGID_INTERVAL_CHECK_REVIEWED_WITH_EXISTING_MOUTH_INTERFERENCE',
 installed_geometry_count=1224,rigid_checked_count=1193,flexible_neck_excluded=31,
 direct_new_cover_pair_count=r['pair_count'],dynamic_pair_count=r['dynamic_pair_count'],invariant_pair_count=r['invariant_pair_count'],source_interval_count=r['interval_count'],
 dynamic_unresolved=0,smallest_certified_dynamic_separation_mm=min(bounds),separation_threshold_mm=r['positive_separation_threshold_mm'],target_clearance_mm=r['target_mm'],
 exact_six_installed_seats=resolved,other_unchanged_rigid_parts=1191,
 inherited_unchanged_pair_review=dict(prior_dynamic_pairs=old['dynamic_pair_count'],prior_named_invariant_contacts=len(oldreview['named_invariant_rows']),prior_review_unresolved=len(oldreview['unresolved'])),
 confirmed_existing_interference=dict(pair=mouth['pair'],first_sampled_angle_deg=mouth['first_sampled_intersection_deg'],volume_at_8p75_mm3=next(x['common_mm3']for x in mouth['representative_samples']if x['angle_deg']==8.75),walk_mouth_command_range_deg=[min(q),max(q)]),
 limitations=['The 0.015 mm certified minimum is nominal tessellated rigid geometry, not a manufacturing clearance allowance or deformable-wire margin.',
 'The direct R26 interval checker covers pairs touching either new cover. Unchanged-unchanged pairs inherit earlier revision checks and named contacts; it is not an all-pairs new approval.',
 '31 free-neck harness pieces were excluded from rigid interval checking. Soft deformation, print tolerances, floor contact and real walking remain unverified.',
 'The replay comes from R21 dynamics at 4.195 kg; R26 estimated 4.443 kg was not dynamically re-integrated.'],
 physical_approved=False,manufacturing_approved=False,
 sources={str(p.relative_to(ROOT)):sha(p) for p in [CHECK/'result.json',CHECK/'pair_index.json',CHECK/'inputs.json',CHECK/'check_delta.py',ROOT/'work/r25-bottom-head-entry/motion/rigid_final/result.json',ROOT/'work/r25-bottom-head-entry/motion_contact_review.json',ROOT/'work/r26-cover-first/verification.json',ROOT/'work/r21-reduced-sway/dynamics/full_v3/nominal/dynamic_trace_for_CAD.json',OUT/'mouth_interference.json',Path(__file__)]})
(OUT/'direct_review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:report[k]for k in ['status','direct_new_cover_pair_count','dynamic_pair_count','dynamic_unresolved','smallest_certified_dynamic_separation_mm','confirmed_existing_interference']},ensure_ascii=False,indent=2))
