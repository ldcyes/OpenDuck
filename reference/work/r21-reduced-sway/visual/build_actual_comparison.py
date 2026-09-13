"""Append only source-bound actual animation; preserve the three frozen R20 scenes."""
from pathlib import Path
import sys,json,hashlib,argparse,math
sys.dont_write_bytecode=True
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from blender_actual_helpers import *
ap=argparse.ArgumentParser();ap.add_argument('--prepared',required=True)
a=ap.parse_args(sys.argv[sys.argv.index('--')+1:])
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
prepared_path=ROOT/a.prepared;d=json.loads(prepared_path.read_text());assert d['status']=='FROZEN_ACTUAL_SOURCES_FOR_VISUALIZATION'
sources=dict(d['sources'])
for p,h in sources.items():assert sha(ROOT/p)==h,p
sources[str(prepared_path.relative_to(ROOT))]=sha(prepared_path)
for script in ['build_actual_comparison.py','blender_actual_helpers.py']:
 p=HERE/script;sources[str(p.relative_to(ROOT))]=sha(p)
out=prepared_path.parent;final=d['purpose']=='FINAL_FOUR_STEP'
static=json.loads((ROOT/d['baseline_static_index']).read_text());anim=json.loads((ROOT/d['baseline_animation_index']).read_text())
sel=json.loads((ROOT/d['selection_path']).read_text());items=sel['items'];joints=sel['joints']
trace=json.loads((ROOT/d['candidate']['trace_path']).read_text());base_trace=json.loads((ROOT/d['baseline']['trace_path']).read_text())
bpy.ops.wm.open_mainfile(filepath=str(ROOT/d['baseline_blend']))
assert len(bpy.data.scenes)==3
old_scenes=list(bpy.data.scenes);static_scene=bpy.data.scenes[static['main_scene']]
# Capture immutable data signatures before adding scenes. Save evaluated pose separately;
# moving the display timeline must never be mistaken for changing a keyframe.
def curves(obj):
 result=[]
 if obj.animation_data and obj.animation_data.action:
  for layer in obj.animation_data.action.layers:
   for strip in layer.strips:
    for slot in obj.animation_data.action.slots:
     bag=strip.channelbag(slot)
     if bag:
      for fc in bag.fcurves:
       result.append([fc.data_path,fc.array_index,[(tuple(k.co),k.interpolation)for k in fc.keyframe_points]])
 return result
mesh_cache={}
def object_signature(obj):
 data=dict(type=obj.type,parent=obj.parent.name if obj.parent else None,parent_inverse=[list(r)for r in obj.matrix_parent_inverse],hide_render=obj.hide_render)
 if obj.type=='MESH':
  if obj.data.name not in mesh_cache:
   arr=np.empty(len(obj.data.vertices)*3,np.float32);obj.data.vertices.foreach_get('co',arr)
   obj.data.calc_loop_triangles();tri=np.array([list(t.vertices)for t in obj.data.loop_triangles],np.int32)
   mesh_cache[obj.data.name]=[sha_bytes(arr.tobytes()),sha_bytes(tri.tobytes())]
  data['mesh']=mesh_cache[obj.data.name]
 if obj.animation_data and obj.animation_data.action:data['animation']=sha_bytes(json.dumps(curves(obj),sort_keys=True).encode())
 else:data['matrix_basis']=[list(r)for r in obj.matrix_basis]
 return data
sha_bytes=lambda b:hashlib.sha256(b).hexdigest()
old_objects={o.name:object_signature(o)for s in old_scenes for o in s.objects}
old_scene_objects={s.name:sorted(o.name for o in s.objects)for s in old_scenes}
def record(avatar,key,scene,source,display_path=None):
 return dict(key=key,scene=scene.name,source=source,display_path=display_path,part_objects={k:o.name for k,o in avatar['parts'].items()},root_object=avatar['root'].name,joint_objects={j['joint']:avatar['rigs'][j['child_link']].name for j in joints},display_offset_object=avatar['offset'].name if 'offset'in avatar else None)
