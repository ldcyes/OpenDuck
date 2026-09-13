"""Bind final visual files and verify the source graph once more before delivery."""
from pathlib import Path
import json,hashlib,subprocess
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text())
audit=read(OUT/'animation_readback_final.json');anim=read(OUT/'animation_build_index.json');static=read(OUT/'static_build_index.json');render=read(OUT/'actual_render_index.json');blend=OUT/'Microduck_R20_修订与实际行走.blend';video=OUT/'R20_实际四步_约12倍速.mp4'
assert audit['passed'] and audit['blend_sha256']==sha(blend)==render['source_blend_sha256']
assert static['selection_sha256']==anim['source_selection_sha256']
sourcechecks=[]
for p,h in anim['sources'].items():
 assert sha(ROOT/p)==h,(p,'SOURCE_CHANGED');sourcechecks.append(dict(path=p,sha256=h))
for row in render['frames']:assert sha(ROOT/row['PNG'])==row['PNG_sha256']
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(video)]));v=next(s for s in probe['streams']if s['codec_type']=='video');assert int(v['nb_frames'])==len(render['frames']);assert v['width']==v['height']==640;assert v['r_frame_rate']=='12/1';assert abs(float(v['duration'])-len(render['frames'])/12)<.001
primary=['Microduck_R20_修订与实际行走.blend','R20_整机静态.png','R20_头部新旧对照.png','R20_实际四步_约12倍速.mp4','交互模型查看说明.md','animation_readback_final.json','animation_build_index.json','static_build_index.json','static_readback.json','static_render_index.json','actual_render_index.json','visual_animation_input.json','build_static_viewer.py','audit_static_and_render.py','append_actual_animation.py','audit_actual_and_render.py','freeze_visual_delivery.py']
primary += [f'video_readback_{i:02d}.png' for i in [1,2,3]]
files={str((OUT/p).relative_to(ROOT)):sha(OUT/p)for p in primary}
# All actual frame images remain reproducible/inspectable; previews are not a geometry proof.
for row in render['frames']:files[row['PNG']]=row['PNG_sha256']
out=dict(status='FROZEN_SOURCE_BOUND_R20_557_ASSEMBLY_AND_ACTUAL_FREE_BASE_ANIMATION',primary_blend=str(blend.relative_to(ROOT)),primary_blend_sha256=sha(blend),selection_path=static['selection_path'],selection_sha256=static['selection_sha256'],trace_path=anim['source_path'],trace_sha256=anim['source_sha256'],trace_duration_s=anim['source_duration_s'],scenes=[static['main_scene'],static['comparison_scene'],anim['scene']],part_count=557,unchanged_R18_exact_mesh_count=static['unchanged_R18_mesh_count'],new_or_replaced_source_STL_count=static['new_source_STL_count'],all_saved_trace_samples=audit['all_saved_source_samples'],all_saved_key_curves=len(audit['all_saved_key_checks']),FK_pose_count=len(audit['independent_FK_pose_checks']),source_hashes_rechecked=len(sourcechecks),sources=anim['sources'],files=files,video=dict(path=str(video.relative_to(ROOT)),sha256=sha(video),frames=int(v['nb_frames']),fps=12,duration_s=float(v['duration']),nominal_time_acceleration=12,last_frame_interval_shortened=True),video_visual_review_checked_frame_indices=[0,88,175],static_readback_stage='static_readback.json is the frozen PRE_ANIMATION source stage; animation_readback_final.json rechecks all 3 scenes against the final blend hash.',limits=['No physical prototype acceptance','Saved-sample animation interpolation is display only, not continuous geometry proof','CAD self-collision checked independently from dynamics contact proxies','Flexible harnesses remain fixed HOME shapes','Manufacturing, strength, thermal, preload and physical walking qualification remain unapproved'],physical_approved=False,manufacturing_approved=False)
(OUT/'visual_delivery_index.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(index=str((OUT/'visual_delivery_index.json').relative_to(ROOT)),sha256=sha(OUT/'visual_delivery_index.json'),files=len(files),blend_sha256=sha(blend)),ensure_ascii=False))
