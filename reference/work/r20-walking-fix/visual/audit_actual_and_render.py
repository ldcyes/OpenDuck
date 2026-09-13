"""Reopen final file; source, exact mesh and all stored animation key checks, independent FK."""
from pathlib import Path
import bpy,numpy as np,json,sys,hashlib,math,argparse,time
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'work/r18-leg-hip-covers/review'));from motion_core import transforms
ap=argparse.ArgumentParser();ap.add_argument('--render',choices=['probe','all']);a=ap.parse_args(sys.argv[sys.argv.index('--')+1:]if'--'in sys.argv else[])
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();static=json.loads((OUT/'static_build_index.json').read_text());idx=json.loads((OUT/'animation_build_index.json').read_text());sel=json.loads((ROOT/idx['source_selection']).read_text());assert sha(ROOT/idx['source_selection'])==idx['source_selection_sha256'];items=sel['items'];joints=sel['joints'];rows={p['part_id']:p for p in static['main_parts']};trace=json.loads((ROOT/idx['source_path']).read_text());samples=trace['samples'];shift=np.eye(4);shift[:3,3]=-np.array(static['native_to_scene_shift_mm'])/1000
for p,h in idx['sources'].items():assert sha(ROOT/p)==h,(p,'changed')
blend=OUT/'Microduck_R20_修订与实际行走.blend';bpy.ops.wm.open_mainfile(filepath=str(blend));assert len(bpy.data.scenes)==3
scene=bpy.data.scenes[idx['scene']];bpy.context.window.scene=scene;bpy.context.window.view_layer=scene.view_layers[0];obs={n:bpy.data.objects[k]for n,k in idx['part_objects'].items()};assert len(obs)==557
checks=[]
def sig(o):
 v=np.empty(len(o.data.vertices)*3,np.float32);o.data.vertices.foreach_get('co',v);o.data.calc_loop_triangles();tri=np.array([list(t.vertices)for t in o.data.loop_triangles],np.int32);return hashlib.sha256(v.tobytes()).hexdigest(),hashlib.sha256(tri.tobytes()).hexdigest()
for p in items:
 n=p['name'];o=obs[n];assert sig(o)==(rows[n]['vertex_sha256'],rows[n]['triangle_sha256']),(n,'GEOMETRY_CHANGED');assert o['source_mesh_sha256']==p['mesh_sha256'];assert o.hide_render==(not p.get('visible_default',True));assert o.hide_get(view_layer=scene.view_layers[0])==(not p.get('visible_default',True))
for k in idx['source_keyframe_checks']:
 s=samples[k['source_index']];f=1+40*s['time_s'];scene.frame_set(math.floor(f),subframe=f%1);bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get();deps.update();tr=transforms(joints,s['q_HOME_delta_deg']);baseT=np.array(s['base_transform_m']);err=0
 for p in items:
  n=p['name'];owner=p['link_frame'];owner='trunk_base'if owner=='MULTI_LINK_FLEX_HARNESS'else owner;tm=tr[owner].copy();tm[:3,3]/=1000;expected=baseT@tm@shift@np.array(rows[n]['expected_matrix_m']);err=max(err,float(np.max(abs(np.array(obs[n].evaluated_get(deps).matrix_world)-expected))))
 assert err<1e-5,(s['time_s'],err);checks.append(dict(time_s=s['time_s'],part_count=557,max_world_matrix_abs_error=err))
def curves(o):
 out={}
 for layer in o.animation_data.action.layers:
  for strip in layer.strips:
   for slot in o.animation_data.action.slots:
    bag=strip.channelbag(slot)
    if bag:
     for fc in bag.fcurves:
      assert all(k.interpolation=='LINEAR'for k in fc.keyframe_points);out[(fc.data_path,fc.array_index)]=np.array([k.co[:]for k in fc.keyframe_points])
 return out
frames=np.array([1+40*s['time_s']for s in samples]);base=bpy.data.objects[idx['root_object']];rootcurves=curves(base);expectedposition=np.array([np.array(s['base_transform_m'])[:3,3]for s in samples]);keychecks=[]
from mathutils import Matrix
quats=[];prev=None
for s in samples:
 q=Matrix(s['base_transform_m']).to_quaternion()
 if prev is not None and q.dot(prev)<0:q.negate()
 quats.append(list(q));prev=q.copy()
for name,values in [('location',expectedposition),('rotation_quaternion',np.array(quats))]:
 for j in range(values.shape[1]):
  ks=rootcurves[(name,j)];assert len(ks)==len(samples);fe=float(abs(ks[:,0]-frames).max());ve=float(abs(ks[:,1]-values[:,j]).max());assert fe<.001 and ve<1e-6;keychecks.append(dict(object=base.name,path=name,index=j,count=len(ks),max_frame_error=fe,max_value_error=ve))
