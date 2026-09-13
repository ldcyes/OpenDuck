"""Blender-only helpers; source geometry and real root motion remain unchanged.

Called only by the final source-bound build after a real R21 trace is frozen.
Importing this file creates no scenes or motion.
"""
import math
import bpy
import numpy as np
from mathutils import Matrix,Vector

def set_linear(obj):
    if not obj.animation_data or not obj.animation_data.action:return
    action=obj.animation_data.action
    for layer in action.layers:
        for strip in layer.strips:
            for slot in action.slots:
                bag=strip.channelbag(slot)
                if bag:
                    for fc in bag.fcurves:
                        for key in fc.keyframe_points:key.interpolation='LINEAR'

def new_scene(name,static_scene,duration_s,fps=40):
    if name in bpy.data.scenes:raise ValueError('Refuse to replace an existing scene')
    scene=bpy.data.scenes.new(name);scene.world=static_scene.world
    scene.unit_settings.system='METRIC';scene.unit_settings.length_unit='MILLIMETERS'
    scene.render.fps=fps;scene.frame_start=1;scene.frame_end=math.ceil(1+fps*duration_s)
    scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=4
    scene.cycles.use_denoising=True;scene.cycles.max_bounces=4
    scene.render.threads_mode='FIXED';scene.render.threads=4
    scene.render.resolution_x=1440;scene.render.resolution_y=1080
    scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
    scene['physical_approved']=False;scene['display_duration_s']=duration_s
    scene['source_end_frame_float']=1+fps*duration_s
    bpy.context.window.scene=scene;bpy.context.window.view_layer=scene.view_layers[0]
    for source in static_scene.objects:
        if source.type=='LIGHT' or source.name=='地面_显示参考':
            obj=source.copy();obj.parent=None;obj.matrix_world=source.matrix_world.copy();scene.collection.objects.link(obj)
    return scene

def collection(scene,name):
    result=bpy.data.collections.new(name);scene.collection.children.link(result);return result

def add_actual_avatar(scene,prefix,items,joints,static_rows,samples,shift_m,source_metadata,display_times=None):
    """Every input key is a real saved pose or explicitly declared display interpolation.

    The source base transform already contains floor placement. Only the old
    static presentation shift is removed from the source part matrix.
    """
    if len(items)!=557 or len(items)!=len(static_rows):raise ValueError('Expected the frozen complete 557-part assembly')
    display_times=[s['time_s']for s in samples]if display_times is None else display_times
    if len(display_times)!=len(samples) or any(b<=a for a,b in zip(display_times,display_times[1:])):raise ValueError('Display keys must be strictly ordered')
    controls=collection(scene,prefix+'控制轴');parts={};pivots={'trunk_base':np.zeros(3)}
    root=bpy.data.objects.new(prefix+'实际自由根',None);controls.objects.link(root);root.rotation_mode='QUATERNION'
    root['root_is_actual_integrated']=True;root['source_trace']=source_metadata['trace_path'];root['source_sha256']=source_metadata['trace_sha256']
    root['floor_already_in_source']=True
    rigs={'trunk_base':root};jmap={j['child_link']:j for j in joints};categories={}
    def rig(link):
        if link in rigs:return rigs[link]
        j=jmap[link];parent=rig(j['parent_link']);pivot=np.array(j['pivot_trunk_mm'])/1000
        obj=bpy.data.objects.new(prefix+j['joint'],None);controls.objects.link(obj)
        obj.parent=parent;obj.matrix_parent_inverse=Matrix.Identity(4)
        obj.location=Vector(pivot-pivots[j['parent_link']]);obj.rotation_mode='AXIS_ANGLE'
        axis=np.array(j['axis_trunk'],float);axis/=np.linalg.norm(axis)
        obj.rotation_axis_angle=(0,*axis);obj['joint_name']=j['joint'];rigs[link]=obj;pivots[link]=pivot
        return obj
    for link in jmap:rig(link)
    for item,row in zip(items,static_rows):
        if item['name']!=row['part_id']:raise ValueError('Source part order changed')
        cat=row['collection'].split('.')[0]
        if cat not in categories:categories[cat]=collection(scene,prefix+cat)
        source=bpy.data.objects[row['object']];obj=source.copy();obj.animation_data_clear()
        categories[cat].objects.link(obj);obj.name=prefix+item['name']
        owner=item['link_frame'];owner='trunk_base'if owner=='MULTI_LINK_FLEX_HARNESS'else owner
        obj.parent=rigs[owner];obj.matrix_parent_inverse=Matrix.Identity(4)
        obj.matrix_basis=Matrix.Translation(Vector(-(pivots[owner]+np.array(shift_m))))@Matrix(row['expected_matrix_m'])
        obj.hide_viewport=False;obj.hide_render=not item.get('visible_default',True)
        obj.hide_set(not item.get('visible_default',True))
        obj['R21_source_part']=item['name'];obj['source_geometry_unchanged']=True
        parts[item['name']]=obj
    previous=None
    for sample,display_time in zip(samples,display_times):
        frame=1+scene.render.fps*float(display_time);T=Matrix(sample['base_transform_m']);quat=T.to_quaternion()
        if previous is not None and quat.dot(previous)<0:quat.negate()
        previous=quat.copy();root.location=T.to_translation();root.rotation_quaternion=quat
        root.keyframe_insert(data_path='location',frame=frame);root.keyframe_insert(data_path='rotation_quaternion',frame=frame)
        for link,j in jmap.items():
            obj=rigs[link];obj.rotation_axis_angle[0]=math.radians(sample['q_HOME_delta_deg'][j['joint']])
            obj.keyframe_insert(data_path='rotation_axis_angle',frame=frame)
    for obj in rigs.values():set_linear(obj)
    return dict(root=root,rigs=rigs,parts=parts,categories=categories,controls=controls)

