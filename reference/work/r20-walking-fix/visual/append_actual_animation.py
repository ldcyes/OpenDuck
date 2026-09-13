"""Add actual free-base integration scene while preserving complete static/source geometry."""
from pathlib import Path
import sys,json,hashlib,math,argparse
import bpy,numpy as np
from mathutils import Matrix,Vector
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'work/r18-leg-hip-covers/review'));from motion_core import transforms
ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);a=ap.parse_args(sys.argv[sys.argv.index('--')+1:])
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();sources={}
def read(p,h=None):
 p=Path(p);p=p if p.is_absolute() else ROOT/p
 actual=sha(p)
 if h:assert actual==h,(str(p),h,actual)
 sources[str(p.relative_to(ROOT))]=actual;return json.loads(p.read_text())
config=read(a.input);assert config['state']=='FROZEN_SOURCES_FOR_VISUALIZATION';idx=read('work/r20-walking-fix/visual/static_build_index.json');static_audit=read('work/r20-walking-fix/visual/static_readback.json');assert static_audit['passed']
sel=read(idx['selection_path'],idx['selection_sha256']);assert config['selection_sha256']==idx['selection_sha256'];items=sel['items'];joints=sel['joints'];partcount=len(items);assert partcount==idx['part_count'];SHIFT=np.array(idx['native_to_scene_shift_mm'])/1000
for p,h in idx['sources'].items():assert sha(ROOT/p)==h,p;sources[p]=h
trace=read(config['trace_path'],config['trace_sha256']);report=read(config['report_path'],config['report_sha256']);contract=read(config['contract_path'],config['contract_sha256']);assert trace['status']=='ACTUAL_CONTINUOUS_FREE_BASE_NUMERICAL_INTEGRATION_FOR_CAD_POSTCHECK'
for d in [trace,report,contract]:
 for p,h in d.get('sources',{}).items():assert sha(ROOT/p)==h,p;sources[p]=h
assert abs(trace['model_mass_kg']-contract['mass_kg'])<1e-10
assert joints==contract['joints'] and contract['assembly_parts']==partcount, 'KINEMATICS_OR_ASSEMBLY_COUNT_DIFFERS'
assert abs(sel['nominal_mass_kg']-contract['mass_kg'])<1e-10, 'VISUAL_SELECTION_MASS_AND_DYNAMIC_MODEL_DIFFER'
for p,h in sel.get('sources',{}).items():assert sha(ROOT/p)==h,p;sources[p]=h
samples=trace['samples'];assert len(samples)>1;assert all(samples[i+1]['time_s']>samples[i]['time_s']for i in range(len(samples)-1));assert samples[0]['time_s']==0
path=OUT/'Microduck_R20_修订与实际行走.blend';assert sha(path)==static_audit['source_blend_sha256'];static_blend_sha=sha(path);bpy.ops.wm.open_mainfile(filepath=str(path));static=bpy.data.scenes[idx['main_scene']]
srcobs={p['part_id']:bpy.data.objects[p['object']]for p in idx['main_parts']};srcwm={p['part_id']:Matrix(p['expected_matrix_m'])for p in idx['main_parts']};scenename='03_实际自由积分_四步行走';assert scenename not in bpy.data.scenes
scene=bpy.data.scenes.new(scenename);scene.unit_settings.system='METRIC';scene.unit_settings.length_unit='MILLIMETERS';scene.render.fps=40;scene.frame_start=1;scene.frame_end=math.ceil(1+40*samples[-1]['time_s']);scene['SOURCE_PATH']=config['trace_path'];scene['SOURCE_SHA256']=config['trace_sha256'];scene['selection_sha256']=idx['selection_sha256'];scene['scope']='ACTUAL_FREE_BASE_INTEGRATION_WITH_ASSUMED_MODEL; CAD collision audit separate';scene['physical_approved']=False;scene['manufacturing_approved']=False;scene['current_CAD_parts']=partcount;scene['model_mass_kg']=trace['model_mass_kg'];scene.world=static.world
scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=4;scene.cycles.use_denoising=True;scene.cycles.max_bounces=4;scene.render.threads_mode='FIXED';scene.render.threads=4;scene.render.resolution_x=800;scene.render.resolution_y=800;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
bpy.context.window.scene=scene;bpy.context.window.view_layer=scene.view_layers[0]
collections={}
for row in idx['main_parts']:
 key=row['collection'].split('.')[0]
 if key not in collections:
  c=bpy.data.collections.new('动态_'+key);scene.collection.children.link(c);collections[key]=c
