"""Integrate only two cover replacements; bind native and mesh evidence."""
from pathlib import Path
import copy
import hashlib
import json
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/p) for p in ['work/r3-mechanics/python-deps','work/r12-motion/python-deps',
    'work/rk-mechanics/python-deps','work/r11-integration/mechanics',
    'work/r23-power-integration/harness/sp3_reroute/runtime']]
import trimesh
import manifold3d as md
import common as c

sources={}
def bind(path, expected=None):
    path=Path(path)
    if not path.is_absolute(): path=ROOT/path
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    if expected is not None: assert digest==expected,(str(path),digest,expected)
    sources[str(path.relative_to(ROOT))]=digest
    return path
def read(path): return json.loads(bind(path).read_text())
def dump(name,value): (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
bind(__file__)
base=read('work/r25-bottom-head-entry/assembly_selection.json')
manifest=read('work/r26-cover-first/mechanics/manifest.json')
native_checks=read('work/r26-cover-first/mechanics/geometry_checks.json')
new=manifest['parts']; assert len(new)==2
old={p['name']:p for p in base['items']}
replacements={p['replaces'][0]:p for p in new}
assert set(replacements)=={'R18P_L_thigh_photo_triangle','R18P_R_thigh_photo_triangle'}
for name,p in replacements.items():
    assert p['link_frame']==old[name]['link_frame']
    assert np.allclose(p['R'],old[name]['R']) and np.allclose(p['t_mm'],old[name]['t_mm'])
items=[replacements.get(p['name'],p) for p in base['items']]
assert len(items)==len(base['items']) and len({p['name'] for p in items})==len(items)
retained=[p for p in items if p['name'] in old]
assert all(p==old[p['name']] for p in retained)
selection=dict(status='R26_A_COVER_FIRST_ENGINEERING_CANDIDATE',items=items,
    joints=copy.deepcopy(base['joints']),service_items=copy.deepcopy(base.get('service_items',[])),
    service_only_items=copy.deepcopy(base.get('service_only_items',[])),
    parent_selection='work/r25-bottom-head-entry/assembly_selection.json',
    parent_selection_sha256=sources['work/r25-bottom-head-entry/assembly_selection.json'],
    replaces=list(replacements),new_part_names=[p['name'] for p in new],
    installed_count=len(items),new_installed_count=2,retained_count=len(retained),
    manufacturing_approved=False,physical_approved=False,
    limits=['Two-cover geometry delta only; inherited R25 head, harness, torque and gait limitations remain.',
            'Reference/visibility flags on retained records are preserved, not reinterpreted as physical certification.'])
assert selection['joints']==base['joints']
dump('assembly_selection.json',selection)

cache={}; native={}
def mesh(part):
    name=part['name']
    if name not in cache:
        path=part.get('analysis_mesh',part['mesh'])
        expected=part.get('analysis_mesh_sha256',part.get('mesh_sha256'))
        m=trimesh.load(bind(path,expected),force='mesh',process=part.get('mesh_load_process',True))
        m.vertices=m.vertices@np.array(part['R']).T+part['t_mm']
        solid=md.Manifold(md.Mesh64(np.array(m.vertices),np.array(m.faces,dtype=np.uint64)))
        cache[name]=(m,solid)
    return cache[name]
def step(part):
    if part['name'] not in native:
        path=bind(part['step'],part.get('step_sha256',part.get('sha256_STEP')))
        native[part['name']]=c.tf(c.read(path),part['R'],part['t_mm'])
    return native[part['name']]
def overlap(a,b,pad=0): return bool(np.all(a[1]>=b[0]-pad) and np.all(b[1]>=a[0]-pad))
def intersection(a,b):
    assert a.status()==md.Error.NoError and b.status()==md.Error.NoError
    result=a^b
    assert result.status()==md.Error.NoError
    return abs(float(result.volume()))

NATIVE_VOLUME_TOL=1e-6
rows=[]
for old_name,p in replacements.items():
    original=old[old_name]
    ns,os=step(p),step(original)
    excess=abs(c.volume(c.cut(ns,os)))
    assert excess<=NATIVE_VOLUME_TOL,(p['name'],'native outside',excess)
    nm,nb=mesh(p); om,ob=mesh(original)
    assert nb.status()==md.Error.NoError and ob.status()==md.Error.NoError
    outside=nb-ob
    assert outside.status()==md.Error.NoError
    mv=abs(float(outside.volume()))
    discrepancy=[]
    if mv>1e-7:
        # Independent tessellations can differ along retained curved boundaries.
        # Record their actual difference rather than labelling it exact containment.
        verts=np.asarray(outside.to_mesh64().vert_properties)[:,:3]
        if len(verts):
            _,distance,_=trimesh.proximity.closest_point(om,verts)
            discrepancy=list(map(float,[distance.min(),distance.max()]))
    rows.append(dict(name=p['name'],old_name=old_name,native_new_minus_old_mm3=excess,
        native_volume_tolerance_mm3=NATIVE_VOLUME_TOL,mesh_new_minus_old_mm3=mv,
        mesh_difference_vertex_distance_to_old_mesh_mm=discrepancy,
        mesh_result=('EXACT_MESH_SUBSET' if mv<=1e-7 else 'INDEPENDENT_TESSELLATION_BOUNDARY_DIFFERENCE_NATIVE_PROOF_CONTROLS'),
        old_native_volume_mm3=c.volume(os),new_native_volume_mm3=c.volume(ns)))

# Check every selected item, including retained hidden entries; no blanket skips.
static=[]; failures=[]; broad_count=0
for p in new:
    nm,nb=mesh(p)
    for other in items:
        if other['name']==p['name']: continue
        om,ob=mesh(other)
        if not overlap(nm.bounds,om.bounds,.02): continue
        broad_count+=1
        valid=ob.status()==md.Error.NoError
        mesh_v=intersection(nb,ob) if valid else None
        native_v=None
        if other.get('step'):
            native_v=abs(c.volume(c.common(step(p),step(other))))
        volume=native_v if native_v is not None else mesh_v
        is_seat=other['name'] in {
            p['replaces'][0].replace('_photo_triangle','_CNC_bridge_saddle'),
            *[p['replaces'][0].replace('_photo_triangle',f'_skin_F{i}_washer_OD7') for i in [1,2]]}
        status='DISJOINT_OR_ZERO_VOLUME_CONTACT'
        if volume is None or volume>NATIVE_VOLUME_TOL:
            status='UNRESOLVED_INTERSECTION'
            failures.append(dict(cover=p['name'],other=other['name'],volume_mm3=volume))
        elif is_seat:
            status='NAMED_UNCHANGED_SEATING_INTERFACE'
        static.append(dict(cover=p['name'],other=other['name'],mesh_common_mm3=mesh_v,
            native_common_mm3=native_v,status=status))

contracts=read('work/r18-leg-hip-covers/legs/reference_design/candidate_v8/fixing_contract.json')
access=[]
for module in contracts['modules']:
    axis=np.array(module['cover_outward_axis'])
    side=module['side']
    for i in [1,2]:
        screw_name=f'R18P_{side}_thigh_skin_F{i}_M2p5x8_screw'
        screw=old[screw_name];sm,_=mesh(screw)
        center=np.array(module['boss_front_faces_HOME_mm'][i-1])
        # External shaft starts just beyond actual screw head, not inside its socket.
        head_front=float(np.max(sm.vertices@axis))
        start=center+axis*(head_front+.02-float(center@axis))
        tool=c.cylinder(start+17.5*axis,1.5,35,axis)
        bounds=np.array(c.properties(tool)['bounds_mm'])
        checks=[]
        for other in items:
            if other['name']==screw_name: continue
            om,ob=mesh(other)
            if not overlap(bounds,om.bounds,.02): continue
            if other.get('step'):
                v=abs(c.volume(c.common(tool,step(other))))
                checks.append(dict(obstacle=other['name'],native_common_mm3=v))
                if v>NATIVE_VOLUME_TOL: failures.append(dict(tool=screw_name,other=other['name'],volume_mm3=v))
            else:
                # Reject an unresolved near obstacle rather than silently ignoring it.
                checks.append(dict(obstacle=other['name'],status='NO_NATIVE_NEAR_OBSTACLE'))
                failures.append(dict(tool=screw_name,other=other['name'],status='NO_NATIVE_NEAR_OBSTACLE'))
        access.append(dict(screw=screw_name,stage='HOME_FINAL_COVER_FASTENING_OTHER_SELECTED_PARTS_PRESENT',
            absent_names=[screw_name],shaft_diameter_mm=3,external_length_mm=35,
            origin_mm=start.tolist(),axis=axis.tolist(),near_obstacles=checks,
            scope='External shaft corridor only. Socket bit fit, hand and handle need first-article acceptance.'))

mass_base=read('work/r25-bottom-head-entry/mass_delta.json')
ledger=read('work/r23-power-integration/integration/mass_final/R23_mass_ledger.json')
mass_rows={x['name']:x for x in ledger['rows']}
M=mass_base['mass_kg']*1000;moment=M*np.array(mass_base['COM_HOME_mm'])
removed=[];added=[]
for old_name,p in replacements.items():
    r=mass_rows[old_name];mass=r['mass_kg']*1000;center=np.array(r['COM_HOME_m'])*1000
    assert abs(mass-old[old_name]['mass_from_CAD_g'])<1e-6
    M-=mass;moment-=mass*center
    removed.append(dict(name=old_name,mass_g=mass,center_mm=center.tolist()))
    mass=p['mass_from_CAD_g'];center=np.array(p['center_mm'])
    M+=mass;moment+=mass*center
    added.append(dict(name=p['name'],mass_g=mass,center_mm=center.tolist()))
mass=dict(status='R26_ENGINEERING_DENSITY_ESTIMATE_NOT_WEIGHED',mass_kg=M/1000,
    COM_HOME_mm=(moment/M).tolist(),delta_mass_g=M-mass_base['mass_kg']*1000,
    delta_COM_HOME_mm=(moment/M-np.array(mass_base['COM_HOME_mm'])).tolist(),removed=removed,added=added,
    physical_approved=False,manufacturing_approved=False,
    limits=['Only cover material changes; no motor change, no dynamics/torque/endurance qualification.'])
dump('mass_delta.json',mass)
report=dict(status='PASS_TWO_COVER_GEOMETRY_DELTA' if not failures else 'UNRESOLVED',
    selection_sha256=hashlib.sha256((OUT/'assembly_selection.json').read_bytes()).hexdigest(),
    parts_total=len(items),retained_part_records_identical=len(retained),joint_records_identical=len(base['joints']),
    independent_subset_checks=rows,static_all_selected_items_tested_per_cover=len(items)-1,
    static_near_pairs=broad_count,static_results=static,tool_access=access,errors=failures,
    motion_delta_proof=dict(method='NATIVE_SOLID_SUBSET_UNDER_IDENTICAL_RIGID_LINK_TRANSFORMS',
        domain='All identical joint poses, not limited to a sampled trajectory',
        argument='N subset O implies T(q)N subset T(q)O; with all other shapes/transforms unchanged, intersections cannot be newly introduced.',
        limits=['This proves no added intersections, not that old intersections are absent.',
                'No new dynamics, elastic deflection, manufacturing tolerance or physical motion approval.',
                'Identical removal paths cannot acquire an obstruction from shortening a cover; unresolved original paths remain unresolved.']),
    physical_approved=False,manufacturing_approved=False,sources=sources)
dump('verification.json',report)
print(json.dumps({k:report[k] for k in ['status','parts_total','retained_part_records_identical','joint_records_identical','static_near_pairs','errors']},indent=2))
assert not failures,failures
