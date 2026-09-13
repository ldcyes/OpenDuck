# 来源与许可

此仓库是用户Microduck工程的整理发布；Pollen Robotics、Radxa、KiCad、ROBOTIS及相关厂商名称用于识别来源，不表示认可本改版。

- Microduck上游软件来自 [pollen-robotics/microduck](https://github.com/pollen-robotics/microduck)，原 [Apache 2.0文本](licenses/microduck-Apache-2.0.txt)保留。R8软件目录中的既有LICENSE和文件内版权/SPDX说明均保留。
- 模型来源为 Pollen Robotics 的 [microduck_rl固定提交29e887ec](https://github.com/pollen-robotics/microduck_rl/tree/29e887ecfbf5d37144759e5a9f8a176dfb83d547)。该提交 [原README](provenance/original/upstream/microduck_rl-README.md)将软件列为Apache 2.0，将3D模型列为 **Creative Commons BY-SA-NC**，没有写具体版本。本整理不替上游指定版本。模型派生的STL、Blender与预览保留署名、相同方式共享、非商业条件；[原始模型来源及修改说明](licenses/original-model-source-NOTICE.md)一并保留。
- 标准KiCad封装库的 [原许可](licenses/KiCad-footprints-LICENSE.md)及文件内部归属保留。自建Microduck库和线路设计没有因此被重新指定为该许可。
- R8 BSP摘录来自 [Radxa kernel固定提交270a678f](https://github.com/radxa/kernel/tree/270a678f8364683447f994adec9d31eb182eaf85)，具体文件与源URL见 [source_manifest.json](software/r8/rk_runtime/deploy/cm4-bsp/source_manifest.json)。这些文件各自的SPDX/版权声明有效，相关 [GPL-2.0](licenses/Radxa-Linux-GPL-2.0.txt)和 [BSD-2-Clause](licenses/Radxa-Linux-BSD-2-Clause.txt)文本附存；它们不由软件目录的Apache文本统一覆盖。
- 电机、连接器、紧固件与厂家外形源按原索引保留来源，工程包内未明示的权利没有被本次公开上传扩展。没有为全工程增设统一LICENSE。

本次修改范围：整理目录；将面向阅读的说明链接改为相对路径或Release入口；添加下载、许可、复算与校验说明。原生KiCad、软件源、原始验证JSON、仿真源脚本与Release资产均保持原字节。转换详情及新旧哈希见 [source-manifest.json](provenance/source-manifest.json) 和 [path-conversions.json](provenance/path-conversions.json)。
