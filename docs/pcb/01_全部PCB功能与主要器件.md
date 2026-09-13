# 当前全部PCB盘点（R20装配基线；R21只读复核）

**12种自制PCB、13块实际用板设计**，其中LEG5左右各一块。当前557件装配只定位7块；另6块尚未完成安装。按板外轮廓、含LEG5重复数量合计16681mm²，这不是可削减面积。原理图、板图和BOM共36份源文件SHA全部复核一致。

以下层数、外形和孔径直接来自当前KiCad文件。功能与主要器件结合原理图/BOM和板上MPN复核。详细针网、封装位置、全部孔及SHA在 [机器可读清单](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>) 和 [原生PCB提取](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>)。

| 自制板 / 数量 | 尺寸mm / 铜层 | 功能 | 主要芯片与关键元件 |
|---|---|---|---|
| 电池主保险板 ×1 | 30×25×1.6 / 2层 | 把首道可更换熔断保护放在电池正极出口，限制短路故障持续能量。它与 Entry 上的 2 A 逻辑支路保险是不同器件。 | 无有源IC；Keystone 3549-2 MINI 保险座；Littelfuse 0297015.WXNV，15 A / 32 V DC |
| 舵机主电源板 ×1 | 65×60×1.6 / 2层 | 用外购 TDK 升降压模块生成舵机电源，加入输出隔离/反向阻断、过压切断、硬件过流检测及电流遥测。 | Q1 CSD18540Q5B；Q2 CSD18540Q5B；Q3 BSS138；U1 i7C2W020A120V-P03-R；U2 LM74800QDRRRQ1；U3 INA226AIDGSR；U4 INA300AIDGSR |
| 电池入口、5 V 与监测板 ×1 | 65×45×1.6 / 2层 | 测量电池电流，产生逻辑 5 V，并在电池与台架 5 V 之间切换；把温度、过流和运行握手接口集中连接到主控。 | U1 INA226AIDGSR；U2 ADS1115IDGSR；U3 LMZM33603RLRR；U4 TPS2117DRLR |
| 再生制动控制与电流测量板 ×1 | 32×30×1.6 / 2层 | 在舵机减速回灌使母线升高时，模拟比较器驱动 MOSFET 接通外置回生电阻，并记录耗能支路电流。 | Q1 CSD18540Q5B；Q2 BSS138；U1 TLV76050DBZR；U2 REF3312AIDBZR；U3 TLV3201AIDBVR；U4 UCC27511DBVR；U5 INA226AIDGSR |
| 65 °C 回生热板温保板 ×1 | 16×12×1 / 2层 | 作为回生散热板局部过热的硬件后备停机输入。 | U1 TMP302ADRLR |
| 75 °C TDK 温保板 ×1 | 16×12×1 / 2层 | 作为 TDK 模块局部过热的硬件后备停机输入。 | U1 TMP302BDRLR |
| RK3576 CM4 主控载板 ×1 | 58×45×1.6 / 4层 | 为外购 RK3576 CM4 提供机械/电源接口、核心支路限流、USB 静电保护、音视频/传感器连接及恢复测试点。计算处理在外购核心板内。 | U1 TPS259530DSGR；U2 USBLC6-2SC6；U3 USBLC6-2SC6；U4 USBLC6-2SC6 |
| 五路腿部配电板 ×2 | 40×36×1.6 / 2层 | 两块相同硬件分别给左右腿 5 台 XM430 分配电源，并并联分发半双工 TTL 数据。 | 无有源IC；每板 5 × Littelfuse 0448003.MR，3 A；每板 5 × S3B-EH(LF)(SN)；每板 1 × SM04B-SRSS-TB(LF)(SN) |
| 三路颈头配电板 ×1 | 40×25×1.6 / 2层 | 给两台颈/头 XM430 和三台串接的 XC330 分配三路独立熔断电源；三个接口实际带五台电机。 | 无有源IC；3 × Littelfuse 0448003.MR，3 A；3 × S3B-EH(LF)(SN)；SM04B-SRSS-TB(LF)(SN) |
| 六轴姿态传感器板 ×1 | 24×18×1.6 / 2层 | 向主控提供惯性传感数据，用于后续姿态估计；本板本身不是已完成的平衡控制器。 | U1 LSM6DSV16XTR |
| I²S 单声道功放板 ×1 | 28×20×1.6 / 2层 | 将主控数字音频转换为单声道扬声器驱动，并提供麦克风支路连接。 | U1 MAX98357AETE+T |
| 数字麦克风与电平转换板 ×1 | 20×14×1 / 2层 | 采集声音，产生麦克风所需 1.8 V，并在麦克风与主控间转换数字接口电平。 | U1 MMICT5848-00-012；U2 TXU0204PWR；U3 TLV75518PDBVR |

