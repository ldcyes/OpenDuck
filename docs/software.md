# 驱动、交互、部署与训练

本仓库包含已交付的R8软件源，实际入口是 [rk_runtime](../software/r8/rk_runtime/README_R8.md) 和 [camera_vla](../software/r8/camera_vla/README_相机与上位机VLA.md)。它们是旧R8 profile的工程软件，不代表当前R20/R21结构已经完成软件适配或实机验证。

| 用途 | 入口 |
|---|---|
| Dynamixel 15轴、IMU、电源与50Hz控制 | [microduck_rk](../software/r8/rk_runtime/microduck_rk) |
| 交互、语音与本地API | [README_INTERACTION](../software/r8/rk_runtime/README_INTERACTION.md) |
| INA226/ADS1115采样及RUN门控 | [README_POWER](../software/r8/rk_runtime/README_POWER.md) |
| RK3576 BSP、SAI1及音频 | [BSP说明](../software/r8/rk_runtime/deploy/cm4-bsp/README.md) |
| 三种电机、14策略轴的训练树生成 | [prepare_training.py](../software/r8/rk_runtime/microduck_rk/prepare_training.py) |
| 相机/VLA、人工示教和HTTP协议 | [camera_vla](../software/r8/camera_vla/README_相机与上位机VLA.md) |
| 原软件验证记录 | [R8_software_verification.json](../software/r8/rk_runtime/reports/R8_software_verification.json) |

原记录报告213项运行时测试与56项相机/协议测试，以及合成输入的固定上游训练树生成、BAM CPU路由检查。它们是历史软件边界测试；本次整理没有重新完成ARM64目标内核编译、板端加载、音频/UVC/WiFi并发、GPU训练、真实示教、实测BAM拟合或策略上机验收。

训练依赖固定上游 [microduck_rl 29e887ec](https://github.com/pollen-robotics/microduck_rl/tree/29e887ecfbf5d37144759e5a9f8a176dfb83d547)和 [BAM 62bd8ce](https://github.com/Rhoban/bam/tree/62bd8ce12154340be97e06f7f41a0ca8f116d967)。完整训练框架、Python环境、模型权重与外部服务凭据没有打进此仓库。依赖清单与生成参数见原README。所有标定模板保持null/false，没有生成新的motion_approved策略。

仅在开发机检查导入及离线测试时，从各软件目录按requirements安装依赖，再使用原测试入口。实际inspect/commission会短时开启受监督电源，commission会改电机寄存器；按原说明先完成真实台架条件，不能把它们作为普通源码验收命令。R20/R21的557件结构、关节安装、质量惯量和运动边界须重新绑定并验收。
