# CM4 实际电源采样与门控

真实后端：power_io.py通过Linux I2C重复起始事务读写大端16位寄存器；GPIO使用libgpiod2字符设备，扫描DT line name，恰好找到一个MICRODUCK_RUN_REQ与一个MICRODUCK_RUN_OK才申请。输出申请时即为低，正逻辑；不硬编码gpiochip号/线偏移。ADC/电流没有模拟回退。

电气冻结合同：INA226 0x40电池、0x41舵机、0x42制动电阻支路，2mΩ Kelvin，CAL0x0A00，1mA/bit；配置0x4327，4次平均、两项各1.1ms。检查厂家/芯片ID、校准回读、转换完成与溢出。ADS1115 0x48用±4.096V/128SPS单次转换，逐次校验通道、配置与完成位；0/1/2为电池/TDK Tc点/制动板NTC，3为同一3.3V激励。ADS1115没有可供本驱动核型号的ID寄存器，BOM与实物型号仍需核验。[TI INA226资料](https://www.ti.com/lit/ds/symlink/ina226.pdf)、[TI ADS1115资料](https://www.ti.com/lit/ds/symlink/ads1115.pdf)、[libgpiod Python API实现](https://github.com/brgl/libgpiod/tree/master/bindings/python/gpiod)是接口依据。

INA三通道采样线程目标50Hz；ADS四通道扫描另起8Hz线程；独立监督线程每10ms检查电源状态/主循环心跳。100kHz共用总线下的实际排程未测，任何电流数据年龄>100ms、温度>250ms、未来时间戳、缺件/读写失败都会锁存故障并请求关电。不能用读取缓存时刻伪装采样新鲜度。温度保留原始ADC及电压，NTC比值≤0.02/≥0.98或激励不在3.1–3.5V拒绝运动。

|项目|警告/持续停止|立即停止|
|---|---|---|
|电池电压|<12.8V警告；<12.4V持续200ms|≤12.0V或>17.0V|
|舵机母线|启动须≥10.40V；<10.30V持续40ms|≤10.10V或>11.65V|
|电池电流绝对值|≥11.5A持续100ms|≥13.0A|
|舵机电流绝对值|≥10A持续200ms|≥11.5A|
|电池NTC|45°C警告|≥50°C|
|TDK Tc点NTC|65°C警告|≥75°C|
|制动散热板NTC|55°C警告|≥65°C|

上述为工程停止门槛。三个温度通道<-20°C也拒绝；独立舵机70°C及更保守的实测标定限制继续生效。RUN_OK是硬件许可，不是供电PG。硬件过流/热切断、再生泄放与紧急断能仍独立存在，软件不声称消除了响应前尖峰。

启动流程：先核已验证配置及策略SHA，RUN保持低；开启真实传感器并等待IMU收敛；请求供电后最多500ms等待RUN_OK和实际≥10.40V母线，随后给舵机200ms启动时间。接下来的无扭矩检查最多5s，之后才切入100ms主循环心跳约束并使能舵机。50Hz run每周期先校验实际供电、逐轴电流及已有姿态/租约，再发送目标。故障不会自动重新上电。异常退出及SIGTERM/SIGINT先请求RUN低，并尝试所有资源清理；关电写失败会保留为失败结果，不能报告正常完成。SIGKILL、内核卡死或GPIO硬件损坏不能由Python finally保证，必须由实测的硬件断能行为覆盖。

## 标定

config/power.template.json的所有测量值为空、measurements_verified=false。先在对应目标BSP确认GPIO命名与设备节点，再读真实原始值：

    python3 -m microduck_rk power-diagnostics --i2c /dev/实际传感器适配器

首次舵机分流器加载校准采用电气图的可拆XT30出口：物理断开功率板W3/W4到PDB的全部舵机总线，将专用电子负载转接线接W3=SERVO_BUS、W4=GND；所有Dynamixel供电必须断开。电子负载从0A开始，台架设置不超过5A。软件提供限时采集，正常RUN授权和OC链保持，不能短接保护：

    python3 -m microduck_rk bench-power-capture --i2c /dev/实际传感器适配器 --confirm-servos-disconnected --seconds 2

时长参数限0.5–5s，母线建立时间计入该期限；超过5A读数、STOP、传感器故障、过压/过温均关电。该命令没有Dynamixel对象，只按名义传感器换算取真实原始读数，返回calibrated=false/motion_approved=false，不生成批准profile。名义NTC/ADC的保护不替代独立硬件切断或台架限流，实际截止延迟须台架测量。

power-diagnostics 始终RUN低，打印calibrated=false/motion_approved=false。原始读数用于与校准仪表对比，不会生成批准配置。INA三路分别测gain/offset；ADC输入参考测gain/offset；每个NTC用25°C与60°C参考点记录Vntc/Vexc及实测上拉阻值。实现由两点解出R25和beta，再计算温度；不将厂家名义3977K冒充逐件校准。记录贴附位置、绝缘和热响应。受检配置中必须填写真实报告引用与实际I2C节点。

实测power.json的SHA及平台SHA同时写入新的calibration、dynamics和两份BAM的r8_actuator元数据；prepare_training另外读取并严格验证--power-config。策略manifest携带相同绑定，配置改动后必须重新验证/导出。测试目录的合成输入只用于软件验证，未提供motion_approved=true的R8策略或实测配置。

    python3 -m microduck_rk inspect --calibration config/calibration.template.json --power-config /absolute/measured-power.json --serial /dev/serial/by-id/实际U2D2
    python3 -m microduck_rk commission --calibration config/calibration.template.json --power-config /absolute/measured-power.json --serial /dev/serial/by-id/实际U2D2

两命令会短时开启受监督的电源，因此应按整机验收手册使用卸载/支持台架；commission只设置并回读参数，不开扭矩，退出关闭RUN。run需要完整运动标定与批准策略，示例：

    python3 -m microduck_rk run --arm --calibration /absolute/calibration.json --power-config /absolute/power.json --serial /dev/serial/by-id/实际U2D2 --policy /absolute/policy.onnx --manifest /absolute/policy.manifest.json --telemetry /tmp/microduck-r8-telemetry.json --seconds 10

另有deploy/microduck-control.service，默认单次60s、Restart=no、无开机enable目标；需实际用户组/设备权限及测量配置，人工确认支持状态和新鲜指令后才手动启动。交互服务继续默认dry-run。本机通过测试不等于CM4内核、载板、实际传感器或连续运动通过；没有新生成的行走权重。


新增再生能量通道：第三只 INA226 地址 **0x42** 测量电阻支路真实电流，2mΩ、CAL0x0A00、1mA/bit、0x4327；VBUS接舵机母线。它与0x40/41逐只标定，模板增益/零点仍null，缺少第三只会在RUN拉高前失败。不能用0x41净舵机电流推断电阻局部回路的耗能。第三路>11.65V也故障；启动必须>10.10V，运行≤10.10V立即故障（仅电阻电压采样断线/供电异常检查，不代替XM实端准入），防止其VBUS断线把耗能估成零；暂不强制比较两路异步电压差。RUN低时容许−0.1V内的小量标定偏差，积分功率钳到非负。

RegenEnergy 使用0x42自己的采样时间，积分正V×正I；每相邻采样区间取两端功率较大值，作为比梯形法保守的采样估计，不能包住采样间漏掉的短脉冲。>0.02A首次采样启动事件，≤0.02A持续1s结束；事件≥20J或滚动30s≥60J会锁存故障并请求RUN低。事件结束、检查调用和RUN关闭均不清滚动窗口；重复时间戳不重复积分，时间倒退/间隔>100ms、缺字段、显著反向电流<-0.02A拒绝，低于零的小量校准偏差不产生负能量。

历史在当前监督进程内保存；进程重启不会知道启动前的能量，不得用重启规避冷却或把该功能称跨重启能量记录。故障后依实测制动板温度和至少30s观察窗口完成冷却核验再人工重启。硬件热停独立，20J/60J只是工程保护门槛，绝非RH050的50W连续散热认证、绝对脉冲能量上界或失控时保证站稳。标定/策略/两类BAM数据均已通过更新的平台SHA要求第三测量通道，旧两通道批准文件拒绝复用。

本轮冻结窗口的唯一源码为 microduck_rk/voltage_limits.py，已进入平台SHA。首件在记录的电池电量、温度、负载下要求W3≥10.50V、每支路降压≤0.20V、每台XM实端探针≥10.30V；不能把10.20V当正常运行最低值。10.3V舵机读数允许，≤10.2V读数立即撤许可；DXL原始0.1V单位用除10换算，避免102×0.1浮点大于10.2而漏停。固件Min10.0V/Max11.8V是独立后备。当前没有稳态降功率/平衡停步策略，不满足准入必须降额重验，低压撤RUN不能声称还会站稳。10.8V±4%角落加线损不保证达到这些门槛。
