"""Bind a fixed source-shell marker and actual R20 baseline before candidates."""
from pathlib import Path
import sys,json,hashlib,subprocess
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'work/python-deps'),str(ROOT/'work/r12-motion/python-deps'),str(ROOT/'work/rk-mechanics/python-deps')]
import numpy as np,trimesh
from sway_metrics import world_metrics,compare_actual,tracking_diagnostics
sources={}
def bind(p,h=None):
 p=Path(p);p=p if p.is_absolute()else ROOT/p;a=hashlib.sha256(p.read_bytes()).hexdigest()
 if h:assert h==a
 sources[str(p.relative_to(ROOT))]=a;return p
def read(p,h=None):return json.loads(bind(p,h).read_text())
index=read('work/r20-walking-fix/dynamics/final_delivery_index.json')
def canonical(k):r=index['canonical'][k];return read(r['path'],r['sha256'])
selection=canonical('assembly_selection');actual=canonical('actual_trace_for_CAD');reference=canonical('reference_trajectory');model=canonical('model_contract')
row=next(r for r in selection['items']if r['name']=='R11_45_top_head_shell');mesh=trimesh.load(bind(row['mesh'],row['mesh_sha256']),force='mesh');assert mesh.is_watertight and mesh.is_winding_consistent and mesh.volume>0
native=np.asarray(mesh.center_mass);home=np.asarray(row['R'])@native+row['t_mm'];assert row['link_frame']=='jaw_soft';assert np.max(abs(home-[32.15540619630929,-.002542452600427706,284.0188094768874]))<1e-8
marker=dict(name='R11_45_top_head_shell_volume_centroid',label_zh='上头壳体积中心',source_part=row['name'],source_mesh=row['mesh'],source_mesh_sha256=row['mesh_sha256'],source_part_row=row,link_frame=row['link_frame'],native_point_mm=native.tolist(),HOME_point_mm=home.tolist(),HOME_point_m=(home/1000).tolist(),closed_mesh_volume_mm3=float(mesh.volume),method='Fixed volume centroid of the original closed positively oriented upper head shell, transformed once by the source R/t into HOME. Not whole-head COM and not a changing world-space bounding box.')
contract=dict(schema='R21_FIXED_WORLD_SWAY_METRICS_V1',physical_approved=False,marker=marker,joints=selection['joints'],targets=dict(minimum_actual_roll_reduction_fraction=.4,minimum_actual_head_marker_Y_reduction_fraction=.3),coordinate_convention='Unmodified simulation world x forward, y lateral, z up. Root transforms include floor placement once. No camera/view transform. Extrinsic xyz roll/pitch/yaw.',acceptance_logic='Compare only actual baseline and actual candidate world peak-to-peak amplitudes over full completed four-step trajectories. Reference tracking and same-time/same-phase visual alignments are separate diagnostics.',required_also_report=['root_world_Y_mm','trunk_yaw_deg','trunk_pitch_deg','root_world_Z_mm','head_marker_world_X_mm','head_marker_world_Z_mm','actual completed steps and net foot forward progress','duration and foot-contact/dynamics/CAD qualification checks'],baseline_actual_trace=index['canonical']['actual_trace_for_CAD'],baseline_reference_trajectory=index['canonical']['reference_trajectory'])
baseline=world_metrics(actual,contract);reference_metrics=world_metrics(reference,contract);contract['baseline_actual_amplitudes']=baseline['metrics'];contract['absolute_sway_targets']=dict(maximum_actual_trunk_roll_peak_to_peak_deg=.6*baseline['metrics']['trunk_roll_deg']['peak_to_peak'],maximum_actual_head_marker_world_Y_peak_to_peak_mm=.7*baseline['metrics']['head_marker_world_Y_mm']['peak_to_peak'])
for p in [OUT/'sway_metrics.py',OUT/'test_sway_metrics.py',Path(__file__)]:bind(p)
contract['sources']=sources.copy();p=OUT/'metrics_contract.json';p.write_text(json.dumps(contract,ensure_ascii=False,indent=2)+'\n');bind(p)
tracking=tracking_diagnostics(actual,reference,contract)
d=dict(status='FROZEN_ACTUAL_R20_BASELINE_FOR_R21_AMPLITUDE_REDUCTION',physical_approved=False,actual=baseline,reference=reference_metrics,tracking_diagnostics=tracking,marker=marker,absolute_targets=contract['absolute_sway_targets'],self_comparison_must_not_pass=compare_actual(baseline,baseline,contract),head_COM_is_additional_metric='evidence/r20_sway_diagnosis.json uses fixed main-head COM as supplementary physical mass motion. Formal visual target uses this shell point.',sources=sources.copy());(OUT/'r20_fixed_marker_baseline.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
reg=subprocess.run([sys.executable,str(OUT/'test_sway_metrics.py')],capture_output=True,text=True);assert reg.returncode==0
(OUT/'metrics_regression.json').write_text(json.dumps(dict(status='PASS_5_REGRESSION_TESTS',returncode=reg.returncode,stdout=reg.stdout,stderr=reg.stderr,test_contract=['Improved reference tracking with identical actual sway fails amplitude gates.','Changing camera metadata cannot alter source-world metrics.','Retiming preserves amplitudes; physical-time and normalized-phase errors remain separate.','Actual roll/head world amplitude reduction passes the declared gates.','Source HOME marker transforms through its actual link before root-to-world.'],sources={str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest()for x in [OUT/'sway_metrics.py',OUT/'test_sway_metrics.py',OUT/'metrics_contract.json',Path(__file__)]}),ensure_ascii=False,indent=2)+'\n')
for name,h in sources.items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h
print(json.dumps(dict(marker_HOME_mm=home.tolist(),actual_roll_pp_deg=baseline['metrics']['trunk_roll_deg']['peak_to_peak'],actual_marker_y_pp_mm=baseline['metrics']['head_marker_world_Y_mm']['peak_to_peak'],targets=contract['absolute_sway_targets'],contract_sha256=hashlib.sha256(p.read_bytes()).hexdigest()),ensure_ascii=False))