controls=bpy.data.collections.new('动态_自由根与15关节');scene.collection.children.link(controls)
base=bpy.data.objects.new('动态_实际自由根',None);controls.objects.link(base);base.rotation_mode='QUATERNION';base['root_is_actual_integrated']=True;base['coordinates']='meters, floor shift already in source; never add SHIFT again'
rigs={'trunk_base':base};pivots={'trunk_base':np.zeros(3)};jmap={j['child_link']:j for j in joints}
def rig(link):
 if link in rigs:return rigs[link]
 j=jmap[link];parent=rig(j['parent_link']);p=np.array(j['pivot_trunk_mm'])/1000;r=bpy.data.objects.new('动态_'+j['joint'],None);controls.objects.link(r);r.parent=parent;r.matrix_parent_inverse=Matrix.Identity(4);r.location=Vector(p-pivots[j['parent_link']]);r.rotation_mode='AXIS_ANGLE';axis=np.array(j['axis_trunk']);axis/=np.linalg.norm(axis);r.rotation_axis_angle=(0,*axis);r['joint_name']=j['joint'];pivots[link]=p;rigs[link]=r;return r
for link in jmap:rig(link)
obs={}
for p,row in zip(items,idx['main_parts']):
 n=p['name'];assert n==row['part_id'];src=srcobs[n];o=src.copy();o.animation_data_clear();collections[row['collection'].split('.')[0]].objects.link(o);owner=p['link_frame'];owner='trunk_base'if owner=='MULTI_LINK_FLEX_HARNESS'else owner;o.parent=rigs[owner];o.matrix_parent_inverse=Matrix.Identity(4);o.matrix_basis=Matrix.Translation(Vector(-(pivots[owner]+SHIFT)))@srcwm[n];o.name='动态_'+n;o['presentation_scope']='R20_SOURCE_BOUND_ACTUAL_ANIMATION';o.hide_viewport=False;o.hide_render=not p.get('visible_default',True);o.hide_set(not p.get('visible_default',True));obs[n]=o
# One key at every saved actual sample; no prescribed root displacement and no smoothing.
previous_quaternion=None
for s in samples:
 f=1+40*s['time_s'];T=Matrix(s['base_transform_m']);quat=T.to_quaternion()
 if previous_quaternion is not None and quat.dot(previous_quaternion)<0:quat.negate()
 previous_quaternion=quat.copy();base.location=T.to_translation();base.rotation_quaternion=quat;base.keyframe_insert(data_path='location',frame=f);base.keyframe_insert(data_path='rotation_quaternion',frame=f)
 for link,j in jmap.items():
  r=rigs[link];r.rotation_axis_angle[0]=math.radians(s['q_HOME_delta_deg'][j['joint']]);r.keyframe_insert(data_path='rotation_axis_angle',frame=f)
def linear(o):
 for layer in o.animation_data.action.layers:
  for strip in layer.strips:
   for slot in o.animation_data.action.slots:
    bag=strip.channelbag(slot)
    if bag:
     for fc in bag.fcurves:
      for k in fc.keyframe_points:k.interpolation='LINEAR'
linear(base)
for link in jmap:linear(rigs[link])
for src in static.objects:
 if src.type=='LIGHT' or src.name=='地面_显示参考':
  o=src.copy();o.parent=None;o.matrix_world=src.matrix_world.copy();scene.collection.objects.link(o)
