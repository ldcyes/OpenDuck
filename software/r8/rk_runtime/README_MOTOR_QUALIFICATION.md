# 独立电机能力资格与装机允许载荷

工程驱动表为10台XM430-W350-T、2台XC330-T288-T（髋yaw ID20/10）、3台XC330-T181-T（头yaw/roll/嘴 ID32/33/34）。两款XC330型号号分别1220与1210，不能混装或共用减速比拟合。

供应商/台架技术条件：以**独立电机夹具**承载，每个已分配ID的XM430须实测持续扭矩下界≥0.90Nm，T288须≥0.13Nm；电机端10.3V、40°C环境，保持与实际工作轨迹覆盖至少7200s，记录电压、电流、转角/速度、扭矩、机壳温度与采样时间。计入力矩测量不确定性后仍须达到下界；壳温始终≤标定运行停止温度且≤70°C。环境40°C是本工程待证实使用上限，不是厂家额定。堵转值、短时逐渐加载曲线及电流读数都不能替代此测试。

请勿用装机薄头架、头壳或嘴托承受0.90Nm能力测试。结构允许载荷、实际模式5电流/P增益/动作步幅与联合运动范围分别验证；嘴部保留独立0.05Nm载荷门槛。独立电机资格通过不改变任何命令目标、限流值或头部机械许可；从台架电流到装机设置必须重新commission/verify并绑定实测动力学、热与轨迹报告。

标定模板新增motor_capability_qualification，默认verified/independent_fixture=false，其余实测字段null。axes必须恰好包含12个指定驱动ID，逐轴model_number、demonstrated_lower_bound_Nm、tested_current_ceiling_raw与报告一致；配置raw不得超受试电流上界。该上界只是独立电机能力试验的配置包络，不证明较低装机电流还能产生0.90Nm，装机实际输出仍由已验证的模式5拟合与负载重放确定。程序同时保留既有calibrated、dynamics_verified、thermal_verified、power_verified和策略批准门禁。

需要提交：原始时间序列、量具/电源精度、夹具与散热照片、每台型号/固件/ID、试验电流与控制参数、温度位置、扭矩下界计算、完整设置和报告哈希。不得填写测试目录中的SYNTHETIC夹具作为实机批准数据。软件只检查声明字段和绑定一致性，真实报告质量由首件验收负责。

官方参考：[T288](https://emanual.robotis.com/docs/en/dxl/x/xc330-t288/)、[T181](https://emanual.robotis.com/docs/en/dxl/x/xc330-t181/)、[XM430](https://emanual.robotis.com/docs/en/dxl/x/xm430-w350/)。0.13/0.90Nm均为工程资格要求，不是本文声称的厂家保证持续额定。
