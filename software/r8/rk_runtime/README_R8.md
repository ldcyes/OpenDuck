# R8 混合驱动、交互与训练软件

本目录运行于 Radxa CM4 RK3576 V1.20，舵机名义轨10.8V。驱动为10×XM430-W350-T、2×XC330-T288-T、3×XC330-T181-T；R1–R7保持冻结。交互文字、按键录音、HTTP语音网关、播放嘴包络及相机/VLA/人工示教客户端均有可执行入口。**未提供已批准的R8低层或VLA权重，标定模板不能启动运动。**

- [交互、语音与本地API](README_INTERACTION.md)
- [真实HOME与支撑模式](README_MOTION_CONTEXT.md)
- [相机/VLA与人工示教](../camera_vla/README_相机与上位机VLA.md)
- [INA/温度/RUN电源闭环](README_POWER.md)
- [CM4实际BSP与SAI1部署](deploy/cm4-bsp/README.md)

## 控制和门禁

microduck_rk/__main__.py的50Hz循环是Dynamixel唯一写入者：15轴实测q/dq、真实SFLP姿态组成61维观察，ONNX输出14维动作，嘴ID34独立。microduck_interaction/executor.py在独立线程合并有限会话/动作/播放；LLM、ASR、TTS、相机和上位机推理在独立进程等待，不阻塞控制周期。计算、目标发送、原子遥测及日志均计入20ms期限；过期或异常结果不发送。

固定映射：ID21/22/23/24/11/12/13/14/30/31为XM430 model1020，ID20/10髋yaw为T288 model1220，ID32/33/34为T181 model1210。XM固件至少45、XC至少46；旧固件可inspect，但不读不支持的Startup Configuration(60)。commission先关全体扭矩，预查全体型号/固件/扭矩状态后才写EEPROM；60清零并立即回读，Drive Mode(10)=0防止目标写入自动开扭矩。

电流配置采用mA：XM向下除2.69，XC除1。300mA初值分别写111raw=298.59mA与300raw；当前配置上限XM2000mA、XC300mA是工程允许范围，不是持续能力保证。改变配置会改变驱动SHA，旧策略拒绝复用。Present Current不相加冒充电池电流，轨电流由独立INA读取。

启用先在TorqueOff下完成慢速型号/寄存器核对及RAM准备，再连续采集至少0.5s稳定HOME。最终实际q/dq及IMU必须仍在100ms时效内；逐轴开扭矩前后重复核STOP、租约、电源许可和样本时效。部分启用失败向全部15轴尝试TorqueOff，外层先撤RUN。短周期心跳在有界启用完成后开始，准备阶段仍受5s电源期限保护。启动不进行盲目回零扫动。

head_home_locked默认持续锁住四个头轴与嘴，实际偏移或速度超限便退出，策略/交互/音频不能绕开。supported_double须确认真实双脚受支持，并使用该模式批准策略；锁住十个腿轴，拒绝速度/body意图，才开放头部互动。无足底接触传感器，软件不会将模式开关当作接触证明。

头范围统一来自motion_limits.py：neck[-20,+5]°、head_pitch±15°、yaw±15°、roll±8°，嘴绝对0..12°且home=0。标定只能收紧。V18已有244个有限离散头姿态几何筛查记录；它不证明任意连续组合或实体运动，正在修订的头壳承托需重新绑定几何证据。当前单脚静力路径固定头/嘴HOME。动态行走中自由转头必须重新训练及验证；新安装相位必须重新量测编码器零点。

嘴独立结构载荷上限0.05Nm。motion标定和直接enable均要求mouth_load_acceptance记录全行程、受阻瞬态、实际电压/温度及电流/P增益/步幅包络；初始300mA不能推定满足力矩限制。电机资格另见README_MOTOR_QUALIFICATION.md：10XM≥0.90Nm、2T288≥0.13Nm，实端10.3V、40°C环境、7200s、壳温≤70°C，是独立电机夹具上的待验收要求，不是厂家持续额定，也不授权薄头架承担0.90Nm。

