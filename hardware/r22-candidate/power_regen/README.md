# R22 TDK Power + Regen 合板

已完成可编辑原理图、真实四层 PCB 和本地库。阶梯板面积 4510 mm²，比原 65×60 + 32×30 mm 两板总面积 4860 mm² 少 350 mm²（7.20%）。原 TDK 模块本体、四个安装孔和原 TDK 器件位置保留，回生电容采用原料号卧装，J1 因实际拔插通道冲突改为同系列 BM08 顶插。当前为工程候选，未制造，未完成热、回生瞬态、低电量或行走验收。

打开 `Microduck_Power_Regen_R22.kicad_pro`；根原理图包含 `power.kicad_sch` 与 `regen.kicad_sch`。`fp-lib-table`、`sym-lib-table` 和本地 `footprints/`、符号库随项目交付，不依赖源目录可写。原生 PCB 是本次权威结果；中间生成/路由脚本仅保留过程追踪，不能只运行早期 `build.py` 覆盖最终板。

| 内容 | 文件 |
|---|---|
| 三页可编辑原理图及浏览版 | `Microduck_Power_Regen_R22.kicad_sch`、`Schematic_R22.pdf`、`schematic_svg/` |
| 实际板图及叠层 | `Microduck_Power_Regen_R22.kicad_pcb`、同名 `.kicad_pro` / `.kicad_dru` |
| 四层铜 PDF / 前背 SVG | `PCB_Copper_R22.pdf`、`PCB_Front.svg`、`PCB_Back.svg` |
| 正背装配图 | `Assembly_Front.svg`、`Assembly_Back.svg`、相应 PNG |
| BOM、源针网及删改映射 | `BOM_R22.csv`、`Pin_to_Net_R22.csv`、`merge_mapping.json`、`equivalence_audit.json` |
| 安装/焊线/插头/孔位接口 | `Board_Interface_R22_Power_Regen.json` |
| 制造、保护、承流和验收边界 | `Validation_Report.md`、`Fabrication_Local_Clearances.json`、`Current_Thermal_Screen.json`、`DC_Copper_Regen_Loop_Final.json` |
| 验证 | `drc.json`、`erc.json`、`verification/enabled/`、`final_sha256.json` |

只在 SERVO_BUS 和 GND 上合网。保留两域 +3V3、回生 5V、内部 SHUNT / INA / 控制网络的独立性；不能据同名直接合并。主电源 INA226 地址 0x41、回生 INA226 地址 0x42、LM74800、INA300、比较器迟滞、驱动和默认关闭保持源功能。唯一 MPN 替代是有安装实形证据的 J1：SM08B → BM08B，SHR-08V-S / SSH-003T-P0.2-H 及八针网络不变。所有其他 MPN 和值均与现行 R13 两源板逐项核对。

铜图前后层统一使用原生 XY 俯视坐标便于对照；`Assembly_Back.svg`/PNG 为翻到背面后的镜像装配视图。装配精确编号、坐标和方向以 BOM 与针网表为准。
