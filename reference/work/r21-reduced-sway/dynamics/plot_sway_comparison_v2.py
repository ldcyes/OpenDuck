"""Comparable world-coordinate signal plots; each column keeps its real time."""
from pathlib import Path
import sys,json,hashlib,argparse
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent;E=OUT.parent/'evidence';sys.path.insert(0,str(E))
from sway_metrics import _series,np,Rotation
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def run(folder,no_plot=False):
 folder=Path(folder).resolve();assert folder.is_relative_to(OUT)
 cp=E/'metrics_contract.json';assert hashlib.sha256(cp.read_bytes()).hexdigest()=='6fc77c713dbdc692caf2d34c120da8de5e666172f07ca80305a191440b47af71';c=json.loads(cp.read_text())
 bp=ROOT/c['baseline_actual_trace']['path'];assert hashlib.sha256(bp.read_bytes()).hexdigest()==c['baseline_actual_trace']['sha256'];tp=folder/'dynamic_trace_for_CAD.json';ap=folder/'acceptance.json';ac=json.loads(ap.read_text());assert ac['checks']['two_forward_steps_each'] and ac['checks']['net_forward_each_foot'],'FULL_FOUR_STEP_TRACE_REQUIRED_FOR_COMPARISON_PLOT'
 series={};stats={}
 for name,p in [('R20 actual baseline',bp),('R21 actual candidate',tp)]:
  s=_series(json.loads(p.read_text()),c);t=s['t'];rpy=np.rad2deg(np.unwrap(Rotation.from_matrix(s['base'][:,:3,:3]).as_euler('xyz'),axis=0));signals={**{'trunk_'+n+'_deg':rpy[:,i]for i,n in enumerate(['roll','pitch','yaw'])},**{'root_world_'+n+'_mm':s['base'][:,i,3]*1000 for i,n in enumerate(['X','Y','Z'])},**{'head_marker_world_'+n+'_mm':s['point'][:,i]*1000 for i,n in enumerate(['X','Y','Z'])}}
  series[name]=(t,signals);stats[name]={k:dict(initial_value=float(v[0]),final_value=float(v[-1]),min=float(v.min()),max=float(v.max()),peak_to_peak=float(np.ptp(v)),maximum_absolute=float(np.max(abs(v))),time_weighted_mean=float(np.trapz(v,t)/(t[-1]-t[0])),time_weighted_RMS=float(np.sqrt(np.trapz(v*v,t)/(t[-1]-t[0]))),sample_median=float(np.median(v)))for k,v in signals.items()};stats[name]['duration_s']=float(t[-1]-t[0])
 paths=[cp,bp,tp,ap,E/'sway_metrics.py',Path(__file__)];sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in paths}
 report=dict(status='ACTUAL_WORLD_SIGNAL_STATISTICS',physical_approved=False,statistics=stats,methods=['Trunk roll/pitch/yaw use the same extrinsic xyz convention as the frozen metric contract.','Time-weighted mean/RMS use trapezoidal integration over saved actual time samples; median is explicitly a sample median.','No offset, camera transform, amplitude normalization or phase warping is applied to metrics.','Separate-column plot has independent actual elapsed-time axes and identical vertical limits in each row.','Shared-time overlay plots original actual samples directly; each trace stops at its own last sample, with no extension or phase resampling.','The same contract upper-head-shell source volume centroid is the head marker; not a moving mesh bounding-box center.'],sources=sources)
 (folder/'sway_extended_statistics.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 if not no_plot:
  names=list(series);keys=['trunk_roll_deg','head_marker_world_Y_mm','root_world_Y_mm'];labels=['Trunk roll (deg)','Upper head shell marker Y (mm)','Root lateral Y (mm)'];fig,ax=plt.subplots(3,2,figsize=(12,9),sharex='col',sharey='row')
  for row,(key,label)in enumerate(zip(keys,labels)):
   allv=np.concatenate([series[n][1][key]for n in names]);lo=float(allv.min());hi=float(allv.max());pad=max((hi-lo)*.08,.5)
   for col,n in enumerate(names):
    t,signals=series[n];a=ax[row,col];a.plot(t,signals[key],color=['#596475','#117B6A'][col],lw=1.4);a.set_ylim(lo-pad,hi+pad);a.axhline(0,color='#999999',lw=.5);a.grid(alpha=.22);a.text(.02,.93,f"Peak-to-peak: {np.ptp(signals[key]):.3f}",transform=a.transAxes,va='top',fontsize=10);a.set_xlim(t[0],t[-1]);
    if col==0:a.set_ylabel(label)
    if row==0:a.set_title(n)
    if row==2:a.set_xlabel('Actual elapsed time (s)')
  fig.suptitle('Four-step free-base simulation: world motion, shared vertical scales',fontsize=14)
  fig.text(.5,.012,'Same 4.195094 kg estimated model and torque caps. Numerical comparison only; no hardware qualification.',ha='center',fontsize=9)
  fig.tight_layout(rect=[0,.035,1,.96]);fig.savefig(folder/'sway_comparison.png',dpi=180);plt.close(fig)
  fig,axes=plt.subplots(2,1,figsize=(12,7),sharex=True)
  for a,key,label in zip(axes,['trunk_roll_deg','head_marker_world_Y_mm'],['Trunk roll (deg)','Upper head shell marker world Y (mm)']):
   for col,n in enumerate(names):
    t,signals=series[n];a.plot(t,signals[key],color=['#596475','#117B6A'][col],lw=1.35,label=n)
   a.set_ylabel(label);a.axhline(0,color='#999999',lw=.5);a.grid(alpha=.22)
  axes[0].legend(loc='upper right');axes[-1].set_xlabel('Actual elapsed time (s); no resampling or phase alignment');axes[-1].set_xlim(0,max(series[n][0][-1]for n in names));fig.suptitle('Actual four-step motion on one physical-time axis')
  fig.text(.5,.01,'R20 ends at its last actual sample. Curves are not extended. Same fixed source marker and world coordinates.',ha='center',fontsize=9)
  fig.tight_layout(rect=[0,.04,1,.96]);fig.savefig(folder/'sway_actual_time_overlay.png',dpi=180);plt.close(fig)
 print(json.dumps({'duration_s':{n:stats[n]['duration_s']for n in stats},'roll_pp_deg':{n:stats[n]['trunk_roll_deg']['peak_to_peak']for n in stats},'head_Y_pp_mm':{n:stats[n]['head_marker_world_Y_mm']['peak_to_peak']for n in stats}},ensure_ascii=False))
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('folder');ap.add_argument('--no-plot',action='store_true');a=ap.parse_args();run(a.folder,a.no_plot)