低压、过热、电流、姿态、STOP、失去RUN_OK、过期租约或周期超时会撤许可并退出。关电/关扭矩会失去支撑，**不等于自动站稳**。Python100ms心跳不能保证内核挂起或GPIO ioctl永久阻塞也必断电，独立硬件保护与实体支持仍必要。

## 标定与部署

Linux Python3.10+，依赖见requirements.txt。配置真实power.json中的Linux设备路径，不能从I2C8名称猜/dev/i2c-8。目标固定BSP使用SAI1及sai1m0、J1.19/.25/.27/.29；MicroduckAudio固定48kHz/S32_LE/双声道。DTS已实际编译、31项回读，三个音频模块已对AMD64 Linux6.8头文件编译；精确ARM64 6.1.84目标完整内核/Module.symvers和交叉工具链不足，目标编译、加载、双工录放与UVC/WiFi并发未通过。详见deploy/cm4-bsp证据，旧ZERO3W设备树不能用于本板。

在支持架上分配唯一ID/1Mbps后，从config/calibration.template.json建立新标定。零点、方向、实际行程、步幅、P增益、IMU安装与质量/惯量都必须量测，不能把旧raw home或工程质量算例当实测。所有模板物理批准项仍false/null。

    python3 -m microduck_rk inspect --calibration config/calibration.template.json --power-config /absolute/measured-power.json --serial /dev/serial/by-id/实际U2D2
    python3 -m microduck_rk commission --calibration config/calibration.template.json --power-config /absolute/measured-power.json --serial /dev/serial/by-id/实际U2D2

inspect会开启受监督电源进行读取；commission写电机配置但保持关扭矩。退出撤RUN。这些命令不表示完成标定或可以承重。run另要求显式--arm、实测供电/热/运动报告、匹配策略manifest和CPU预检。

电压准入为指定电量/温度/负载下W3≥10.50V、支路线损≤0.20V、每台XM探针实端≥10.30V。启动W3≥10.40V；运行W3<10.30V持续40ms或≤10.10V立即停，舵机读数≤10.2V停，10.3V正常；固件10.0–11.8V是后备窗口。TDK±4%与线损并不能保证每个容差角落10A正常，不满足就降低准入负载并重验；未实现受控平衡降功率策略。

相邻camera_vla已绑定R8 profile、限位SHA、实测标定、模式、OS05A10图像方向；实际采集、上传、响应检查和人工示教代码可运行，VLA仍经此唯一本地执行器。新权重与真实示教尚未提供。服务默认dry-run，统一/tmp/microduck-r8-command.json、/tmp/microduck-r8.STOP及/opt/microduck-r8部署路径。

## 三型号、逐轴BAM训练

prepare_training已接通三份独立真实拟合文件，而不是把14轴全部套进XL330/单XC330默认BAM。生成树内注册microduck_r8_xm430、microduck_r8_xc330和microduck_r8_xc330_t288三种自定义电机；10个XM430、2个髋yaw T288和2个头部策略T181分别匹配准确关节名，每轴独立实例、P增益和等效限流。第3个T181是嘴，不进14维策略。T288减速比不同，不能沿用T181的BAM拟合。

