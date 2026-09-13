# R22 入口板安装件

52×42×1.6 mm 入口板采用四个非矩形分布孔：H1(3,3)、H2(23,3)、H3(3,39)、H4(49,39)，均为Ø2.2。坐标从PCB左下角按原生板图读取，不能沿用原65×45板的四角孔距。

实际制造件为 [6061框架STEP](STEP_毫米/R22_Entry5V_rigid_frame.step) 和四个5 mm PEEK隔柱；完整13件及其源摘要见[manifest.json](manifest.json)。[尺寸图](R22-ENTRY-001_dimensions.pdf)用于读图，STEP定义名义实体。金属框架采用6061-T651机加工；不能把打印塑料框架视为同等承载方案。螺纹、螺钉内六角、倒角等制造细节没有全部建模。

| 项目 | 数量 | 尺寸或要求 |
|---|---:|---|
| 金属框架 | 1 | 四周梁名义6×3 mm，连接杆名义3×3 mm；保留原底脚与原两处M2.5固定孔 |
| 板固定螺纹 | 4 | M2×0.4通牙；底孔Ø1.6，名义材料厚3 mm，有效啮合至少2.5 mm |
| PEEK隔柱 | 4 | OD5 / ID2.2 / 长5 mm，未增强PEEK |
| M2×10内六角螺钉 | 4 | 名义头Ø3.8×2；采购公差、牙端倒角和实际啮合长度须检查 |
| M2垫圈 | 4 | OD4.3 / ID2.2 / 厚0.3 mm |

PCB背面坐标为world Y=-8；框架承压面Y=-3；隔柱跨过其间5 mm。背面元件最大高2.7 mm，名义余隙2.3 mm。原头壳载架及其六件底脚M2.5五金保留。PCB并未上移；顶插口按真实BM封装和SHR线端重新设计。

名义螺纹插入深度为10−0.3−1.6−5=3.1 mm，因此相对3 mm框架尾面名义突出0.1 mm。这是尺寸账，不是有效螺纹实测值。加工与装配需配对确认有效牙长≥2.5 mm、尾端不碰邻件，禁止靠过度拧紧压缩PCB或隔柱来补偿。孔位置与隔柱长度建议首件控制±0.05 mm；最终材料、孔位、板厚与五金公差须按整套实件检查。拧紧力矩需在实际PCB/PEEK叠层试样上确定，本文件不凭钢螺钉额定推定塑料叠层力矩。

装配时先固定原底脚，再安装四隔柱、入口板、垫圈和螺钉。使用1.5 mm内六角L形扳手，工作直腿至少30 mm；工具截面用Ø2 mm圆柱预算，不能用更粗的批头柄代换。[静态检查（工程包）](https://github.com/ldcyes/OpenDuck/releases/download/r22-compact-power-candidate-20260914/R22-engineering-candidate.zip)覆盖新133项与保留469项，以及新件内部，共71,155对，无未解释有限相交；四条工具通道对其余物体均至少1 mm的检查界限。具名螺纹啮合及同一连接器的冗余表示单列；同连接器不同导线另由[逐线检查（工程包）](https://github.com/ldcyes/OpenDuck/releases/download/r22-compact-power-candidate-20260914/R22-engineering-candidate.zip)核对。

附件名义质量比原框架及其对应五金减少1.465 g；这不代表整块电源或整机减重。框架的实际受载、振动、拧紧、打印外壳配合及完整线束仍需实物验证。没有样机，本候选尚未制造放行。


## 发布副本中的工程包引用

以下文件保留在 [R22工程ZIP](https://github.com/ldcyes/OpenDuck/releases/download/r22-compact-power-candidate-20260914/R22-engineering-candidate.zip) 内；下载后按归档路径打开：

- `work/r22-compact-power/mechanics/entry_home_check.json`
- `work/r22-compact-power/mechanics/individual_connector_wire_separation.json`


本页为GitHub浏览副本，仅转换文档路径并标明历史状态。原始JSON、板图和归档文件保持原字节；文档原SHA与发布副本SHA见[路径转换记录](../../../../provenance/r22-document-path-conversions.json)。原始交付校验表对应工程ZIP内的文档。
