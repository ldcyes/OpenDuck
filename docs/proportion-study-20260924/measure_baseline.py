"""Read-only R25 geometry audit. No manufacturing geometry is modified."""
from pathlib import Path
import hashlib
import json
import sys

import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'work/r11-integration/loads'))
from kinematics import Kinematics

sources = {}
def read(path):
    raw = (ROOT / path).read_bytes()
    sources[path] = hashlib.sha256(raw).hexdigest()
    return json.loads(raw)

selection = read('work/r25-bottom-head-entry/assembly_selection.json')
index = read('work/r25-bottom-head-entry/visual/build_index.json')
check = read('work/r25-bottom-head-entry/visual/readback.json')
stance = read('work/r21-reduced-sway/gait/support_pair_v4.json')['stance']
blend = ROOT / 'work/r25-bottom-head-entry/visual/OpenDuck_R25_底部走线.blend'
assert hashlib.sha256(blend.read_bytes()).hexdigest() == check['blend_sha256']
sources[str(blend.relative_to(ROOT))] = check['blend_sha256']
sources[str(Path(__file__).relative_to(ROOT))] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(blend))
scene = bpy.data.scenes[index['main_scene']]
bpy.context.window.scene = scene
parts = {p['name']: p for p in selection['items']}
assert len(parts) == len(index['main_parts'])
shift = np.array(index['native_to_scene_shift_mm'])
model = Kinematics(selection)
q = np.deg2rad([stance['initial_q_HOME_delta_deg'][n] for n in model.names])
T, pivots, axes = model.forward(q)
base = np.array(stance['initial_base_transform_m'])
assert np.allclose(base[:3, :3], np.eye(3))
rows = []
all_home, all_stance = [], []
shown = []
for entry in index['main_parts']:
    p = parts[entry['part_id']]
    obj = scene.objects[entry['object']]
    if not entry['visible_default']:
        continue
    shown.append(obj)
    local = np.empty(len(obj.data.vertices) * 3, dtype=np.float64)
    obj.data.vertices.foreach_get('co', local)
    M = np.array(obj.matrix_world)
    home = (local.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]) * 1000 - shift
    H = T.get(p['link_frame'], np.eye(4))
    posed = home @ H[:3, :3].T + H[:3, 3] * 1000
    posed = posed @ base[:3, :3].T + base[:3, 3] * 1000
    # Neck has zero delta in this stance; deformable HOME wires are valid only here.
    if p['link_frame'] == 'MULTI_LINK_FLEX_HARNESS':
        assert all(abs(stance['initial_q_HOME_delta_deg'][n]) < 1e-12
                   for n in ['neck_pitch','head_pitch','head_yaw','head_roll'])
    hb = np.array([home.min(0), home.max(0)])
    sb = np.array([posed.min(0), posed.max(0)])
    all_home.extend(hb)
    all_stance.extend(sb)
    rows.append(dict(name=p['name'], link=p['link_frame'], kind=p.get('kind'),
                     home_bounds_mm=hb.tolist(), stance_bounds_mm=sb.tolist()))

joint_map = {j['joint']: np.array(j['pivot_trunk_mm']) for j in selection['joints']}
lengths = {}
for side in ['left', 'right']:
    points = [joint_map[side + '_' + name] for name in ['hip_pitch','knee','ankle']]
    upper, lower = [float(np.linalg.norm(b-a)) for a,b in zip(points,points[1:])]
    lengths[side] = dict(upper_axis_distance_mm=upper, lower_axis_distance_mm=lower,
                         sum_axis_distances_mm=upper+lower,
                         home_hip_to_ankle_vertical_mm=float(points[0][2]-points[2][2]),
                         home_pivots_mm=[p.tolist() for p in points])

home = np.array(all_home)
posed = np.array(all_stance)
report = dict(status='READ_ONLY_BASELINE_MEASUREMENT_NOT_NEW_DESIGN', physical_approved=False,
              visible_parts=len(rows), sources=sources,
              HOME_bounds_mm=[home.min(0).tolist(), home.max(0).tolist()],
              HOME_height_mm=float(np.ptp(home[:,2])),
              R21_preparation_pose_on_R25_bounds_mm=[posed.min(0).tolist(), posed.max(0).tolist()],
              R21_preparation_pose_on_R25_height_mm=float(np.ptp(posed[:,2])),
              lengths=lengths, parts=rows,
              limits=['R21 pose applied kinematically to R25; not a new collision or balance result.',
                      'Axis distances include lateral offsets and are not equal to visible leg length.',
                      'HOME is the saved assembly pose, not a released walking stance.'])
(OUT/'baseline_measurements.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')

# Orthographic review views preserve every part and the saved HOME pose.
scene.render.engine = 'CYCLES'
scene.cycles.samples = 8
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 4
scene.render.threads_mode = 'FIXED'
scene.render.threads = 4
scene.render.resolution_x = 800
scene.render.resolution_y = 1000
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
points = np.array(all_home) / 1000 + shift / 1000
center = Vector((points.min(0)+points.max(0))/2)
scene.camera.data.type = 'ORTHO'
for name, direction in [('front', (1,0,0)), ('side', (0,-1,0))]:
    direction = Vector(direction)
    rotation = (-direction).to_track_quat('-Z','Y')
    projected = (points - np.array(center)) @ np.array(rotation.to_matrix())
    scene.camera.data.ortho_scale = 1
    frame = np.array([list(p) for p in scene.camera.data.view_frame(scene=scene)])
    span = np.ptp(projected, axis=0)
    unit_span = np.ptp(frame, axis=0)
    scene.camera.data.ortho_scale = float(max(span[0]/unit_span[0], span[1]/unit_span[1])*1.14)
    scene.camera.location = center + direction * 2
    scene.camera.rotation_euler = rotation.to_euler()
    scene.render.filepath = str(OUT/f'baseline-{name}.png')
    bpy.ops.render.render(write_still=True)
print(json.dumps({k:v for k,v in report.items() if k not in ['parts','sources']},ensure_ascii=False))
