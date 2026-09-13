"""Independent saved-trajectory acceptance and stance/swing metrics."""
from quasistatic import *
import argparse

def analyze(folder):
 folder=Path(folder).resolve();rp=folder/'report.json';tp=folder/'trajectory.json';report=json.loads(rp.read_text());trace=json.loads(tp.read_text());s=trace['samples'];critp=OUT/'acceptance_criteria.json';crit=json.loads(critp.read_text());ev=StaticEvaluator(ROOT/report['parameters']['model']if report['parameters']['model']else MODEL,ROOT/report['parameters']['contract']if report['parameters']['contract']else CONTRACT)
 foot_reports={};force_threshold=crit['force_threshold_for_loaded_contact_N']
 for link,poly in ev.feet.items():
  local=poly-poly.mean(0);points=np.array([local@np.array(r['feet'][link]['rotation_world']).T+np.array(r['feet'][link]['outline_mean_world_m'])for r in s]);on=np.array([link in r['support_links']for r in s]);groups=[];swings=[];i=0
  while i<len(s):
   j=i+1
   while j<len(s)and on[j]==on[i]:j+=1
   if on[i]:
    loaded=[k for k in range(i,j)if s[k]['foot_normal_force_N'][link]>force_threshold]
    if loaded:
     first=loaded[0];last=loaded[-1];displ=np.linalg.norm((points[loaded,:,:2]-points[first,:,:2])*1000,axis=2);groups.append(dict(start_s=s[i]['time_s'],end_s=s[j-1]['time_s'],first_loaded_s=s[first]['time_s'],last_loaded_s=s[last]['time_s'],loaded_samples=len(loaded),max_polygon_point_XY_displacement_mm=float(displ.max()),center_delta_mm=((points[last].mean(0)-points[first].mean(0))*1000).tolist()))
   else:
    k=i+int(np.argmax([r['feet'][link]['min_z_m']for r in s[i:j]]));swings.append(dict(start_s=s[i]['time_s'],end_s=s[j-1]['time_s'],peak_minimum_sole_z_mm=s[k]['feet'][link]['min_z_m']*1000,peak_time_s=s[k]['time_s'],center_forward_change_mm=float((points[j-1].mean(0)[0]-points[i].mean(0)[0])*1000),maximum_contact_force_N=max(r['foot_normal_force_N'][link]for r in s[i:j])))
   i=j
  foot_reports[link]=dict(stance_intervals=groups,swing_intervals=swings,net_center_displacement_mm=((points[-1].mean(0)-points[0].mean(0))*1000).tolist(),maximum_stance_slip_mm=max((g['max_polygon_point_XY_displacement_mm']for g in groups),default=None),completed_forward_steps=sum(g['center_forward_change_mm']>5 and g['peak_minimum_sole_z_mm']>=2 for g in swings))
 checks={
  'completed_requested_duration':report['status']=='COMPLETED',
  'root_orientation_tracking':report['max_root_orientation_error_deg']<=crit['maximum_root_orientation_reference_error_deg'],
  'joint_tracking':max(x['max_tracking_error_deg']for x in report['actuators'])<=crit['maximum_joint_tracking_error_deg'],
  'saturation_duration':max(x['max_continuous_saturation_s']for x in report['actuators'])<=crit['maximum_continuous_actuator_saturation_s']+1e-10,
  'torque_caps_preserved':report['maximum_torque_limit_excess_Nm']<=1e-10,
  'stance_slip':all(f['maximum_stance_slip_mm']is not None and f['maximum_stance_slip_mm']<=crit['maximum_stance_foot_polygon_point_horizontal_displacement_mm']for f in foot_reports.values()),
  'two_forward_steps_each':all(f['completed_forward_steps']>=crit['minimum_completed_steps_each_foot']for f in foot_reports.values()),
  'net_forward_each_foot':all(f['net_center_displacement_mm'][0]>=crit['minimum_net_forward_each_foot_mm']for f in foot_reports.values()),
  'swing_clearance':all(f['swing_intervals']and all(g['peak_minimum_sole_z_mm']>=crit['minimum_peak_swing_sole_floor_clearance_mm']for g in f['swing_intervals'])for f in foot_reports.values())}
 bp=folder/'interval_joint_bounds.json';b=json.loads(bp.read_text());ii=b['intervals'];checks['numerical_interval_coverage']=sum(i['integration_steps']for i in ii)==b['total_integration_steps']and all(a['end_s']==z['start_s']and a['q_end_HOME_deg']==z['q_start_HOME_deg']for a,z in zip(ii,ii[1:]))
 result=dict(status='SIMULATION_THRESHOLDS_MET'if all(checks.values())else'SIMULATION_THRESHOLDS_NOT_MET',physical_approved=False,checks=checks,feet=foot_reports,root_error_deg=report['max_root_orientation_error_deg'],max_joint_tracking_error_deg=max(x['max_tracking_error_deg']for x in report['actuators']),max_continuous_saturation_s=max(x['max_continuous_saturation_s']for x in report['actuators']),sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in [rp,tp,bp,critp,Path(__file__)]})
 (folder/'acceptance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:result[k]for k in ['status','checks','root_error_deg','max_joint_tracking_error_deg','max_continuous_saturation_s']},ensure_ascii=False));print({k:{j:v for j,v in f.items()if j not in ['stance_intervals','swing_intervals']}for k,f in foot_reports.items()})
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('folder');a=p.parse_args();analyze(a.folder)
