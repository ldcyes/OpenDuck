# Entry 5V R22：可编辑设计审查候选

现板 52 × 42 × 1.60 mm，四层，面积 2184 mm²；权威 R13 继承源为 65 × 45 mm，面积下降 25.33%。本目录包含实际已布线、重铺铜的原生工程，不是占位外形。未制造、未下单、未做温升/负载/EMI 实测；2.7 A 设计工作预算和 3 A 上限仍须实际供电与热验证。

## 打开与审查

- 编辑入口：`Microduck_Entry_5V_R22.kicad_pro`；同名 SCH、PCB、DRU 和本地 `footprints/`、符号库、库表一起保留。
- 板图：`preview/Entry_R22_PCB.pdf`（四铜层和正反装配层），`Entry_R22_Top.svg/.png`、`Entry_R22_Bottom.svg/.png`；原理图 PDF/SVG 同目录。
- 58 件 BOM、物理针脚网名：`assembly/`；完整机械接口：`Board_Interface_R22_Entry.json`。
- 主验收记录：`verification/electrical_equivalence.json`、`ERC.json`、`DRC_original_rules.json`、`DRC_all_rules_enabled.json`、`DRC_fabrication_rules.json`。
- 电源压降以 `verification/DC_New_vs_Source_Final.json` 为准；中心线简化筛查仅作路径诊断。热场景和原生铜面积在 `power_copper_thermal_audit.json`。
- `DELIVERABLE_SHA256.json` 列最终审查文件摘要。`verification` 其余带 candidate、seed、routing、before、post 等名称的中间记录仅为诊断历史，不是放行结果。

## 电路等价与明确变更

源为 `work/r13-electronics/inherited/Entry_5V_R8/` 现行 SCH/PCB，未覆盖。58 个位号、200 个数字铜焊盘实例、159 个原理图物理针脚逐项比对等价；全部值和全部 IC 型号保留。8 个逻辑/传感插头、8 个电源焊线端、四端 WSL27262L000FEA 2 mΩ 分流器、0448002.MR 2 A 保险、保护与阈值不变。

