"""Read the saved R29 blend and check selected geometry and animation binding."""
from pathlib import Path
import hashlib
import json
import math
import sys

import bpy
from mathutils import Matrix

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bounds(mesh):
    return [[min(v.co[i] for v in mesh.vertices) for i in range(3)],
            [max(v.co[i] for v in mesh.vertices) for i in range(3)]]


def main(trace_path):
    sel_path = HERE / 'assembly_selection.json'
    sel = load(sel_path)
    index = load(HERE / 'blender_build_index.json')
    expected = load(HERE / 'blender_source_geometry.json')
    trace = load(trace_path)
    assert index['selection_sha256'] == sha(sel_path)
    assert index['trace_sha256'] == sha(trace_path)
    assert len(sel['items']) == 1224 and len(sel['joints']) == 15
    base = bpy.data.scenes[index['static_scene']]
    motion = bpy.data.scenes[index['motion_scene']]
    assert base['selection_sha256'] == sha(sel_path)
    assert base['physical_approved'] is False and motion['physical_approved'] is False
    assert len(index['static_changed_objects']) == 5
    assert len(index['motion_part_objects']) == 1224
    readback = {}
    for part in sel['items']:
        name = part['name']
        obj = bpy.data.objects[index['motion_part_objects'][name]]
        assert obj.name in motion.objects and obj.type == 'MESH'
        if name not in index['static_changed_objects']:
            continue
        sobj = bpy.data.objects[index['static_changed_objects'][name]]
        assert sobj.name in base.objects and sobj.data == obj.data
        source = ROOT / part['mesh']
        digest = part.get('mesh_sha256', part.get('sha256_STL'))
        assert digest == sha(source) == sobj['source_geometry_sha256']
        got = bounds(sobj.data)
        exp = expected[name]['bounds_mm']
        error = max(abs(got[side][axis] - exp[side][axis])
                    for side in range(2) for axis in range(3))
        assert error <= 1e-3, (name, got, exp, error)
        assert len(sobj.data.polygons) > 10
        readback[name] = dict(source_sha256=digest, bounds_mm=got,
                              bound_error_mm=error, vertices=len(sobj.data.vertices),
                              faces=len(sobj.data.polygons))
    assert len(readback) == 5
    root = bpy.data.objects[index['root_object']]
    assert root.animation_data and root.name in motion.objects
    assert root['source_sha256'] == sha(trace_path)
    assert motion.frame_end == math.ceil(1 + motion.render.fps * trace['time_s'])
    poses = []
    for frame, sample in [(1, trace['samples'][0]),
                          (motion.frame_end, trace['samples'][-1])]:
        motion.frame_set(frame)
        matrix = Matrix(sample['base_transform_m'])
        pos_error = max(abs(root.location[i] - matrix.translation[i]) for i in range(3))
        angle_error = root.rotation_quaternion.rotation_difference(matrix.to_quaternion()).angle
        assert pos_error < 1e-5 and angle_error < 1e-5, (frame, pos_error, angle_error)
        joint_error = 0.0
        for joint, object_name in index['joint_objects'].items():
            actuator = bpy.data.objects[object_name]
            assert actuator.animation_data and actuator.name in motion.objects
            err = abs(actuator.rotation_axis_angle[0] - math.radians(sample['q_HOME_delta_deg'][joint]))
            joint_error = max(joint_error, err)
        assert joint_error < 1e-5, (frame, joint_error)
        poses.append(dict(frame=frame, root_position_error_m=pos_error,
                          root_angle_error_rad=angle_error,
                          worst_joint_error_rad=joint_error))
    out = dict(status='R29_BLENDER_READBACK_PASS',
               blend_sha256=sha(bpy.data.filepath), selection_sha256=sha(sel_path),
               trace_sha256=sha(trace_path),
               installed_part_count=len(index['motion_part_objects']),
               joint_count=len(index['joint_objects']),
               changed_geometry=readback, checked_poses=poses,
               physical_approved=False, manufacturing_approved=False)
    (HERE / 'blender_readback.json').write_text(json.dumps(out, indent=2, ensure_ascii=False) + '\n')
    print('R29_BLENDER_READBACK_PASS', len(readback), flush=True)


if __name__ == '__main__':
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    if len(args) != 1:
        raise SystemExit('Expected final R29 dynamic_trace_for_CAD.json path')
    main(Path(args[0]).resolve())
