"""Independently verify raw roll and fixed-point amplitudes using scalar source FK."""
from pathlib import Path
import sys,json,hashlib,math
sys.dont_write_bytecode=True
import numpy as np
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent;OUT=HERE/'release_v3'
sys.path.insert(0,str(ROOT/'work/r18-leg-hip-covers/review'));from motion_core import transforms
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();sources={}
def read(p,h=None):
 a=sha(ROOT/p)
 if h:assert a==h,p
 sources[p]=a;return json.loads((ROOT/p).read_text())
c=read('work/r21-reduced-sway/evidence/metrics_contract.json','6fc77c713dbdc692caf2d34c120da8de5e666172f07ca80305a191440b47af71')
a=read('work/r20-walking-fix/dynamics/release_v4/runs/nominal/dynamic_trace_for_CAD.json','5d9104173386da8d4e04a4929a6cd9d98260aadf87aedf09cb42c82c9b5b0282')
b=read('work/r21-reduced-sway/dynamics/full_v3/nominal/dynamic_trace_for_CAD.json','524b29651e786bb9ef1608693a349df3e1e059f9b523fe4f5abc20e7647ba240')
formal=read('work/r21-reduced-sway/dynamics/full_v3/nominal/sway_comparison.json','d1b2e54df9375da5067cd39e6e4bdf96622bb596f757c03949d0cabb50fad2b5')
prepared=read('work/r21-reduced-sway/visual/release_v3/prepared_visual_inputs.json')
marker=np.r_[c['marker']['HOME_point_mm'],1.];out={}
for name,trace,expected in [('baseline',a,formal['actual_baseline']),('candidate',b,formal['actual_candidate'])]:
 rolls=[];Ys=[]
 for sample in trace['samples']:
  T=np.array(sample['base_transform_m']);rolls.append(math.degrees(math.atan2(T[2,1],T[2,2])))
  fk=transforms(c['joints'],sample['q_HOME_delta_deg']);home=fk[c['marker']['link_frame']]@marker;home[:3]/=1000;world=T@home;Ys.append(float(world[1]*1000))
 metrics={}
 for k,values in [('trunk_roll_deg',rolls),('head_marker_world_Y_mm',Ys)]:
  z=dict(min=min(values),max=max(values),peak_to_peak=max(values)-min(values))
  for field in z:
   assert abs(z[field]-expected['metrics'][k][field])<1e-8
   assert abs(z[field]-prepared['metrics'][name]['metrics'][k][field])<1e-8
  metrics[k]=z
 times=np.array([s['time_s']for s in trace['samples']]);mean=float(np.sum((np.array(rolls[:-1])+rolls[1:])*.5*np.diff(times))/(times[-1]-times[0]))
 assert abs(mean-prepared['anti_constant_tilt_metrics'][name]['actual_roll_time_weighted_mean_deg'])<1e-10
 out[name]=dict(saved_actual_samples=len(rolls),metrics=metrics,time_weighted_roll_mean_deg=mean)
roll_reduction=1-out['candidate']['metrics']['trunk_roll_deg']['peak_to_peak']/out['baseline']['metrics']['trunk_roll_deg']['peak_to_peak'];head_reduction=1-out['candidate']['metrics']['head_marker_world_Y_mm']['peak_to_peak']/out['baseline']['metrics']['head_marker_world_Y_mm']['peak_to_peak']
assert roll_reduction<.4 and head_reduction<.3
for p in ['work/r18-leg-hip-covers/review/motion_core.py',str(Path(__file__).relative_to(ROOT))]:sources[p]=sha(ROOT/p)
result=dict(status='PASS_INDEPENDENT_SCALAR_FK_AND_DIRECT_ATAN2_RAW_AMPLITUDES',passed=True,method='Scalar native FK for every original saved pose and fixed HOME marker; direct atan2(R21,R22) roll; no sway_metrics.py and no camera or phase-resampled series.',results=out,actual_roll_reduction_fraction=roll_reduction,actual_head_marker_Y_reduction_fraction=head_reduction,roll_target_met=False,head_marker_target_met=False,physical_approved=False,sources=sources)
(OUT/'independent_raw_sway_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print('INDEPENDENT_RAW_SWAY_PASS',roll_reduction,head_reduction)
