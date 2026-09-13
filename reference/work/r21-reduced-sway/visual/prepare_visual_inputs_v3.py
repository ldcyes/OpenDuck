"""Freeze actual-only visual inputs and optional explicit phase display mapping."""
from pathlib import Path
import sys,json,hashlib,argparse
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE),str(ROOT/'work/r21-reduced-sway/evidence')]
import numpy as np
from scipy.spatial.transform import Rotation
from comparison_timeline import ActualSeries,phase_mapping
from sway_metrics import world_metrics,compare_actual,_series
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();sources={}
def read(path,h=None):
    path=Path(path);path=path if path.is_absolute()else ROOT/path
    actual=sha(path)
    if h:assert actual==h,str(path)
    sources[str(path.relative_to(ROOT))]=actual;return json.loads(path.read_text())
ap=argparse.ArgumentParser();ap.add_argument('--config',required=True);args=ap.parse_args()
c=read(args.config);assert c['purpose']in ['FINAL_FOUR_STEP','PREFIX_HELPER_TEST'];final=c['purpose']=='FINAL_FOUR_STEP'
out=ROOT/c['output_dir'];assert out.is_relative_to(HERE);out.mkdir(parents=True,exist_ok=True)
base=read('work/r20-walking-fix/visual/visual_delivery_index.json');static=read('work/r20-walking-fix/visual/static_build_index.json');anim=read('work/r20-walking-fix/visual/animation_build_index.json')
assert sha(ROOT/base['primary_blend'])==base['primary_blend_sha256'];sources[base['primary_blend']]=base['primary_blend_sha256']
selection=read(base['selection_path'],base['selection_sha256']);assert len(selection['items'])==557
baseline=read(base['trace_path'],base['trace_sha256']);candidate=read(c['candidate']['trace_path'],c['candidate']['trace_sha256'])
model=read(c['candidate']['contract_path'],c['candidate']['contract_sha256'])
report=read(c['candidate']['report_path'],c['candidate']['report_sha256'])
assert abs(candidate['model_mass_kg']-model['mass_kg'])<1e-10 and model['joints']==selection['joints'] and model['assembly_parts']==557
assert abs(selection['nominal_mass_kg']-model['mass_kg'])<1e-10
contract=read('work/r21-reduced-sway/evidence/metrics_contract.json','6fc77c713dbdc692caf2d34c120da8de5e666172f07ca80305a191440b47af71')
assert contract['joints']==selection['joints']
for d in [candidate,model,report]:
    for p,h in d.get('sources',{}).items():
        assert sha(ROOT/p)==h,p;sources[p]=h
if final:
    assert c.get('final_evidence'),'Full comparison requires the final verification inputs'
    for entry in c['final_evidence']:read(entry['path'],entry['sha256'])
series={k:ActualSeries(t)for k,t in [('baseline',baseline),('candidate',candidate)]}
metrics={k:world_metrics(t,contract)for k,t in [('baseline',baseline),('candidate',candidate)]}
extra={}
for k,t in [('baseline',baseline),('candidate',candidate)]:
    ss=_series(t,contract);roll=np.rad2deg(np.unwrap(Rotation.from_matrix(ss['base'][:,:3,:3]).as_euler('xyz')[:,0]))
    # Time-weighted mean avoids saved-sample density bias. Median remains labelled.
    extra[k]=dict(actual_roll_time_weighted_mean_deg=float(np.trapz(roll,ss['t'])/(ss['t'][-1]-ss['t'][0])),actual_roll_saved_sample_median_deg=float(np.median(roll)),actual_roll_absolute_max_deg=float(np.max(abs(roll))),actual_roll_initial_deg=float(roll[0]),actual_roll_final_deg=float(roll[-1]),actual_head_marker_INITIAL_world_m=ss['point'][0].tolist())
