"""Render fixed-world views from an audited actual-only Blender file; never save edits."""
from pathlib import Path
import sys,json,hashlib,argparse,math,time
sys.dont_write_bytecode=True
import bpy,numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[3]
ap=argparse.ArgumentParser();ap.add_argument('--index',required=True);ap.add_argument('--mode',choices=['probe','video'],default='probe');ap.add_argument('--scene-mode',choices=['candidate_actual','same_actual_time','same_phase'],default='same_actual_time');ap.add_argument('--source-interval',type=float,default=1.);a=ap.parse_args(sys.argv[sys.argv.index('--')+1:])
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();ip=ROOT/a.index;idx=json.loads(ip.read_text());out=ip.parent;prepared=json.loads((ROOT/idx['prepared_path']).read_text());audit=json.loads((out/'readback.json').read_text());assert audit['passed'];blend=ROOT/idx['blend_path'];assert sha(blend)==audit['source_blend_sha256']
assert a.mode!='video'or idx['purpose']=='FINAL_FOUR_STEP','Prefix may only render diagnostic stills'
row=next(r for r in idx['scenes']if r['mode']==a.scene_mode);bpy.ops.wm.open_mainfile(filepath=str(blend));scene=bpy.data.scenes[row['scene']];bpy.context.window.scene=scene;bpy.context.window.view_layer=scene.view_layers[0]
source_aspect=scene.render.resolution_y/scene.render.resolution_x
scene.cycles.samples=3;scene.render.resolution_x=1200 if a.scene_mode!='candidate_actual'else 900
# Preserve the source-build aspect ratio so a different output resolution cannot
# change projection scale or label extent.
scene.render.resolution_y=round(scene.render.resolution_x*source_aspect)
label=bpy.data.objects[row['label_object']];initial_body=label.data.body
if prepared['purpose']=='FINAL_FOUR_STEP' and a.scene_mode=='same_phase':
 initial_body='R20（左）与 R21（右） · 对齐参考步态阶段 / 相同比例\n两侧实际时钟不同；未按真实接触事件对齐\n实际积分；实物未验收'
elif prepared['purpose']=='FINAL_FOUR_STEP' and a.scene_mode=='same_actual_time':
 initial_body=f"R20（左）与 R21（右） · 相同实际时间 / 相同比例\n共同时间段 0–{row['duration_s']:.2f} s；R21 全程 {prepared['metrics']['candidate']['duration_s']:.2f} s\n实际积分；实物未验收"
frames=out/(a.scene_mode+'_'+a.mode+'_frames');frames.mkdir(exist_ok=True)
if a.mode=='probe':times=sorted(set([0.,row['duration_s']*.6,row['duration_s']]))
else:times=np.arange(0,row['duration_s'],a.source_interval).tolist()+[row['duration_s']]
records=[]
for i,t in enumerate(times):
 f=1+40*t;scene.frame_set(math.floor(f),subframe=f%1);deps=bpy.context.evaluated_depsgraph_get();deps.update()
 clock_values={name:float(bpy.data.objects[obj].evaluated_get(deps)['actual_time_s'])for name,obj in row['clocks'].items()}
 time_label=' / '.join(f'{name} = {value:.2f} s'for name,value in clock_values.items())if clock_values else f'实际时间 = {t:.2f} s'
 body=initial_body+'\n'+time_label
 if a.mode=='video':
  body+=f' · R20 时钟约 {a.source_interval*12:g} 倍速，R21 按阶段变速'if a.scene_mode=='same_phase'else f' · 预览约 {a.source_interval*12:g} 倍速' 
 if prepared['purpose']=='FINAL_FOUR_STEP':
  bm=prepared['metrics']['baseline']['metrics'];cm=prepared['metrics']['candidate']['metrics']
  roll_reduction=100*(1-cm['trunk_roll_deg']['peak_to_peak']/bm['trunk_roll_deg']['peak_to_peak']);head_reduction=100*(1-cm['head_marker_world_Y_mm']['peak_to_peak']/bm['head_marker_world_Y_mm']['peak_to_peak'])
  body+=f'\n完整实际侧倾峰峰：{bm["trunk_roll_deg"]["peak_to_peak"]:.2f}° → {cm["trunk_roll_deg"]["peak_to_peak"]:.2f}°，减少 {roll_reduction:.1f}%'
  body+=f'\n上头壳固定点横摆：{bm["head_marker_world_Y_mm"]["peak_to_peak"]:.1f} → {cm["head_marker_world_Y_mm"]["peak_to_peak"]:.1f} mm，减少 {head_reduction:.1f}%'
  body+=f'\n侧倾 40% 目标：{"达到"if roll_reduction>=40 else"未达到"}；头部 30% 目标：{"达到"if head_reduction>=30 else"未达到"}'
 label.data.body=body;label.data.size=.022 if a.scene_mode!='candidate_actual'else .011
 deps.update();cam_eval=scene.camera.evaluated_get(deps);text_eval=label.evaluated_get(deps);to_camera=cam_eval.matrix_world.inverted()@text_eval.matrix_world
 text_corners=np.array([list(to_camera@Vector(v))for v in text_eval.bound_box]);frustum=scene.camera.data.view_frame(scene=scene);x_edge=max(abs(v.x)for v in frustum);y_edge=max(abs(v.y)for v in frustum)
 assert np.max(abs(text_corners[:,0]))<x_edge and np.max(abs(text_corners[:,1]))<y_edge,'RENDER_TEXT_OUTSIDE_FRUSTUM'
 # Last metrics line sits above the head for both full and comparison views.
 scene.render.filepath=str(frames/f'{i:04d}.png');start=time.time();bpy.ops.render.render(write_still=True,scene=scene.name)
 records.append(dict(index=i,display_time_s=t,actual_clocks_s=clock_values,source_frame_float=f,PNG=str(Path(scene.render.filepath).relative_to(ROOT)),PNG_sha256=sha(scene.render.filepath),render_seconds=time.time()-start))
 print('RENDERED',a.scene_mode,i,t,flush=True)
report=dict(status='RENDERED_SOURCE_BOUND_ACTUAL_DISPLAY',purpose=idx['purpose'],scene_mode=a.scene_mode,source_blend_path=idx['blend_path'],source_blend_sha256=sha(blend),fixed_camera_world_matrix=[list(r)for r in cam_eval.matrix_world],orthographic_scale_m=scene.camera.data.ortho_scale,projected_horizontal_span_m=2*x_edge,projected_vertical_span_m=2*y_edge,all_rendered_text_inside_frustum=True,frames=records,video_fps=12 if a.mode=='video'else None,nominal_display_interval_s=a.source_interval if a.mode=='video'else None,nominal_display_speedup=a.source_interval*12 if a.mode=='video'else None,last_interval_shortened=True if a.mode=='video'else None,physical_approved=False,sources={str(ip.relative_to(ROOT)):sha(ip),str((out/'readback.json').relative_to(ROOT)):sha(out/'readback.json'),str(Path(__file__).relative_to(ROOT)):sha(__file__)})
(out/(a.scene_mode+'_'+a.mode+'_render_index.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
