from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();load=lambda p:json.loads(Path(p).read_text())
s=load(O/'assembly_selection.json');m=load(O/'manifest.json');errors=[];checked=[]
def check(v,msg):
 if not v:errors.append(msg)
def bind(path,expected):
 p=ROOT/path;check(p.is_file() and sha(p)==expected,'source '+str(path));checked.append(path)
for p,h in s['sources'].items():bind(p,h)
check(len(s['items'])==1225 and len({p['name']for p in s['items']})==1225,'installed population')
check(s['new_installed_count']==37,'new count')
for p in s['items']:
 bind(p['mesh'],p['mesh_sha256'])
 if p.get('analysis_mesh'):bind(p['analysis_mesh'],p['analysis_mesh_sha256'])
for p in m['parts'][:3]:
 bind(p['manufacturing_master'],p['manufacturing_master_sha256']);check(p['mesh_watertight'] and p['solid_count']==1,'print topology '+p['name'])
 for rb in p['readback']:check(rb['vertex_error_mm']<1e-10 and rb['indexed_faces_identical'],'print readback')
h=sha(O/'assembly_selection.json');static=load(O/'static_check.json');detail=load(O/'detail_checks.json');service=load(O/'service_check.json');motion=load(O/'motion/final_v3/result.json');contact=load(O/'contact_review.json');visual=load(O/'visual/readback.json');shell=load(O/'shell_surface_audit.json')
check(static['selection_sha256']==h and not static['errors'],'static binding/errors')
check(detail['selection_sha256']==h,'detail binding');check(service['source_selection_sha256']==h,'service binding')
check(not detail['optical']['intersections'],'optical obstruction')
check(not any(r['intersections']for r in detail['front_driver_checks']),'tool obstruction')
check(detail['mouth']['minimum_continuous_lower_bound_mm']>4.74,'mouth bound')
check(not service['intersections'],'service intersections');check(all(r['continuous_bound_after_first_mm']>0 for r in service['near_pairs']),'service continuous after1mm')
check(service['initial_seat_directional_proof']['old_shell_first_mm_continuous_lower_bound_mm']>0,'initial shell separation')
check(service['initial_seat_directional_proof']['minimum_rear_support_lateral_gap_mm']>1,'initial support separation')
check(contact['selection_sha256']==h and contact['dynamic_unresolved_count']==0,'contact scope')
check(contact['result_sha256']==sha(O/'motion/final_v3/result.json'),'motion result binding')
check(load(O/'motion/final_v3/run_binding.json')['selection_sha256']==sha(O/'rigid_inputs.json'),'rigid binding')
check(motion['full_partition_verified'],'motion partition')
check(shell['new_sha256']==m['parts'][2]['mesh_sha256'] and shell['status']=='SURFACE_PRESERVATION_OUTSIDE_DECLARED_LUG_BOXES','shell identity audit')
check(visual['blend_sha256']==sha(O/'visual/Microduck_R24_摄像头前盖.blend'),'Blender readback')
check(visual['build_index_sha256']==sha(O/'visual/build_index.json'),'Blender index')
check(load(O/'visual/build_index.json')['sources']['work/r24-head-front/assembly_selection.json']==h,'Blender selection')
for p,h0 in visual['renders'].items():check(sha(O/'visual'/p)==h0,'render '+p)
for r in m['native_seating_checks']:check(r['intersection_mm3']<1e-8,'native seat')
threads={frozenset(r[:2])for r in m['named_thread_contacts']};seats={frozenset((r['a'],r['b']))for r in contact['seats']}
for r in static['near_rows']:
 if r['intersection_mm3']>1e-8:check(frozenset((r['a'],r['b'])) in threads|seats,'unclassified intersection '+str(r))
mass=load(O/'mass_delta.json');check(abs(mass['delta_mass_g']-47.90334273607311)<1e-6,'mass delta');check(mass['camera']['mass_kg']==.015,'camera ownership')
import fitz
pdf=fitz.open(O/'R24_前盖尺寸与装配.pdf');check(len(pdf)==3,'PDF pages')
report=dict(status='SCOPED_DESIGN_CHECKS_COMPLETE_WITH_CONTACTS_AND_LIMITS' if not errors else 'FAIL',errors=errors,source_checks=len(checked),selection_sha256=h,installed_count=1225,new_count=37,static_delta_pairs=static['requested_pair_count'],rigid_motion_delta_pairs=motion['pair_count'],mouth_continuous_lower_bound_mm=detail['mouth']['minimum_continuous_lower_bound_mm'],optical_gap_mm=detail['optical']['minimum_capped_gap_mm'],mass_delta_g=mass['delta_mass_g'],physical_approved=False,manufacturing_approved=False,verified_files={str(p.relative_to(ROOT)):sha(p) for p in [O/'manifest.json',O/'detail_checks.json',O/'static_check.json',O/'service_check.json',O/'contact_review.json',O/'shell_surface_audit.json',O/'mass_delta.json',O/'R24_前盖尺寸与装配.pdf',O/'visual/readback.json',O/'README.md',Path(__file__)]})
(O/'delivery_verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items()if k!='verified_files'},indent=2));assert not errors,errors