安装孔与外形约束（XY均为原始KiCad毫米坐标；不是整机坐标）：

| 板 | 固定孔与声孔 | 当前安装 / 缩板时必须保留的接口 |
|---|---|---|
| Main_Fuse_R8 | H1 (3,3) φ2.2；H2 (3,22) φ2.2 | 已定位工程参照（未实装验收）。保留两颗 φ2.2 固定孔、MINI 可拔保险座、AWG16 端接与独立线夹空间；电芯真实正极到首保险的已批准总导体上限100mm仍适用。缩板不能破坏15A路径或裸端邻近间隙。 |
| TDK_Power_R8 | H2 (62,3) φ2.2；H1 (3,3) φ2.2；H4 (62,57) φ2.2；H3 (3,57) φ2.2 | 已定位工程参照（未实装验收）。四孔59×54mm固定图样和外购TDK功率模块引脚/本体是主要几何约束；输入输出大电流铜、Kelvin采样、输出反向阻断与Tc散热/探头接口需保留。模块内部不能随载板缩放。 |
| Entry_5V_R8 | H4 (62,42) φ2.2；H3 (3,42) φ2.2；H1 (3,3) φ2.2；H2 (62,3) φ2.2 | 已定位工程参照（未实装验收）。四孔59×39mm；头部既有安装座及8个控制/NTC插头与配对插头通道绑定当前板形。电池测量回路、5V转换和台架切换的热/回流路径不能只按空白面积删去。 |
| Regen_R8 | H3 (3,27) φ2.2；H1 (3,3) φ2.2；H2 (29,3) φ2.2；H4 (29,27) φ2.2 | 尚未纳入当前557件装配，保留旧待安装画廊来源。四孔26×24mm；板尚未在当前557件内安装。外置RH电阻和热片与此板分开，需保留MOSFET脉冲回流、取样分流器Kelvin引线、驱动去耦与AWG16端接。 |
| Thermal_65C_R8 | H2 (14,2) φ2.2；H1 (2,2) φ2.2 | 尚未纳入当前557件装配，保留旧待安装画廊来源。两孔中心距12mm，1.0mm板厚；当前无最终热接触安装。缩小后仍需确定65°C热板接触区域、绝缘、固定压力与热响应，不能仅以板外形尺寸替代测温界面。 |
| Thermal_75C_R8 | H1 (2,2) φ2.2；H2 (14,2) φ2.2 | 尚未纳入当前557件装配，保留旧待安装画廊来源。两孔中心距12mm，1.0mm板厚；当前无最终TDK Tc热接触安装。TMP302B设定及探头与模块真实Tc区的接触/热滞后需要保留和核验。 |
| CM4_Carrier_R13 | H1 (5,6) φ2.7；H4 (52.95,38.98) φ2.7；H3 (52.95,5.98) φ2.7；H2 (5,39) φ2.7 | 已定位工程参照（未实装验收）。四个φ2.7孔来自现有板图，孔排保持47.95mm横距、33mm纵距及右排−0.02mm偏差；与核心板φ2.6孔、4mm/1.5mm/5mm PEEK栈和M2×22通栓同轴。三组100针DF40的位置/朝向/1.5mm配合高度不可同步缩放；USB差分与完整参考地、eFuse热铜和插拔空间同属约束。R20只把旧无孔预览换为真实有孔板体，未改电路、外形或板厚。 |
| LEG5 | H2 (37,16.5) φ2.7；H1 (3,18) φ2.7 | 已定位工程参照（未实装验收）。每块两φ2.7孔为(3,18)/(37,16.5)，不是同一水平线；两块板分别连接左右腿。既有LEG5支架/工具井、5个JST EH3插头、3A支路保险、AWG16电源端接与大电流回流需保留；J6细线地不装以免旁路动力回流。 |
| HEAD3 | H2 (37,12) φ2.7；H1 (3,12) φ2.7 | 已定位工程参照（未实装验收）。两φ2.7孔中心距34mm，当前头架jaw_soft位置已固定；3个EH3接口共带5个电机，不能按3电机缩减容量。应保留移动头颈线束的服务弯、支柱及配对插头空间。 |
| IMU_P0 | H1 (2.8,2.8) φ2.2；H2 (21.2,15.2) φ2.2 | 尚未纳入当前557件装配，保留旧待安装画廊来源。两φ2.2对角孔(2.8,2.8)/(21.2,15.2)，当前无最终安装/传感轴合同。缩板需保留加速度计/陀螺仪的刚性安装、坐标定义、去耦及接头；J2调试口在工程BOM规定为DNP，不能仅凭PCB封装出现认定装配。 |
| AMP_R3 | H1 (2.5,2.5) φ2.2；H2 (25.5,17.5) φ2.2 | 尚未纳入当前557件装配，保留旧待安装画廊来源。两φ2.2对角孔(2.5,2.5)/(25.5,17.5)，当前支架/安装未闭合；5V输入、I²S、麦克风支路及桥接扬声器连接器占边，需保留功放散热与扬声器双端回流，SPK_P/SPK_N均不是地。 |
| MIC_R3 | H1 (2.2,2.2) φ2.2；H2 (17.8,11.8) φ2.2；U1 (2.092,9) φ0.65声孔 | 尚未纳入当前557件装配，保留旧待安装画廊来源。两φ2.2固定孔加U1下φ0.65声孔；声孔不是第三个固定孔。1.0mm板厚、底部拾音孔/外壳声道/密封泡棉和数字时钟隔离需配套，当前尚无实际安装合同。 |

