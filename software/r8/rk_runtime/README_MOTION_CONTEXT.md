# 头部 HOME 与支撑上下文合同

本阶段默认 head_home_locked。单脚静力路径和腿部策略的前提是颈、头四轴及嘴保持实测 HOME。运动前，先在TorqueOff完成慢速verify/RAM准备，再连续读取真实 q/dq 与 IMU：五个头/嘴轴距实测 home 均不超过 0.5°、速度均不超过 0.03 rad/s，连续稳定至少 0.5 s；2 s 内不满足就退出并撤 RUN_REQ。最终稳定读回之后，逐轴TorqueOn前后仍核真实q/dq及IMU年龄≤100ms、STOP、租约和电源许可；遥测落盘或总线过慢导致过期会撤销启用。短周期心跳在有界启用结束后才开始，准备阶段仍受5s期限。它不会先发HOME后当作已到位，不进行未知范围的回零扫动。

启用后每个控制周期继续核查，任何头/嘴偏移、速度超限、样本陈旧超过 100 ms、重复/未来时间戳或连续采样中断会停止运动许可。高层四个头目标和嘴目标必须为零；策略四个头动作也被置零，实际头目标保持标定 home。音频驱动嘴在此模式被拒绝，离线 dry-run 仍可演示。停止或撤 RUN 不等于机器人能站稳，支持架和物理防护仍是必要条件。

只有明确确认实际双脚受支持的装配、且用该模式训练/批准的策略，才可用 --motion-context supported_double --confirm-supported-double。该模式先同样等待头与腿 HOME 稳定，随后腿保持 HOME（目标及策略十个腿动作均锁住），禁止 vx/vy/yaw/body 意图；连续监测腿 q/dq、IMU 倾斜≤5°和各轴角速度绝对值≤0.05 rad/s。此时开放 V11 保守头范围：neck[-20,+5]°、pitch±15°、yaw±15°、roll±8°，嘴0..12°，仍受实测限位、步幅及嘴0.05 Nm载荷验收限制。没有足底接触传感器，确认开关不是接触测量；软件状态明确 contact_automatically_proven=false。V18已有244个有限离散头姿态几何筛查记录；当前皮壳承托修订需重新绑定，任意连续组合及动态/物理运动仍未批准。

运行入口新增 --telemetry /tmp/microduck-r8-state.json。实时交互服务的 --runtime-telemetry 必须指向同一文件；启动时核标定，非零动作提交、播放开始前和每次租约写入都核相同 profile、标定 SHA、限位 SHA、armed 状态、≤100 ms 本机遥测以及当前上下文。失效即停止新租约。明确会话中的全零帧可用于启动握手，但不会自动无限续租；ASR/LLM 等待和意图过期仍可能使原控制环停止并关扭矩。原子状态文件不是防恶意本机进程的安全边界。

训练生成器同样接受 --motion-context，两种模式生成不同逐关节 action_scale_by_joint 与命令采样范围。head_home_locked 的四头策略 scale=0，supported_double 的十腿策略 scale=0；HOME 偏置来自同一实测标定。两种模式都保留 raw_unfiltered_network_output 作为下一次观察中的 previous_action，与固定上游 [mjlab v1.3.0 JointPositionAction](https://github.com/mujocolab/mjlab/blob/v1.3.0/src/mjlab/envs/mdp/actions/actions.py) 的 raw/processed action 分离行为一致。manifest 绑定上下文及全部 scale，旧无掩码策略或另一上下文策略会拒绝。61维观察和14维输出形状不变。

没有默认实机批准模型。模板的几何、动力学、热、供电、嘴载荷和电机能力验收仍为 false/null；实际生成烟测使用明显标识的合成输入，只证明配置和路由能生成，没有训练或物理运行。未来要在行走中自由转头，必须用新合同重新完成动态训练、完整碰撞及实机负载验收。
