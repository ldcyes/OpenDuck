"""Preserve unchanged source meshes and import only explicit source-bound R20 replacements."""
from pathlib import Path
import bpy,json,hashlib,math,numpy as np,sys,argparse
from mathutils import Matrix,Vector
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sources={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,h=None):
 p=Path(p);p=p if p.is_absolute()else ROOT/p;a=sha(p)
 if h:assert a==h,(p,h,a)
 sources[str(p.relative_to(ROOT))]=a;return json.loads(p.read_text())
head=read('work/r20-walking-fix/head_mount/head_delivery_index.json')
parser=argparse.ArgumentParser();parser.add_argument('--selection');args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
selection_path=args.selection or head['primary_files']['selection'];sel=read(selection_path,head['files'].get(selection_path));items=sel['items'];by={p['name']:p for p in items}
current=read('work/r18-leg-hip-covers/CURRENT_DESIGN.json');sourceblend=ROOT/current['viewer']['path'];assert sha(sourceblend)==current['viewer']['sha256'];sources[current['viewer']['path']]=sha(sourceblend)
index=read(current['source_geometry_selection_in_viewer']['path'],current['source_geometry_selection_in_viewer']['sha256']);SHIFT=np.array(index['native_to_scene_shift_mm'])/1000
oldsel=read('work/r18-leg-hip-covers/legs/reference_design/candidate_v8/motion_diagnostic/diagnostic_selection.json');oldby={p['name']:p for p in oldsel['items']}
read('work/r20-walking-fix/head_mount/candidate_manifest.json')
new_names={p['name'] for p in items if p['name'] not in oldby or any(p.get(k)!=oldby[p['name']].get(k) for k in ['mesh_sha256','R','t_mm','link_frame'])}
assert len(items)==557 and len(by)==557 and len(new_names)>=29
bpy.ops.wm.open_mainfile(filepath=str(sourceblend));oldscenes=list(bpy.data.scenes);oldmain=bpy.data.scenes[index['main_scene']]
source_objects={p['part_id']:bpy.data.objects[p['object']]for p in index['main_parts']};source_matrices={n:o.matrix_world.copy() for n,o in source_objects.items()}
for p in index['main_parts']:assert np.max(abs(np.array(source_matrices[p['part_id']])-np.array(p['expected_matrix'])))<2e-6,p['part_id']
original_lights=[o for o in oldmain.objects if o.type=='LIGHT'];world=oldmain.world
font=bpy.data.fonts.load('/mnt/c/Windows/Fonts/msyh.ttc');font.pack()

def material(name,color,alpha=1,metal=0):
 m=bpy.data.materials.new(name);m.use_nodes=True;n=m.node_tree.nodes.get('Principled BSDF');n.inputs['Base Color'].default_value=(*color,1);n.inputs['Alpha'].default_value=alpha;n.inputs['Metallic'].default_value=metal;n.inputs['Roughness'].default_value=.38;m.diffuse_color=(*color,alpha);return m
steel=material('R20_标准金属五金',(.37,.44,.50),metal=.7);pcb=material('R20_现有载板含真实安装孔',(.035,.25,.105),metal=.1)
ghost=material('旧散热器_透视显示原交体',(.45,.58,.65),alpha=.25);gold=material('旧重复压条',(.94,.58,.05),alpha=.5)
red=material('原STEP真实交体',(.95,.025,.012));red.node_tree.nodes.get('Principled BSDF').inputs['Emission Color'].default_value=(.95,.025,.012,1);red.node_tree.nodes.get('Principled BSDF').inputs['Emission Strength'].default_value=.8
ink=material('说明字',(.025,.035,.045))
def studio(scene,center,scale,direction=(.9,-1,.4),res=(1000,1000)):
 scene.unit_settings.system='METRIC';scene.unit_settings.length_unit='MILLIMETERS';scene.world=world;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=12;scene.cycles.use_denoising=True;scene.cycles.max_bounces=5
 scene.render.threads_mode='FIXED';scene.render.threads=4;scene.render.resolution_x=res[0];scene.render.resolution_y=res[1];scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
 for src in original_lights:
  o=src.copy();o.data=src.data.copy();o.parent=None;o.matrix_world=src.matrix_world.copy();scene.collection.objects.link(o)
 camera_data=bpy.data.cameras.new(scene.name+'_camera');camera=bpy.data.objects.new(scene.name+'_camera',camera_data);scene.collection.objects.link(camera);scene.camera=camera;camera_data.type='ORTHO';camera_data.ortho_scale=scale
 dr=Vector(direction).normalized();camera.location=Vector(center)+dr*2;camera.rotation_euler=(-dr).to_track_quat('-Z','Y').to_euler();return camera
def label(scene,cam,body,x,y,size):
 d=bpy.data.curves.new(body[:30],'FONT');d.body=body;d.font=font;d.size=size;d.space_line=1.25;o=bpy.data.objects.new(body[:30],d);scene.collection.objects.link(o);o.parent=cam;o.location=(x,y,-1);d.materials.append(ink);return o
def put_in(o,collection):
 for col in list(o.users_collection):col.objects.unlink(o)
 collection.objects.link(o)
