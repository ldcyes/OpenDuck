"""Reopen the saved visualization, verify geometry, every saved key and source FK."""
from pathlib import Path
import sys,json,hashlib,math,argparse
sys.dont_write_bytecode=True
import bpy,numpy as np
from mathutils import Matrix
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'work/r18-leg-hip-covers/review'))
from motion_core import transforms
ap=argparse.ArgumentParser();ap.add_argument('--index',required=True);a=ap.parse_args(sys.argv[sys.argv.index('--')+1:])
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();sha_bytes=lambda b:hashlib.sha256(b).hexdigest()
index_path=ROOT/a.index;idx=json.loads(index_path.read_text());out=index_path.parent
for p,h in idx['sources'].items():assert sha(ROOT/p)==h,p
prepared=json.loads((ROOT/idx['prepared_path']).read_text());assert sha(ROOT/idx['prepared_path'])==idx['prepared_sha256']
static=json.loads((ROOT/prepared['baseline_static_index']).read_text());sel=json.loads((ROOT/prepared['selection_path']).read_text());items=sel['items'];joints=sel['joints'];rows={r['part_id']:r for r in static['main_parts']};shift=np.eye(4);shift[:3,3]=-np.array(static['native_to_scene_shift_mm'])/1000
blend=ROOT/idx['blend_path'];bpy.ops.wm.open_mainfile(filepath=str(blend));assert len(bpy.data.scenes)==(6 if idx['purpose']=='FINAL_FOUR_STEP'else 5)
mesh_cache={};anim_cache={}
def curves(obj,raw=False):
 result=[]
 if obj.animation_data and obj.animation_data.action:
  for layer in obj.animation_data.action.layers:
   for strip in layer.strips:
    for slot in obj.animation_data.action.slots:
     bag=strip.channelbag(slot)
     if bag:
      for fc in bag.fcurves:
       assert all(k.interpolation=='LINEAR'for k in fc.keyframe_points),(obj.name,'NONLINEAR_DISPLAY')
       result.append([fc.data_path,fc.array_index,[(tuple(k.co),k.interpolation)for k in fc.keyframe_points]])
 if raw:return result
 return {(path,i):np.array([co for co,_ in values])for path,i,values in result}
def mesh_sig(obj):
 if obj.data.name not in mesh_cache:
  v=np.empty(len(obj.data.vertices)*3,np.float32);obj.data.vertices.foreach_get('co',v);obj.data.calc_loop_triangles();tri=np.array([list(t.vertices)for t in obj.data.loop_triangles],np.int32)
  mesh_cache[obj.data.name]=[sha_bytes(v.tobytes()),sha_bytes(tri.tobytes())]
 return mesh_cache[obj.data.name]
def object_signature(obj):
 data=dict(type=obj.type,parent=obj.parent.name if obj.parent else None,parent_inverse=[list(r)for r in obj.matrix_parent_inverse],hide_render=obj.hide_render)
 if obj.type=='MESH':data['mesh']=mesh_sig(obj)
 if obj.animation_data and obj.animation_data.action:data['animation']=sha_bytes(json.dumps(curves(obj,True),sort_keys=True).encode())
 else:data['matrix_basis']=[list(r)for r in obj.matrix_basis]
 return data
