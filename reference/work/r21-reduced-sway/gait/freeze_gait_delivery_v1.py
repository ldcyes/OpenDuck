from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[3];O=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
D=json.loads((O/'trajectory_4steps_v3.json').read_text());M=json.loads((O/'math_review_4steps_v3.json').read_text());L=json.loads((O/'load_shares_4steps_v3.json').read_text());G=json.loads((O/'stance_comparison_v1.json').read_text());BASE=json.loads((ROOT/'work/r21-reduced-sway/evidence/r20_fixed_marker_baseline.json').read_text());S=D['summary'];old=BASE['reference']['metrics'];roll=S['reference_roll_range_deg'];head=S['reference_top_shell_marker_y_range_mm'];ratio=D['duration_s']/174.84653355870492;reductions=dict(reference_body_roll_percent=100*(1-(roll[1]-roll[0])/old['trunk_roll_deg']['peak_to_peak']),reference_head_marker_Y_percent=100*(1-(head[1]-head[0])/old['head_marker_world_Y_mm']['peak_to_peak']))
assert M['trajectory_sha256']==sha(O/'trajectory_4steps_v3.json')and M['max_actual_sole_target_point_error_mm']<.01;assert S['cycle_count']==2 and S['steps_by_foot']=={'ankle_left':2,'ankle_right':2};assert L['summary']['sample_count']==S['sample_count']and L['summary']['maximum_static_allocated_utilization']<1.
note=f'''R21 保留 R20 最终557件结构、原足部和4.195093550kg名义模型，只修改站姿及步态。本入口交付四步参考、源绑定与静态载荷检查；实际自由基座仿真及全零件几何结论由总报告单独引用，不作实物制造或行走放行。

起始站姿 toe=27.974372°、bend=−16.642768°、髋/踝俯仰分配 split=8.783137°。每腿仍只有5个转动自由度，没有新增 ankle-roll。两脚各沿用6件真实源几何，支撑多边形面积质心间距由171.366602mm变为140.465952mm（缩窄18.03%），实际材料并集内缘间隙为4.633913mm；没有单独缩放脚或移动关节轴。旧探索记录中的顶点均值不能当作面积质心。

完整参考为195.441745秒、582条共同五次时标的直线q段、8399个导出样本。两脚各迈2步、各前进20mm。相对R20的174.846534秒增加{(ratio-1)*100:.2f}%；各同名阶段至少保留R20原时长，运动上限需要时才延长。末尾6个真实关节回中段各约0.29秒，总1.750271秒，phase_progress接近1不会把它们压成瞬时。

每个两步周期末q回到同一个INIT，根与双脚的完整姿态只沿世界X平移10mm；第二周期保留这一真实平移，没有根重置或把脚重新摆回起点。参考根由指定支撑足重构，实际动力学根必须保持自由。两足之间的q直线插值最大足底点偏差为0.003822mm，数值微穿不能当作TPU压缩或接触合格证据。

同参考类型比较，躯干roll峰峰从47.767778°降为33.231561°（下降{reductions['reference_body_roll_percent']:.2f}%）；正式头部点横向峰峰从265.596279mm降为183.910880mm（下降{reductions['reference_head_marker_Y_percent']:.2f}%）。正式头点为R11_45_top_head_shell闭合网格体积中心，HOME坐标[32.1554061963,−0.0025424526,284.018809477]mm。这里不是实际动态减幅结论；预设40%躯干目标尚未达到。

完整8399样本按给定load_fraction重新分配静态载荷，最大工程限幅利用率0.850007728（约85.00077%，保留数值误差）。单足支撑COP边界约8mm；R20双足分配器采用每足2mm内缩，Fz>2N的双足接触最小为1.999589mm。日志static_designated_support是假设一只脚承担全部重量，双脚换重/回中时它可超过1，不能替代真实双足负载分配。计划0负载也不表示实际已经卸载，实际接触按动力学Fz另查。

工程扭矩限幅未增加：每腿hip-yaw/hip-roll各0.90Nm、hip-pitch/knee各1.35Nm、ankle1.00Nm；neck-pitch/head-pitch各0.90Nm、head-yaw/head-roll各0.13Nm、mouth0.08Nm。它们是当前低电量设计假设下的控制限幅，不是实测连续扭矩、编码器角度或结构强度资格。

正式四步以机器人已准备好新站姿为起点。编码器q=0 HOME的有界单支撑求解没有合格解，这不是全局不可能证明。另行的R20准备站姿→R21准备站姿候选不在本入口放行，也未并入正式四步；自动启动仍需独立的几何、载荷和真实接触验证。
'''
np=O/'减摆步态说明.md';assert not np.exists();np.write_text(note)
roles={'trajectory_4steps_v3.json':'FINAL_REFERENCE_TRAJECTORY','trajectory_segments_4steps_v3.json':'EXACT_Q_SEGMENTS','phase_boundaries_4steps_v3.json':'EXACT_REFERENCE_PHASE_BOUNDARIES','trajectory_support_4steps_v3.json':'SOLE_AND_HYPOTHETICAL_SINGLE_SUPPORT_DIAGNOSTIC','math_review_4steps_v3.json':'OUTPUT_LEVEL_SOURCE_AND_MATH_CHECK','load_shares_4steps_v3.json':'ALL_REFERENCE_SAMPLES_COMMANDED_STATIC_LOAD_ALLOCATION','reduced_cycle_keypoints_v5.json':'CLOSED_TWO_STEP_CYCLE_WITH_REAL_FINAL_STANCE_BRIDGE','support_pair_v4.json':'INDEPENDENT_SUPPORT_ENDPOINTS','actual_stance_geometry_v1.json':'ACTUAL_FOOT_MATERIAL_AT_START','stance_comparison_v1.json':'AREA_CENTROID_AND_FOOT_GEOMETRY_COMPARISON','home_support_probe_v1.json':'UNQUALIFIED_HOME_START_DIAGNOSTIC','减摆步态说明.md':'USER_NOTE'}
files=[dict(path=str((O/n).relative_to(ROOT)),sha256=sha(O/n),bytes=(O/n).stat().st_size,role=r)for n,r in roles.items()];sources={str(Path(__file__).relative_to(ROOT)):sha(Path(__file__))};visited=set()
def bind(p,expected=None):
 p=Path(p);p=p if p.is_absolute()else ROOT/p;h=sha(p);key=str(p.relative_to(ROOT))if p.is_relative_to(ROOT)else str(p)
 assert expected is None or h==expected,('SOURCE_HASH_MISMATCH',key,expected,h)
 assert key not in sources or sources[key]==h;sources[key]=h
 if p.suffix!='.json'or key in visited:return
 visited.add(key)
 def scan(x):
  if isinstance(x,dict):
   for k,v in x.items():
    if k in ['sources','guard_sources']and isinstance(v,dict):
     for path,hs in v.items():
      if isinstance(hs,str)and len(hs)==64:bind(path,hs)
    else:scan(v)
  elif isinstance(x,list):
   for a in x:scan(a)
 scan(json.loads(p.read_text()))
