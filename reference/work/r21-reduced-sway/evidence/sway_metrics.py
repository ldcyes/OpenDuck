"""Source-fixed world amplitudes; reference tracking and phase alignment separate.

No camera/view transform is consumed. This module never alters trajectories.
"""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'work/python-deps'),str(ROOT/'work/r12-motion/python-deps')]
import numpy as np
from scipy.spatial.transform import Rotation,Slerp

def _series(trace,contract):
 samples=trace['samples'];t=np.array([s['time_s']for s in samples],float)
 if len(t)<2 or not np.isfinite(t).all() or np.any(np.diff(t)<=0):raise ValueError('NONFINITE_OR_NONINCREASING_TIME')
 base=[]
 for s in samples:
  if 'base_transform_m'in s:B=np.asarray(s['base_transform_m'],float)
  else:
   B=np.eye(4);B[:3,:3]=Rotation.from_quat(np.array(s['root_quaternion_wxyz'])[[1,2,3,0]]).as_matrix();B[:3,3]=s['root_xyz_m']
  if B.shape!=(4,4) or not np.isfinite(B).all() or np.max(abs(B[:3,:3].T@B[:3,:3]-np.eye(3)))>1e-8 or abs(np.linalg.det(B[:3,:3])-1)>1e-8:raise ValueError('INVALID_ROOT_TRANSFORM')
  base.append(B)
 base=np.asarray(base);T={'trunk_base':base};pending=list(contract['joints']);names=[j['joint']for j in pending]
 q=np.array([[s['q_HOME_delta_deg'][n]for n in names]for s in samples]);jn={n:i for i,n in enumerate(names)}
 if not np.isfinite(q).all():raise ValueError('NONFINITE_JOINT_ANGLES')
 while pending:
  ready=[j for j in pending if j['parent_link']in T]
  if not ready:raise ValueError('INVALID_JOINT_TREE')
  for j in ready:
   axis=np.array(j['axis_trunk'],float);axis/=np.linalg.norm(axis);p=np.array(j['pivot_trunk_mm'])/1000.;R=Rotation.from_rotvec(np.deg2rad(q[:,jn[j['joint']]])[:,None]*axis).as_matrix();H=np.tile(np.eye(4),(len(t),1,1));H[:,:3,:3]=R;H[:,:3,3]=p-np.einsum('nij,j->ni',R,p);T[j['child_link']]=T[j['parent_link']]@H;pending.remove(j)
 marker=contract['marker'];head=T[marker['link_frame']];point=np.einsum('nij,j->ni',head[:,:3,:3],marker['HOME_point_m'])+head[:,:3,3]
 return dict(t=t,base=base,point=point,head=head,phase=[s.get('phase','UNSPECIFIED')for s in samples])

def _amplitude(v):return dict(min=float(np.min(v)),max=float(np.max(v)),peak_to_peak=float(np.ptp(v)))

def world_metrics(trace,contract):
 s=_series(trace,contract);base=s['base'];rpy=np.rad2deg(np.unwrap(Rotation.from_matrix(base[:,:3,:3]).as_euler('xyz'),axis=0));hrpy=np.rad2deg(np.unwrap(Rotation.from_matrix(s['head'][:,:3,:3]).as_euler('xyz'),axis=0))
 signals={**{'trunk_'+n+'_deg':rpy[:,i]for i,n in enumerate(['roll','pitch','yaw'])},**{'root_world_'+n+'_mm':base[:,i,3]*1000 for i,n in enumerate(['X','Y','Z'])},**{'head_marker_world_'+n+'_mm':s['point'][:,i]*1000 for i,n in enumerate(['X','Y','Z'])},**{'head_world_'+n+'_deg':hrpy[:,i]for i,n in enumerate(['roll','pitch','yaw'])}}
 phases={}
 for p in dict.fromkeys(s['phase']):
  ids=np.array([i for i,n in enumerate(s['phase'])if n==p]);phases[p]=dict(start_s=float(s['t'][ids[0]]),end_s=float(s['t'][ids[-1]]),metrics={k:_amplitude(v[ids])for k,v in signals.items()})
 return dict(sample_count=len(s['t']),start_s=float(s['t'][0]),end_s=float(s['t'][-1]),duration_s=float(s['t'][-1]-s['t'][0]),coordinate_convention='Source world: x forward, y lateral, z up; extrinsic xyz roll/pitch/yaw. No camera transform.',metrics={k:_amplitude(v)for k,v in signals.items()},phase_summaries=phases)

