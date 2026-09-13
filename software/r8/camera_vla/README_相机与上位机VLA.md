# R8 相机、上位机 VLA 与人工示教

本目录实际迁入并适配了采集 client、认证 HTTP host、SmolVLAAdapter、人工 record 和 LeRobot dataset 导出。机器人为 Radxa CM4 RK3576；相机为 Waveshare OS05A10 5MP USB Camera(A)，SKU33123。R3文件保持冻结。没有提供 R8 VLA 权重、GPU训练成果或实机视觉行走通过记录。

链路为 USB2 UVC → 最新640×480 JPEG及真实q/dq/IMU → 上位机HTTP → 短时高层意图 → R8唯一本地仲裁器 → 50Hz控制器。相机程序不导入Dynamixel，不直接写command文件。模型输入21维（15实测q+3gyro+3gravity）；15实测dq仍保留在记录中。输出11维高层动作，沿用当前 neck[-20,+5]°、pitch±15°、yaw±15°、roll±8°、嘴0..12°合同。模式head_home_locked禁止头/嘴；supported_double禁止腿/速度/body，且需实际支持架确认和对应低层策略。

每份观测、响应、数据集和模型绑定robot_profile、实测calibration SHA、motion_limits SHA、motion_context与相机型号/方向。新建观测要求相机交付年龄≤150ms、真实状态≤100ms、IMU年龄≤30ms、图像/状态偏差≤100ms。收到响应再次核当前真实armed/ready状态及上述身份，随后在本地仲裁器接收时再按同一RK单调时钟核观察期限（默认750ms，最大1s），禁止传输迟到后重新打时间戳。序号只用一次，意图与闭嘴宽限均不得越过观察期限。显式停止、网络异常、模型越界或失去状态会停止该会话的新租约。

**低层失去租约后会撤RUN/关扭矩，不等于自动站稳。** 当前没有在VLA等待、ASR等待时无限续租零命令，也未实现经过实机验证的平衡保持。双足受支持互动与离线验证可先进行；连续行走仍需本地动态策略和整机验证。

## 离线验证

保持camera_vla与rk_runtime相邻。在camera_vla目录运行：

    python3 -m unittest discover -s tests -v
    python3 -m microduck_vision.client --help
    python3 -m microduck_vision.record --help

测试启动真实本机HTTP服务，模拟数据明确限于测试，覆盖认证、完整观察→host→ReplyGate→本地Arbiter、重复/过时响应、R8身份、限位/上下文、示教来源和训练绑定。普通测试不需OpenCV、torch或机器人。

## 部署

1. 使用R8/rk_runtime部署指南完成控制和电源前置验收。运行控制器时设 --telemetry /tmp/microduck-r8-state.json；交互服务 --runtime-telemetry 指向同一路径。支持互动需双方使用对应supported_double策略/模式。模板仍无法运动。
2. 上位机设置私有MICRODUCK_VLA_TOKEN（客户端同值），先启动模拟服务：

       python3 -m microduck_vision.host --backend mock

   服务默认127.0.0.1:8767。跨机用TLS或从RK建立SSH转发：

       ssh -N -L 8767:127.0.0.1:8767 USER@WORKSTATION

   直接非本机监听必须提供--cert/--key；客户端--ca-file可指定CA。语音网关用8768，本机执行器8766，本地LLM8081，互不占同端口。
3. RK安装有GStreamer支持的系统OpenCV，核实际/dev/v4l/by-id设备和640×480 MJPG模式。示例管线（DEVICE替换为真实持久设备路径）：

       v4l2src device=DEVICE io-mode=4 ! image/jpeg,width=640,height=480,framerate=30/1 ! jpegdec ! videoconvert ! video/x-raw,format=BGR ! appsink max-buffers=1 drop=true sync=false

   USB相机与U2D2、无线共享CM4内部HUB，实际带宽/丢帧及控制排程尚未测。只保留最新帧；接收尺寸不是640×480则拒绝。当前采样时间是驱动帧交付时刻，不冒称曝光时刻，需用外部同步实验量测缓冲延迟。
4. 相机方向必须先实看标定板，明确传--rotation 0或180；没有沿用R3的CSI/FPC倒装假设。将同一方向写入数据集和checkpoint：

       python3 -m microduck_vision.client --telemetry /tmp/microduck-r8-state.json --task '保持当前允许姿态' --pipeline '上述完整实测管线' --rotation 0 --seconds 10

   默认只记录候选动作，不请求本地动作会话。--live另需MICRODUCK_LOCAL_TOKEN、已运行的真实本地执行器、批准的VLA模型及全部硬件门禁。mock后端拒绝live。相机程序不会代替用户配置WiFi，也没有集成RTSP/WebRTC网页直播。

## 实际模型与训练

上位机独立环境按requirements-host.txt固定LeRobot提交安装；真实训练前验证CUDA环境。复制train_microduck.example.json后填写本地真实数据，执行lerobot-train --config_path=配置路径。该训练模板保持base投影32维：21维状态补到32，11维动作由32投影裁回；禁止Aloha关节变换。这里没有真实R8训练数据或模型，不能用通用机械臂权重伪装为本机策略。

record只读真实相机、遥测和认证/v1/status，不发动作：

    python3 -m microduck_vision.record --pipeline '上述完整管线' --rotation 0 --telemetry /tmp/microduck-r8-state.json --task '人工允许姿态示教' --seconds 10 --output episode01.jsonl

仅接受健康live的manual会话，确认已发送高层command与当前人工intent一致，source timestamp不得早于本次人工intent起点，且intent仍有效。标签采用已经发送的嘴目标，不能当嘴已到位。默认successful=false/UNREVIEWED；人工检查整段后才可进入导出，VLA/对话/模拟结果不能当人工标签。

    python3 -m microduck_vision.dataset episode01.jsonl --validate-only
    python3 -m microduck_vision.dataset episode01.jsonl --root /data/microduck-r8-dataset --repo-id local/microduck-r8

强制5Hz±40ms、图像/已发送动作≤100ms，同episode及跨episode相机方向、标定、运动SHA和模式必须一致。head_home_locked与supported_double分别形成数据/模型。导出本地LeRobot数据及meta/microduck_training_profile.json；不上传数据。将该profile复制到训练checkpoint根目录，与全部配置/权重/processor文件逐一列SHA到manifest。以microduck-manifest.example.json建立新manifest，模板approved_for_simulation/live均false；完成真实验证后才能填批准记录并运行：

    python3 -m microduck_vision.host --backend smolvla --manifest /absolute/r8-manifest.json

此适配器加载训练保存的pre/postprocessor、归一化统计和模型权重；不只加载一个safetensors文件。原R3标定/模型/数据合同会被R8拒绝。图像、网络、观察延迟、意图中断应进入任务训练与离线回放，低层BAM/动态训练见相邻rk_runtime文档。最终功能边界：客户端与适配代码可执行，真实权重、GPU训练、RK摄像头和视觉动作实测尚未完成。