cam=static.camera.copy();cam.data=static.camera.data.copy();cam.parent=None;scene.collection.objects.link(cam);scene.camera=cam;cam.name='动态_查看相机';center=Vector((.025,0,.30));direction=Vector((.9,-1,.4)).normalized();cam.location=center+2*direction;cam.rotation_euler=(-direction).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=.78
font=next(f for f in bpy.data.fonts if f.packed_file);d=bpy.data.curves.new('动态_说明','FONT');d.font=font;d.size=.015;d.space_line=1.3;d.body=config['render_label']+'\n'+f"{trace['model_mass_kg']:.5f} kg 估计 · {partcount} 件真实 CAD\n实物行走未验收；按空格播放、拖动时间轴";ob=bpy.data.objects.new('动态_说明',d);scene.collection.objects.link(ob);ob.parent=cam;ob.location=(-.365,.35,-1);d.materials.append(bpy.data.materials['说明字'])
checks=[]
for ii in sorted(set([0,1,*np.linspace(0,len(samples)-1,10,dtype=int).tolist(),len(samples)-1])):
 s=samples[ii];f=1+40*s['time_s'];scene.frame_set(math.floor(f),subframe=f%1);bpy.context.view_layer.update();tr=transforms(joints,s['q_HOME_delta_deg']);baseT=np.array(s['base_transform_m']);sh=np.eye(4);sh[:3,3]=-SHIFT;error=0
 for p in items:
  n=p['name'];owner=p['link_frame'];owner='trunk_base'if owner=='MULTI_LINK_FLEX_HARNESS'else owner;tm=tr[owner].copy();tm[:3,3]/=1000;expected=baseT@tm@sh@np.array(srcwm[n]);error=max(error,float(np.max(abs(np.array(obs[n].matrix_world)-expected))))
 assert error<1e-5,(ii,error);checks.append(dict(source_index=int(ii),time_s=s['time_s'],part_count=partcount,max_world_matrix_abs_error=error))
scene.frame_set(1);bpy.context.window.scene=static;bpy.context.window.view_layer=static.view_layers[0];bpy.context.preferences.filepaths.save_version=0
sources[str(Path(__file__).relative_to(ROOT))]=sha(__file__);sources['work/r18-leg-hip-covers/review/motion_core.py']=sha(ROOT/'work/r18-leg-hip-covers/review/motion_core.py')
for p,h in sources.items():assert sha(ROOT/p)==h,p
note=bpy.data.texts.new('01_实际积分动画说明.txt');note.write('场景03全部557件使用实际自由根与关节积分记录。时间=（帧−1）/40秒，全部保存采样均有关键帧，采样间为显示插值，不增加碰撞证明。接触、惯量、摩擦和电机能力采用报告假设；真实CAD碰撞由另行几何报告核对；线束仍为固定HOME形状。物理受载、热与行走验收未执行。\n'+config['render_label']+'\n')
out=dict(status='ACTUAL_FREE_BASE_SCENE_ADDED_READBACK_PENDING',source_static_blend_sha256=static_blend_sha,source_selection=idx['selection_path'],source_selection_sha256=idx['selection_sha256'],scene=scenename,part_count=partcount,source_path=config['trace_path'],source_sha256=config['trace_sha256'],source_samples=len(samples),source_duration_s=samples[-1]['time_s'],fps=40,source_keyframe_checks=checks,part_objects={n:o.name for n,o in obs.items()},root_object=base.name,joint_objects={jmap[k]['joint']:rigs[k].name for k in jmap},render_label=config['render_label'],label_object=ob.name,config=config,sources=sources,physical_approved=False,manufacturing_approved=False)
(OUT/'animation_build_index.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');t=bpy.data.texts.new('animation_build_index.json');t.write(json.dumps(out,ensure_ascii=False,indent=2));bpy.ops.wm.save_as_mainfile(filepath=str(path),compress=True);print('ACTUAL_ANIMATION_SAVED',partcount,len(samples),flush=True)
