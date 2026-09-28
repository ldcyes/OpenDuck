"""Subtract a clearanced swept mouth envelope from the R26 lower head shell."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = HERE / 'mechanics_10deg'
sys.path[:0] = [
    str(ROOT / 'work/r12-motion/python-deps'),
    str(ROOT / 'work/rk-mechanics/python-deps'),
    str(ROOT / 'work/r18-leg-hip-covers/review'),
    str(ROOT / 'work/r23-power-integration/integration'),
]
import manifold3d as md
import numpy as np
import trimesh
from mesh_print_export import export_indexed
from motion_core import transforms


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_solid(part):
    mesh = trimesh.load(ROOT / part['mesh'], force='mesh', process=part.get('mesh_load_process', True))
    vertices = np.asarray(mesh.vertices) @ np.asarray(part['R']).T + np.asarray(part['t_mm'])
    result = md.Manifold(md.Mesh64(vertices, np.asarray(mesh.faces, dtype=np.uint64)))
    assert result.status() == md.Error.NoError
    return result


def main():
    selection_file = ROOT / 'work/r26-cover-first/assembly_selection.json'
    selection = json.loads(selection_file.read_text())
    parts = {item['name']: item for item in selection['items']}
    shell_part = parts['R25_lower_head_shell_bottom_entry']
    mouth_part = parts['R12_mouth_load_carrier']
    shell = load_solid(shell_part)
    mouth = load_solid(mouth_part)
    # A circumscribed 80-face sphere has exact inradius 3.45 mm.  At 0.25
    # degree samples the carrier moves <= 0.392 mm to its nearest sample,
    # proving >= 3.058 mm nominal continuous clearance for the mesh.
    sphere_mesh = trimesh.creation.icosphere(subdivisions=1, radius=1.0)
    face_offset = np.sum(np.asarray(sphere_mesh.vertices)[np.asarray(sphere_mesh.faces)[:, 0]] * np.asarray(sphere_mesh.face_normals), axis=1)
    sphere_mesh.apply_scale(3.45 / float(np.min(np.abs(face_offset))))
    sphere = md.Manifold(md.Mesh64(np.asarray(sphere_mesh.vertices), np.asarray(sphere_mesh.faces, dtype=np.uint64)))
    expanded = mouth.minkowski_sum(sphere)
    assert expanded.status() == md.Error.NoError
    poses = []
    for angle in np.arange(0, 10 + 1e-9, 0.25):
        joint_angles = {joint['joint']: 0.0 for joint in selection['joints']}
        joint_angles['mouth_candidate'] = float(angle)
        transform = transforms(selection['joints'], joint_angles)[mouth_part['link_frame']]
        poses.append(expanded.transform(transform[:3]))
    # The subtraction is local to the swept mouth; no brackets or actuators move.
    relieved = md.Manifold.batch_boolean([shell] + poses, md.OpType.Subtract)
    assert relieved.status() == md.Error.NoError
    components = sorted(relieved.decompose(), key=lambda part: abs(part.volume()), reverse=True)
    assert components and all(abs(part.volume()) < 1.0 for part in components[1:]), (
        'load-bearing geometry disconnected', [(x.volume(), x.bounding_box()) for x in components]
    )
    # Exclude only detached CSG skin flakes under 1 cubic millimetre; record each.
    excluded_flakes = [dict(volume_mm3=part.volume(), bounds_mm=part.bounding_box()) for part in components[1:]]
    relieved = components[0]
    assert 0 < relieved.volume() < shell.volume()
    result_mesh = relieved.to_mesh64()
    print_mesh = trimesh.Trimesh(
        vertices=np.asarray(result_mesh.vert_properties)[:, :3],
        faces=np.asarray(result_mesh.tri_verts),
        process=False,
    )
    assert print_mesh.is_watertight and print_mesh.is_winding_consistent
    name = 'R29_lower_head_shell_mouth_10deg_3mm'
    exported = export_indexed(print_mesh, OUT, name)
    mass_g = print_mesh.volume * shell_part['density_assumption_g_cm3'] / 1000
    report = {
        'name': name,
        'replaces': shell_part['name'],
        'source_selection': str(selection_file.relative_to(ROOT)),
        'source_selection_sha256': sha(selection_file),
        'source_shell': shell_part['mesh'],
        'source_shell_sha256': sha(ROOT / shell_part['mesh']),
        'source_mouth': mouth_part['mesh'],
        'source_mouth_sha256': sha(ROOT / mouth_part['mesh']),
        'printing_master': str(exported['manufacturing_path'].relative_to(ROOT)),
        'analysis_mesh': str(exported['mesh_path'].relative_to(ROOT)),
        'print_master_sha256': sha(exported['manufacturing_path']),
        'analysis_mesh_sha256': sha(exported['mesh_path']),
        'mesh_load_process': False,
        'units': 'mm',
        'sweep': {'start_deg': 0, 'end_deg': 10, 'sample_step_deg': 0.25,
                  'sample_count': len(poses), 'envelope_polyhedron_inradius_mm': 3.45,
                  'envelope_polyhedron_circumradius_mm': float(np.linalg.norm(sphere_mesh.vertices, axis=1).max()),
                  'envelope_polyhedron_faces': len(sphere_mesh.faces)},
        'original_volume_mm3': shell.volume(),
        'new_volume_mm3': print_mesh.volume,
        'removed_volume_mm3': shell.volume() - print_mesh.volume,
        'excluded_numerical_flakes': excluded_flakes,
        'original_mass_g': shell_part.get('mass_from_CAD_g'),
        'new_mass_g': mass_g,
        'new_center_mm': print_mesh.center_mass.tolist(),
        'new_inertia_g_mm2': (print_mesh.moment_inertia * shell_part['density_assumption_g_cm3'] / 1000).tolist(),
        'readback': exported['readback'],
        'software_mouth_limit_deg': [0, 10],
        'full_25deg_travel_approved': False,
        'physical_approved': False,
        'manufacturing_approved': False,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (HERE / 'manifest_10deg.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ('original_volume_mm3', 'new_volume_mm3', 'removed_volume_mm3', 'new_mass_g')}, indent=2))


if __name__ == '__main__':
    main()
