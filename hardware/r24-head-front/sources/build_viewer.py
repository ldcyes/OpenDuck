"""Create the source-bound R24 model from retained R22 objects and new CAD."""
from pathlib import Path
import hashlib
import json
import sys
import argparse

import bpy
import numpy as np
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--selection', default='work/r24-head-front/assembly_selection.json')
parser.add_argument('--output-dir', type=Path, default=OUT)
parser.add_argument('--no-render', action='store_true')
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
OUT = args.output_dir.resolve()
OUT.mkdir(parents=True, exist_ok=True)
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
sources = {}


def read(path):
    sources[path] = sha(ROOT / path)
    return json.loads((ROOT / path).read_text())


selection = read(args.selection)
prior = read('work/r23-power-integration/visual/build_index.json')
prior_check = read('work/r23-power-integration/visual/readback.json')
prior_path = 'work/r23-power-integration/visual/Microduck_R23_电源集成设计.blend'
assert sha(ROOT / prior_path) == prior_check['blend_sha256']
sources[prior_path] = sha(ROOT / prior_path)
bpy.ops.wm.open_mainfile(filepath=str(ROOT / prior_path))
old_scenes = list(bpy.data.scenes)
old_main = bpy.data.scenes[prior['main_scene']]
old_rows = {r['part_id']: r for r in prior['main_parts']}
old_objects = {name: old_main.objects[r['object']] for name, r in old_rows.items()}
shift = np.array(prior['native_to_scene_shift_mm']) / 1000


def material(name, color, metal=0):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    node = m.node_tree.nodes.get('Principled BSDF')
    node.inputs['Base Color'].default_value = (*color, 1)
    node.inputs['Metallic'].default_value = metal
    node.inputs['Roughness'].default_value = .4
    return m


materials = {
    'shell': material('R24_外壳', (.87, .88, .85)),
    'rubber': material('R24_柔性护套', (.16, .19, .22)),
    'positive': material('R24_电源正极', (.55, .035, .028)),
    'ground': material('R24_地线', (.055, .065, .075)),
    'metal': material('R24_金属', (.46, .52, .57), .65),
    'insulator': material('R24_绝缘件', (.69, .55, .30)),
    'wire': material('R24_线束', (.04, .34, .60)),
    'black': material('R24_商用器件', (.06, .07, .09)),
    'lens': material('R24_光学镜头', (.025, .055, .07), .3),
    'pcb': material('R24_PCB', (.025, .26, .12)),
    'connector': material('R24_插头', (.81, .84, .81)),
}


def assign(obj, part):
    text = (part['name'] + ' ' + str(part.get('material', '')) + ' ' + part.get('kind', '')).lower()
    key = 'metal'
    if any(t in text for t in ('peek', 'ptfe', 'silicone', 'insulat', 'polymer', 'pad', 'duct')):
        key = 'insulator'
    if any(t in text for t in ('wire', 'harness', 'cable')):
        key = 'wire'
    if any(t in text for t in ('fan', 'thermistor', 'sensor_body')):
        key = 'black'
    if 'pcb' in text or 'substrate' in text:
        key = 'pcb'
    if 'connector' in text or 'xt30' in text:
        key = 'connector'
    if any(t in text for t in ('pa2200', 'pa12', 'top_head_shell', 'chest_skin')):
        key = 'shell'
    if any(t in text for t in ('tpu', 'vmq', 'rubber')):
        key = 'rubber'
    if key == 'wire' and any(t in text for t in ('positive', '_pos', '_bat_plus')):
        key = 'positive'
    if key == 'wire' and any(t in text for t in ('ground', '_gnd', '_bat_minus')):
        key = 'ground'
    if 'eye_bezel' in text: key = 'black'
    if 'os05a10_lens' in text: key = 'lens'
    if 'os05a10_module_body' in text: key = 'pcb'
    obj.data.materials.clear()
    obj.data.materials.append(materials[key])


world = bpy.data.worlds.new('R24_world')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (.7, .75, .8, 1)
world.node_tree.nodes['Background'].inputs['Strength'].default_value = .8