外购模块单列；不加到13块自制板中：

| 外购模块 | 主要电子功能 / 芯片 | 尺寸及当前装配口径 |
|---|---|---|
| Radxa CM4 RK3576 核心板 | 运行Linux、控制与网络/上位机客户端；自制载板提供供电和接口，不含RK3576处理器。 Rockchip RK3576；RK806S-5 PMIC；RTL8211FS(I)(-VS) 以太网PHY；FE1_1S USB Hub；LPDDR4X/eMMC随采购SKU，容量/料号不在本盘点中重新定型 | 源STEP的PCB约54.98×40.02×1.2mm；这是板材范围，不是整模块最大高度。三组100针DF40；四个原厂孔φ2.6。与现有载板、PEEK、散热器耳和M2×22通栓共轴，保持安装位置。 |
| ROBOTIS U2D2 | USB转DYNAMIXEL半双工TTL/RS485；当前使用TTL数据，不供电机动力电源。 封装内USB/串口/收发器具体IC料号未在当前已核资料中确定 | 外壳48×18×14.9mm。当前557件主选择无U2D2独立实体；USB口/TTL插头及固定/工具空间须另外完成。 |
| PCM-L04S30-566（Li-ion 4S） | C0…C4电芯抽头保护及P−回流，和首道15A保险分工不同。 保护IC及MOSFET具体料号未由供应方冻结资料确认 | 60×60×5mm最大包络。当前躯干包络位置已入557选择；真实焊盘、端接、绝缘和固定界面仍需供应方合同。 |
| TDK i7C2W020A120V-P03-R | 产生名义10.8V舵机母线；外侧保护/监测由TDK_Power_R8负责。 模块内部控制IC未单独定型；采购件为完整i7C2W020A120V-P03-R | 开框模块图示34.04×36.83mm（±0.38），高14.35mm（±0.70）；默认引脚3.68mm单列。65×60mm是外侧自制载板。不能重复计为第14块自制板，也不能随承载板同比例缩小；保留Tc区与散热接口。 |
| Waveshare OS05A10 USB Camera (A), 33123 | OS05A10图像传感器输出USB视频供RK3576或上位机视觉/VLA使用。 OS05A10图像传感器；USB桥接IC具体MPN未在所核资料中确认 | 板25×25×1.6mm，总深22.1mm；图示主要外形公差±0.2mm。图上四φ2孔呈21×21mm孔距；镜头和插头深度须保留。当前557主选择没有对应摄像头实体，不能以旧功能表称已安装。 |