def compare_actual(baseline,candidate,contract):
 b=baseline['metrics'];c=candidate['metrics'];roll=1-c['trunk_roll_deg']['peak_to_peak']/b['trunk_roll_deg']['peak_to_peak'];head=1-c['head_marker_world_Y_mm']['peak_to_peak']/b['head_marker_world_Y_mm']['peak_to_peak'];targets=contract['targets']
 rr=roll>=targets['minimum_actual_roll_reduction_fraction'];hh=head>=targets['minimum_actual_head_marker_Y_reduction_fraction']
 return dict(actual_roll_reduction_fraction=float(roll),actual_head_marker_Y_reduction_fraction=float(head),actual_roll_target_met=bool(rr),actual_head_marker_Y_target_met=bool(hh),both_sway_targets_met=bool(rr and hh),durations_s=dict(baseline=baseline['duration_s'],candidate=candidate['duration_s']),other_axis_amplitude_changes={k:dict(baseline=b[k]['peak_to_peak'],candidate=c[k]['peak_to_peak'],change=c[k]['peak_to_peak']-b[k]['peak_to_peak'])for k in ['root_world_Y_mm','trunk_yaw_deg','trunk_pitch_deg','root_world_Z_mm','head_marker_world_X_mm','head_marker_world_Z_mm']},scope='Actual world amplitudes only. Reference tracking quality, camera and retiming cannot substitute for these two gates. Stability, foot progress/slip, caps and CAD checks remain separate.')

def tracking_diagnostics(actual,reference,contract):
 a=_series(actual,contract);r=_series(reference,contract)
 def errors(ai,ri,x):
  if len(ri)==1:Rs=np.repeat(r['base'][ri,:3,:3],len(ai),axis=0)
  else:Rs=Slerp(r['t'][ri],Rotation.from_matrix(r['base'][ri,:3,:3]))(x).as_matrix()
  angle=np.rad2deg((Rotation.from_matrix(Rs).inv()*Rotation.from_matrix(a['base'][ai,:3,:3])).magnitude());return dict(samples=len(ai),maximum_root_orientation_error_deg=float(angle.max()),RMS_root_orientation_error_deg=float(np.sqrt(np.mean(angle**2))))
 ii=np.flatnonzero((a['t']>=r['t'][0])&(a['t']<=r['t'][-1]));time=errors(ii,np.arange(len(r['t'])),a['t'][ii])if len(ii)else dict(samples=0,maximum_root_orientation_error_deg=None)
 phase=[];unmatched=[]
 for p in dict.fromkeys(a['phase']):
  ai=np.flatnonzero(np.array(a['phase'])==p);ri=np.flatnonzero(np.array(r['phase'])==p)
  if not len(ri):unmatched.append(p);continue
  progress=(a['t'][ai]-a['t'][ai[0]])/max(float(a['t'][ai[-1]]-a['t'][ai[0]]),1e-15);x=r['t'][ri[0]]+progress*(r['t'][ri[-1]]-r['t'][ri[0]]);e=errors(ai,ri,x);phase.append(dict(phase=p,**e))
 return dict(time_aligned=dict(**time,method='Same elapsed physical time in common time range; no phase warping.'),phase_progress_aligned=dict(maximum_root_orientation_error_deg=max((p['maximum_root_orientation_error_deg']for p in phase),default=None),phase_results=phase,unmatched_actual_phases=unmatched,method='Same declared phase label and normalized within-phase progress. This is a diagnostic alignment, never an actual execution trace.'),scope='Root reference tracking reported separately; not used by actual-amplitude acceptance.')
