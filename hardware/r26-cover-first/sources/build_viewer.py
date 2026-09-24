"""Standalone complete R26 assembly and source-matched orthographic views."""
from pathlib import Path
import hashlib
import json
import bpy
import numpy as np
from mathutils import Matrix,Vector

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent/'visual';OUT.mkdir(exist_ok=True)
sources={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
    sources[p]=sha(ROOT/p)
    return json.loads((ROOT/p).read_text())
selection=read('work/r26-cover-first/assembly_selection.json')
verification=read('work/r26-cover-first/verification.json');assert not verification['errors']
old_index=read('work/r25-bottom-head-entry/visual/build_index.json')
old_readback=read('work/r25-bottom-head-entry/visual/readback.json')
old_path='work/r25-bottom-head-entry/visual/OpenDuck_R25_底部走线.blend'
assert sha(ROOT/old_path)==old_readback['blend_sha256']
sources[old_path]=old_readback['blend_sha256']
sources[str(Path(__file__).relative_to(ROOT))]=sha(__file__)
bpy.ops.wm.open_mainfile(filepath=str(ROOT/old_path))
baseline=bpy.data.scenes[old_index['main_scene']]
baseline.name='06_R25_original_reference'
for prior in bpy.data.scenes:
    if prior.name == '02_R25_头部摄像头前盖': prior.name='04_R25_head_camera_retained'
    if prior.name == '03_R25_头部底部走线': prior.name='05_R25_bottom_entry_retained'
old_rows={r['part_id']:r for r in old_index['main_parts']}
old_objects={n:baseline.objects[r['object']] for n,r in old_rows.items()}
shift=np.array(old_index['native_to_scene_shift_mm'])/1000
main=bpy.data.scenes.new('01_R26_complete_assembly')
main.world=baseline.world
main.unit_settings.system='METRIC';main.unit_settings.length_unit='MILLIMETERS'
main['scope']='A: two shortened thigh covers. Leg axes and commercial actuators unchanged.'
main['physical_approved']=False
bpy.context.window.scene=main
collections={};objects={};records=[]
new_names=set(selection['new_part_names'])
def group(name):
    if name not in collections:
        col=bpy.data.collections.new(name);main.collection.children.link(col);collections[name]=col
    return collections[name]
for p in selection['items']:
    name=p['name']
    if name in new_names:
        mesh=ROOT/p['mesh'];assert sha(mesh)==p['mesh_sha256'];sources[p['mesh']]=p['mesh_sha256']
        bpy.ops.wm.ply_import(filepath=str(mesh),merge_verts=False)
        obj=bpy.context.object
        for col in list(obj.users_collection):col.objects.unlink(obj)
        group('R26_short_thigh_covers').objects.link(obj)
        M=np.eye(4);M[:3,:3]=np.array(p['R'])*.001;M[:3,3]=np.array(p['t_mm'])/1000+shift
        obj.matrix_world=Matrix(M)
        for material in old_objects[p['replaces'][0]].data.materials:obj.data.materials.append(material)
    else:
        original=old_objects[name];obj=original.copy();obj.parent=None;obj.animation_data_clear()
        group('Retained_'+p.get('link_frame','reference')).objects.link(obj)
        obj.matrix_world=Matrix(old_rows[name]['matrix_m'])
    obj.name='R26_'+name
    obj['part_id']=name;obj['link_frame']=p['link_frame'];obj['source_mesh']=p['mesh']
    obj['source_mesh_sha256']=p['mesh_sha256'];obj['physical_approved']=False
    obj['r26_changed']=name in new_names
    obj.hide_viewport=False;obj.hide_render=not p.get('visible_default',True)
    obj.hide_set(not p.get('visible_default',True))
    verts=np.empty(len(obj.data.vertices)*3,np.float32);obj.data.vertices.foreach_get('co',verts)
    records.append(dict(part_id=name,object=obj.name,vertices=len(obj.data.vertices),
        vertex_sha256=hashlib.sha256(verts.tobytes()).hexdigest(),matrix_m=np.array(obj.matrix_world).tolist(),
        visible_default=p.get('visible_default',True),changed=name in new_names))
    objects[name]=obj
services=[]
for r in old_index['service_parts']:
    obj=baseline.objects[r['object']].copy();obj.parent=None;obj.animation_data_clear()
    group('Hidden_noninstalled_service_references').objects.link(obj)
    obj.matrix_world=Matrix(r['matrix_m']);obj.name='R26_SERVICE_'+r['part_id']
    obj.hide_render=True;obj.hide_set(True)
    entry=dict(r,object=obj.name);services.append(entry)

def setup(scene,rx,ry):
    scene.render.engine='CYCLES';scene.cycles.samples=16;scene.cycles.use_denoising=True
    scene.cycles.max_bounces=5;scene.render.threads_mode='FIXED';scene.render.threads=4
    scene.render.resolution_x=rx;scene.render.resolution_y=ry;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='AgX'
    cam=bpy.data.objects.new(scene.name+'_camera',bpy.data.cameras.new(scene.name+'_camera'))
    scene.collection.objects.link(cam);scene.camera=cam;cam.data.type='ORTHO'
    for i,rotation in enumerate([(.4,-.5,-.7),(-.4,.7,2.4)]):
        light=bpy.data.lights.new(scene.name+'_sun_'+str(i),'SUN');light.energy=[2.5,1.2][i];light.angle=.3
        lo=bpy.data.objects.new(light.name,light);scene.collection.objects.link(lo);lo.rotation_euler=rotation
def fit(scene,objs,direction,margin=1.12):
    bpy.context.window.scene=scene
    scene.frame_set(scene.frame_current)
    scene.view_layers[0].update()
    bpy.context.evaluated_depsgraph_get().update()
    points=np.array([o.matrix_world@Vector(v) for o in objs for v in o.bound_box])
    center=Vector((points.min(0)+points.max(0))/2);d=Vector(direction).normalized()
    rot=(-d).to_track_quat('-Z','Y');local=(points-np.array(center))@np.array(rot.to_matrix())
    scene.camera.data.ortho_scale=1
    frame=np.array([list(v) for v in scene.camera.data.view_frame(scene=scene)])
    spans=np.ptp(local,axis=0);unit=np.ptp(frame,axis=0)
    scene.camera.data.ortho_scale=float(max(spans[0]/unit[0],spans[1]/unit[1])*margin)
    scene.camera.location=center+d*2;scene.camera.rotation_euler=rot.to_euler()
    return center
setup(main,900,1100)
visible=[objects[p['name']] for p in selection['items'] if p.get('visible_default',True)]
center=fit(main,visible,(1,0,0))
main.render.filepath=str(OUT/'01-front.png');bpy.ops.render.render(write_still=True,scene=main.name)
fit(main,visible,(0,-1,0));main.render.filepath=str(OUT/'02-side.png');bpy.ops.render.render(write_still=True,scene=main.name)

textmat=bpy.data.materials.new('Comparison_labels');textmat.diffuse_color=(.025,.035,.045,1)
def comparison(name,only_leg=False):
    sc=bpy.data.scenes.new(name);sc.world=main.world;sc.unit_settings.system='METRIC'
    setup(sc,1600,1000 if only_leg else 1200)
    bpy.context.window.scene=sc
    sc.view_layers[0].update()
    shown=[];step=.24 if only_leg else .34
    for i,(label,lookup) in enumerate([('R25 | before',old_objects),('R26 | A',objects)]):
        for p in selection['items']:
            if not p.get('visible_default',True):continue
            if only_leg and p['link_frame'] not in ['upper_leg_right','leg_2','ankle_right','hip_l_2','bearing_roll']:continue
            key=p['replaces'][0] if lookup is old_objects and p['name'] in new_names else p['name']
            orig=lookup[key];obj=orig.copy();obj.parent=None;obj.animation_data_clear();sc.collection.objects.link(obj)
            M=orig.matrix_world.copy();M.translation.x+=i*step
            obj.matrix_world=M;obj.update_tag(refresh={'OBJECT'})
            obj.hide_render=False;obj.hide_viewport=False;shown.append(obj)
        font=bpy.data.curves.new(name+'_label_'+str(i),'FONT');font.body=label;font.size=.016;font.align_x='CENTER'
        txt=bpy.data.objects.new(font.name,font);sc.collection.objects.link(txt)
        txt.location=(.02+i*step,-.20,-.025);txt.rotation_euler=(np.pi/2,0,0);font.materials.append(textmat)
        shown.append(txt)
    fit(sc,shown,(0,-1,0),1.08)
    sc['scope']='Same scale and original HOME pose; display copies only.'
    return sc
full=comparison('02_R25_R26_same_scale')
full.render.filepath=str(OUT/'03-full-comparison.png');bpy.ops.render.render(write_still=True,scene=full.name)
detail=comparison('03_R25_R26_leg_detail',True)
detail.render.filepath=str(OUT/'04-leg-comparison.png');bpy.ops.render.render(write_still=True,scene=detail.name)
fit(main,visible,(1,0,0));bpy.context.window.scene=main
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            region=area.spaces.active.region_3d;region.view_location=center;region.view_distance=.95
            region.view_rotation=main.camera.rotation_euler.to_quaternion();region.view_perspective='ORTHO'
            area.spaces.active.shading.type='SOLID';area.spaces.active.shading.color_type='MATERIAL'
            area.spaces.active.clip_end=100
note=bpy.data.texts.new('00_R26_README')
note.write('R26 A: two shorter thigh covers; same leg axes, motors and mounting parts. Scene01 is complete assembly, scenes02/03 are before-after display comparisons. Scene06 retains original R25. Head scenes retain R25 geometry including its separate motor opening. Select/hide individual parts in Outliner. No physical or manufacturing approval. Printed masters, source STEP and verification are separate deliverables.\n')
index=dict(status='BUILT_PENDING_INDEPENDENT_READBACK',main_scene=main.name,part_count=len(records),
    main_parts=records,service_count=len(services),service_parts=services,native_to_scene_shift_mm=(shift*1000).tolist(),
    sources=sources,physical_approved=False,manufacturing_approved=False,
    comparison_scenes=[full.name,detail.name],baseline_scene=baseline.name)
(OUT/'build_index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n')
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'OpenDuck_R26_cover_first.blend'),compress=True)
print('R26_COMPLETE_SAVED',len(records),len(services),flush=True)