12台XM430与3台XC330自带驱动/编码器电子器件；它们属于外购完整舵机，内部板数/IC/制造文件不在本工程自制PCB清单。风扇等产品内部电子亦不按未核数量追加自制板。

当前原生设计入口（均已核SHA，源文件未改）：

| 板 | 原理图 | PCB | BOM |
|---|---|---|---|
| Main_Fuse_R8 | [SCH](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>) | [PCB](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>) | [BOM](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>) |
| TDK_Power_R8 | [SCH](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>) | [PCB](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>) | [BOM](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>) |
| Entry_5V_R8 | [SCH](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>) | [PCB](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>) | [BOM](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>) |
| Regen_R8 | [SCH](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>) | [PCB](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>) | [BOM](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>) |
| Thermal_65C_R8 | [SCH](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>) | [PCB](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>) | [BOM](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>) |
| Thermal_75C_R8 | [SCH](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>) | [PCB](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>) | [BOM](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>) |
| CM4_Carrier_R13 | [SCH](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>) | [PCB](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>) | [BOM](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>) |
| LEG5 | [SCH](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>) | [PCB](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>) | [BOM](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>) |
| HEAD3 | [SCH](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>) | [PCB](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>) | [BOM](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>) |
| IMU_P0 | [SCH](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>) | [PCB](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>) | [BOM](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>) |
| AMP_R3 | [SCH](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>) | [PCB](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>) | [BOM](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>) |
| MIC_R3 | [SCH](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>) | [PCB](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>) | [BOM](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>) |

现有13个独立熔断支路连接15台电机：LEG5两板各5路；HEAD3的前两路各1台XM430，第三路为3台XC330串接。3A保险额定值不等于主动限流，也不是持续运动电流能力的实物证据。

RK3576在外购核心板上，自制CM4载板没有另一颗RK处理器。R20头部修订只取消重复压条、补五金，并将旧无孔载板预览换为已有4个φ2.7孔的实体；当前4层R13电路版未改。隐藏的核心板MAX包络仍不是芯片和PCB的真实材料。

6块待安装板为Regen、Thermal65、Thermal75、IMU、AMP、MIC；它们的制造源存在，旧画廊提供查看，但不在当前557件机器人内部。U2D2和相机也没有纳入当前557主选择的实际独立实体。不能从有原理图或图库推出整机已经完整安装。

根代理已完成两轮规则检查：[当前项目规则、重铺铜及全走线检查](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>)中，12种板的ERC/DRC/未连线/原理图对应差异均为0；[额外启用原忽略规则的诊断](<https://github.com/ldcyes/OpenDuck/releases/tag/r13.8-simulation-20260913>)出现43项警告（38项缺courtyard、4项CORE_5V及1项SYSTEM_5V走线未对准过孔中心），没有新增短路、未连线或原理图对应差异。两轮规则集合不同，不能写成无条件“所有DRC零问题”。逐板结果已绑定本清单相同PCB SHA。

缩板可行性由根代理另行报告。板子面积缩小若改变孔位、B2B接口、插头/线束通道、散热或高电流铜，会引出相应机械与电气复核；不按任意百分比保证可缩。制造、上电、温升、音频、线束和实体行走仍未验收。