for j in joints:
 o=bpy.data.objects[idx['joint_objects'][j['joint']]];fc=curves(o);axis=np.array(j['axis_trunk']);axis/=np.linalg.norm(axis);values=np.column_stack([np.radians([s['q_HOME_delta_deg'][j['joint']]for s in samples]),np.repeat(axis[None,:],len(samples),axis=0)])
 for k in range(4):
  ks=fc[('rotation_axis_angle',k)];assert len(ks)==len(samples);fe=float(abs(ks[:,0]-frames).max());ve=float(abs(ks[:,1]-values[:,k]).max());assert fe<.001 and ve<1e-6;keychecks.append(dict(object=o.name,path='rotation_axis_angle',index=k,count=len(ks),max_frame_error=fe,max_value_error=ve))
# Both static scenes stay static and preserve stored source geometry and display transforms.
staticchecks=[]
ss=bpy.data.scenes[static['main_scene']];bpy.context.window.scene=ss;bpy.context.window.view_layer=ss.view_layers[0];ss.frame_set(1);deps=bpy.context.evaluated_depsgraph_get();deps.update()
for row in static['main_parts']:
 o=bpy.data.objects[row['object']];assert o.animation_data is None and o.parent is None;assert sig(o)==(row['vertex_sha256'],row['triangle_sha256']);err=float(abs(np.array(o.evaluated_get(deps).matrix_world)-np.array(row['expected_matrix_m'])).max());assert err<1e-6;staticchecks.append(err)
cs=bpy.data.scenes[static['comparison_scene']];bpy.context.window.scene=cs;bpy.context.window.view_layer=cs.view_layers[0];deps=bpy.context.evaluated_depsgraph_get();deps.update()
for row in static['comparison_parts']:
 o=bpy.data.objects[row['object']];assert o.animation_data is None;err=float(abs(np.array(o.evaluated_get(deps).matrix_world)-np.array(row['expected_matrix_m'])).max());assert err<1e-6
out=dict(passed=True,status='PASS_THREE_SCENES_557_EXACT_MESH_ALL_SAVED_KEYS_AND_FK',blend_sha256=sha(blend),static_parts_verified=len(staticchecks),comparison_parts_verified=len(static['comparison_parts']),dynamic_parts_verified=len(obs),all_saved_key_checks=keychecks,all_saved_source_samples=len(samples),independent_FK_pose_checks=checks,sources=idx['sources'],physical_approved=False,manufacturing_approved=False)
(OUT/'animation_readback_final.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print('FINAL_READBACK_PASS',len(obs),len(keychecks),len(samples),flush=True)
if not a.render:raise SystemExit()
bpy.ops.wm.open_mainfile(filepath=str(blend));scene=bpy.data.scenes[idx['scene']];bpy.context.window.scene=scene;bpy.context.window.view_layer=scene.view_layers[0];scene.cycles.samples=3;scene.render.resolution_x=640;scene.render.resolution_y=640;outdir=OUT/'actual_frames';outdir.mkdir(exist_ok=True)
# 1 s source intervals at 12 fps => approximately 12x playback, explicitly labelled.
times=np.arange(0,idx['source_duration_s'],1.).tolist()+[idx['source_duration_s']]
if a.render=='probe':times=[0.,idx['source_duration_s']/2,idx['source_duration_s']]
renders=[]
for i,t in enumerate(times):
 f=1+40*t;scene.frame_set(math.floor(f),subframe=f%1);bpy.context.view_layer.update();label=bpy.data.objects[idx['label_object']];label.data.body=idx['render_label']+'\n'+f"t = {t:.2f} s · 视频约 12 倍速\n实际积分 / 实物未验收";scene.render.filepath=str(outdir/(f'probe_{i:03d}.png'if a.render=='probe'else f'{i:04d}.png'));begin=time.time();bpy.ops.render.render(write_still=True,scene=scene.name);renders.append(dict(time_s=t,PNG=str(Path(scene.render.filepath).relative_to(ROOT)),PNG_sha256=sha(scene.render.filepath),render_seconds=time.time()-begin));print('RENDER_DONE',i,t,round(time.time()-begin,2),flush=True)
(OUT/('probe_render_index.json'if a.render=='probe'else'actual_render_index.json')).write_text(json.dumps(dict(source_blend_sha256=sha(blend),frame_interval_source_s=1,video_fps=12,time_acceleration_nominal=12,last_video_interval_shortened=True,frames=renders,physical_approved=False),ensure_ascii=False,indent=2)+'\n')
