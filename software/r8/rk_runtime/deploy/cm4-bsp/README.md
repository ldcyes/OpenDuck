# CM4 R8 实际 BSP 与声卡部署

本目录适用于自制 R8 载板和 **Radxa CM4 RK3576 V1.20、带 U5 FCU760K 板载无线的 SKU**。不能把 DTS 用于 Raspberry Pi CM4、Q38、ZERO3W 或原 Radxa IO 板。目标内核来自 Radxa 官方 rk2410 profile：radxa/kernel 的 linux-6.1-stan-rkr4.1，固定 commit **270a678f8364683447f994adec9d31eb182eaf85**。来源及 SHA 见 source_manifest.json。

已完成：专用板级 DTS 实现、实际 DTC 编译、31 项 DTB 属性/codec 源码一致性回读、总线发现的 4 项边界测试、实际音频回调测试、三个模块对 Ubuntu 6.8.0-138 AMD64 headers 的 clean build。未完成：RK3576 ARM64 目标内核/模块构建、启动加载、GPIO/电压波形、I2C 实物、声卡/DMA 双工、WiFi/UVC 同时运行。随包 DTB 是已编译的工程配置，不代表目标系统已验收；不提供可误装的 AMD64 .ko。

## 控制器与物理接口

|接口|实际 CM4 引脚|固定 BSP 节点/功能|
|---|---|---|
|I2C SCL/SDA|J3A.56/.58，GPIO1_C6/C7|i2c8@2acb0000，i2c8m1_xfer，function10，100kHz|
|RUN_REQ|J3A.30，GPIO1_C1|MICRODUCK_RUN_REQ，正逻辑，外部下拉，运行时独占|
|RUN_OK|J3A.28，GPIO1_C4|MICRODUCK_RUN_OK，正逻辑，只是硬件许可，不是母线PG|
|AMP_ENABLE|J3A.37，GPIO1_C0|MICRODUCK_AMP_ENABLE，正逻辑，由 MAX codec 持有|
|SAI1 WS/BCLK|J1.19/.25，GPIO4_A5/A3|sai1@2a610000，sai1m0_lrck/sclk，function1|
|SAI1 RX/TX|J1.27/.29，GPIO4_B3/A7|sai1m0_sdi0/sdo0，function1|
|U2D2 USB|J1.64 DP/.66 DM|模块 U6 FE1_1S 下游端口2|
|UVC USB|J1.70 DP/.72 DM|同一 HUB 下游端口3|
|无线|模块 U5 FCU760K，J4 天线座|HUB 下游端口4；使用匹配 CM4 官方系统的驱动和固件|
|刷机 USB|J3B.103 DM/.105 DP，ID101不接|usb_drd0_dwc3 仅 peripheral、高速 USB2，无主机 VBUS 输出|

模块 U6 上游接 OTG1，所以 usb_drd1_dwc3 保持 host，保留官方 CM4.dtsi 的 PHY、WiFi 电源使能和板载配置。U2D2/UVC 5V 来自载板独立支路，没有原 IO 板 GPIO0_D3 控电。系统 5V 输入命名 vcc_sys，仅描述真实外部电源，不把舵机 RUN_REQ 绑成系统稳压器。原 IO 板 ES8388、耳机、PCIe、RTC、IO EEPROM 等配置没有继承。

