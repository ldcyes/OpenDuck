from pathlib import Path
import json,hashlib,sys
ROOT=Path(__file__).resolve().parents[2];O=Path(__file__).parent
load=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();errors=[];checked=[]
def check(v,msg):
 if not v:errors.append(msg)
def bind(p,h):
 p=Path(p);check(p.is_file()and sha(p)==h,'source '+str(p));checked.append(str(p))
S=load(O/'assembly_selection.json');bind(O/'assembly_selection.json',load(O/'visual/build_index.json')['sources']['work/r25-bottom-head-entry/assembly_selection.json']);check(len(S['items'])==1224 and len({p['name']for p in S['items']})==1224,'installed population');check(S['new_installed_count']==88,'delta count')
for p,h in S['sources'].items():bind(ROOT/p,h)
for p in S['items']+S['service_items']:
 for k in ['mesh','step','analysis_mesh']:
  if p.get(k):
   h=p.get(k+'_sha256',p.get('sha256_STEP'if k=='step'else'sha256_STL'))
   if h:bind(ROOT/p[k],h)
for p in load(O/'mechanics/manifest.json')['parts']:
 if p.get('manufacturing_master'):
  bind(ROOT/p['manufacturing_master'],p['manufacturing_master_sha256']);check(all(x['indexed_faces_identical']and x['vertex_error_mm']<1e-10 and x['watertight']for x in p['readback']),'print topology '+p['name'])
A=load(O/'candidate_selection.json');geo=lambda p:(p['mesh'],p['R'],p['t_mm'],p.get('analysis_mesh'))
check({p['name']:geo(p)for p in A['items']}=={p['name']:geo(p)for p in S['items']},'static exact geometry identity')
static=load(O/'candidate_check.json');contact=load(O/'native_contact_review.json');check(not static['invalid']and not contact['unresolved'],'static contact scope');check(len(contact['rows'])==len(static['hits']),'all static intersections reviewed')
for p,h in contact['sources'].items():bind(ROOT/p,h)
rigid=load(O/'rigid_geometry_identity.json');check(rigid['items_identical']and rigid['interval_bounds_identical'],'rigid geometry unchanged');bind(O/'rigid_inputs.json',rigid['previous_rigid_sha256']);bind(O/'assembly_selection.json',rigid['new_selection_sha256'])
motion=load(O/'motion/rigid_final/result.json');mc=load(O/'motion_contact_review.json');check(motion['full_partition_verified']and not mc['dynamic_unresolved_count']and not mc['unresolved'],'rigid interval checks');check(load(O/'motion/rigid_final/run_binding.json')['selection_sha256']==sha(O/'rigid_inputs.json'),'motion binding')
for p,h in mc['sources'].items():bind(O/p,h)
mouth=load(O/'mouth_check.json');check(not mouth['new_or_increased_intersections'],'new mouth interference');bind(O/'rigid_inputs.json',mouth['source_selection_sha256'])
tools=load(O/'tool_access.json');check(not any(r['intersections']for r in tools['checks']),'staged driver access');bind(O/'assembly_selection.json',tools['selection_sha256'])
check(len(load(O/'tail_validation.json')['rows'])==31,'31 fixed tails');cut=load(O/'Complete_Conductor_Lengths_R25.json');check(len(cut['rows'])==59 and len(cut['R25_changes'])==31,'complete cut ownership');check(not cut['manufacturing_approved'],'cut release boundary')
V=load(O/'visual/readback.json');bind(O/'visual/OpenDuck_R25_底部走线.blend',V['blend_sha256']);bind(O/'visual/build_index.json',V['build_index_sha256']);check(V['part_count']==1224,'Blender population')
for p,h in V['renders'].items():bind(O/'visual'/p,h)
F=load(O/'flex/compact_bundle_home/validation.json');check(F['possible_wire_pair_overlap_count']==0,'HOME wire pair screen');check(len(F['rows'])==31,'HOME wire count')
family=load(O/'flex/compact_bundle_family/finite9_summary.json');check(not family['missing_cases']and family['all31_geometry_and_pair_pass'],'selected nine-pose geometric family')
for p,h in family['source_hashes'].items():bind(ROOT/p,h)
# Finite-body report coverage is reported explicitly, not silently inherited from another family.
body_missing=[r['index']for r in family['cases']if r.get('body_report')is None];body_fail=[r['index']for r in family['cases']if r.get('body_errors')or r.get('body_intersections')]
check(not body_missing and not body_fail and family['all_body_screens_pass'] and len(family['cases'])==9 and all(r['body_route_hash_matches']and r['body_selection_unchanged']for r in family['cases']),'selected nine-pose body checks')
import fitz
pdf=fitz.open(O/'R25_头部底部入口与装配.pdf');check(len(pdf)==2,'PDF pages')
report=dict(status='SCOPED_ENGINEERING_CHECKS_PASS_WITH_EXPLICIT_LIMITS'if not errors else'INCOMPLETE',errors=errors,selection_sha256=sha(O/'assembly_selection.json'),source_checks=len(checked),installed_count=1224,new_count=88,static_near_pairs=static['tested'],reviewed_static_intersections=len(contact['rows']),rigid_dynamic_pairs=motion['dynamic_pair_count'],rigid_interval_count=motion['interval_count'],free_pose_count=len(family['cases']),free_body_near_pairs=family['total_body_near_pairs'],free_minimum_wire_gap_lower_mm=family['minimum_wire_pair_gap_lower_mm'],free_maximum_length_error_mm=family['maximum_absolute_length_error_mm'],free_body_missing=body_missing,free_body_failures=body_fail,free_continuous_motion_proven=False,mouth_baseline_collision_first_deg=min(r['angle_deg']for r in mouth['intersections']),mass_kg=load(O/'mass_delta.json')['mass_kg'],physical_approved=False,manufacturing_approved=False,verified_files={str(p.relative_to(ROOT)):sha(p)for p in [O/'README.md',O/'mass_delta.json',O/'Complete_Conductor_Lengths_R25.json',O/'tool_access.json',O/'tail_validation.json',O/'mouth_check.json',O/'R25_头部底部入口与装配.pdf',O/'visual/readback.json',Path(__file__)]})
(O/'delivery_verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items()if k!='verified_files'},indent=2));assert not errors,errors
