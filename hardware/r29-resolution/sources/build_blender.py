"""Build an inspectable R29 assembly and a replay of the R29-mass nominal trace.

Run with bundled Blender: blender -b --python build_blender.py -- TRACE_JSON
The R25 reference scenes are retained from the R26 source file. This file
changes five selected meshes and never represents a physical walking test.
"""
from pathlib import Path
import hashlib
import json
import sys

import bpy
import numpy as np
from mathutils import Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'work/r27-walk-simulation/visual'))
from blender_actual_helpers_r27 import add_actual_avatar, frontal_camera, new_scene


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def imported_mesh(path):
    before = set(bpy.data.objects)
    suffix = path.suffix.lower()
    if suffix == '.ply':
        bpy.ops.wm.ply_import(filepath=str(path), global_scale=1.0)
    elif suffix == '.stl':
        bpy.ops.wm.stl_import(filepath=str(path), global_scale=1.0)
    else:
        raise ValueError(f'Unsupported Blender analysis mesh: {path}')
    added = set(bpy.data.objects) - before
    assert len(added) == 1, (path, added)
    obj = added.pop()
    assert obj.type == 'MESH' and len(obj.data.vertices) > 3
    assert all(abs(obj.matrix_world[i][i] - 1) < 1e-9 for i in range(3))
    mesh = obj.data.copy()
    bpy.data.objects.remove(obj, do_unlink=True)
    return mesh


def main(trace_path):
    selection_path = HERE / 'assembly_selection.json'
    index_path = ROOT / 'work/r26-cover-first/visual/build_index.json'
    readback_path = ROOT / 'work/r26-cover-first/visual/readback.json'
    source_blend = ROOT / 'work/r26-cover-first/visual/OpenDuck_R26_cover_first.blend'
    selection, index, readback, trace = map(load, (selection_path, index_path, readback_path, trace_path))
    assert len(selection['items']) == len(index['main_parts']) == 1224
    assert len(selection['joints']) == 15 and len(trace['samples']) == 9774
    assert sha(source_blend) == readback['blend_sha256']
    assert set(trace['samples'][0]['q_HOME_delta_deg']) == {j['joint'] for j in selection['joints']}
    bpy.ops.wm.open_mainfile(filepath=str(source_blend))
    base = bpy.data.scenes[index['main_scene']]
    base.name = '01_R29_complete_assembly'
    bpy.context.window.scene = base
    bpy.context.window.view_layer = base.view_layers[0]
    rows = []
    replaced = selection['revision_replacements']
    inverse = {old: new for new, old in replaced.items()}
    new_items = {item['name']: item for item in selection['items']}
    changed_rows = {}
    for item, original in zip(selection['items'], index['main_parts']):
        old_name = original['part_id']
        assert item['name'] == inverse.get(old_name, old_name)
        row = dict(original)
        if old_name in inverse:
            mesh_path = ROOT / item['mesh']
            mesh_digest = item.get('mesh_sha256', item.get('sha256_STL'))
            assert mesh_digest and sha(mesh_path) == mesh_digest, item['name']
            source_obj = bpy.data.objects[row['object']]
            assert source_obj.name in base.objects
            new_mesh = imported_mesh(mesh_path)
            for mat in source_obj.data.materials:
                new_mesh.materials.append(mat)
            source_obj.data = new_mesh
            source_obj.name = 'R29_' + item['name']
            source_obj['source_geometry_sha256'] = mesh_digest
            source_obj['replaces'] = old_name
            source_obj['manufacturing_approved'] = False
            row.update(part_id=item['name'], object=source_obj.name, changed=True,
                       collection='R29_clearance_revision')
            changed_rows[item['name']] = source_obj.name
        else:
            assert item['name'] == old_name
            row['collection'] = 'R29_retained'
        rows.append(dict(row, expected_matrix_m=row['matrix_m']))
    assert len(changed_rows) == 5
    base['selection_sha256'] = sha(selection_path)
    base['status'] = 'R29_R26_FIVE_PART_ENGINEERING_CANDIDATE'
    base['physical_approved'] = False
    base['manufacturing_approved'] = False
    scene = new_scene('07_R29_R26质量重算四步运动', base, trace['time_s'], fps=40)
    scene['scope'] = 'R29 geometry on an integrated free-base trace re-solved with R29 mass and inertias.'
    scene['limitations'] = 'R20 contact shapes, estimated mass, rigid wire surrogates, unmeasured low-voltage continuous torque.'
    scene['physical_approved'] = False
    scene['manufacturing_approved'] = False
    metadata = dict(trace_path=str(trace_path.relative_to(ROOT)), trace_sha256=sha(trace_path))
    avatar = add_actual_avatar(scene, 'R29_', selection['items'], selection['joints'], rows,
                               trace['samples'], np.array(index['native_to_scene_shift_mm'])/1000,
                               metadata)
    camera = frontal_camera(scene, base, width_m=.72)
    camera.location = Vector((2, 0, .29))
    camera.rotation_euler = Vector((-1, 0, 0)).to_track_quat('-Z', 'Y').to_euler()
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.display.shading.light = 'STUDIO'
    scene.display.shading.color_type = 'MATERIAL'
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.render.resolution_x = 720
    scene.render.resolution_y = 900
    scene.frame_set(1)
    bpy.context.window.scene = scene
    scene['flex_wires_are_rigid_display_approximation'] = True
    scene['mouth_operational_range_deg'] = '0..10'
    text = bpy.data.texts.new('R29_运动范围与验收状态')
    text.write('R29 assembly has five R26 part replacements. Four-step nominal motion is a R29-mass numerical integration, not a hardware test. The 31 free wires are display-only rigid approximations. Mouth commands are limited to 0..10 degrees, but no physical hard stop or first-article tolerance proof exists. Continuous low-battery motor torque qualification is pending.\n')
    out_index = dict(status='R29_BLENDER_PENDING_READBACK', selection_sha256=sha(selection_path),
                     trace_sha256=sha(trace_path), source_blend_sha256=sha(source_blend),
                     static_scene=base.name, motion_scene=scene.name,
                     part_count=len(avatar['parts']), joint_count=len(selection['joints']),
                     source_samples=len(trace['samples']), duration_s=trace['time_s'],
                     static_changed_objects=changed_rows,
                     motion_part_objects={name: obj.name for name, obj in avatar['parts'].items()},
                     root_object=avatar['root'].name,
                     joint_objects={j['joint']: avatar['rigs'][j['child_link']].name for j in selection['joints']},
                     physical_approved=False, manufacturing_approved=False)
    (HERE / 'blender_build_index.json').write_text(json.dumps(out_index, indent=2, ensure_ascii=False) + '\n')
    bpy.context.preferences.filepaths.save_version = 0
    outfile = HERE / 'OpenDuck_R29_R26_mass_motion.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(outfile), compress=True)
    print('R29_BLENDER_SAVED', outfile, flush=True)


if __name__ == '__main__':
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    if len(args) != 1:
        raise SystemExit('Expected final R29 dynamic_trace_for_CAD.json path')
    main(Path(args[0]).resolve())