# Locate old complete actual avatar without touching old action data.
baseline_avatar=dict(root=bpy.data.objects[anim['root_object']],rigs={'trunk_base':bpy.data.objects[anim['root_object']]},parts={n:bpy.data.objects[o]for n,o in anim['part_objects'].items()},categories={})
for j in joints:baseline_avatar['rigs'][j['child_link']]=bpy.data.objects[anim['joint_objects'][j['joint']]]
for row in static['main_parts']:
 cat=row['collection'].split('.')[0];obj=baseline_avatar['parts'][row['part_id']]
 if cat not in baseline_avatar['categories']:baseline_avatar['categories'][cat]=next(c for c in obj.users_collection if c.name.startswith('动态_'))
font=next(f for f in bpy.data.fonts if f.packed_file)
annotation_material=bpy.data.materials.new('R21_高对比说明字');annotation_material.diffuse_color=(.012,.018,.025,1);annotation_material.use_nodes=True
nodes=annotation_material.node_tree.nodes;nodes.clear();emission=nodes.new('ShaderNodeEmission');emission.inputs['Color'].default_value=(.012,.018,.025,1);emission.inputs['Strength'].default_value=1
output=nodes.new('ShaderNodeOutputMaterial');annotation_material.node_tree.links.new(emission.outputs[0],output.inputs['Surface'])
def label(scene,body,width=1.4):
 data=bpy.data.curves.new(scene.name+'_说明','FONT');data.font=font;data.size=.018 if width>1 else .014;data.space_line=1.25;data.body=body
 obj=bpy.data.objects.new(scene.name+'_说明',data);scene.collection.objects.link(obj);obj.parent=scene.camera
 frustum=scene.camera.data.view_frame(scene=scene);x_edge=max(abs(v.x)for v in frustum);y_edge=max(abs(v.y)for v in frustum)
 obj.location=(-x_edge+.025,y_edge-.04,-1)
 data.materials.append(annotation_material);return obj.name
r21name='04_R21实际积分_完整四步'if final else'04_R21右步前缀_仅流程测试'
scene=new_scene(r21name,static_scene,trace['samples'][-1]['time_s']);scene.render.resolution_x=900;scene.render.resolution_y=1000;frontal_camera(scene,static_scene,width_m=.9)
avatar=add_actual_avatar(scene,'R21_',items,joints,static['main_parts'],trace['samples'],np.array(static['native_to_scene_shift_mm'])/1000,d['candidate'])
full_label=label(scene,('R21 实际自由积分 · 完整四步'if final else'R21 右步前缀 · 仅动画流程测试')+'\n557 件原 CAD；实物未验收',.78)
records=[record(avatar,'candidate_full',scene,d['candidate'])];scene_records=[dict(scene=scene.name,mode='candidate_actual',label_object=full_label,clocks={},duration_s=trace['samples'][-1]['time_s'])]
common=new_scene('05_R20与R21_同实际时间',static_scene,d['common_time_duration_s']);frontal_camera(common,static_scene,width_m=1.4)
# For this fixed camera, screen right is world +Y. Labels and offsets must agree.
ba=clone_avatar(common,'同时间_R20_',baseline_avatar,-.32);ca=clone_avatar(common,'同时间_R21_',avatar,.32)
records += [record(ba,'same_time_baseline',common,d['baseline']),record(ca,'same_time_candidate',common,d['candidate'])]
clocks={}
for k,av,tr in [('R20',ba,base_trace),('R21',ca,trace)]:
 ts=[0.,d['common_time_duration_s']];clocks[k]=add_clock(common,'同时间_'+k,ts,ts).name
