"""Repair only phase-view controls from raw-source-preserving display inputs."""
from pathlib import Path
import sys,json,hashlib,math
sys.dont_write_bytecode=True
import bpy,numpy as np
from mathutils import Matrix
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent;OUT=HERE/'release_v3';DIAG=OUT/'diagnostic_key_insertion'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
old=json.loads((DIAG/'FAILED_build_index.json').read_text());prepared=json.loads((OUT/'prepared_visual_inputs.json').read_text());display=json.loads((ROOT/prepared['phase_display_path']).read_text());samples=display['samples'];frames=np.float32(1+40*np.array(display['display_times_s']));assert np.all(np.diff(frames)>.01)
for p,h in prepared['sources'].items():assert sha(ROOT/p)==h,p
sel=json.loads((ROOT/prepared['selection_path']).read_text());joints=sel['joints'];raw=json.loads((ROOT/prepared['candidate']['trace_path']).read_text());assert len(raw['samples'])==9774
assert np.isin([s['time_s']for s in raw['samples']],[s['time_s']for s in samples]).all()
bpy.ops.wm.open_mainfile(filepath=str(DIAG/'FAILED_Microduck_R21_实际减摆对照.blend'))
avatar=next(a for a in old['avatars']if a['key']=='same_phase_candidate');scene=bpy.data.scenes[avatar['scene']];bpy.context.window.scene=scene;bpy.context.window.view_layer=scene.view_layers[0]
changed=[]
def bag_curves(obj):
 action=obj.animation_data.action
 return [fc for layer in action.layers for strip in layer.strips for slot in action.slots for fc in strip.channelbag(slot).fcurves]
def assign(obj,channels):
 obj.animation_data_clear()
 for path in channels:obj.keyframe_insert(data_path=path,frame=float(frames[0]))
 for fc in bag_curves(obj):
  values=channels[fc.data_path][:,fc.array_index];co=np.column_stack([frames,values]).astype(np.float32)
  assert len(fc.keyframe_points)==1
  fc.keyframe_points.add(len(co)-1);fc.keyframe_points.foreach_set('co',co.ravel())
  for point in fc.keyframe_points:point.interpolation='LINEAR'
  fc.update()
  actual=np.empty(co.size,np.float32);fc.keyframe_points.foreach_get('co',actual)
  assert len(fc.keyframe_points)==len(co) and np.array_equal(actual.reshape(-1,2),co),(obj.name,fc.data_path,fc.array_index,'STANDARD_BULK_UPDATE_CHANGED_KEYS')
 obj.update_tag();changed.append(obj.name)
root=bpy.data.objects[avatar['root_object']];quats=[];prev=None
for s in samples:
 q=Matrix(s['base_transform_m']).to_quaternion()
 if prev is not None and q.dot(prev)<0:q.negate()
 quats.append(list(q));prev=q.copy()
assign(root,dict(location=np.array([np.array(s['base_transform_m'])[:3,3]for s in samples]),rotation_quaternion=np.array(quats)))
for j in joints:
 axis=np.array(j['axis_trunk']);axis/=np.linalg.norm(axis)
 values=np.column_stack([np.radians([s['q_HOME_delta_deg'][j['joint']]for s in samples]),np.repeat(axis[None,:],len(samples),axis=0)])
 assign(bpy.data.objects[avatar['joint_objects'][j['joint']]],dict(rotation_axis_angle=values))
scene_row=next(s for s in old['scenes']if s['mode']=='same_phase');clock=bpy.data.objects[scene_row['clocks']['R21']]
assign(clock,{'["actual_time_s"]':np.array([s['time_s']for s in samples])[:,None]})
sources=dict(prepared['sources']);sources[str((OUT/'prepared_visual_inputs.json').relative_to(ROOT))]=sha(OUT/'prepared_visual_inputs.json')
for name in ['build_actual_comparison.py','blender_actual_helpers.py','repair_phase_view_curves.py']:
 p=HERE/name;sources[str(p.relative_to(ROOT))]=sha(p)
old.update(status='SOURCE_BOUND_BUILD_READBACK_PENDING_AFTER_STANDARD_PHASE_CURVE_REPAIR',prepared_sha256=sha(OUT/'prepared_visual_inputs.json'),sources=sources,phase_curve_repair=dict(changed_control_objects=changed,display_samples=len(samples),original_actual_samples=9774,phase_knot_key_resolution=display['phase_knot_key_resolution'],API='Standard foreach_set of chronological LINEAR keys followed by FCurve.update and exact stored-key comparison',failed_snapshot_classification='diagnostic_key_insertion/ is failed history, not accepted verification'))
(OUT/'build_index.json').write_text(json.dumps(old,ensure_ascii=False,indent=2)+'\n')
note=bpy.data.texts.new('R21_相位显示边界精度.txt');note.write('全部 9774 个原始实际采样保留。额外显示阶段界若距原采样不超过 0.011 帧，不再插入，以避免 Blender 近邻合并覆盖原始采样。真实阶段 JSON 和完整物理幅值不变。\n'+json.dumps(display['phase_knot_key_resolution'],ensure_ascii=False,indent=2))
static=json.loads((ROOT/prepared['baseline_static_index']).read_text());bpy.context.window.scene=bpy.data.scenes[static['main_scene']];bpy.context.window.view_layer=bpy.context.window.scene.view_layers[0];bpy.context.window.scene.frame_set(1);bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Microduck_R21_实际减摆对照.blend'),compress=True);print('PHASE_VIEW_ONLY_REPAIRED_STANDARD_FCURVE_UPDATE',len(changed),len(samples),flush=True)