phase=None;phase_samples=None;display_times=None
if final:
    phase=read(c['phase_map']['path'],c['phase_map']['sha256']);mapping=phase_mapping(phase['rows'],series['baseline'].times[-1],series['candidate'].times[-1])
    # The R20 display clock is unchanged. Map every R21 actual key plus exact
    # phase boundaries; no saved physical sample is lost or averaged away.
    raw_times=series['candidate'].times
    raw_display_frames=np.float32(1+40*mapping.baseline_time(raw_times))
    assert np.all(np.diff(raw_display_frames)>0), 'Raw actual samples cannot share Blender keys'
    kept_knots=[];coalesced_knots=[]
    for knot in mapping.candidate_knots:
        if np.any(raw_times==knot):continue
        frame=float(np.float32(1+40*mapping.baseline_time([knot])[0]))
        near=int(np.argmin(abs(raw_display_frames.astype(float)-frame)))
        frame_gap=abs(float(raw_display_frames[near])-frame)
        if frame_gap<=.011:
            coalesced_knots.append(dict(extra_reference_knot_s=float(knot),retained_original_sample_index=near,retained_original_time_s=float(raw_times[near]),actual_time_difference_s=float(raw_times[near]-knot),mapped_frame_gap=frame_gap,reason='Preserve original actual key; an extra display-only knot cannot occupy the Blender insertion/update near-key merge tolerance; omitted extra point only, original saved key preserved.'))
        else:kept_knots.append(knot)
    real_times=np.unique(np.r_[raw_times,kept_knots])
    assert np.isin(raw_times,real_times).all()
    assert np.all(np.diff(np.float32(1+40*mapping.baseline_time(real_times)))>0)
    knot_resolution=dict(original_saved_samples=len(raw_times),original_saved_samples_removed=0,extra_knots_added=len(kept_knots),extra_knots_coalesced_with_original=coalesced_knots,max_coalesced_actual_time_difference_s=max([abs(k['actual_time_difference_s'])for k in coalesced_knots]or[0.]))
    phase_samples=series['candidate'].at(real_times);display_times=mapping.baseline_time(real_times).tolist()
    phase_path=out/'candidate_phase_display_samples.json'
    phase_path.write_text(json.dumps(dict(status='DISPLAY_RESAMPLED_REAL_INTEGRATION_NOT_NEW_PHYSICS',physical_approved=False,trace_source=c['candidate'],display_time_axis='R20 elapsed seconds; R21 actual seconds are explicitly mapped',samples=phase_samples,display_times_s=display_times,phase_rows=phase['rows'],phase_knot_key_resolution=knot_resolution),ensure_ascii=False,separators=(',',':'))+'\n')
    sources[str(phase_path.relative_to(ROOT))]=sha(phase_path)
result=dict(status='FROZEN_ACTUAL_SOURCES_FOR_VISUALIZATION',purpose=c['purpose'],candidate=c['candidate'],baseline=dict(trace_path=base['trace_path'],trace_sha256=base['trace_sha256']),selection_path=base['selection_path'],selection_sha256=base['selection_sha256'],baseline_blend=base['primary_blend'],baseline_blend_sha256=base['primary_blend_sha256'],baseline_static_index='work/r20-walking-fix/visual/static_build_index.json',baseline_animation_index='work/r20-walking-fix/visual/animation_build_index.json',metrics_contract_path='work/r21-reduced-sway/evidence/metrics_contract.json',metrics=metrics,anti_constant_tilt_metrics=extra,full_trace_sway_comparison=compare_actual(metrics['baseline'],metrics['candidate'],contract)if final else None,metrics_scope='Full raw original actual samples only; no phase resampling, camera offset or clipped comparison timeline.'if final else'Prefix-only helper test; no formal complete-gait reduction ratio is calculated.',phase_display_path=str(phase_path.relative_to(ROOT))if final else None,phase_map=phase,source_frame_rate=40,common_time_duration_s=float(min(s.times[-1]for s in series.values())),part_count=557,physical_approved=False,manufacturing_approved=False,config=c,sources=sources)
for p in [Path(__file__).name,'comparison_timeline.py']:
    path=HERE/p;sources[str(path.relative_to(ROOT))]=sha(path)
sources['work/r21-reduced-sway/evidence/sway_metrics.py']=sha(ROOT/'work/r21-reduced-sway/evidence/sway_metrics.py')
for p,h in sources.items():assert sha(ROOT/p)==h,p
(out/'prepared_visual_inputs.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print('ACTUAL_VISUAL_INPUTS_BOUND',c['purpose'],len(candidate['samples']),len(sources))
