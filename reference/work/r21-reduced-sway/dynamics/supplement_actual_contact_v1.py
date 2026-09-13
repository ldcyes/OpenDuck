"""Saved numerical contact-load groups independent of planned stance labels."""
from pathlib import Path
import sys,json,hashlib,argparse
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'work/r20-walking-fix/dynamics'))
from quasistatic import StaticEvaluator,np

def diagnose(folder):
 folder=Path(folder).resolve();assert folder.is_relative_to(OUT)
 rp=folder/'report.json';tp=folder/'trajectory.json';report=json.loads(rp.read_text());trace=json.loads(tp.read_text());ss=trace['samples'];criteria=ROOT/'work/r20-walking-fix/dynamics/acceptance_criteria.json';crit=json.loads(criteria.read_text());threshold=crit['force_threshold_for_loaded_contact_N'];ev=StaticEvaluator(ROOT/report['parameters']['model'],ROOT/report['parameters']['contract']);feet={}
 for link,poly in ev.feet.items():
  local=poly-poly.mean(0);points=np.array([local@np.asarray(s['feet'][link]['rotation_world']).T+np.asarray(s['feet'][link]['outline_mean_world_m'])for s in ss]);loaded=np.array([s['foot_normal_force_N'][link]>threshold for s in ss]);planned=np.array([link in s['support_links']for s in ss]);groups=[];outside=[]
  def scan(flag):
   groups=[];i=0
   while i<len(ss):
    if not flag[i]:i+=1;continue
    j=i+1
    while j<len(ss)and flag[j]:j+=1
    displ=np.linalg.norm((points[i:j,:,:2]-points[i,:,:2])*1000,axis=2)
    groups.append(dict(start_s=ss[i]['time_s'],end_s=ss[j-1]['time_s'],sample_count=j-i,maximum_normal_force_N=max(s['foot_normal_force_N'][link]for s in ss[i:j]),max_polygon_point_XY_displacement_from_first_loaded_sample_mm=float(displ.max()),phases=list(dict.fromkeys(s['phase']for s in ss[i:j])),planned_support_sample_count=int(planned[i:j].sum())))
    i=j
   return groups
  groups=scan(loaded);outside=scan(loaded&~planned)
  feet[link]=dict(actual_loaded_contact_intervals=groups,actual_loaded_during_planned_swing_intervals=outside,maximum_loaded_group_polygon_XY_displacement_mm=max((g['max_polygon_point_XY_displacement_from_first_loaded_sample_mm']for g in groups),default=None),maximum_force_during_planned_swing_N=max((s['foot_normal_force_N'][link]for i,s in enumerate(ss)if not planned[i]),default=None))
 result=dict(status='SUPPLEMENTAL_ACTUAL_LOADED_CONTACT_DIAGNOSTIC',physical_approved=False,force_threshold_N=threshold,feet=feet,all_actual_loaded_groups_within_original_3mm_slip_limit=all(f['maximum_loaded_group_polygon_XY_displacement_mm']is not None and f['maximum_loaded_group_polygon_XY_displacement_mm']<=crit['maximum_stance_foot_polygon_point_horizontal_displacement_mm']for f in feet.values()),limits=['Groups use actual saved normal force >2 N, irrespective of planned support labels.','All samples are saved numerical states near20 ms; not every solver force iteration or physical foot sensor reading.','Force-threshold crossings split groups; short low-force gaps are reported as separate groups, with no invented sticking assumption.','This does not replace original frozen acceptance criteria, actual CAD/floor checks, or evidence of a physical startup/contact-sensing controller.','Horizontal movement is maximum source-polygon-point displacement from the first loaded sample within each group, not a full material-friction characterization.'],sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in [rp,tp,criteria,ev.model_path,ev.contract_path,Path(__file__)]})
 p=folder/'actual_contact_supplement.json';p.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'all_loaded_groups_within3mm':result['all_actual_loaded_groups_within_original_3mm_slip_limit'],'max_loaded_XY_mm':{k:v['maximum_loaded_group_polygon_XY_displacement_mm']for k,v in feet.items()}},ensure_ascii=False))
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('folder');a=ap.parse_args();diagnose(a.folder)
