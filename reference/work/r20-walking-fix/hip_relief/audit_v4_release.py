"""Read-only audit of the locally gated v4 candidate; not assembly approval."""
from pathlib import Path
import hashlib, json, sys
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'work/python-deps'),str(ROOT/'work/r12-motion/python-deps'),str(ROOT/'work/rk-mechanics/python-deps')]
import numpy as np
import trimesh
P=Path(__file__).resolve().parent/'candidate_v4'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
inputs={}; checked={}
def load(name):
 p=P/name;inputs[str(p.relative_to(ROOT))]=sha(p);return json.loads(p.read_text())
manifest=load('candidate_manifest.json');mass=load('mass_inertia_delta.json')
hosts=load('host_and_tool_self_access.json');interfaces=load('interface_preservation.json')
clearance=load('motor_saddle_continuous_clearance.json');load('local_continuous_clearance.json')
for filename in list(inputs):
 d=json.loads((ROOT/filename).read_text())
 for p,h in d.get('sources',{}).items():
  actual=sha(ROOT/p);assert actual==h,(p,h,actual);checked[p]=actual
rec=manifest['cad_parts'][0];part=manifest['parts'][0]
for kind,alias in [('mesh','STL'),('step','STEP')]:
 p=ROOT/rec[kind];h=sha(p)
 assert h==rec[kind+'_sha256']==rec['sha256_'+alias]==part[kind+'_sha256']
 assert p==(P/'CAD'/rec[alias]) and rec[kind]==part[kind]
 checked[str(p.relative_to(ROOT))]=h
mesh=trimesh.load(ROOT/rec['mesh'],force='mesh');raw=trimesh.load(ROOT/rec['mesh_cleanup_evidence']['raw_mesh'],force='mesh')
assert mesh.is_watertight and mesh.is_winding_consistent and mesh.volume>0
assert not np.any(mesh.area_faces==0)
assert np.array_equal(np.unique(mesh.vertices,axis=0),np.unique(raw.vertices,axis=0))
assert len(raw.faces)-len(mesh.faces)==rec['mesh_cleanup_evidence']['removed_exactly_zero_area_face_count']
assert abs(mesh.volume-raw.volume)<1e-9
assert len(hosts['hosts'])==2 and all(r['new_original_STEP_common_mm3']<1e-7 for r in hosts['hosts'])
assert len(hosts['tool_corridors'])==4 and all(r['new_rail_common_mm3']<1e-7 for r in hosts['tool_corridors'])
assert all(r['protected_plate_removed_mm3']<1e-5 and r['protected_plate_added_mm3']<1e-5 for r in interfaces['interfaces'])
certs={}
for name in ['motor','saddle']:
 c=clearance[name]['certificate'];a=sorted(c['accepted'],key=lambda r:r['start_u'])
 assert c['passed'] and c['failed']==[] and a[0]['start_u']==0 and a[-1]['end_u']==1
 assert all(x['end_u']==y['start_u'] for x,y in zip(a,a[1:]))
 assert all(r['end_u']>r['start_u'] and r['lower_bound_mm']>=2.2 for r in a)
 certs[name]=dict(accepted_contiguous_intervals=len(a),failed_intervals=0,parameter_range=[0,1],minimum_certified_mesh_gap_mm=min(r['lower_bound_mm'] for r in a))
assert len(rec['new_path_HOME_mm'])==8
assert rec['centerline_changed_indices']==[2,3,4,5]
for r in rec['old_to_new_path_mapping']:
 assert r['old_HOME_mm']==rec['old_path_HOME_mm'][r['old_point_index']]
 assert r['new_HOME_mm']==rec['new_path_HOME_mm'][r['new_point_index']]
 assert np.array_equal(np.array(r['new_HOME_mm'])-r['old_HOME_mm'],r['delta_HOME_mm'])
assert mass['add_mass_rows'][0]['nominal_g']==rec['mass_from_CAD_g']
assert mass['add_mass_rows'][0]['COM_home_mm']==rec['center_mm']
assert abs(mass['after_nominal_kg']-(mass['before_nominal_kg']+mass['delta_nominal_g']/1000))<1e-14
I=np.array(mass['add_mass_rows'][0]['I_COM_home_kg_m2']);assert np.allclose(I,I.T) and np.linalg.eigvalsh(I).min()>0
inputs[str(Path(__file__).resolve().relative_to(ROOT))]=sha(Path(__file__).resolve())
report=dict(status='LOCAL_V4_READONLY_RELEASE_AUDIT_PASSED_FULL_ASSEMBLY_PENDING',physical_approved=False,manufacturing_approved=False,
 summaries=dict(continuous_mesh_clearance=certs,roll_range_deg=clearance['certified_roll_range_deg'],native_STEP_hosts_common_mm3=[r['new_original_STEP_common_mm3'] for r in hosts['hosts']],tool_self_common_mm3=[r['new_rail_common_mm3'] for r in hosts['tool_corridors']],mesh_alias_and_raw_cleanup_verified=True,route_mapping_and_mass_verified=True,nominal_assembly_mass_kg=mass['after_nominal_kg']),
 inputs=inputs,verified_sources=checked,
 limitations=['This audits local evidence and its complete interval accounting; it does not independently recompute every Boolean or replace the root whole-assembly scan.','The two moving-pair certificates apply to supplied tessellated rigid sources and their complete stated roll range.','Four tool checks cover the new rail itself only. Neighbouring parts and installation sequence require separate assembly access review.','Material strength, encoder limits, actual manufacture, cables, contact elasticity and hardware loading are not qualified.'])
out=P/'local_release_audit.json';assert not out.exists();out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(path=str(out.relative_to(ROOT)),sha256=sha(out),summary=report['summaries']),ensure_ascii=False,indent=2))
