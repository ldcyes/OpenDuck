from pathlib import Path
import sys,json,hashlib
sys.dont_write_bytecode=True
E=Path(__file__).resolve().parent;ROOT=E.parents[2];sys.path.insert(0,str(E))
from sway_metrics import _series,np
cp=E/'metrics_contract.json';c=json.loads(cp.read_text());tp=ROOT/c['baseline_actual_trace']['path'];assert hashlib.sha256(tp.read_bytes()).hexdigest()==c['baseline_actual_trace']['sha256'];a=_series(json.loads(tp.read_text()),c)
rootY=a['base'][:,1,3]*1000
root_rotated_HOME=np.einsum('nij,j->ni',a['base'][:,:3,:3],c['marker']['HOME_point_m'])[:,1]*1000
head_q_correction=a['point'][:,1]*1000-rootY-root_rotated_HOME
total=a['point'][:,1]*1000;i=int(np.argmin(total));j=int(np.argmax(total));parts={'root_translation':rootY,'root_rotation_of_fixed_HOME_marker':root_rotated_HOME,'head_joint_motion_relative_to_HOME':head_q_correction}
deltas={k:float(v[j]-v[i])for k,v in parts.items()};assert abs(sum(deltas.values())-np.ptp(total))<1e-10
r=dict(status='EXACT_SAME_TWO_EXTREMA_DECOMPOSITION_NOT_SUM_OF_INDEPENDENT_RANGES',minimum_marker_time_s=float(a['t'][i]),maximum_marker_time_s=float(a['t'][j]),actual_head_marker_Y_peak_to_peak_mm=float(np.ptp(total)),contributions_between_those_same_two_times_mm=deltas,individual_component_ranges_mm={k:float(np.ptp(v))for k,v in parts.items()},method='head_worldY = root_translationY + worldY(Rroot * fixed_HOME_marker) + worldY(Rroot * (current_marker_in_trunk - fixed_HOME_marker)); all terms compared at the same two total-marker extrema.',limits=['Rotation term includes full measured-in-simulation roll/pitch/yaw coupling, not roll alone.','The separate component ranges cannot generally be added.','Head joint correction is observed numerical tracking motion, not an active head-stabilization command.','No physical weighing, inertial calibration or hardware motion measurement.'],sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in [cp,tp,E/'sway_metrics.py',Path(__file__)]})
p=E/'r20_head_sway_decomposition.json';p.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:r[k]for k in ['actual_head_marker_Y_peak_to_peak_mm','contributions_between_those_same_two_times_mm','individual_component_ranges_mm']},indent=2))