for f in files:bind(f['path'],f['sha256'])
for p in [ROOT/'work/r21-reduced-sway/evidence/r20_fixed_marker_baseline.json',ROOT/'work/r21-reduced-sway/evidence/metrics_contract.json',O/'export_reduced_v3.py',O/'finish_cycle_v5.py',O/'screen_load_shares_v1.py',O/'verify_trajectory_v1.py',O/'describe_stance_geometry_v1.py']:bind(p)
idx=dict(status='FROZEN_R21_REFERENCE_GAIT_SOURCE_MATH_AND_COMMANDED_STATIC_LOAD_DELIVERY',physical_approved=False,manufacturing_approved=False,all_interference_or_hardware_approved=False,primary_reference=str((O/'trajectory_4steps_v3.json').relative_to(ROOT)),final_selection='work/r20-walking-fix/assembly_final/assembly_selection.json',files=files,sources=sources,summary=dict(**S,static_load_allocation=L['summary'],reference_only_reductions=reductions,duration_ratio_to_R20=ratio,foot_centroid_spacing_reduction_percent=G['foot_centroid_spacing_reduction_percent']),limitations=['Formal gait starts in the prepared R21 stance; automaticq=0HOME entry is not qualified.','Preparatory candidates and mutable preparation files are excluded from this index.','Reference shared support/root reconstruction is not a weld in the actual free-base simulation.','Dynamic and whole-assembly geometry reports are owned by their separate frozen delivery indexes.'])
p=O/'final_delivery_index.json';assert not p.exists();p.write_text(json.dumps(idx,ensure_ascii=False,indent=2)+'\n');print(len(files),len(sources),sha(p),flush=True)
