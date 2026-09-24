"""Replay recorded R21 integrated motion on unchanged R26 kinematics and R26 geometry."""
from pathlib import Path
import sys,json,hashlib,math
sys.dont_write_bytecode=True
import bpy,numpy as np
from mathutils import Vector
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE))
from blender_actual_helpers_r27 import add_actual_avatar,new_scene,frontal_camera
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
sp=ROOT/'work/r26-cover-first/assembly_selection.json';ip=ROOT/'work/r26-cover-first/visual/build_index.json'
rp=ROOT/'work/r26-cover-first/visual/readback.json';tp=ROOT/'work/r21-reduced-sway/dynamics/full_v3/nominal/dynamic_trace_for_CAD.json'
sel=json.loads(sp.read_text());index=json.loads(ip.read_text());readback=json.loads(rp.read_text());trace=json.loads(tp.read_text())
assert readback['status']=='R26_COMPLETE_MODEL_READBACK_PASS' and len(sel['items'])==1224
assert trace['status']=='ACTUAL_CONTINUOUS_FREE_BASE_NUMERICAL_INTEGRATION_FOR_CAD_POSTCHECK' and len(trace['samples'])==9774
assert set(trace['samples'][0]['q_HOME_delta_deg'])=={j['joint']for j in sel['joints']}
blend=ROOT/'work/r26-cover-first/visual/OpenDuck_R26_cover_first.blend';assert sha(blend)==readback['blend_sha256']
bpy.ops.wm.open_mainfile(filepath=str(blend));base=bpy.data.scenes[index['main_scene']]
rows=[]
for item,row in zip(sel['items'],index['main_parts']):
    assert item['name']==row['part_id']
    rows.append(dict(row,collection=('R26_printed_cover' if row['changed'] else 'R26_retained'),expected_matrix_m=row['matrix_m']))
scene=new_scene('07_R27_R26四步运动回放',base,trace['time_s'],fps=40)
scene['scope']='R21 integrated free-base trace replayed on R26 geometry; dynamic loads not re-solved for R26 mass.'
scene['source_kinematics']='R26 joints identical to R25/R21; 1224 installed geometry entries.'
scene['physical_approved']=False;scene['manufacturing_approved']=False
metadata=dict(trace_path=str(tp.relative_to(ROOT)),trace_sha256=sha(tp))
avatar=add_actual_avatar(scene,'R27_',sel['items'],sel['joints'],rows,trace['samples'],np.array(index['native_to_scene_shift_mm'])/1000,metadata)
cam=frontal_camera(scene,base,width_m=.72);cam.location=Vector((2,0,.29));cam.rotation_euler=Vector((-1,0,0)).to_track_quat('-Z','Y').to_euler()
scene.render.engine='BLENDER_WORKBENCH';scene.display.shading.light='STUDIO';scene.display.shading.color_type='MATERIAL'
scene.display.shading.show_shadows=True;scene.display.shading.show_cavity=True
scene.render.resolution_x=720;scene.render.resolution_y=900;scene.render.resolution_percentage=100
scene.view_settings.view_transform='Standard';scene.render.image_settings.file_format='PNG'
scene.frame_set(1);bpy.context.window.scene=scene
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   area.spaces.active.region_3d.view_location=Vector((0,0,.29));area.spaces.active.region_3d.view_distance=.85
   area.spaces.active.region_3d.view_rotation=cam.rotation_euler.to_quaternion()
   area.spaces.active.region_3d.view_perspective='ORTHO'
text=bpy.data.texts.new('07_R27_运动范围与限制')
text.write('R26 full assembly geometry driven by all 9,774 saved R21 free-base integration samples over 195.44175 s. R26 cover geometry is exact; motors, joints and leg lengths are unchanged. R21 dynamics were not re-solved for R26 mass. Flexible free neck wires are anchored as a display-only approximation and must not be used for clearance claims. This is an engineering replay, not physical walking approval.\n')
scene['free_neck_wire_display_approximation']=True
source={str(p.relative_to(ROOT)):sha(p)for p in [sp,ip,rp,tp,blend,Path(__file__),HERE/'blender_actual_helpers_r27.py']}
index_out=dict(status='R27_R26_ACTUAL_TRACE_REPLAY_PENDING_READBACK',scene=scene.name,part_count=len(avatar['parts']),joint_count=len(sel['joints']),source_samples=len(trace['samples']),duration_s=trace['time_s'],fps=scene.render.fps,root_object=avatar['root'].name,joint_objects={j['joint']:avatar['rigs'][j['child_link']].name for j in sel['joints']},part_objects={n:o.name for n,o in avatar['parts'].items()},source_hashes=source,physical_approved=False,manufacturing_approved=False)
(HERE/'build_index.json').write_text(json.dumps(index_out,ensure_ascii=False,indent=2)+'\n')
bpy.context.preferences.filepaths.save_version=0
out=HERE/'OpenDuck_R27_R26_四步运动回放.blend';bpy.ops.wm.save_as_mainfile(filepath=str(out),compress=True)
print('R27_REPLAY_SAVED',out,flush=True)