采用固定上游microduck_rl提交29e887ecfbf5d37144759e5a9f8a176dfb83d547及其uv.lock中的[BAM 62bd8ce](https://github.com/Rhoban/bam/blob/62bd8ce12154340be97e06f7f41a0ca8f116d967/bam/mjlab.py)。自定义JSON使用BAM的m6格式，kt、R、armature、摩擦参数和error_gain必须全部提供有限的测量拟合值；已有XL330默认名会被拒绝。每轴effective_current_limit_A是对模式5实测响应识别得到的**模型等效参数**，不直接等于目标raw或标称供电电流。必须在该关节实际P增益、目标电流、10.8V轨、速度和热条件下做独立holdout验证。

准备输入：

1. 新实测标定文件及报告。
2. config/dynamics.template.json：实际R8刚体质量/质心/惯量、几何通过记录、14轴对应型号/goal_current_raw/P增益/等效限流、终端电压与延迟范围、三份BAM SHA256。默认全为空值/false，不以旧1.25kg目标或旧网格体积替代。
3. config/bam_xm430.template.json、bam_xc330.template.json和bam_t288.template.json：分别用真实拟合结果填写，不能用本目录测试夹具。
4. 真实R8模型目录，含robot_walk.xml、robot_groundcontact.xml、robot_allcollisions.xml、所需网格；每份XML策略关节顺序必须与14轴ABI一致，每个inertial刚体都必须在dynamics中有测量数据。

    python3 -m microduck_rk.prepare_training \
      --upstream /absolute/pinned-microduck-rl \
      --output /absolute/new-r8-training-tree \
      --calibration /absolute/r8-calibrated.json \
      --dynamics /absolute/r8-measured-dynamics.json \
      --power-config /absolute/measured-power.json \
      --bam-xm430-json /absolute/xm430-fit.json \
      --bam-xc330-json /absolute/xc330-t181-fit.json \
      --bam-t288-json /absolute/xc330-t288-fit.json \
      --robot-model-dir /absolute/r8-mjcf

生成前校验三模型哈希和14轴映射，输出已存在时拒绝覆盖。生成树带R8_TRAINING_INPUTS.json与适配器；用该固定上游README的uv sync --frozen（Python3.12）及train入口训练Mjlab-Velocity-Flat-MicroDuck。训练和MuJoCo-Warp GPU尚未运行。只这一任务进入本交付合同，其他上游翻滚/滑轮/起身模型没有因此获得R8适配验收。

低层command delay以实际物理步长计数；高层VLA图像/网络延迟、意图到期停顿和ASR等待需另外进入任务随机化/回放。各关节电压/支路压降随机化是终端不确定性模型，并非完成了公共10.8V稳压器、BMS与再生能量耦合仿真，必须用实测holdout确认它覆盖实际工况。

导出ONNX后：

    python3 -m microduck_rk.make_manifest --training-inputs /absolute/new-r8-training-tree/R8_TRAINING_INPUTS.json --policy /absolute/policy.onnx --checkpoint /absolute/checkpoint.pt

新manifest默认motion_approved=false。仅有ONNX shape61→14不够：R8 robot、固定驱动profileSHA、每轴配置SHA、标定SHA、实际策略SHA及验证报告均需匹配。R1/R3权重不能直接启用。

## 验证和交付边界

在rk_runtime目录执行python3 -m unittest discover -s tests -v，最新结果与来源SHA见reports/R8_software_verification.json和R8_source_sha256.json；camera_vla有独立协议/HTTP/示教回归报告。R3历史报告单独归档，不计作R8硬件通过。

已在实际固定上游树上完成明确标注的合成输入整树生成、AST检查和固定BAM CPU核心三模型路由验证。这证明软件配置与接口可以执行，不是实测电机拟合、GPU训练、RK运行或连续行走。电源INA/ADS/GPIO实际适配代码和故障逻辑已实现，物理系数未填，不能用测试夹具批准profile。

4S1P Molicel M50A典型72Wh、数据表最低能量合计69.2Wh。假设仅70%可用时为48.44Wh；1h/2h分别要求全机电池端平均功率不超过48.44/24.22W。70%及全机实际功耗均未验证，续航仍是目标，不能由3.46kg工程质量、静力或电机名义参数保证。实测方案和计算见../../驱动/审查/运行许可与续航复核。

[XM430官方控制表](https://emanual.robotis.com/docs/en/dxl/x/xm430-w350/)、[XC330官方控制表](https://docs.robotis.com/docs/dxl/model_reference/x_series/xc_series/xc330-t181/)为型号、寄存器和单位依据；[M50A V1.4数据表](https://www.molicel.com/wp-content/uploads/INR21700M50A_1.4_Product-Data-Sheet-of-INR-21700-M50A-80097.pdf)为电芯能量依据。
