"""Freeze accepted R21 visual artifacts after source, curve and media verification."""
from pathlib import Path
import hashlib, json

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'work/r21-reduced-sway/visual'
OUT = BASE / 'release_v3'
def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as stream:
        for block in iter(lambda: stream.read(4*1024*1024), b''): h.update(block)
    return h.hexdigest()
def rel(p): return str(Path(p).relative_to(ROOT))
def read(p): return json.loads(Path(p).read_text())
def record(p): return dict(path=rel(p), sha256=sha(p), bytes=Path(p).stat().st_size)

def main():
    audit = read(OUT/'readback.json'); build = read(OUT/'build_index.json')
    inputs = read(OUT/'prepared_visual_inputs.json'); raw = read(OUT/'independent_raw_sway_audit.json')
    phase = read(OUT/'actual_phase_mapping.json'); phase_samples=read(OUT/'candidate_phase_display_samples.json')
    assert audit['passed'] and raw['passed']
    assert audit['purpose'] == 'FINAL_FOUR_STEP' and build['part_count'] == 557
    assert len(audit['unchanged_R20_scenes']) == 3 and len(audit['avatars']) == 5
    curve_count = sum(len(x['all_key_checks']) for x in audit['all_key_checks'])
    fk_count = sum(p['parts'] for x in audit['avatars'] for p in x['pose_checks'])
    assert curve_count == 335 and fk_count == 33420
    assert len(phase['rows']) == 30 and len(phase_samples['samples']) == 9799
    resolution = phase_samples['phase_knot_key_resolution']
    assert resolution['original_saved_samples'] == 9774 and resolution['original_saved_samples_removed'] == 0
    assert not raw['roll_target_met'] and not raw['head_marker_target_met']
    blend = ROOT / audit['source_blend_path']; assert sha(blend) == audit['source_blend_sha256']

    gate_pins = {
      'dynamics': ('work/r21-reduced-sway/dynamics/final_delivery_index.json', '870eea3b312d8aff62fb53ba9fcfb5c997413e1c4766c81f52a3a67f33970852'),
      'actual_CAD': ('work/r21-reduced-sway/geometry/actual_4steps_v3_coverage/independent_actual_geometry_review.json','81f1d694bc37761585f7e9437bdbca564bcdf82cf1fe75283badbd3a5773da1b'),
      'actual_floor': ('work/r21-reduced-sway/geometry/actual_4steps_v3_floor/index.json','178f386c58cf0f536b09f9900d6761db057cabec304355083298a6de55564642'),
      'reference_CAD': ('work/r21-reduced-sway/geometry/reference_4steps_v3_review/reference_review.json','186d914b85be9aaa067cc103ffdadb3d80a44d1451be22408a4bcecf68e32ac7')}
    gates={}
    for name,(p,s) in gate_pins.items():
        assert sha(ROOT/p)==s, ('GATE_HASH',p)
        gates[name] = record(ROOT/p)
        gates[name]['status'] = read(ROOT/p).get('status')

    videos=[]; accepted=[]; source_hashes={}
    def bind(path, expected=None):
        p=ROOT/path if not Path(path).is_absolute() else Path(path); key=rel(p)
        value=expected or sha(p)
        assert key not in source_hashes or source_hashes[key]==value, ('SOURCE_CONFLICT',key)
        source_hashes[key]=value
    accepted_paths=[OUT/n for n in ['config.json','prepared_visual_inputs.json','actual_phase_mapping.json',
        'candidate_phase_display_samples.json','build_index.json','readback.json','independent_raw_sway_audit.json',
        'R21_模型与视频查看说明.md']]
    accepted_paths += [BASE/n for n in ['frozen_baseline_source_graph_audit.json','phase_reference_mapping_v3.json',
        'comparison_timeline.py','blender_actual_helpers.py','bind_actual_phase_mapping.py',
        'prepare_visual_inputs_v3.py','build_actual_comparison.py','repair_phase_view_curves.py',
        'readback_actual_comparison.py','independent_full_sway_audit.py','render_actual_comparison_final.py',
        'render_actual_comparison_final_v2.py','encode_verified_videos.py','finalize_visual_delivery.py']]
    for mode in ['candidate_actual','same_phase']:
        rip=OUT/f'{mode}_video_render_index.json'; eip=OUT/f'{mode}_video_encoding_audit.json'
        rr,ee=read(rip),read(eip)
        assert ee['passed'] and ee['all_output_frames_decoded_without_error']
        assert ee['original_blend_unchanged_after_encoding'] and rr['source_blend_sha256']==sha(blend)
        assert len(rr['frames'])==ee['render_frame_count']==len(ee['captions'])
        assert rr['frames'][0]['display_time_s']==0
        target_end=inputs['metrics']['candidate']['duration_s'] if mode=='candidate_actual' else inputs['metrics']['baseline']['duration_s']
        assert abs(rr['frames'][-1]['display_time_s']-target_end)<1e-9
        for f,c in zip(rr['frames'],ee['captions']):
            assert f['index']==c['frame_index'] and f['actual_clocks_s']==c['actual_clocks_s']
            assert f['display_time_s']==c['display_time_s']
        vp=ROOT/ee['video_path']; assert sha(vp)==ee['video_sha256']
        videos.append(dict(**record(vp),mode=mode,frame_count=ee['render_frame_count'],
            video_duration_s=float(ee['ffprobe']['duration']),video_fps=12,
            source_display_time_extent_s=ee['full_source_time_extent_s'],
            nominal_R20_or_actual_speedup=24,candidate_phase_speed='variable by reference stage' if mode=='same_phase' else '24x except shortened final interval'))
        accepted_paths += [rip,eip,vp,ROOT/ee['subtitle_path']]
        accepted_paths += [ROOT/x['path'] for x in ee['previews']]
        for k,v in ee['sources'].items(): bind(k,v)
        for k,v in rr['sources'].items(): bind(k,v)
    # Keep the common-actual-time view as a still plus the full Blender scene.
    # Its three-frame caption-encoding helper is not an additional public video.
    accepted_paths += [OUT/'same_actual_time_probe_render_index.json', OUT/'same_actual_time_probe_encoding_audit.json', OUT/'same_actual_time_probe_已解码_0002.png']
    accepted_paths.append(blend)
    for p in accepted_paths:
        if p.suffix=='.json':
            d=read(p)
            if isinstance(d.get('sources'),dict):
                for k,v in d['sources'].items():
                    if isinstance(v,str) and len(v)==64: bind(k,v)
        bind(p)
    for p,_ in gate_pins.values(): bind(p)
    for k,v in read(BASE/'frozen_baseline_source_graph_audit.json')['sources'].items(): bind(k,v)
    # A fresh stream hash compares every accepted source to the pinned graph.
    for k,v in source_hashes.items(): assert sha(ROOT/k)==v, ('SOURCE_HASH_MISMATCH',k)
    files={rel(p):sha(p) for p in accepted_paths}
    previews=[record(OUT/'same_phase_video_已解码_0030.png'),
              record(OUT/'candidate_actual_video_已解码_0030.png'),
              record(OUT/'same_actual_time_probe_已解码_0002.png')]
    result=dict(status='FINAL_SOURCE_BOUND_SIX_SCENE_ACTUAL_VISUAL_DELIVERY',passed=True,
        primary_blend=record(blend),videos=videos,preferred_previews=previews,
        viewing_guide=record(OUT/'R21_模型与视频查看说明.md'),
        scenes=audit['unchanged_R20_scenes']+[x['scene'] for x in build['scenes']],
        actual_CAD_instances=557,unchanged_original_scenes=3,unchanged_original_objects=audit['unchanged_R20_objects'],
        actual_saved_samples=dict(R20=8744,R21=9774),phase_display_samples=9799,
        complete_curve_count=curve_count,independent_part_matrix_checks=fk_count,
        complete_key_and_geometry_readback=record(OUT/'readback.json'),
        final_blend_hash_unchanged_after_all_render_and_encode=True,
        phase_intervals=30,phase_mapping=record(OUT/'actual_phase_mapping.json'),phase_knot_display_resolution=resolution,
        actual_roll_reduction_fraction=raw['actual_roll_reduction_fraction'],
        actual_head_marker_Y_reduction_fraction=raw['actual_head_marker_Y_reduction_fraction'],
        original_targets=dict(roll_reduction_fraction=.40,head_marker_Y_reduction_fraction=.30,
                             roll_target_met=False,head_marker_target_met=False),
        metrics_computed_from='Complete raw original actual samples; no camera, phase display or cropped shared-time sequence',
        independent_nonvisual_gates=gates,
        retained_limitations=['Slow, assumed-model numerical simulation; no hardware/load/thermal/low-battery qualification',
            'Reference retains 72 legacy narrow/unproven pairs; actual retains 34 unresolved pairs',
            'Reference phase names do not assert zero actual foot force; phase view is not force-event synchronization',
            'Build/preparation PENDING wording is an immutable stage snapshot; this index binds subsequent successful readback and independent final gates'],
        media_inspection=dict(scope='Decoded candidate frames 0/30/final and phase frames 0/30/final; common-time final still',
            readable_clock_and_metric_headers=True,body_and_feet_visible=True,fixed_comparison_camera_and_equal_scale=True,
            header_is_display_only=True),
        diagnostic_artifacts='Local failed key-insertion files, prefix helper, Workbench probe, and still caption helper video are not final public artifacts',
        physical_approved=False,manufacturing_approved=False,
        file_count=len(files),files=files,source_hash_count=len(source_hashes),all_source_hashes_freshly_verified=True,sources=source_hashes)
    dest=BASE/'visual_delivery_index.json';dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('VISUAL_DELIVERY_PASS',len(files),len(source_hashes),sha(dest),flush=True)

if __name__=='__main__':main()