维护口 J3B.98 的 VBUSDET 已在载板接入参考分压：USB维护口自身 VBUS→R7 10kΩ 1%→检测节点，R8 20kΩ 1%由节点到GND；芯片内部40kΩ下拉与20kΩ并联，5V名义检测电压2.857V。CM4已有C1404=100nF，不在载板重复。维护口VBUS不并入系统5V。此接法与Rockchip RK3576 USB指南V1.1.0图13一致；非Type-C控制器方案需要真实VBUS检测，保持本包peripheral配置，不使用vbus-always-on代替分压。指南另说明Maskrom枚举不依赖VBUSDET电平；这项芯片规则不等于本板已完成USB枚举或刷机测试。[Rockchip USB指南](https://docs.bit-brick.com/pdf/rk/usb/Rockchip_RK3576_Developer_Guide_USB_CN.pdf)。

GPIO_VREF J3A.78 必须由载板连接 CM4 3.3V；音频域模块 R101=0Ω、R100不装，3.3V。MCLK J1.23 未接；没有为旧板针脚创建别名。引脚名不代表 gpiochip 编号固定。DTS 使用 GPIO 默认下拉 pinctrl，没有占用 RUN_REQ 的 gpio-hog；真实软件通过 libgpiod2 请求初值低。复位、启动和进程死锁时的安全依赖实际外部下拉/硬件保护，不能以 Python 的100ms心跳声称内核挂起或 GPIO ioctl 永久阻塞也必断电。

## 音频实际 API 适配

目标 BSP 的驱动是 **CONFIG_SND_SOC_ROCKCHIP_SAI / rockchip_sai.c**。其 DAI 支持 set_sysclk 与 set_tdm_slot，不提供 set_bclk_ratio；因此没有沿用旧 R3 I2S_TDM 回调或 rockchip,trcm-* 属性。

machine driver 固定卡名 MicroduckAudio，链路 Microduck SAI1 Duplex。单个 SAI1 CPU DAI 同时连接 HiFi 播放 codec 和 dmic-hifi 采集 codec。只允许48kHz、S32_LE、2通道；请求内部 MCLK12.288MHz，调用 set_tdm_slot(tx=3,rx=3,slots=2,width=32)。SAI 源码使用同一 CKR/FSCR，单 lane ×2通道×32bit→BCLK3.072MHz，LRCK48kHz。它的 slots/mask 参数并非所有字段都用于硬件，因此2通道与单 lane 的固定约束必须保留。正常 capture STOP 仅停止 RX，不关闭仍运行的 TX；实际启动/停止顺序和时钟连续性仍须示波器与双工录放验证。

microduck-max98357a.c / microduck-dmic.c 保留独立方向 guard，DT compatible 也为本包专用，stock codec 不能静默替换。所附 patch 是相对官方 Linux v6.1 的来源差异，不是自动应用到任意 BSP 的补丁。三个 .c 必须一起针对目标内核编译。T5848 的左槽有效，右槽不是第二支麦克风；软件录音取左槽。ALSA 输入/输出配置统一 plughw:CARD=MicroduckAudio,DEV=0，仍由部署配置明确指定。

本目录也可在有 cpp/dtc/fdtget 的 PC 运行 make dtb 与 make verify，以随包固定官方依赖复现 DT 编译和回读。源码保留原许可。

## 固定版本构建

本轮实际编译前检查见 verification_ONLY/ARM64_exact_target_preflight.json。固定源码为6.1.84，官方rockchip_linux_defconfig启用CONFIG_MODVERSIONS=y。本机有Clang14，但无AArch64 GCC/binutils、无LLVM lld，且没有该目标完整已配置/已构建内核及Module.symvers，所以本轮未执行/未通过ARM64模块构建。不能用modules_prepare产生正确版本符号：Linux官方明确其不会生成Module.symvers，启用MODVERSIONS时须完整内核构建。该缺口仍是目标部署门槛，现有6.8 AMD64结果只证明那套头文件上的可编译性。[Linux 6.1外部模块说明](https://docs.kernel.org/6.1/kbuild/modules.html)。


按官方 BSP 说明取得 rk2410 工作树，确认代码版本等于上述 commit。reference/ 中只有构建设备树需要的官方文件及审查来源，不能当成完整可编译内核。目标内核须采用匹配 CM4 的官方配置、工具链和固件包。

把本目录 rk3576-microduck-r8.dts 放入目标内核 arch/arm64/boot/dts/rockchip/，在其 Makefile 增加：

    dtb-$(CONFIG_ARCH_ROCKCHIP) += rk3576-microduck-r8.dtb

合并 microduck.config 到目标 .config 后运行 olddefconfig，再确认 CONFIG_GPIO_CDEV、I2C_CHARDEV、SND_SOC_ROCKCHIP_SAI、FTDI_SIO、USB_VIDEO_CLASS 等没有因依赖而被清除。该配置不是完整的无线固件包；保留官方系统的无线驱动/固件，按实机 lsusb 和内核日志核对 FCU760K 枚举。

在 ARM64 编译环境中执行（KERNEL_SRC 是上述已配置、已构建且与最终运行内核一致的绝对路径，CROSS_COMPILE 是实际工具链前缀；在目标板原生构建时省略 CROSS_COMPILE）：

    make -C "$KERNEL_SRC" ARCH=arm64 CROSS_COMPILE="$CROSS_COMPILE" rockchip/rk3576-microduck-r8.dtb
    make -C "$KERNEL_SRC" ARCH=arm64 CROSS_COMPILE="$CROSS_COMPILE" M="$PWD" modules

记录目标 kernel release、config SHA、DTS/DTB/module SHA 和编译日志。只安装这个目标内核生成的三个 .ko，depmod 后随专用 DT 启动；保留可恢复的官方启动项。不能把 PC 的6.8构建结果或仅 DTC 返回0当成ARM64驱动验证。

## 上电发现与验收顺序

1. 先断开舵机总线电源，只启用系统电源；确认实际加载 model/compatible 正确。运行 python3 discover.py，只读核对三条唯一 GPIO 名和 I2C 控制器的 of_node。工具不拉高 RUN_REQ，输出的 /dev/i2c-N 才是 power.json 的 i2c_device，不能由 I2C8 名称猜 /dev/i2c-8。
2. power-diagnostics 以实际设备路径读取 INA0x40/0x41/0x42、ADS0x48；仍 RUN低。DTS 不创建这些内核客户端，IMU0x6a同样由本运行时独占；不要另开 iio/hwmon/扫描程序与运行时抢总线。校准和隔离电子负载步骤见 ../../README_POWER.md。
3. 实测 RUN低启动、请求/许可读回、母线建立500ms、撤销请求和每个故障注入；RUN_OK不是PG，实际 INA 母线验证不能省。只有被测记录进入校准配置后才可能通过运行时门槛。
4. 确认三个音频模块实际 probe，cat /proc/asound/cards 中出现 MicroduckAudio。以 arecord -D plughw:CARD=MicroduckAudio,DEV=0 -r48000 -fS32_LE -c2 -d10 capture.wav 录音，同时低音量播放48k WAV。分别先停录音/先停播放，重复测试另一方向不中断，示波器确认3.072MHz/48kHz与正确采样沿。不要用扬声器实际播放的回声当 ASR 麦克风通路已合格的唯一证据。
5. U2D2 使用实际 /dev/serial/by-id，UVC 用实际 /dev/v4l/by-id；USB2 HUB 的 UVC、无线、U2D2共享带宽。MJPG 帧率、丢帧、ASR负载和50Hz周期需同机测试。没有实测前不承诺网络、相机与闭环同时满载运行。

运动标定、允许姿态和训练模型门槛仍独立存在；已有有限离散几何筛查不能扩大当前运动合同或替代动态/实机验收。DT或声卡通过也不使motion_approved变成true。

官方来源：[CM4 原理图 V1.20](https://dl.radxa.com/cm4/docs/hw/radxa_cm4_schematic_v1.20.pdf)、[Radxa BSP 编译说明](https://docs.radxa.com/en/rock4/rock4d/low-level-dev/kernel)、[固定 CM4 模块设备树](https://github.com/radxa/kernel/blob/270a678f8364683447f994adec9d31eb182eaf85/arch/arm64/boot/dts/rockchip/rk3576-radxa-cm4.dtsi)、[固定 SAI 驱动](https://github.com/radxa/kernel/blob/270a678f8364683447f994adec9d31eb182eaf85/sound/soc/rockchip/rockchip_sai.c)。