def category(p):
 if not p.get('visible_default',True):return '06_独立参考包络_默认隐藏'
 c=p.get('category','')
 if c=='01_motors':return '01_电机'
 if c in ['02_motor_interfaces','03_structure','09_mounts']:return '02_结构与支架'
 if c in ['06_electronics','07_wiring','08_harness']:return '03_PCB与电气'
 if c=='10_fasteners_insulation':return '05_五金与绝缘'
 return '04_外壳与覆盖件'
scene=bpy.data.scenes.new('01_完整装配_557件_静态');scene['scope']='Source-bound complete selected assembly, HOME only; no animation or physical test qualification.';scene['part_count']=557;scene['selection_path']=selection_path;scene['selection_sha256']=sources[selection_path];scene['physical_approved']=False
collections={}
for name in sorted({category(p) for p in items}):
 col=bpy.data.collections.new(name);scene.collection.children.link(col);collections[name]=col
bpy.context.window.scene=scene;bpy.context.window.view_layer=scene.view_layers[0]
part_objects={};records=[]
for p in items:
 n=p['name'];col=collections[category(p)]
 if n not in new_names:
  src=source_objects[n];o=src.copy();o.animation_data_clear();o.parent=None;col.objects.link(o);o.matrix_world=source_matrices[n];origin='R18_SOURCE_VIEWER_EXACT_VERTEX_COPY'
 else:
  assert sha(ROOT/p['mesh'])==p['mesh_sha256'];sources[p['mesh']]=p['mesh_sha256'];sources[p['step']]=sha(ROOT/p['step']);assert sources[p['step']]==p['step_sha256']
  bpy.ops.wm.stl_import(filepath=str(ROOT/p['mesh']));o=bpy.context.object;put_in(o,col);o.parent=None;A=np.eye(4);A[:3,:3]=np.asarray(p['R'])*.001;A[:3,3]=np.asarray(p['t_mm'])/1000+SHIFT;T=Matrix(A);o.matrix_world=T;o.data.materials.clear();o.data.materials.append(pcb if 'PCB_' in n else (source_objects[p.get('replaces_name',n)].data.materials[0] if p.get('replaces_name',n) in source_objects and len(source_objects[p.get('replaces_name',n)].data.materials) else steel));origin='R20_CURRENT_BOUND_STL_NO_MODIFICATION'
 o.name='R20_'+p.get('label_zh',n);o['part_id']=n;o['link_frame']=p['link_frame'];o['source_mesh']=p['mesh'];o['source_mesh_sha256']=p['mesh_sha256'];o['source_selection']=selection_path;o['presentation_scope']='R20_COMPLETE_557_STATIC';o['manufacturing_approved']=False;o['physical_approved']=False
 o.hide_viewport=False;o.hide_render=not p.get('visible_default',True);o.hide_set(not p.get('visible_default',True));part_objects[n]=o
 v=np.empty(len(o.data.vertices)*3,np.float32);o.data.vertices.foreach_get('co',v);o.data.calc_loop_triangles();tri=np.array([list(t.vertices) for t in o.data.loop_triangles],np.int32)
 records.append(dict(part_id=n,object=o.name,collection=col.name,origin=origin,source_mesh_sha256=p['mesh_sha256'],expected_matrix_m=np.array(o.matrix_world).tolist(),vertex_count=len(o.data.vertices),triangle_count=len(tri),vertex_sha256=hashlib.sha256(v.tobytes()).hexdigest(),triangle_sha256=hashlib.sha256(tri.tobytes()).hexdigest(),visible_default=p.get('visible_default',True)))
cam=studio(scene,[.015,0,.31],.76);label(scene,cam,'R20 完整装配 · 557 件\n静态查看；实物与制造验收未完成',-.35,.33,.016)
me=bpy.data.meshes.new('Ground');me.from_pydata([(-2,-2,0),(2,-2,0),(2,2,0),(-2,2,0)],[],[(0,1,2,3)]);floor=bpy.data.objects.new('地面_显示参考',me);scene.collection.objects.link(floor);me.materials.append(material('Floor',(.58,.61,.64)))
scene.frame_start=1;scene.frame_end=1;scene.frame_set(1)

