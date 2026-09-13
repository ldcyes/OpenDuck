# Radxa CM4 R8 接口接入记录

模组基线为Radxa CM4 RK3576 V1.20。下列连接来自电气代理对官方原理图p6/p18/p21/p23的核对；实际 BSP 引脚和驱动适配现已写入 cm4-bsp/，基于固定官方 rk2410 内核完成 DTC 和 PC 模块编译。目标板加载与物理运行仍未测试。

|用途|模组信号/物理引脚|软件边界|
|---|---|---|
|音频时钟|SAI1_M0：J1.19 LRCK、J1.25 BCLK|48kHz、S32_LE、2通道，共64fs帧|
|音频数据|J1.27 RX/SDI0、J1.29 TX/SDO0|输入/输出ALSA设备均由部署配置提供|
|可选主时钟|J1.23 MCLK|现音频器件不要求连接|
|音频电平|R101接3.3V、R100不装|不能套用旧ZERO3W引脚表|
|传感器总线|I2C8_M1：J3A.58 SDA、J3A.56 SCL|启动100kHz；Linux适配器号不得据名称推断为8|
|GPIO参考电压|J3A.78 GPIO_VREF绑模组3.3V|模组R188/R189已有2.2k上拉，载板勿任意重复|
|IMU|LSM6DSV16X地址0x6A|现运行时使用真实SFLP数据，设备路径必须显式指定|
|电源测量|INA226 0x40电池、0x41舵机轨、0x42制动电阻支路；ADS1115 0x48温度|实际驱动与故障逻辑已实现，原始数据与校准步骤见../README_POWER.md|
|RUN门控|J3A.30 GPIO1_C1 RUN_REQ；J3A.28 GPIO1_C4 RUN_OK|有效高，libgpiod2按MICRODUCK_RUN_REQ/OK名称操作；RUN_OK是许可，不是PG|
|U2D2 USB|J1.64 DP、J1.66 DM|运行时使用实际/dev/serial/by-id路径|
|UVC USB|J1.70 DP、J1.72 DM|模组内置HUB；5V由载板分支供电|

ALSA的MicroduckAudio是约定名称，只有实际驱动probe后才会存在。R3的RK3566设备树和6.8 AMD64驱动构建结果不能当成CM4目标内核验证。专用板级设备树、三个适配模块、只读总线发现工具及详细构建/验收步骤见 [cm4-bsp/README.md](cm4-bsp/README.md)。目标内核构建与实际卡枚举结果必须补实测记录。
