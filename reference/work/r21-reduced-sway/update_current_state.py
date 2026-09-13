"""Promote the reviewed numerical gait; retain the unchanged R20 hardware base."""
from pathlib import Path
import hashlib, json
ROOT=Path(__file__).resolve().parents[2];WORK=Path(__file__).resolve().parent
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(1024*1024):h.update(b)
 return h.hexdigest()
def main():
 r=json.loads((WORK/'final_review_index.json').read_text());v=json.loads((WORK/'交付文件验证.json').read_text())
 assert r['review_checks_passed'] and v['passed']
 assert sha(ROOT/v['archive'])==v['archive_sha256']
 baseline=json.loads((WORK/'baseline_snapshot.json').read_text())
 for row in baseline['protected_files']:assert sha(ROOT/row['path'])==row['sha256']
 out=ROOT/v['public_folder'];model=next(x for x in r['public_artifacts']if x['path'].endswith('.blend'))
 current=dict(status='CURRENT_REDUCED_SWAY_SIMULATION_WITH_R20_HARDWARE_BASE',
              physical_approved=False,manufacturing_approved=False,normal_speed_walking_qualified=False,
              structure_revision='R20 / R13.7',motion_revision='R21 / R13.8',electrical_revision='R13 native source; 2026-09-13 read-only DRC review',
              selection_path=r['selection_path'],selection_sha256=r['selection_sha256'],
              reference_path=r['reference_path'],reference_sha256=r['reference_sha256'],
              final_review='work/r21-reduced-sway/final_review_index.json',final_review_sha256=sha(WORK/'final_review_index.json'),
              actual_trace='work/r21-reduced-sway/dynamics/full_v3/nominal/dynamic_trace_for_CAD.json',
              complete_viewer=str((out/model['destination']).relative_to(ROOT)),
              guide=str((out/'00_减摆结果与查看说明.md').relative_to(ROOT)),archive=v['archive'],archive_sha256=v['archive_sha256'],
              pcb_review='outputs/PCB_功能_DRC与尺寸复核_2026-09-13/00_PCB检查与缩板结论.md',
              predeclared_sway_targets_met=False,preparation_transition_qualified=False)
 (WORK/'CURRENT_DESIGN.json').write_text(json.dumps(current,ensure_ascii=False,indent=2)+'\n')
 doc=f'''# 当前工程状态

当前运动参考为 **R21 / R13.8 减摆步态**；结构与制造源继续采用 **R20 / R13.7**，电气继续采用当前R13原生板图。没有放行新的缩小PCB。

- [减摆结果与完整查看说明](<{out/'00_减摆结果与查看说明.md'}>)
- [完整Blender装配与实际对照](<{out/model['destination']}>)
- [R13.8步态更新包](<{ROOT/v['archive']}>)
- [全部PCB功能与主要器件](<{ROOT/'outputs/PCB_功能_DRC与尺寸复核_2026-09-13/01_全部PCB功能与主要器件.md'}>)
- [DRC与缩板评估](<{ROOT/'outputs/PCB_功能_DRC与尺寸复核_2026-09-13/00_PCB检查与缩板结论.md'}>)
- [沿用的R13.7完整结构包](<{ROOT/'outputs/R13_7_结构与步态修复.zip'}>)
- [本版来源索引](<{WORK/'CURRENT_DESIGN.json'}>)

相同557件、4.195094kg名义模型，实际身体侧倾及上头壳固定点横摆均减少约28.6%；四种工况通过原慢速四步数值检查。原40%/30%优化目标仍未达到。四步约195.44s，左右脚各两步。

参考与名义实际轨迹的全机几何检查均完成，原72对参考窄/未证和34对实际名义接口仍保留，不能据此认定整机所有装配间隙合格。未进行实物、正常步速、温升、低电量持续扭矩或制造验收。

正式四步从已检查的新准备站姿初始化；另存站姿过渡候选尚未取得同等级完整验证。6块自制PCB、U2D2与相机仍需详细安装，其已有估算质量应随真实安装替换，不能重复计重。PCB现有规则DRC为0，额外启用原忽略规则后43项警告仍逐项保留。
'''
 (ROOT/'当前工程状态.md').write_text(doc)
 print('CURRENT_STATE_PROMOTED_WITH_UNCHANGED_R20_HARDWARE')
if __name__=='__main__':main()
