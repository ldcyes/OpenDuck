"""Source-bound spring-body packing study; no installed R29 assembly changes.

The solid exported here is a conservative *body envelope*, not a spring part
or a manufacturing model. It intentionally omits spring legs, arbor, anchors,
fasteners and their tolerances.
"""
from pathlib import Path
import hashlib
import json
import math
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / 'work/r12-motion/python-deps'),
                str(ROOT / 'work/rk-mechanics/python-deps'),
                str(ROOT / 'work/r18-leg-hip-covers/review')]
import manifold3d as md
import numpy as np
import trimesh
from motion_core import transforms


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def solid(item):
    path = ROOT / item['mesh']
    digest = item.get('mesh_sha256', item.get('sha256_STL'))
    assert digest == sha(path), item['name']
    mesh = trimesh.load(path, force='mesh', process=item.get('mesh_load_process', True))
    vertices = np.asarray(mesh.vertices) @ np.asarray(item['R']).T + np.asarray(item['t_mm'])
    shape = md.Manifold(md.Mesh64(vertices, np.asarray(mesh.faces, dtype=np.uint64)))
    assert shape.status() == md.Error.NoError, item['name']
    return shape, vertices


def main():
    selection_path = ROOT / 'work/r29-r26-resolution/assembly_selection.json'
    selection = json.loads(selection_path.read_text())
    assert selection['status'] == 'R29_R26_FIVE_PART_CLEARANCE_CANDIDATE'
    parts = {item['name']: item for item in selection['items']}
    pivot = np.asarray(next(j for j in selection['joints']
                            if j['joint'] == 'mouth_candidate')['pivot_trunk_mm'])
    assert np.allclose(pivot, [18.894538843760103, 88.1999755293131,
                               242.75716053019593], atol=1e-5)

    # The 96-gon inradius exceeds the desired 6.10 mm wire outside radius.
    radius_mm = 6.11
    y_min_mm, y_max_mm = 79.0, 85.7
    mesh = trimesh.creation.cylinder(radius=radius_mm,
                                     height=y_max_mm-y_min_mm, sections=96)
    mesh.apply_transform(trimesh.transformations.rotation_matrix(math.pi/2, [1, 0, 0]))
    mesh.apply_translation([pivot[0], (y_min_mm+y_max_mm)/2, pivot[2]])
    assert radius_mm * math.cos(math.pi/96) > 6.10
    candidate = md.Manifold(md.Mesh64(np.asarray(mesh.vertices),
                                      np.asarray(mesh.faces, dtype=np.uint64)))
    assert candidate.status() == md.Error.NoError
    envelope_path = HERE / 'spring_body_clearance_envelope.ply'
    mesh.export(envelope_path)

    low, high = np.asarray(mesh.vertices).min(0), np.asarray(mesh.vertices).max(0)
    home_pairs = []
    for item in selection['items']:
        if item['link_frame'] == 'MULTI_LINK_FLEX_HARNESS':
            continue
        path = ROOT / item['mesh']
        loaded = trimesh.load(path, force='mesh', process=item.get('mesh_load_process', True))
        vertices = np.asarray(loaded.vertices) @ np.asarray(item['R']).T + np.asarray(item['t_mm'])
        if np.any(vertices.min(0) > high) or np.any(vertices.max(0) < low):
            continue
        digest = item.get('mesh_sha256', item.get('sha256_STL'))
        assert digest == sha(path), item['name']
        neighbor = md.Manifold(md.Mesh64(vertices, np.asarray(loaded.faces, dtype=np.uint64)))
        assert neighbor.status() == md.Error.NoError, item['name']
        common = abs(float((candidate ^ neighbor).volume()))
        home_pairs.append(dict(name=item['name'], common_mm3=common))
    assert not [row for row in home_pairs if row['common_mm3'] > 1e-6]

    # Circumscribed 80-face sphere: no intersection proves >=3.45 mm at
    # each sampled angle, then carrier vertex travel closes the gaps.
    sphere_mesh = trimesh.creation.icosphere(subdivisions=1, radius=1.0)
    offsets = np.sum(np.asarray(sphere_mesh.vertices)[np.asarray(sphere_mesh.faces)[:, 0]]
                     * np.asarray(sphere_mesh.face_normals), axis=1)
    sphere_mesh.apply_scale(3.45 / float(np.min(np.abs(offsets))))
    sphere = md.Manifold(md.Mesh64(np.asarray(sphere_mesh.vertices),
                                   np.asarray(sphere_mesh.faces, dtype=np.uint64)))
    inflated = candidate.minkowski_sum(sphere)
    assert inflated.status() == md.Error.NoError
    static = {}
    for name in ('R29_lower_head_shell_mouth_10deg_3mm',
                 'R25_top_head_shell_closed_side'):
        shape, _ = solid(parts[name])
        static[name] = abs(float((inflated ^ shape).volume()))
    assert max(static.values()) < 1e-6
    carrier, vertices = solid(parts['R12_mouth_load_carrier'])
    radius = float(np.linalg.norm(vertices-pivot, axis=1).max())
    pose_rows = []
    for angle in np.arange(0, 10.0001, 0.25):
        q = {j['joint']: 0.0 for j in selection['joints']}
        q['mouth_candidate'] = float(angle)
        transform = transforms(selection['joints'], q)[parts['R12_mouth_load_carrier']['link_frame']]
        common = abs(float((inflated ^ carrier.transform(transform[:3])).volume()))
        pose_rows.append(dict(angle_deg=float(angle), inflated_common_mm3=common))
    assert max(row['inflated_common_mm3'] for row in pose_rows) < 1e-6
    between_pose_motion = 2 * radius * math.sin(math.radians(0.125)/2)
    continuous_bound = 3.45 - between_pose_motion

    E = 200000.0   # N/mm^2, study assumption until material cert
    d = 0.7        # mm wire
    D = 11.5       # mm mean coil diameter
    n = 3.0        # active turns, per spring
    pair_preload_Nmm = 20.0
    rate_one_Nmm_rad = E*d**4/(64*D*n)
    rate_pair_Nmm_rad = 2*rate_one_Nmm_rad
    qstress = (D/d + 0.07)/(D/d - 0.75)
    torque_10_Nmm = pair_preload_Nmm + rate_pair_Nmm_rad*math.radians(10)
    stress_0 = qstress*32*(pair_preload_Nmm/2)/(math.pi*d**3)
    stress_10 = qstress*32*(torque_10_Nmm/2)/(math.pi*d**3)
    alpha_10_deg = (torque_10_Nmm/2)/rate_one_Nmm_rad*180/math.pi
    inner_diameter_min_mm = D*n/(n+alpha_10_deg/360)-d
    report = dict(
        status='SPRING_BODY_ONLY_PACKING_PASS_INTERFACE_UNDESIGNED',
        installed_in_R29=False, physical_approved=False, manufacturing_approved=False,
        source_selection_sha256=sha(selection_path),
        source_mesh_sha256={name: parts[name].get('mesh_sha256', parts[name].get('sha256_STL'))
                            for name in ('R29_lower_head_shell_mouth_10deg_3mm',
                                         'R25_top_head_shell_closed_side',
                                         'R12_mouth_load_carrier')},
        envelope_mesh=str(envelope_path.relative_to(ROOT)),
        envelope_sha256=sha(envelope_path),
        envelope_is_manufacturing_master=False,
        envelope=dict(pivot_mm=pivot.tolist(), y_mm=[y_min_mm,y_max_mm],
                      radial_outer_bound_mm=radius_mm,
                      intended_spring_body_OD_mm=12.2,
                      icosphere_inradius_mm=3.45),
        home_all_rigid=dict(part_count=1193, broadphase_pairs=home_pairs,
                            max_true_overlap_mm3=max((r['common_mm3'] for r in home_pairs), default=0)),
        continuous_carrier_clearance=dict(sample_count=len(pose_rows),
                                          sample_step_deg=0.25,
                                          max_inflated_common_mm3=max(r['inflated_common_mm3'] for r in pose_rows),
                                          carrier_vertex_radius_mm=radius,
                                          interpolation_displacement_bound_mm=between_pose_motion,
                                          nominal_lower_bound_mm=continuous_bound,
                                          pose_rows=pose_rows),
        static_inflated_common_mm3=static,
        spring_study=dict(count=2, wire_d_mm=d, mean_D_mm=D, active_turns_each=n,
                          E_assumed_GPa=E/1000, free_body_length_each_mm=(n+1.5)*d,
                          body_spacer_allowance_mm=0.4,
                          pair_preload_at_0deg_Nm=pair_preload_Nmm/1000,
                          pair_rate_Nm_rad=rate_pair_Nmm_rad/1000,
                          pair_closing_torque_at_10deg_Nm=torque_10_Nmm/1000,
                          corrected_bending_stress_0deg_MPa=stress_0,
                          corrected_bending_stress_10deg_MPa=stress_10,
                          inside_diameter_10deg_estimate_mm=inner_diameter_min_mm,
                          proposed_mandrel_OD_mm=9.5,
                          material_grade_and_allowable_stress='UNSPECIFIED',
                          fatigue_life_approved=False,
                          geometry_attachment_approved=False),
        manufacturer_guide_url='https://www.federnshop.com/download/pdf/Gutekunst-Federn-1x1-2013-E.pdf',
        manufacturer_guide_pages='20–21, section 1.4.4',
        excluded_geometry=['spring wire legs', 'rotating arbor and horn fasteners',
                           'fixed anchor and fasteners', 'axial retainer', '31 flexible harness parts'],
    )
    report_path = HERE / 'spring_body_study.json'
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({k: report[k] for k in ('status','installed_in_R29')}, indent=2))
    print('continuous_nominal_lower_bound_mm', continuous_bound)


if __name__ == '__main__':
    main()
