"""Fresh Blender process verifies every recorded motion key and sampled R26 CAD FK."""
from pathlib import Path
import sys,json,hashlib,math
sys.dont_write_bytecode=True
import bpy,numpy as np
from mathutils import Matrix
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'work/r18-leg-hip-covers/review'))
from motion_core import transforms
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
idx=json.loads((HERE/'build_index.json').read_text());sel=json.loads((ROOT/'work/r26-cover-first/assembly_selection.json').read_text());static=json.loads((ROOT/'work/r26-cover-first/visual/build_index.json').read_text());trace=json.loads((ROOT/'work/r21-reduced-sway/dynamics/full_v3/nominal/dynamic_trace_for_CAD.json').read_text())
for rel,h in idx['source_hashes'].items():assert sha(ROOT/rel)==h,rel
blend=HERE/'OpenDuck_R27_R26_四步运动回放.blend';bpy.ops.wm.open_mainfile(filepath=str(blend))
scene=bpy.data.scenes[idx['scene']];bpy.context.window.scene=scene;bpy.context.window.view_layer=scene.view_layers[0]
assert idx['part_count']==len(sel['items'])==len(static['main_parts'])==1224
assert idx['joint_count']==len(sel['joints'])==15 and idx['source_samples']==len(trace['samples'])==9774
assert scene['physical_approved'] is False and scene['free_neck_wire_display_approximation'] is True
assert scene.camera and scene.camera.data.type=='ORTHO' and scene.render.fps==40
frames=1+40*np.array([s['time_s']for s in trace['samples']]);samples=trace['samples']

def curves(obj):
 out={};assert obj.animation_data and obj.animation_data.action,obj.name
 for layer in obj.animation_data.action.layers:
  for strip in layer.strips:
   for slot in obj.animation_data.action.slots:
    bag=strip.channelbag(slot)
    if bag:
     for fc in bag.fcurves:
      assert all(k.interpolation=='LINEAR'for k in fc.keyframe_points)
      out[(fc.data_path,fc.array_index)]=np.array([tuple(k.co)for k in fc.keyframe_points])
 return out
keychecks=[]
def checkkeys(obj,path,values):
 fc=curves(obj)
 for col in range(values.shape[1]):
  k=fc[(path,col)];assert k.shape==(len(samples),2)
  fe=float(abs(k[:,0]-frames).max());ve=float(abs(k[:,1]-values[:,col]).max())
  assert fe<.001 and ve<1e-5,(obj.name,path,col,fe,ve)
  keychecks.append(dict(object=obj.name,path=path,index=col,keys=len(k),max_frame_error=fe,max_value_error=ve))
root=bpy.data.objects[idx['root_object']]
checkkeys(root,'location',np.array([np.array(s['base_transform_m'])[:3,3]for s in samples]))
q=[];last=None
for sample in samples:
 x=Matrix(sample['base_transform_m']).to_quaternion()
 if last and x.dot(last)<0:x.negate()
 q.append(list(x));last=x.copy()
checkkeys(root,'rotation_quaternion',np.array(q))
for j in sel['joints']:
 obj=bpy.data.objects[idx['joint_objects'][j['joint']]];axis=np.array(j['axis_trunk'],float);axis/=np.linalg.norm(axis)
 values=np.column_stack([np.radians([s['q_HOME_delta_deg'][j['joint']]for s in samples]),np.repeat(axis[None,:],len(samples),axis=0)])
 checkkeys(obj,'rotation_axis_angle',values)
static_rows={r['part_id']:r for r in static['main_parts']};parts={name:bpy.data.objects[obj]for name,obj in idx['part_objects'].items()}
assert len(parts)==1224 and len(set(idx['part_objects'].values()))==1224
for item in sel['items']:
 obj=parts[item['name']];row=static_rows[item['name']]
 verts=np.empty(len(obj.data.vertices)*3,np.float32);obj.data.vertices.foreach_get('co',verts)
 assert hashlib.sha256(verts.tobytes()).hexdigest()==row['vertex_sha256'],item['name']
 assert obj.hide_render==(not item.get('visible_default',True))
shift=np.eye(4);shift[:3,3]=-np.array(static['native_to_scene_shift_mm'])/1000
indices=sorted(set([0,1,len(samples)-1,*np.linspace(0,len(samples)-1,13,dtype=int).tolist()]))
poses=[]
for i in indices:
 f=frames[i];scene.frame_set(math.floor(f),subframe=f%1);deps=bpy.context.evaluated_depsgraph_get();deps.update()
 sample=samples[i];fk=transforms(sel['joints'],sample['q_HOME_delta_deg']);T=np.array(sample['base_transform_m']);largest=0;worst=None
 for item in sel['items']:
  name=item['name'];owner=item['link_frame'];owner='trunk_base'if owner=='MULTI_LINK_FLEX_HARNESS'else owner
  tm=fk[owner].copy();tm[:3,3]/=1000
  expected=T@tm@shift@np.array(static_rows[name]['matrix_m']);actual=np.array(parts[name].evaluated_get(deps).matrix_world)
  error=float(abs(expected-actual).max())
  if error>largest:largest=error;worst=name
 assert largest<2e-5,(i,worst,largest)
 poses.append(dict(sample_index=i,time_s=sample['time_s'],parts=len(parts),largest_matrix_error_m=largest,worst_part=worst))
report=dict(status='R27_R26_ALL_9774_MOTION_KEYS_AND_FULL_1224_PART_FK_READBACK_PASS',blend_sha256=sha(blend),index_sha256=sha(HERE/'build_index.json'),samples=len(samples),duration_s=samples[-1]['time_s'],geometry_parts=len(parts),animation_channels_checked=len(keychecks),all_key_checks=keychecks,pose_checks=poses,physical_approved=False,manufacturing_approved=False)
(HERE/'readback.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('R27_READBACK_PASS',len(keychecks),len(poses),max(x['largest_matrix_error_m']for x in poses),flush=True)