for name,signature in idx['old_object_signatures'].items():assert object_signature(bpy.data.objects[name])==signature,(name,'OLD_OBJECT_CHANGED')
for name,objects in idx['old_scene_objects'].items():assert sorted(o.name for o in bpy.data.scenes[name].objects)==objects,(name,'OLD_SCENE_CHANGED')
checks=[];all_keys=[];clocks=[]
for avatar in idx['avatars']:
 scene=bpy.data.scenes[avatar['scene']];bpy.context.window.scene=scene;bpy.context.window.view_layer=scene.view_layers[0];scene.frame_set(1)
 current_deps=bpy.context.evaluated_depsgraph_get();current_deps.update()
 raw=json.loads((ROOT/avatar['source']['trace_path']).read_text());assert sha(ROOT/avatar['source']['trace_path'])==avatar['source']['trace_sha256'];samples=raw['samples'];times=[s['time_s']for s in samples]
 if avatar['display_path']:
  display=json.loads((ROOT/avatar['display_path']).read_text());samples=display['samples'];times=display['display_times_s']
  actual_saved=np.array([s['time_s']for s in raw['samples']]);display_actual=np.array([s['time_s']for s in samples]);assert np.isin(actual_saved,display_actual).all(),'SAVED_SAMPLE_DROPPED'
 frames=1+40*np.array(times);root=bpy.data.objects[avatar['root_object']];partobjs={k:bpy.data.objects[n]for k,n in avatar['part_objects'].items()};assert len(partobjs)==557
 for item in items:
  obj=partobjs[item['name']];row=rows[item['name']];assert mesh_sig(obj)==[row['vertex_sha256'],row['triangle_sha256']],item['name']
  assert obj['source_mesh_sha256']==item['mesh_sha256'];assert obj.hide_render==(not item.get('visible_default',True));assert obj.hide_get(view_layer=scene.view_layers[0])==(not item.get('visible_default',True))
 offset=np.eye(4)
 if avatar['display_offset_object']:
  ob=bpy.data.objects[avatar['display_offset_object']];offset=np.array(ob.evaluated_get(current_deps).matrix_world);assert ob['display_offset_only']and ob['excluded_from_sway_metrics'];assert np.max(abs(offset[:3,:3]-np.eye(3)))<1e-9;assert offset[0,3]==offset[2,3]==0
  screen_right=np.array(scene.camera.evaluated_get(current_deps).matrix_world)[:3,0]
  projected_offset=float(screen_right@offset[:3,3]);assert (projected_offset<0)if avatar['key'].endswith('baseline')else(projected_offset>0),(avatar['key'],'LEFT_RIGHT_LABEL_MISMATCH')
 positions=np.array([np.array(s['base_transform_m'])[:3,3]for s in samples]);quats=[];prev=None
 for s in samples:
  q=Matrix(s['base_transform_m']).to_quaternion()
  if prev is not None and q.dot(prev)<0:q.negate()
  quats.append(list(q));prev=q.copy()
 rootcurves=curves(root);this_keys=[]
 def verify_keys(obj,path,values):
  fc=curves(obj)
  for channel in range(values.shape[1]):
   ks=fc[(path,channel)];assert len(ks)==len(samples),(avatar['key'],obj.name,'KEY_COUNT')
   fe=float(abs(ks[:,0]-frames).max());ve=float(abs(ks[:,1]-values[:,channel]).max());assert fe<.001 and ve<1e-6,(avatar['key'],obj.name,fe,ve)
   this_keys.append(dict(object=obj.name,path=path,index=channel,count=len(ks),max_frame_error=fe,max_value_error=ve))
 verify_keys(root,'location',positions);verify_keys(root,'rotation_quaternion',np.array(quats))
 for j in joints:
  ob=bpy.data.objects[avatar['joint_objects'][j['joint']]];axis=np.array(j['axis_trunk']);axis/=np.linalg.norm(axis)
  values=np.column_stack([np.radians([s['q_HOME_delta_deg'][j['joint']]for s in samples]),np.repeat(axis[None,:],len(samples),axis=0)])
  verify_keys(ob,'rotation_axis_angle',values)
 all_keys.append(dict(avatar=avatar['key'],all_saved_samples=len(samples),all_key_checks=this_keys))
 pose_checks=[]
 indices=sorted(set([0,1,*np.linspace(0,len(samples)-1,11,dtype=int).tolist(),len(samples)-1]))
 for i in indices:
  s=samples[i];f=frames[i];scene.frame_set(math.floor(f),subframe=f%1);deps=bpy.context.evaluated_depsgraph_get();deps.update()
  trs=transforms(joints,s['q_HOME_delta_deg']);T=np.array(s['base_transform_m']);err=0
  for item in items:
   owner=item['link_frame'];owner='trunk_base'if owner=='MULTI_LINK_FLEX_HARNESS'else owner;tm=trs[owner].copy();tm[:3,3]/=1000
   expected=offset@T@tm@shift@np.array(rows[item['name']]['expected_matrix_m']);actual=np.array(partobjs[item['name']].evaluated_get(deps).matrix_world)
   err=max(err,float(abs(expected-actual).max()))
  assert err<1e-5,(avatar['key'],i,err)
  pose_checks.append(dict(sample_index=i,actual_time_s=s['time_s'],display_time_s=times[i],parts=557,max_world_matrix_abs_error=err))
 checks.append(dict(avatar=avatar['key'],pose_checks=pose_checks,display_offset_m=offset[:3,3].tolist()))
 print('AVATAR_READBACK_PASS',avatar['key'],len(samples),flush=True)
for row in idx['scenes']:
 scene=bpy.data.scenes[row['scene']];camera=scene.camera
 assert camera.data.type=='ORTHO'and camera['fixed_world_view']and not camera['robot_tracking_camera']
 assert camera.animation_data is None and camera.parent is None
 if row['mode'].startswith('same_'):assert abs(camera.data.ortho_scale-1.4)<1e-6
 bpy.context.window.scene=scene;bpy.context.window.view_layer=scene.view_layers[0]
 for source,clockname in row['clocks'].items():
  obj=bpy.data.objects[clockname];fc=curves(obj)[('["actual_time_s"]',0)]
  if row['mode']=='same_actual_time':expected=np.array([[1,0],[1+40*row['duration_s'],row['duration_s']]])
  elif source=='R20':expected=np.array([[1,0],[1+40*row['duration_s'],row['duration_s']]])
  else:
   data=json.loads((ROOT/prepared['phase_display_path']).read_text());expected=np.column_stack([1+40*np.array(data['display_times_s']),[s['time_s']for s in data['samples']]])
  assert fc.shape==expected.shape and np.max(abs(fc-expected))<.001
  clocks.append(dict(scene=scene.name,clock=source,key_count=len(fc),max_clock_frame_value_error=float(abs(fc-expected).max())))
result=dict(status='PASS_ALL_ORIGINAL_SCENES_AND_SOURCE_KEYS_557_PARTS_FK',passed=True,purpose=idx['purpose'],source_blend_path=idx['blend_path'],source_blend_sha256=sha(blend),unchanged_R20_scenes=list(idx['old_scene_objects']),unchanged_R20_objects=len(idx['old_object_signatures']),avatars=checks,all_key_checks=all_keys,clock_checks=clocks,metrics_from_full_raw_original_samples=prepared['purpose']=='FINAL_FOUR_STEP',full_trace_sway_comparison=prepared['full_trace_sway_comparison'],physical_approved=False,manufacturing_approved=False,sources={**idx['sources'],str(index_path.relative_to(ROOT)):sha(index_path),str(Path(__file__).relative_to(ROOT)):sha(__file__),'work/r18-leg-hip-covers/review/motion_core.py':sha(ROOT/'work/r18-leg-hip-covers/review/motion_core.py')})
(out/'readback.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print('R21_READBACK_PASS',len(checks),flush=True)
