# 复算和来源核验

## 小规模复核

在仓库根目录用Python 3运行：

```sh
python3 tools/verify_publication.py
python3 -m pip install -r tools/requirements-analysis.txt
python3 tools/recompute_sway.py
```

第一项逐个验证复制文件的新SHA256、本地KiCad库路径、12种板与原理图完整性。第二项使用仓库内两版实际CAD轨迹、原始固定指标合同与原始sway_metrics.py重新计算侧倾及头壳固定点横摆，核对原结论；不重跑动力学积分和全部几何配对检查。

下载Release文件后，可再执行：

```sh
python3 tools/verify_publication.py --assets /absolute/download-directory
```

仓库原生KiCad设计建议使用生成/检查记录相同的KiCad版本。每板从hardware/kicad的对应.kicad_pro打开，fp-lib-table/sym-lib-table均随板附带；完整原检查报告见docs/pcb。这里没有因上传而重新制造、缩板或清除原43项警告。

## 完整历史复算

1. 下载并校验R13.7结构包和R13.8更新包。
2. 将R13.7内“工程快照”内容（work与outputs）恢复到新的工作根目录。
3. 将R13.8内“工程更新”内容合并到同一根目录。
4. 按原始说明安装数值库、KiCad、Blender及必要外部运行环境。执行前查看脚本中的ROOT/路径；部分历史渲染或打包脚本保存了原开发机绝对路径，必须在个人工作副本中配置成本地路径，不能直接当作可移植一键流程。

精选原代码放在reference/work中，保持字节及原目录关系；这里未包含所有网格、历史状态、运行环境和中间结果，完整依赖以Release包及其索引为准。上面的便携减摆复核入口接受仓库路径，不要求原开发机路径。

原始索引放在provenance/original，均为字节原样副本。它们描述原工作根目录和原SHA，历史绝对路径仅为来源证据；不要把它们解释为GitHub链接。面向阅读的docs另做路径转换，未收进Git的历史材料链接指向Release，由原始索引定位包内文件。所有转换都记录在provenance/path-conversions.json；source-manifest.json同时保存原SHA和发布副本SHA，没有拿原SHA冒充改写后的摘要。

完整包内仍有未通过目标的候选和历史资料；判断正式基线应以原CURRENT_DESIGN.json、final_review_index.json及当前README为准。任何数值通过都不升级physical_approved/manufacturing_approved。

## 大文件策略

Git只存便于浏览和复核的源码与报告，大模型和原包使用Release资产。依据 [GitHub大文件说明](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github) 与 [Release配额](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)，仓库单文件低于100 MiB，Release每项低于2 GiB；此仓库不依赖Git LFS。