def scene(name):
    s = bpy.data.scenes.new(name)
    s.unit_settings.system = 'METRIC'
    s.unit_settings.length_unit = 'MILLIMETERS'
    s.world = world
    s.render.engine = 'CYCLES'
    s.cycles.device = 'CPU'
    s.cycles.samples = 12
    s.cycles.use_denoising = True
    s.cycles.max_bounces = 5
    s.render.threads_mode = 'FIXED'
    s.render.threads = 4
    s.render.resolution_x = 1400
    s.render.resolution_y = 1200
    s.render.resolution_percentage = 100
    s.render.image_settings.file_format = 'PNG'
    s.view_settings.view_transform = 'AgX'
    s.frame_start = s.frame_end = 1
    camera = bpy.data.cameras.new(name + '_camera')
    obj = bpy.data.objects.new(camera.name, camera)
    s.collection.objects.link(obj)
    s.camera = obj
    camera.type = 'ORTHO'
    for i, (rotation, power) in enumerate([((.4, -.5, -.7), 2.5), ((-.4, .7, 2.4), 1.2)]):
        light = bpy.data.lights.new(name + '_light_' + str(i), 'SUN')
        light.energy, light.angle = power, .3
        obj = bpy.data.objects.new(light.name, light)
        s.collection.objects.link(obj)
        obj.rotation_euler = rotation
    s['scope'] = 'R24 static CAD integration; qualification is reported separately.'
    s['physical_approved'] = False
    return s


def collection(s, name):
    c = bpy.data.collections.new(name)
    s.collection.children.link(c)
    return c


def fit_camera(s, objects, direction):
    points = [obj.matrix_world @ Vector(corner) for obj in objects for corner in obj.bound_box]
    array = np.array(points)
    center = Vector((array.min(0) + array.max(0)) / 2)
    direction = Vector(direction).normalized()
    rotation = (-direction).to_track_quat('-Z', 'Y')
    inverse = rotation.to_matrix().transposed()
    local = np.array([inverse @ (p - center) for p in points])
    span = local.max(0) - local.min(0)
    # Read Blender's actual frame: ortho_scale is horizontal for this aspect.
    s.camera.data.ortho_scale = 1
    frame = np.array([list(p) for p in s.camera.data.view_frame(scene=s)])
    unit_span = frame.max(0) - frame.min(0)
    s.camera.data.ortho_scale = float(max(span[0] / unit_span[0], span[1] / unit_span[1]) * 1.13)
    s.camera.location = center + direction * 2
    s.camera.rotation_euler = rotation.to_euler()
    return list(center)


main = scene('01_R24_完整装配')
bpy.context.window.scene = main
groups, objects, records = {}, {}, []
for part in selection['items']:
    name = part['name']
    domain = 'head_front' if part.get('is_new') else None
    group_name = ('R24_' + domain) if domain else ('保留_' + part.get('category', 'R22'))
    if not part.get('visible_default', True):
        group_name = '隐藏参考_' + group_name
    if group_name not in groups:
        groups[group_name] = collection(main, group_name)
    if domain:
        path = ROOT / part['mesh']
        assert sha(path) == part['mesh_sha256']
        sources[part['mesh']] = sha(path)
        if path.suffix.lower() == '.ply':
            bpy.ops.wm.ply_import(filepath=str(path), merge_verts=False)
        else:
            bpy.ops.wm.stl_import(filepath=str(path))
        obj = bpy.context.object
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        groups[group_name].objects.link(obj)
        matrix = np.eye(4)
        matrix[:3, :3] = np.array(part['R']) * .001
        matrix[:3, 3] = np.array(part['t_mm']) / 1000 + shift
        obj.matrix_world = Matrix(matrix)
        assign(obj, part)
    else:
        obj = old_objects[name].copy()
        obj.animation_data_clear()
        obj.parent = None
        groups[group_name].objects.link(obj)
        obj.matrix_world = Matrix(old_rows[name]['matrix_m'])
    obj.name = 'R24_' + name
    for key, value in {'part_id': name, 'link_frame': part['link_frame'], 'source_mesh': part['mesh'],
                       'source_mesh_sha256': part['mesh_sha256'], 'physical_approved': False,
                       'r24_domain': domain or 'retained_R22',
                       'component_kind': part.get('kind', 'retained'),
                       'geometry_reference_only': part.get('reference_only', False),
                       'kinematics_mode': part.get('kinematics_mode', 'rigid_HOME'),
                       'description': part.get('notes', '')}.items():
        obj[key] = value
    obj.hide_viewport = False
    obj.hide_render = not part.get('visible_default', True)
    obj.hide_set(not part.get('visible_default', True))
    objects[name] = obj
    vertices = np.empty(len(obj.data.vertices) * 3, np.float32)
    obj.data.vertices.foreach_get('co', vertices)
    records.append(dict(part_id=name, object=obj.name, vertices=len(obj.data.vertices),
                        vertex_sha256=hashlib.sha256(vertices.tobytes()).hexdigest(),
                        matrix_m=np.array(obj.matrix_world).tolist(), visible_default=part.get('visible_default', True)))