# Two separate displays, not two robots coexisting physically.
comparison=bpy.data.scenes.new('02_头部安装_旧与新对照');comparison['scope']='Side-by-side display offsets only. Old analytic overlap and source-bound revised mounting.';comparison['physical_approved']=False;comparison['manufacturing_approved']=False
bpy.context.window.scene=comparison;bpy.context.window.view_layer=comparison.view_layers[0]
subgroup=lambda n:n.startswith(('R10_HEAD_CM4','R10_HEAD_R8_CM4','R10_HEAD_REFERENCE_SUNON','R11_CM4','R20_CM4')) or n in ['R13_VIEW_CM4carrier_U2','R13_VIEW_CM4carrier_U3','R13_head_shell_carrier_Entry_ports']
comparison_records=[]
for stage,srcmap,rows_by,off in [('旧安装_两根重复压条',source_objects,oldby,np.array([0,.09,0])),('R20安装_四组贯穿螺栓',part_objects,by,np.array([0,-.09,0]))]:
 col=bpy.data.collections.new(stage);comparison.collection.children.link(col)
 for n in srcmap:
  if not subgroup(n):continue
  src=srcmap[n];p=rows_by[n];o=src.copy();o.data=src.data.copy();o.animation_data_clear();o.parent=None;col.objects.link(o);T=source_matrices[n].copy() if stage.startswith('旧') else src.matrix_world.copy();T.translation+=Vector(off);o.matrix_world=T;o.name=stage+'_'+n;o['part_id']=n;o['presentation_scope']='HEAD_COMPARISON_DISPLAY_COPY';o['display_offset_m']=off.tolist();o.hide_viewport=False;o.hide_render=not p.get('visible_default',True);o.hide_set(not p.get('visible_default',True))
  if stage.startswith('旧') and n=='R10_HEAD_R8_CM4_6061_finned_heatsink':o.data.materials.clear();o.data.materials.append(ghost)
  if n.startswith('R11_CM4_front_clamp_bar'):o.data.materials.clear();o.data.materials.append(gold)
  comparison_records.append(dict(stage=stage,part_id=n,object=o.name,source_mesh_sha256=p['mesh_sha256'],display_offset_m=off.tolist(),expected_matrix_m=np.array(T).tolist()))
ad=read('work/r19-walking-simulation/review/four_baseline_pairs/adjudication.json');intersections=[]
bpy.context.window.scene=comparison;bpy.context.window.view_layer=comparison.view_layers[0]
for p in ad['rows']:
 if not p['real_STEP_material_intersection']:continue
 f=p['analytic_intersection_STL'];assert sha(ROOT/f)==p['analytic_intersection_STL_sha256'];sources[f]=sha(ROOT/f)
 bpy.ops.wm.stl_import(filepath=str(ROOT/f));o=bpy.context.object;o.name='旧安装_真实STEP交体_'+p['pair'][1];o.scale=(.001,)*3;o.location=Vector(SHIFT+np.array([0,.09,0]));o.data.materials.clear();o.data.materials.append(red);o['presentation_scope']='OLD_ORIGINAL_ANALYTIC_STEP_INTERSECTION';o['common_mm3']=p['original_analytic_STEP_common_mm3'];intersections.append(dict(object=o.name,source_STL=f,source_STL_sha256=sha(ROOT/f),common_mm3=p['original_analytic_STEP_common_mm3']))
cam=studio(comparison,[.085,0,.270+SHIFT[2]],.36,direction=(-1,0,.3),res=(1500,1000));label(comparison,cam,'旧安装：重复压条\n2 × 63.291 mm³ 真穿透',-.163,.099,.008);label(comparison,cam,'R20：原安装耳 + 通栓\n原孔轴与 4 mm PEEK 保留',.013,.099,.008);label(comparison,cam,'两侧仅作显示对照；实物装配与载荷试验尚未完成。',-.16,-.109,.0065)
for oldscene in oldscenes:bpy.data.scenes.remove(oldscene)
for ob in list(bpy.data.objects):
 if ob.users==0:bpy.data.objects.remove(ob)
bpy.context.window.scene=scene;bpy.context.window.view_layer=scene.view_layers[0];bpy.context.view_layer.update();bpy.context.preferences.filepaths.save_version=0
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   area.spaces.active.region_3d.view_distance=.88;area.spaces.active.region_3d.view_location=(.02,0,.30);area.spaces.active.clip_end=100;area.spaces.active.shading.type='MATERIAL'
text=bpy.data.texts.new('00_R20_查看说明.txt');text.write('场景01：完整557件静态装配；按电机、结构、PCB电气、外壳、五金、隐藏参考包络分组。选择零件可查看part_id、source_mesh及所属link。场景02：旧散热器重复压条与R20四组通栓的对照；两侧只是显示偏移。新载板已经包含当前KiCad四个真实孔。未经过实物受载、装配或行走试验。后续实际积分动画将另加场景，不把参考根轨迹当作物理积分。\n')
sources[str(Path(__file__).relative_to(ROOT))]=sha(__file__)
for p,h in sources.items():assert sha(ROOT/p)==h,p
report=dict(status='R20_STATIC_557_AND_HEAD_COMPARISON_BUILT_READBACK_PENDING',selection_path=selection_path,selection_sha256=sources[selection_path],native_to_scene_shift_mm=(SHIFT*1000).tolist(),main_scene=scene.name,part_count=557,unchanged_R18_mesh_count=557-len(new_names),new_source_STL_count=len(new_names),main_parts=records,comparison_scene=comparison.name,comparison_parts=comparison_records,old_true_intersections=intersections,source_viewer=current['viewer'],physical_approved=False,manufacturing_approved=False,sources=sources)
(OUT/'static_build_index.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');t=bpy.data.texts.new('static_build_index.json');t.write(json.dumps(report,ensure_ascii=False,indent=2));path=OUT/'Microduck_R20_修订与实际行走.blend';bpy.ops.wm.save_as_mainfile(filepath=str(path),compress=True)
print('STATIC_SAVED',len(records),len(comparison_records),flush=True)
