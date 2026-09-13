"""Independent ledger, source and compiled-model checks of final actual CAD review.

This does not rerun every geometric boolean and does not exempt unresolved fits.
It deliberately stays outside final_delivery_index to avoid circular bindings.
"""
from pathlib import Path
import sys,argparse,re
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'work/python-deps'),str(ROOT/'work/r12-motion/python-deps'),str(ROOT/'work/rk-mechanics/python-deps'),str(ROOT/'work/r20-walking-fix/dynamics')]
from quasistatic import *
ap=argparse.ArgumentParser()
for arg in ['boxes','anchors','run','floor','label']:ap.add_argument('--'+arg,required=True)
args=ap.parse_args();assert re.fullmatch('[a-z0-9_]+',args.label)
HERE=Path(__file__).resolve().parent;NEWOUT=HERE/args.label;NEWOUT.mkdir(exist_ok=False)
MODEL_DIR=ROOT/'work/r20-walking-fix/dynamics/release_v4/verified_models'
import importlib.util
from collections import Counter

sources={'work/r20-walking-fix/dynamics/review_actual_geometry.py':'2ba1f440ff66a649026dac1ae3e68511fe10f67056cd8a39741eae7e7aed15f8'}
def bind(p):
 p=Path(p);p=p if p.is_absolute() else ROOT/p
 h=hashlib.sha256(p.read_bytes()).hexdigest();sources[str(p.relative_to(ROOT))]=h;return p
def read(p):return json.loads(bind(p).read_text())
def module(p,name):
 p=bind(p);sp=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m

G=ROOT/'work/r20-walking-fix/geometry'
sel=read('work/r20-walking-fix/assembly_final/assembly_selection.json');by={r['name']:r for r in sel['items']}
box=read(args.boxes)
adj=read(args.anchors)
trace=read(ROOT/args.run/'dynamic_trace_for_CAD.json')['samples']
bounds=read(ROOT/args.run/'interval_joint_bounds.json')
report=read(ROOT/args.run/'report.json')
old=read('work/r19-walking-simulation/path_support/gait_collision_evidence/manifest.json')
hip=read('work/r20-walking-fix/hip_relief/candidate_v4/host_and_tool_self_access.json')
assert all(r['new_original_STEP_common_mm3']==0 for r in hip['hosts'])
hipfinite=read(G/'final_hip_reference_v4/final_hip_reference_v4_finite.json')
floor=read(args.floor)
anchor_module=module(HERE/'adjudicate_actual_anchors.py','actual_anchor_independent_module')
bind(G/'check_interval_bounds.py');bind(G/'check_candidate_v2.py')
bind('work/r19-walking-simulation/geometry/check_walking.py')
bind('work/r18-leg-hip-covers/review/motion_core.py')
bind('work/r18-leg-hip-covers/review/differential_check.py')

N=bounds['interval_count'];names=[j['joint']for j in sel['joints']]
assert N==box['interval_count']==len(bounds['intervals'])==len(trace)-1
assert box['total_integration_steps']==bounds['total_integration_steps']
assert len(sel['items'])==box['assembly_parts']==557
assert abs(trace[0]['time_s'])<1e-12 and abs(bounds['intervals'][0]['start_s'])<1e-12
steps=0
for k,row in enumerate(bounds['intervals']):
 a,b=trace[k],trace[k+1];count=row['integration_steps'];steps+=count
 assert count>=1 and isinstance(count,int)
 assert abs(row['start_s']-a['time_s'])<1e-10 and abs(row['end_s']-b['time_s'])<1e-10
 assert abs(row['end_s']-row['start_s']-count*bounds['dt_s'])<1e-7
 for n in names:
  lo,hi=row['q_min_HOME_deg'][n],row['q_max_HOME_deg'][n]
  assert np.isfinite([lo,hi]).all() and lo<=hi
  assert row['q_start_HOME_deg'][n]==a['q_HOME_delta_deg'][n]
  assert row['q_end_HOME_deg'][n]==b['q_HOME_delta_deg'][n]
  assert lo<=min(a['q_HOME_delta_deg'][n],b['q_HOME_delta_deg'][n])+1e-10
  assert hi>=max(a['q_HOME_delta_deg'][n],b['q_HOME_delta_deg'][n])-1e-10
assert steps==bounds['total_integration_steps'] and abs(trace[-1]['time_s']-report['simulated_duration_s'])<1e-10