def clone_avatar(scene,prefix,avatar,display_y_m):
    """Share meshes and existing animation data. Offset is a separate display parent."""
    bpy.context.window.scene=scene;bpy.context.window.view_layer=scene.view_layers[0]
    controls=collection(scene,prefix+'控制轴');categories={};mapping={}
    for old in avatar['rigs'].values():
        new=old.copy();controls.objects.link(new);new.name=prefix+old.name;mapping[old]=new
    for category,old_collection in avatar['categories'].items():
        categories[category]=collection(scene,prefix+category)
    for name,old in avatar['parts'].items():
        category=next(cat for cat,c in avatar['categories'].items()if old.name in c.objects)
        new=old.copy();categories[category].objects.link(new);new.name=prefix+name;mapping[old]=new
        new.hide_set(old.hide_render)
    for old,new in mapping.items():
        if old.parent:new.parent=mapping[old.parent]
        new.matrix_parent_inverse=old.matrix_parent_inverse.copy();new.matrix_basis=old.matrix_basis.copy()
    offset=bpy.data.objects.new(prefix+'仅画面横移',None);controls.objects.link(offset)
    offset.location=(0,display_y_m,0);offset['display_offset_only']=True;offset['excluded_from_sway_metrics']=True
    mapping[avatar['root']].parent=offset
    return dict(root=mapping[avatar['root']],rigs={k:mapping[v]for k,v in avatar['rigs'].items()},parts={k:mapping[v]for k,v in avatar['parts'].items()},categories=categories,controls=controls,offset=offset)

def frontal_camera(scene,static_scene,name='固定正视相机',width_m=1.4):
    camera=static_scene.camera.copy();camera.data=static_scene.camera.data.copy();camera.parent=None
    scene.collection.objects.link(camera);scene.camera=camera;camera.name=name
    direction=Vector((1,0,0));center=Vector((0,0,.33))
    camera.location=center+2*direction;camera.rotation_euler=(-direction).to_track_quat('-Z','Y').to_euler()
    camera.data.type='ORTHO';camera.data.ortho_scale=width_m
    camera['fixed_world_view']=True;camera['robot_tracking_camera']=False
    return camera

def add_clock(scene,prefix,actual_times,display_times):
    obj=bpy.data.objects.new(prefix+'实际时间_秒',None);scene.collection.objects.link(obj)
    obj['scope']='Explicit source clock; phase-aligned display is not same physical time'
    for actual,display in zip(actual_times,display_times):
        obj['actual_time_s']=float(actual);obj.keyframe_insert(data_path='["actual_time_s"]',frame=1+scene.render.fps*float(display))
    set_linear(obj);return obj