为解决实机颈轨及头壳的出线、弯线和拔插空间，已授权将 J3/J5/J6/J7/J8 改为同族真正顶插 BM02/BM08/BM03/BM03/BM05B-SRSS-TB(LF)(SN)。J1/J2/J4 继续侧插 SM02/SM02/SM10。新 BM 焊盘、固定脚、Fab、方向、料号均在 SCH/PCB/BOM/接口中显式替换；仍用对应 SHR 壳和 SSH 端子，逐针网名完全相同。[JST SH 原厂图](https://www.jst-mfg.com/product/pdf/eng/eSH.pdf)

U1/U2 使用 TI DGS0010A 原厂推荐的 1.45 × 0.30 mm 焊盘、0.50 mm 节距、4.40 mm 行中心距，取代通用库的 0.35 mm 宽盘。器件本体、机械包络、料号和针号保持；本地封装名为 `TI_DGS0010A_Manufacturer_1p45x0p30`。原厂尺寸截图见 verification。[INA226](https://www.ti.com/lit/ds/symlink/ina226.pdf)、[ADS1115](https://www.ti.com/lit/ds/symlink/ads1115.pdf)

## 制造与机械接口

名义对称叠层为 F.Cu 0.070 / PP 0.185 / In1.Cu 0.035 / Core 1.000 / In2.Cu 0.035 / PP 0.185 / B.Cu 0.070 mm，两面阻焊各 0.010 mm，总计 1.600 mm。此为工程叠层提案；成品厚度、公差、2 oz 最小成品铜厚、25 µm 孔铜及填孔盖铜工艺需厂家按实际报价确认。In1 为 GND 参考层，未布置信号走线；In2 承担信号与局部电源铜。

保留原项目尺寸规则并仅加严 DRU：全局铜距 ≥0.16 mm、新线宽 ≥0.20 mm、Zone 铜距 ≥0.205 mm。严格全局 0.20 mm 的附加诊断只剩四处 0.175 mm 的局部过孔—逃线间距，见 `DRC_nominal_0p20.json`，没有 Zone 间距违规。分别为 I2C_SDA 过孔 (45.3,7.5)、两个 LOGIC_VIN 过孔 (10.6,23.7)/(10.6,24.7)、GND 过孔 (17.3,15.5)。这些必须作为真实 2 oz 制造约束告知厂家，未降低规则隐藏。0.175 mm 高于厂家公布的 0.16 mm 下限。[JLCPCB 铜厚能力](https://jlcpcb.com/help/article/jlcpcb-copper-weight)

四个 Ø2.2 mm 安装孔中心为 (3,3)、(23,3)、(3,39)、(49,39) mm。机械父装配姿态保持 R=[[1,0,0],[0,0,-1],[0,1,0]]，t=[−3,−8,259]，jaw_soft；孔位/器件姿态均以 JSON 为准。正面真实最大高 13.0 mm（C11），C18 最大 12.7 mm；背面 C14/C15 最大 2.7 mm。5 mm PEEK 柱名义留下 2.3 mm 背件至铝架距离，柱、螺钉、垫圈和工具空间由整机机械审查另核。

BM 配对总高原厂约 6.3 mm，采用 6.5 mm 预算，保留 +Z 方向 5 mm 直出、R5 弯线和 8 mm 拔插空间。J5 最终中心 (33.4,4.0)；其余接口均已冻结。8 个焊线端使用 Ø6 mm 铜盘、Ø2.4 mm 孔，正反各 7×7 mm 工艺 courtyard；不能将焊线和焊锡过程包络当作零厚度点。正面已加 W1–W8 与正负极丝印。

## 电源铜、压降与热边界

重铺后 U3 PGND14/15/18 位于同一块顶层连续地铜；AGND 独立，SW 只在模块引脚间局部连接，无 SW 过孔或外引铜区。保留四层地铜，未删地以获取 DRC 通过。模块 PGND 和 VOUT 各 10 个 Ø0.45/0.20 mm 热/电流孔，MUX 四组各 4 个并联孔；涉及盘内孔要求填孔盖铜。铜面积不是有效散热面积。[LMZM33603 布局/热要求](https://www.ti.com/lit/ds/symlink/lmzm33603.pdf)

实际原生铺铜、焊盘、走线和贯穿孔提取后，用同一铜电阻率、温度系数和 25 µm 孔铜假设对比。过孔沿周向 32 扇区分布连接各铜层；源/目标盘为理想等势端子，焊点/触点/线束另计。电源路径采用 0.05/0.025 mm 网格，地回流采用 0.10/0.075 mm；新板细网格变化不超过 2.5%，地回流不超过 0.6%。四个解析基准（均匀铜片和单孔/四孔）通过，但这不构成实际电热验证。

| 完整板内回路（含地） | 源 R20 | R22 R20 | 改善 |
|---|---:|---:|---:|
| MOBILE：U3 → MUX 输入、MUX 输出 → W7、W8 → PGND | 21.290 mΩ | 10.502 mΩ | −50.67% |
| BENCH：W5 → MUX 输入、MUX 输出 → W7、W8 → W6 | 13.084 mΩ | 6.933 mΩ | −47.01% |

其中 MUX 本身另按 33 mΩ 最大值（−40…105°C，5 V/3.3 V 表项）计入，绝不采用典型 18.5 mΩ。LMZM VFB 全温最低 0.98 V、41.0k/10.0k 电阻各初始 ±0.1% 得分压下限 4.98997 V；再计两个电阻独立 ±25 ppm/K、80 K 温差后为 4.97396 V。[TPS2117](https://www.ti.com/lit/ds/symlink/tps2117.pdf)、[Yageo 电阻规格](https://www.yageogroup.com/component-documentation/download/specsheet/RT0603BRD0710KL)

以铜温 105°C、有效铜截面只有名义 80%、另加 5% 数值模型余量作工程筛查，2.7 A 的板端电压约 4.835 V，3 A 约 4.820 V，尚未扣纹波、动态额外下陷及外部线束/触点。TI 的 10 mVpp 纹波和 0.04% 负载调整率均仅为典型，没有可据此保证的最大值。若实测满足纹波 ≤50 mVpp、额外动态下陷 ≤20 mV，2.7 A 外部总回路电阻仍须低于约 14.9 mΩ；3 A 约 8.3 mΩ。该条件是验收预算，不是已验证能力。

BENCH 5 V±5% 电源若落到 4.75 V，经过任何正压降后都不能保证负载 4.75 V；源板同样存在此边界。2.7 A 时仅板铜与 MUX 就要求 W5/W6 输入约 ≥4.872 V，纹波/动态/线束还需另加，详 JSON。

LMZM 3 A 是器件额定上限，四层本身不能证明封闭头壳可持续输出 3 A。热报告列效率 85/90/93%、有效热阻 25/35/45 K/W 与 50°C 环境的场景；原厂 63×63 mm 四层 2 oz 的 18.9 K/W 不直接套用。须实测最低电池电压、2.7 A 工作及 3 A 峰值的 W7/W8 电压、纹波、温升、保护及切换；2 A 输入保险还要核启动浪涌与温度降额。主 3.8 mm 电池通道和 2 mΩ 分流器的损耗不能由上游 15 A 保险标称推定持续载流通过。

## 可重复工具链

KiCad 10.0.6，`work/tooling/kicad-python` 与 `work/tooling/kicad-cli`。在原 workspace 中，最终 PCB 可由 `build_entry.py` → `apply_routes.py`（读取已审查 routes.json）→ `finalize_labels.py` 重建，随后重铺铜/DRC/接口/网表等价导出。`prepare_routes.py`/`route_entry.py` 是探索布局的路由工具；重跑路由会生成新候选，必须重新审查。`augment_power.py`、`finalize_routes.py` 等为废弃诊断尝试，不属于最终重建顺序。

DC 求解脚本 `solve_dc_copper.py` 提供 `solve(d, net, src_pins, dst_pins, grid_mm)`，只读 native 几何 JSON。使用系统 Python 的 numpy/scipy 和 shapely2，建议 OPENBLAS_NUM_THREADS=1、OMP_NUM_THREADS=1。`.deps` 是本地运行缓存，不是设计交付依赖。源文件 SHA 和最终文件 SHA 已记录；没有修改任何原源文件。