# Reconstruct per-pair interval partitions from certificates, not summary counts.
pairs=box['pair_index'];pair_ids={frozenset(p):i for i,p in enumerate(pairs)}
assert len(pair_ids)==len(pairs)==557*556//2
cross=[by[a]['link_frame']!=by[b]['link_frame'] for a,b in pairs]
spans=[[]for _ in pairs];material_count=margin_count=0
minimum_lb=np.full(len(pairs),np.inf)
for cert in box['certificates']:
 a,b=cert['first_interval'],cert['end_interval_exclusive'];ids=cert['pair_ids']
 assert 0<=a<b<=N and len(set(ids))==len(ids)
 assert cert['level']in ['2.2mm','positive_material']
 assert cert['minimum_lower_bound_mm'] >= (2.2 if cert['level']=='2.2mm' else 1e-4)
 material_count+=(b-a)*len(ids)
 if cert['level']=='2.2mm':margin_count+=(b-a)*len(ids)
 for i in ids:
  assert cross[i]
  spans[i].append((a,b,cert['level']))
  minimum_lb[i]=min(minimum_lb[i],cert['minimum_lower_bound_mm'])
unresolved={pair_ids[frozenset(r['pair'])]:r for r in box['unresolved_pairs']}
for i,is_cross in enumerate(cross):
 if not is_cross:assert not spans[i];continue
 ss=sorted(spans[i]);end=0;uncovered=0
 for a,b,_ in ss:
  assert a>=end,('OVERLAPPING_CERTIFICATES',pairs[i]);uncovered+=a-end;end=b
 uncovered+=N-end
 if i in unresolved:assert uncovered==unresolved[i]['unresolved_intervals']
 else:assert uncovered==0,('GAP_WITHOUT_EXPLICIT_UNRESOLVED',pairs[i])
assert material_count==box['certified_material_pair_intervals']
assert margin_count==box['certified_2p2mm_pair_intervals']
assert material_count+sum(r['unresolved_intervals']for r in unresolved.values())==N*sum(cross)==box['pair_interval_requests']
assert len(unresolved)==34 and all(r['unresolved_intervals']==N for r in unresolved.values())
baseline_box=read(G/'final_actual_boxes/numerical_state_box_check.json')
assert {frozenset(r['pair'])for r in box['unresolved_pairs']}=={frozenset(r['pair'])for r in baseline_box['unresolved_pairs']}
assert box['all_material_separation_certified'] is False

targets=[]
for hit in old['pairs']:
 i=pair_ids[frozenset([hit['a'],hit['b']])];assert i not in unresolved
 targets.append(dict(pair=pairs[i],old_reference_common_mm3=hit['common_mm3'],actual_material_intervals=N,actual_2p2mm_intervals=sum(b-a for a,b,l in spans[i]if l=='2.2mm'),conservative_certificate_group_lower_bound_mm=float(minimum_lb[i])))
rail_targets=[]
for host in ['left_hip_roll_motor','left_hip_roll_fixed','left_hip_pitch_motor','left_hip_pitch_fixed']:
 if host not in by:continue
 i=pair_ids[frozenset(['R20_left_hip_rail_offset',host])]
 if not cross[i]:continue
 assert i not in unresolved
 rail_targets.append(dict(pair=pairs[i],actual_material_intervals=N,actual_2p2mm_intervals=sum(b-a for a,b,l in spans[i]if l=='2.2mm'),conservative_certificate_group_lower_bound_mm=float(minimum_lb[i])))

# Independent Rodrigues/SciPy tree product is checked against the compiled
# MuJoCo body frames, with every actual free root transform retained.
ev=StaticEvaluator(MODEL_DIR/'current_robot_contact4.xml',MODEL_DIR/'model_contract_contact4.json')
bind(ev.model_path);bind(ev.contract_path)
indices=sorted(set(np.linspace(0,N,18,dtype=int).tolist()+[r['interval_anchor']for r in box['raw_positive_actual_anchors']]))
max_rot=0.;max_pos=0.
for k in indices:
 s=trace[k];B=np.asarray(s['base_transform_m']);q=s['q_HOME_delta_deg'];T=anchor_module.independent_FK(sel['joints'],q);ev.set_state(q,B)
 assert np.array_equal(T['MULTI_LINK_FLEX_HARNESS'],np.eye(4))
 for link,Hmm in T.items():
  if link=='MULTI_LINK_FLEX_HARNESS':continue
  H=Hmm.copy();H[:3,3]/=1000;W=B@H;bid=ev.m.body(link).id
  pos=W[:3,:3]@ev.pivots.get(link,np.zeros(3))+W[:3,3]
  max_rot=max(max_rot,float(abs(W[:3,:3]-ev.d.xmat[bid].reshape(3,3)).max()))
  max_pos=max(max_pos,float(abs(pos-ev.d.xpos[bid]).max()))
assert max_pos<1e-12 and max_rot<1e-12

