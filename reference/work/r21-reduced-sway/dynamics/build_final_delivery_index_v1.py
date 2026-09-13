"""Freeze R21 physics entry after all four immutable runs and derived reports exist."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[3];D=Path(__file__).resolve().parent;W=D.parent;R=D/'full_v3';E=W/'evidence'
files={};sources={};parsed={}
def rel(p):return str(Path(p).resolve().relative_to(ROOT))
def desc(p):
 p=Path(p).resolve();key=rel(p)
 if key not in files:files[key]=dict(path=key,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size)
 return files[key]
def read(p):
 p=Path(p).resolve();x=json.loads(p.read_text());desc(p)
 for key,h in x.get('sources',{}).items():
  if isinstance(h,str) and len(h)==64:
   if key in sources:assert sources[key]==h,('CONFLICTING_SOURCE_HASH',key)
   sources[key]=h
 parsed[rel(p)]=x;return x
base=read(ROOT/'work/r20-walking-fix/dynamics/final_delivery_index.json');contract=read(E/'metrics_contract.json');assert desc(E/'metrics_contract.json')['sha256']=='6fc77c713dbdc692caf2d34c120da8de5e666172f07ca80305a191440b47af71'
canonical={k:desc(ROOT/base['canonical'][k]['path'])for k in ['assembly_selection','assembly_composition','model','model_contract','criteria','contact_geometry_equivalence','head_mass_delta','hip_mass_delta','mass_model_update_check']}
canonical.update({k:desc(p)for k,p in {
 'reference_trajectory':W/'gait/trajectory_4steps_v3.json','reference_segments':W/'gait/trajectory_segments_4steps_v3.json','reference_phase_boundaries':W/'gait/phase_boundaries_4steps_v3.json',
 'feedforward':R/'feedforward_contact4.json','controller':D/'controller_r21_v1.py','actual_trace_for_CAD':R/'nominal/dynamic_trace_for_CAD.json','actual_trajectory':R/'nominal/trajectory.json','interval_joint_bounds':R/'nominal/interval_joint_bounds.json','report':R/'nominal/report.json','acceptance':R/'nominal/acceptance.json','actual_contact_supplement':R/'nominal/actual_contact_supplement.json',
 'sway_metrics_contract':E/'metrics_contract.json','sway_comparison':R/'nominal/sway_comparison.json','sway_extended_statistics':R/'nominal/sway_extended_statistics.json','plot':R/'nominal/sway_comparison.png','actual_time_overlay':R/'nominal/sway_actual_time_overlay.png',
 'pending_electronics_mass_scope':E/'pending_electronics_mass_audit.json','independent_all_reference_static_screen':E/'independent_static/full_4steps_v3.json','double_support_static_screen':W/'gait/keypoint_both_support_static_4steps_v3.json'}.items()})
assert canonical['reference_trajectory']['sha256']=='9ae29d7be2dd7e211482bfb13ba49b2234e4ecaf782c945b46b9a944b41a7d5d'
assert canonical['reference_segments']['sha256']=='ee996121ee5e1fd0f35455ab0b462212d96fdfecd7962540a70db8ae8ff8431b'
for p in [ROOT/canonical['reference_trajectory']['path'],ROOT/canonical['reference_segments']['path'],E/'pending_electronics_mass_audit.json',E/'independent_static/full_4steps_v3.json',W/'gait/keypoint_both_support_static_4steps_v3.json',E/'metrics_regression.json',D/'pipeline_preparation.json',D/'isolation_check.json',D/'plot_full_gait_guard_check_v2.json']:
 read(p)
cases={}
for name in ['nominal','half_timestep','friction_0p5','contact9']:
 f=R/name;rp=read(f/'report.json');ac=read(f/'acceptance.json');co=read(f/'actual_contact_supplement.json');sw=read(f/'sway_comparison.json');ext=read(f/'sway_extended_statistics.json');read(f/'dynamic_trace_for_CAD.json')
 params=rp['parameters'];expected={'nominal':(.00025,.8,'4'),'half_timestep':(.000125,.8,'4'),'friction_0p5':(.00025,.5,'4'),'contact9':(.00025,.8,'9')}[name]
 assert params['dt']==expected[0] and params['friction']==expected[1];assert params['model'].endswith('current_robot_contact'+expected[2]+'.xml');assert params['imu_gain']==0
 feet=ac['feet'];metrics=dict(duration_s=rp['simulated_duration_s'],root_error_deg=ac['root_error_deg'],joint_error_deg=ac['max_joint_tracking_error_deg'],continuous_saturation_s=ac['max_continuous_saturation_s'],foot_slip_mm=max(f['maximum_stance_slip_mm']for f in feet.values()),actual_loaded_group_slip_mm=max(f['maximum_loaded_group_polygon_XY_displacement_mm']for f in co['feet'].values()),net_left_forward_mm=feet['ankle_left']['net_center_displacement_mm'][0],net_right_forward_mm=feet['ankle_right']['net_center_displacement_mm'][0],completed_steps_left=feet['ankle_left']['completed_forward_steps'],completed_steps_right=feet['ankle_right']['completed_forward_steps'],minimum_peak_swing_clearance_mm=min(g['peak_minimum_sole_z_mm']for f in feet.values()for g in f['swing_intervals']),trunk_roll_peak_to_peak_deg=sw['actual_candidate']['metrics']['trunk_roll_deg']['peak_to_peak'],head_marker_Y_peak_to_peak_mm=sw['actual_candidate']['metrics']['head_marker_world_Y_mm']['peak_to_peak'])
 cases[name]={k:desc(f/p)for k,p in {'report':'report.json','acceptance':'acceptance.json','actual_trajectory':'trajectory.json','actual_trace_for_CAD':'dynamic_trace_for_CAD.json','interval_joint_bounds':'interval_joint_bounds.json','actual_contact_supplement':'actual_contact_supplement.json','sway_comparison':'sway_comparison.json','sway_extended_statistics':'sway_extended_statistics.json'}.items()};cases[name].update(metrics=metrics,acceptance_status=ac['status'],acceptance_checks=ac['checks'],actual_loaded_contact_within_3mm=co['all_actual_loaded_groups_within_original_3mm_slip_limit'],amplitude_comparison=sw['amplitude_comparison'],parameters=params)
for p in [D/'prepare_feedforward_r21_v1.py',D/'controller_r21_v1.py',D/'analyze_run_r21_v1.py',D/'export_trace_r21_v1.py',D/'compare_sway_r21.py',D/'supplement_actual_contact_v1.py',D/'plot_sway_comparison_v2.py',Path(__file__),R/'feedforward_contact4.json',R/'feedforward_contact9.json',E/'sway_metrics.py',E/'test_sway_metrics.py',E/'r20_fixed_marker_baseline.json',E/'r20_head_sway_decomposition.json']:
 desc(p)
 if p.suffix=='.json':read(p)
original_pass=all(c['acceptance_status']=='SIMULATION_THRESHOLDS_MET'for c in cases.values());loaded_pass=all(c['actual_loaded_contact_within_3mm']for c in cases.values());positive=all(c['amplitude_comparison']['actual_roll_reduction_fraction']>0 and c['amplitude_comparison']['actual_head_marker_Y_reduction_fraction']>0 for c in cases.values());target_pass=all(c['amplitude_comparison']['both_sway_targets_met']for c in cases.values())
status='NUMERICAL_WALKING_CRITERIA_MET_WITH_REDUCED_SWAY'if original_pass and loaded_pass and positive else'NUMERICAL_REDUCED_SWAY_CRITERIA_NOT_ALL_MET'
nom=cases['nominal'];sw=parsed[rel(R/'nominal/sway_comparison.json')];b=sw['actual_baseline']['metrics'];n=sw['actual_candidate']['metrics'];ratio=sw['amplitude_comparison'];report=['R21 四步减摆数值对照','',f"名义实际自由根积分 {nom['metrics']['duration_s']:.3f} 秒，左右各迈 {nom['metrics']['completed_steps_left']} / {nom['metrics']['completed_steps_right']} 步。整机采用同一 4.195094 kg 估计质量模型和原有、未经台架实测的工程扭矩上限；未施加机身外力、焊定根节点或在积分中瞬移。",'', '| 实际全程指标 | R20 | R21 |','|---|---:|---:|']
for label,key in [('躯干 roll 峰峰值（度）','trunk_roll_deg'),('上头壳固定中心世界 Y 峰峰值（mm）','head_marker_world_Y_mm'),('根世界 Y 峰峰值（mm）','root_world_Y_mm'),('躯干 yaw 峰峰值（度）','trunk_yaw_deg'),('躯干 pitch 峰峰值（度）','trunk_pitch_deg')]:report.append(f"| {label} | {b[key]['peak_to_peak']:.3f} | {n[key]['peak_to_peak']:.3f} |")
report+=['',f"实际 roll 减幅 {ratio['actual_roll_reduction_fraction']*100:.2f}%，固定头点横摆减幅 {ratio['actual_head_marker_Y_reduction_fraction']*100:.2f}%。原优化目标仍是 40% / 30%；名义两项目标同时达到：{ratio['both_sway_targets_met']}。较小的实际改善与原目标是否达到分别报告。",'', '| 工况 | 根误差（度） | 关节误差（度） | 实际加载接触最大滑移（mm） | 连续饱和（ms） | 原四步标准 |','|---|---:|---:|---:|---:|---|']
for name,c in cases.items():
 m=c['metrics'];report.append(f"| {name} | {m['root_error_deg']:.4f} | {m['joint_error_deg']:.4f} | {m['actual_loaded_group_slip_mm']:.4f} | {m['continuous_saturation_s']*1000:.3f} | {c['acceptance_status']} |")
report+=['','图中两列使用各自真实时间和同一纵轴尺度。头点是同一上头壳闭合体积中心，固定于原 CAD 坐标；没有摄像机、显示偏移或时间对齐参与减幅计算。','',f"R20 时长 {sw['actual_baseline']['duration_s']:.3f} 秒，R21 时长 {sw['actual_candidate']['duration_s']:.3f} 秒。慢速四步诊断不等同已验收的正常行走速度。",'','计划支撑标签和零目标负载不是实测足触事件。补充接触报告按实际保存的法向力大于 2 N 重新分组，覆盖计划抬脚初期仍接触地面的情况。','', '缺安装几何的 6 块自制板及 U2D2、摄像头已由 8 个质量组计入，共 63.856284 g（含 AMP 合组扬声器）；质量、位置、惯性与安装池仍是估计/目录预留，尚未完成实际安装或称重。以后落实安装时应替换已有行并扣对应预留，不能重复增加板重。','', '这些结果只适用于冻结质量、惯性、接触和电机能力假设下的数值模型。整机 CAD 干涉、实际地板、初始化到窄站姿的可执行动作、实物装配和受载行走分别验收；本报告不批准制造或实物资格。']
md=D/'四步减摆动力学对照.md';md.write_text('\n'.join(report)+'\n');canonical['readable_report']=desc(md)
history=[{'name':name,'report':desc(D/name/'nominal/report.json')}for name in ['stance_v4_hold','prefix_v1','midtransfer_full_v1']]
for key,d in files.items():
 if key in sources:assert sources[key]==d['sha256'],('CHANGED_INDEXED_SOURCE',key)
 sources[key]=d['sha256']
for key,h in sources.items():
 p=ROOT/key;assert p.is_file(),('MISSING_SOURCE',key);assert hashlib.sha256(p.read_bytes()).hexdigest()==h,('SOURCE_HASH_MISMATCH',key)
result=dict(status=status,physical_approved=False,manufacturing_approved=False,hardware_qualified=False,canonical=canonical,cases=cases,all_original_numerical_criteria_met=original_pass,all_actual_loaded_contact_groups_within_original_slip_limit=loaded_pass,actual_roll_and_head_improve_in_all_cases=positive,predeclared_sway_optimization_targets_met_in_all_cases=target_pass,precedence=['Only full_v3/nominal is the canonical complete actual trajectory. Initial hold, one-step and mid-transfer runs are diagnostics only.','The same source marker and fixed40percent roll/30percent headY optimization targets remain unchanged, even if only a smaller positive reduction is delivered.','Actual world amplitude is distinct from joint/root reference tracking, rendering camera transforms and phase alignment.','Formal whole-CAD/floor and startup-transition review are external to this rigid-contact physics entry.','Six not-yet-mounted PCB groups plus U2D2/camera are included as inherited mass/COM assumptions; this does not prove final component installation or mass calibration.'],diagnostic_history=history,sources=sources,all_source_hashes_verified=True,files=list(files.values()),total_indexed_file_bytes=sum(d['bytes']for d in files.values()))
# History descriptions above are indexed as files but not used as final simulation evidence.
result['files']=list(files.values());result['total_indexed_file_bytes']=sum(d['bytes']for d in files.values())
p=D/'final_delivery_index.json';assert not p.exists(),'DO_NOT_OVERWRITE_FROZEN_FINAL_INDEX';p.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'path':rel(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'status':status,'source_count':len(sources),'indexed_files':len(files),'all_original_numerical_criteria_met':original_pass,'predeclared_sway_targets_met_all':target_pass},ensure_ascii=False))