body='R20（左）与 R21（右） · 相同实际时间 / 相同比例\n'+('完整原始摆幅指标独立计算'if final else'仅右步前缀流程测试；不代表完整减摆率')+'\n实际积分；实物未验收'
scene_records.append(dict(scene=common.name,mode='same_actual_time',label_object=label(common,body),clocks=clocks,duration_s=d['common_time_duration_s']))
if final:
 phase_data=json.loads((ROOT/d['phase_display_path']).read_text());phase=new_scene('06_R20与R21_相同步态阶段',static_scene,base_trace['samples'][-1]['time_s']);frontal_camera(phase,static_scene,width_m=1.4)
 pb=clone_avatar(phase,'同阶段_R20_',baseline_avatar,-.32)
 pc=add_actual_avatar(phase,'同阶段_R21_',items,joints,static['main_parts'],phase_data['samples'],np.array(static['native_to_scene_shift_mm'])/1000,d['candidate'],phase_data['display_times_s'])
 offset=bpy.data.objects.new('同阶段_R21_仅画面横移',None);pc['controls'].objects.link(offset);offset.location=(0,.32,0);offset['display_offset_only']=True;offset['excluded_from_sway_metrics']=True;pc['root'].parent=offset;pc['offset']=offset
 records += [record(pb,'same_phase_baseline',phase,d['baseline']),record(pc,'same_phase_candidate',phase,d['candidate'],d['phase_display_path'])]
 c20=add_clock(phase,'同阶段_R20',[0.,base_trace['samples'][-1]['time_s']],[0.,base_trace['samples'][-1]['time_s']])
 c21=add_clock(phase,'同阶段_R21',[s['time_s']for s in phase_data['samples']],phase_data['display_times_s'])
 body='R20（左）与 R21（右） · 相同步态阶段 / 相同比例\n两侧实际时钟不同；阶段间仅显示映射\n实际积分；实物未验收'
 scene_records.append(dict(scene=phase.name,mode='same_phase',label_object=label(phase,body),clocks={'R20':c20.name,'R21':c21.name},duration_s=base_trace['samples'][-1]['time_s']))
for row in scene_records:
 s=bpy.data.scenes[row['scene']];s['R21_purpose']=d['purpose'];s['selection_sha256']=d['selection_sha256'];s['metrics_scope']=d['metrics_scope'];s['no_camera_compensation']=True;s.frame_set(1)
for name,snapshot in old_objects.items():assert object_signature(bpy.data.objects[name])==snapshot,(name,'OLD_OBJECT_CHANGED')
for name,names in old_scene_objects.items():assert sorted(o.name for o in bpy.data.scenes[name].objects)==names,(name,'OLD_SCENE_MEMBERS_CHANGED')
result=dict(status='SOURCE_BOUND_BUILD_READBACK_PENDING',purpose=d['purpose'],prepared_path=str(prepared_path.relative_to(ROOT)),prepared_sha256=sha(prepared_path),old_scene_objects=old_scene_objects,old_object_signatures=old_objects,avatars=records,scenes=scene_records,part_count=557,source_saved_samples=len(trace['samples']),phase_saved_sample_inclusion='All candidate source times retained; exact phase knots may add display-only samples',sources=sources,physical_approved=False,manufacturing_approved=False)
name='Microduck_R21_实际减摆对照.blend'if final else'Microduck_R21_PREFIX_HELPER_TEST.blend';blend=out/name
result['blend_path']=str(blend.relative_to(ROOT))
(out/'build_index.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
text=bpy.data.texts.new('R21_查看说明.txt');text.write('R20 原三场景保持；R21 为真实自由根积分记录。场景05比较相同实际时间，场景06仅匹配明确步态阶段并保留各自真实时钟。横移仅用于并排显示，原物理坐标/完整摆幅指标不受影响。全部保存实际采样保留关键帧；显示插值不是新仿真，不增加碰撞证明。\n'+d['metrics_scope']+'\n'+json.dumps(d['full_trace_sway_comparison'],ensure_ascii=False))
bpy.context.window.scene=static_scene;bpy.context.window.view_layer=static_scene.view_layers[0];bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(blend),compress=True)
print('R21_BUILD_SAVED',str(blend),len(bpy.data.scenes),len(records),flush=True)