raw={frozenset([r['a'],r['b']]):r for r in box['raw_positive_actual_anchors']}
adjudicated={frozenset(r['pair']):r for r in adj['rows']}
assert raw.keys()==adjudicated.keys() and len(raw)==4
for p,r in raw.items():
 k=r['interval_anchor'];assert r['q_HOME_delta_deg']==trace[k]['q_HOME_delta_deg'];assert abs(r['time_s']-trace[k]['time_s'])<1e-10
 ar=adjudicated[p];assert ar['q_HOME_delta_deg']==r['q_HOME_delta_deg']
 if ar['classification']=='SOURCE_MESH_MICRO_RESIDUE_ORIGINAL_STEP_ZERO_AT_THIS_ACTUAL_ANCHOR':assert ar['independent_original_STEP_common_mm3']==0
 else:assert ar['classification']=='SAME_WIRE_TAIL_AND_HOME_ROUTE_REFERENCE_OVERLAP'
assert not adj['unclassified_or_positive_original_material']
same_link_micro=[]
for r in hipfinite['positive_pairs']:
 hit=r['maximum'];assert by[hit['a']]['link_frame']==by[hit['b']]['link_frame']
 same_link_micro.append(dict(pair=[hit['a'],hit['b']],mesh_common_mm3=hit['common_mm3'],scope='Same-link relative pose invariant; source STEP host audit is a separate geometric check, not a general motor-fit qualification.'))

for d in [box,adj,hip,hipfinite,floor,bounds,report]:
 for p,h in d.get('sources',{}).items():
  pp=bind(p);assert sources[str(pp.relative_to(ROOT))]==h,('CHANGED_SOURCE',p)
bind(__file__)
out=dict(actual_run=args.run,reference_scope='Supplied actual trace only. Prefix coverage never means full walking approval.',status='INDEPENDENT_COVERAGE_AND_NAMED_ANCHOR_REVIEW_WITH_34_UNRESOLVED_PAIRS_RETAINED',physical_approved=False,all_material_separation_certified=False,review_method='Read-only source/formula review plus independent per-pair interval-ledger reconstruction and compiled-body FK comparison. Does not duplicate every closed-mesh distance/boolean.',assembly_parts=557,numerical_intervals=N,numerical_integration_steps=steps,cross_link_pairs=sum(cross),same_link_pairs_excluded_from_dynamic_boxes=len(pairs)-sum(cross),pair_interval_requests=N*sum(cross),certified_material_pair_intervals=material_count,certified_2p2mm_pair_intervals=margin_count,ledger_has_no_overlap_or_unreported_coverage_gap=True,trace_interval_endpoint_bindings_exact=True,original_six_collision_pairs=targets,left_hip_revised_cross_link_pairs=rail_targets,independent_FK_checks=dict(actual_poses=len(indices),links_per_pose=16,max_rotation_matrix_error=max_rot,max_position_error_m=max_pos,fixed_HOME_harness_transform='Identity in trunk coordinates; whole free-root transform is common and cancels for self-distance. It is a frozen installation reference, not a simulated deforming wire.'),raw_positive_anchor_count=4,raw_positive_classifications=[dict(pair=r['pair'],time_s=r['time_s'],original_STEP_common_mm3=r['independent_original_STEP_common_mm3'],classification=r['classification'])for r in adj['rows']],no_unnamed_actual_raw_positive=True,unresolved_pairs=box['unresolved_pairs'],unresolved_intervals_per_pair=N,unresolved_pairs_are_not_automatically_exempted=True,same_link_revised_rail_mesh_residues=same_link_micro,scope_limits=['Positive-material threshold is only 0.0001 mm plus 0.00001 mm numerical guard; only separately labeled ranges certify 2.2 mm, and neither includes manufacturing tolerances or deformation.',f'34 pairs remain unresolved over all {N} supplied intervals; their identities must match the named R20 unresolved list. They are not blanket approved.',f'The {steps} integration steps are enclosed by controller-recorded extrema; intermediate true ODE solutions and physical compliance are not proved.','Same-link 49627 pair fit review is outside the dynamic boxes; revised rail has explicit original STEP host checks, while all inherited intended contacts remain separate.','The separately bound full-source-CAD floor report gives numerical TPU penetration and non-TPU separation; no material-compression qualification is inferred.','Fixed trunk HOME cable geometry and its moving jaw-linked tail are two representations of the same conductor. Their named overlap does not qualify bend radius, routing or cable life.'],sources=sources)
(NEWOUT/'independent_actual_geometry_review.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:out[k]for k in ['status','pair_interval_requests','certified_material_pair_intervals','certified_2p2mm_pair_intervals','independent_FK_checks','original_six_collision_pairs','left_hip_revised_cross_link_pairs']},ensure_ascii=False))
