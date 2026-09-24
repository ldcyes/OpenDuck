# OpenDuck R27：R26 四步行走运动回放

[English](README_EN.md) · [R26 覆盖件与完整静态模型](../r26-cover-first/README.md)

本版把已保存的 R21 自由根数值积分轨迹驱动到 R26 的完整装配。时长 195.44175 s、四步、9,774 个真实保存姿态；Blender 中 1,224 项装配几何可逐件选择。视频将这段过程约 24 倍速展示。**这是 R26 外形的运动回放，不是按 R26 质量重新求解的动力学试验。**

![四步运动中段](images/mid-walk.jpg)

[完整可交互 Blender](https://github.com/ldcyes/OpenDuck/releases/download/r27-r26-four-step-replay-20260925/OpenDuck-R27-R26-four-step-replay.blend) · [四步视频](https://github.com/ldcyes/OpenDuck/releases/download/r27-r26-four-step-replay-20260925/OpenDuck-R27-R26-four-step-preview.mp4) · [工程证据包](https://github.com/ldcyes/OpenDuck/releases/download/r27-r26-four-step-replay-20260925/R27-walk-replay-evidence.zip) · [SHA256](https://github.com/ldcyes/OpenDuck/releases/download/r27-r26-four-step-replay-20260925/SHA256SUMS.txt)

运动模型新增场景 `07_R27_R26四步运动回放`，保留 R26 原有静态装配和对比场景。打开后选择场景 07，在时间轴上播放或逐帧查看；动态场景使用实际自由根和 15 个关节的保存数据，不是凭图像插值生成的任意步态。

## 干涉判断

R26 仅缩短两块大腿罩，且两块新的 STEP 实体均为旧罩实体的子集。两罩对应的旧版连续运动检查各包含 57 组动态配对，在 9,773 个积分区间内没有未解决的动态穿透；其余 1,191 项刚体零件与关节变换保持原状。因此，同一轨迹下 R26 不会比已检查的 R25 刚体装配新增穿透。旧版装配的 110 项命名安装接触沿用其逐项分类；这不等于全机器人任何姿态都没有冲突。

31 项自由颈部线束没有纳入旧刚体区间检查。视频中它们按显示用近似方式随躯干移动，不能用于判断线束在弯折、拉力和公差下的间隙。既有嘴部与下头壳约 8.75° 起的冲突仍保留；本次四步轨迹嘴部指令为 0°。

## 动力学边界

R21 原动力学模型为 4.195094 kg；R26 结构估计为 4.443060 kg，相差约 247.97 g。原轨迹的脚底接触、力矩和稳定性结果不能转写为 R26 新动力学验收。仍须以 R26 实测质量、惯量、电池电压、柔性线束和真实地面重新求解并做台架及行走验收。**本文件不授权样机上电行走。**

[运动来源与碰撞证据](verification/analysis.json) · [Blender 全部关键帧和位置回读](verification/readback.json) · [构建及检查程序](sources)
