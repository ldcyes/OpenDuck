# 嘴部双扭簧减矩研究 / Mouth counterbalance study

这是**未装入 R29 的设计研究**。[线圈空间和结构检查](CAD_REVIEW.md)只验证假定弹簧线圈体的保守包络；[解析力矩报告](TORQUE_REVIEW.md)只在保存的无弹簧轨迹上抵扣假设弹簧力矩。两者均不改变 [R29 装配清单](../../verification/assembly_selection.json)或现行 **0.05 Nm** 嘴部结构上限。

假定两只并列弹簧各采用 0.7 mm 钢丝、11.5 mm 平均圈径、3 有效圈，合计闭嘴预载 0.020 Nm。按[弹簧制造商 Gutekunst 的设计手册](https://www.federnshop.com/download/pdf/Gutekunst-Federn-1x1-2013-E.pdf)估算，双簧合成角刚度为 0.04350 Nm/rad。在四条已保存步态的每 20 ms 样本上作**事后解析抵扣**，嘴电机峰值约 0.03835 Nm。参考线圈体在 0–10° 与嘴部载体的名义连续间隙下界为 3.0581 mm。

弹簧腿、固定与转动锚点、导向芯轴、挡圈和螺钉叠层尚无可制造总成；材料强度、预载和寿命未获供应商确认，也没有带弹簧质量和闭环控制的四工况重算。因此**当前无弹簧 R29 仍因嘴部扭矩超限而阻断行走**。本目录中的 PLY 是线圈体空间包络，不能交给加工厂当作弹簧图纸。

This is an **uninstalled feasibility study**. [Coil-body clearance](CAD_REVIEW.md) omits legs and anchors; the [torque calculation](TORQUE_REVIEW.md) applies an assumed spring moment to saved unsprung samples. Neither constitutes a spring-equipped closed-loop gait or an as-built spring specification. The unsprung R29 mouth torque still exceeds its active 0.05 Nm structural limit.