center = fit_camera(main, [objects[p['name']] for p in selection['items'] if p.get('visible_default', True)], (.9, -1, .4))
details = []
detail_specs = [('02_R24_头部摄像头前盖', lambda p: p['link_frame'] in ('jaw_soft', 'mouth_link'), (1, -.55, .25))]

for title, predicate, direction in detail_specs:
    chosen = [p for p in selection['items'] if predicate(p) and p.get('visible_default', True)]
    if not chosen:
        continue
    s = scene(title)
    groups_detail, shown = {}, []
    for part in chosen:
        label = part.get('r24_domain', part.get('r22_domain', 'reference'))
        if label not in groups_detail:
            groups_detail[label] = collection(s, label)
        obj = objects[part['name']].copy()
        obj.parent = None
        groups_detail[label].objects.link(obj)
        obj.matrix_world = objects[part['name']].matrix_world.copy()
        obj.hide_viewport = obj.hide_render = False
        obj.hide_set(False)
        shown.append(obj)
    fit_camera(s, shown, direction)
    details.append(s)

service_collection = collection(main, '服务通道与自由态参考_默认隐藏_不重复装机')
service_records = []
bpy.context.window.scene = main
for part in selection['service_items']:
    path = ROOT / part['mesh']
    expected = part.get('mesh_sha256', part.get('sha256_STL'))
    assert sha(path) == expected
    sources[part['mesh']] = expected
    if path.suffix.lower() == '.ply':
        bpy.ops.wm.ply_import(filepath=str(path), merge_verts=False)
    else:
        bpy.ops.wm.stl_import(filepath=str(path))
    obj = bpy.context.object
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    service_collection.objects.link(obj)
    matrix = np.eye(4)
    matrix[:3, :3] = np.array(part['R']) * .001
    matrix[:3, 3] = np.array(part['t_mm']) / 1000 + shift
    obj.matrix_world = Matrix(matrix)
    obj.name = 'R24_SERVICE_' + part['name']
    obj['part_id'] = part['name']
    obj['source_mesh'] = part['mesh']
    obj['scope'] = ('Free-state manufacturing reference; installed shape counted separately'
                    if part.get('kind') == 'free_state_manufacturing_reference'
                    else 'Non-installed service or clearance reference; see source contract')
    obj['source_kind'] = part.get('kind', 'non_installed_reference')
    obj['source_notes'] = str(part.get('notes', ''))
    obj.hide_render = True
    obj.hide_set(True)
    vertices = np.empty(len(obj.data.vertices) * 3, np.float32)
    obj.data.vertices.foreach_get('co', vertices)
    service_records.append(dict(part_id=part['name'], object=obj.name, vertices=len(obj.data.vertices),
                                vertex_sha256=hashlib.sha256(vertices.tobytes()).hexdigest(),
                                matrix_m=np.array(obj.matrix_world).tolist()))

for s in old_scenes:
    bpy.data.scenes.remove(s)
for obj in list(bpy.data.objects):
    if not obj.users:
        bpy.data.objects.remove(obj)
bpy.context.window.scene = main
bpy.context.window.view_layer = main.view_layers[0]
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            area.spaces.active.region_3d.view_distance = .9
            area.spaces.active.region_3d.view_location = center
            area.spaces.active.shading.type = 'SOLID'
            area.spaces.active.shading.color_type = 'MATERIAL'
            area.spaces.active.clip_end = 100
text = bpy.data.texts.new('00_R24_查看说明.txt')
text.write('R24 头部摄像头前盖设计。场景01完整装配，场景02头部。Outliner可选择和隐藏部件；摄像头为厂商尺寸包络，并非精确CAD。前盖/眼罩/四个壳体耳座新设计；镜头朝+X。3MF为打印主文件。装配、光学和运动检查的范围及未决事项见R24说明；不代表制造或实物验收通过。\n')
index = dict(status='R24_STATIC_MODEL_BUILT_READBACK_PENDING', main_scene=main.name,
             details=[s.name for s in details], part_count=len(records), main_parts=records,
             native_to_scene_shift_mm=(shift * 1000).tolist(), sources=sources,
             service_count=len(service_records), service_parts=service_records,
             physical_approved=False, manufacturing_approved=False)
(OUT / 'build_index.json').write_text(json.dumps(index, ensure_ascii=False, indent=2) + '\n')
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'Microduck_R24_摄像头前盖.blend'), compress=True)
if not args.no_render:
    for s in [main] + details:
        s.render.filepath = str(OUT / (s.name + '.png'))
        bpy.ops.render.render(write_still=True, scene=s.name)
print('R24_STATIC_MODEL_SAVED', len(records), flush=True)
