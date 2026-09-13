# R8交互运行入口（默认模拟）

本目录从R3交互实现复制，并接到R8混合驱动/新robot_profile。先读README_R8.md；R1/R3权重不能直接驱动R8。以下音频和网络功能沿用已有实现，Radxa CM4真实声卡、BSP和电气接口仍必须按R8硬件定型重新验证。

控制逻辑位于 microduck_rk/__main__.py 的 run：实测 IMU/舵机 → 61 维观察 → ONNX → 14 维动作 + 独立嘴 → Dynamixel。只有此循环写舵机。microduck_interaction/executor.py 在独立线程以 50 Hz 合并限时意图与播放音量，写原子 command JSON；providers.py 和文字/PTT CLI 在另一个进程等待服务，不能阻塞控制循环。相邻camera_vla的R8客户端现已接入采集/上传/当前遥测检查/人工示教，绑定R8 profile、标定、限位SHA与支撑上下文；返回意图经此执行器，见[相机部署](../camera_vla/README_相机与上位机VLA.md)。没有真实R8 VLA权重。

当前默认head_home_locked需要真实HOME连续稳定读回，禁止交互头/嘴和音频嘴运动；supported_double须确认实体支持并使用对应策略，锁十腿后才允许上述头部范围。两模式的实际状态在每次非零租约及播放前复核，见[README_MOTION_CONTEXT.md](README_MOTION_CONTEXT.md)。motion_limits.py是唯一限位源码；读写command和模型/标定/训练均绑定其SHA。V18有244个有限离散头姿态几何筛查记录，当前头壳修订需重新复核；它不等于任意连续姿态或物理运动批准。

嘴部0..12°角度目标还须满足独立0.05Nm结构载荷验收。音量包络不测力矩，初始300mA不表示薄嘴托已合格；实测标定、限流、P增益、步幅仍有效。

## 离线启动和演示

仅需 Linux Python 3.10+ 标准库，不安装机器人依赖也可验证交互。以下均在 rk_runtime 目录运行。每个使用 API 的终端要设置相同随机令牌；示例不要照用固定密码。

    export MICRODUCK_LOCAL_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
    python3 -m microduck_interaction serve --dry-log /tmp/microduck-r8-demo.jsonl

另一个终端设置相同令牌后：

    python3 -m microduck_interaction status
    python3 -m microduck_interaction demo
    python3 -m microduck_interaction play examples/synthetic_duck_cue.wav

默认没有 ALSA 调用、command 文件写入或舵机连接。demo 拒绝连接正在写真实 command 的服务。play 可在同一服务上模拟，且以后可在明确启用音频后播放。examples/synthetic_duck_cue.wav 是 1 秒人工合成音效，非鸭叫录音、非实机采集；对应 synthetic_duck_envelope_50hz.json 含增益 0.20 后的 50 Hz 嘴目标预览。预览角度是目标，受原控制循环的 0.5 rad/s 和标定每步限制，不能当实际嘴运动曲线。

## 接入服务和说话

复制 deploy/interaction.env.example 到本机私有配置，填写服务 URL、令牌和模型名。CLI 环境变量不会从 systemd 自动传到交互终端，可在可信配置文件上使用 set -a; source 配置; set +a。勿把密钥提交或复制入公开工程。

    python3 -m microduck_interaction text '请向我打个招呼'
    python3 -m microduck_interaction text '看向左边' --no-speech
    python3 -m microduck_interaction ptt --wav /absolute/speech.wav

PTT 实际录音需要明确加 --live-audio。按回车开始，再按回车结束，最长 10 秒；录音/ASR 阶段不创建动作租约。先获得有效 LLM 计划并准备完整 TTS WAV，再提交动作；服务失败不会用编造结果继续。--no-speech 只跳过合成，不伪装为声音播放。

    python3 -m microduck_interaction ptt --live-audio

当前是按键对话，没有常驻唤醒词、回声消除、打断正在说话的全双工对话或网页聊天 UI。相机/VLA使用相邻目录的实际客户端，不代表已接通网页直播。

LLM 支持两个明确协议：generic 向自备网关发送 {schema:1,robot_profile,text,system_prompt}，返回下述 Plan；chat-completions 发送 model、messages、response_format=json_object、temperature=0、max_tokens，读取 choices[0].message.content。MICRODUCK_LLM_MAX_TOKENS 默认 256，可设 64..512。支持此格式的本地或远程服务才能直接接入；不是任意厂商 URL 都可工作。HTTP 超时 0.05..15 秒、响应字节限制、禁止重定向，错误不输出密钥。网络请求在 CLI 进程等待；DNS/慢速流的底层总时限可能超过单次 socket timeout，动作/会话到期仍独立生效，不会等网络续租。截断、重复 JSON 键、NaN、越界或多余键一律拒绝，不重试执行旧动作。

## 可启动的开源语音网关（上位机）

microduck_interaction/speech_gateway.py 是真实后端适配，ASR 用 faster-whisper CPU/int8，TTS 用 eSpeak NG 普通话 cmn。不是 mock 服务；R3/R8未在目标机安装模型和espeak-ng，因此识别准确度、合成听感和响应时间均未实测。eSpeak NG 是机械合成音 fallback，不承诺自然人声。使用官方后端接口：[faster-whisper](https://github.com/SYSTRAN/faster-whisper)、[eSpeak NG](https://github.com/espeak-ng/espeak-ng)、[cmn 语言支持](https://github.com/espeak-ng/espeak-ng/blob/master/docs/languages.md)。

在 Linux 上位机创建 Python 虚拟环境、安装 requirements-speech-host.txt 和系统包 espeak-ng。另行下载有权使用的多语言 CTranslate2 faster-whisper 模型到本地目录（例如官方文档支持的 tiny/base 级别），目录必须含 model.bin、tokenizer.json、config.json（防止缺失 tokenizer 时上游隐式下载），保存模型来源/版本/许可证；本工程没有附权重、隐式下载或代替用户接受许可证。仅英文 .en 模型不适合中文。通过 espeak-ng --voices=cmn 验证发行版包含中文数据。

    python3 -m pip install -r requirements-speech-host.txt
    export MICRODUCK_SPEECH_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
    python3 -m microduck_interaction.speech_gateway --model-dir /absolute/local-faster-whisper-model

网关默认且强制只监听 127.0.0.1:8768（动作 API 为 8766，VLA 为 8767，本地 LLM 为 8081）。RK 在另一台机器时，在 RK 上建立 ssh -N -L 8768:127.0.0.1:8768 用户@上位机，ASR/TTS URL 仍使用 http://127.0.0.1:8768；也可由上位机 TLS 反向代理提供 HTTPS。不能把明文网关直接绑定局域网 IP。把 MICRODUCK_ASR_API_KEY 和 MICRODUCK_TTS_API_KEY 设为上位机同一 MICRODUCK_SPEECH_TOKEN。

网关每次只处理一个请求，超时默认 12 秒，忙时 503，无效输入 400，后端失败 503，超时 504。每次启动独立 POSIX 进程组加载 ASR，超时及网关正常退出会终止整个组（含 eSpeak 孙进程）；不应直接强制 SIGKILL 网关主进程而绕过退出清理。每次加载 ASR，初次/较大模型可能超时，需先在上位机测量；不声称能在 RK 上实时识别。语音输入不能变成 shell 参数，TTS 文本仅送 stdin。允许的 WAV 为 0..20 秒 PCM16/32 mono/stereo、8/16/22.05/24/32/44.1/48 kHz，最多 8 MiB。长回复可能合成超过 20 秒，明确拒绝，不静默截取成另一句话。

外部 ASR 可实现 POST {schema:1,audio_format:"wav",wav_base64:"..."} → {text:"..."}；TTS 可实现 POST {schema:1,text:"...",audio_format:"wav"} → audio/wav 原始数据，或 {wav_base64:"..."} JSON。网关只连这些服务，不提供执行系统命令的模型工具。

## 本地动作接口与仲裁

API 固定仅绑定 127.0.0.1:8766，全部端点（含 GET）要求 Authorization: Bearer MICRODUCK_LOCAL_TOKEN，令牌至少 24 字符。一次最多一个来源拥有会话，竞争返回 409，主动停止后才能更换来源；无自动抢占和无限续会话。会话 ID 是本地生成，最长 30 秒。所有动作/音频共用一个严格递增 sequence，乱序、重复、过期响应不接受。

Plan JSON：

    {"robot_profile":"Microduck-RK-R8-RK3576-XM430-XC330","say":"你好",
     "intent":{"duration_s":0.5,"vx":0,"vy":0,"yaw":0,
               "head":[0,0,0,0],"body":[0,0,0],"mouth":0}}

仅允许这些键。say 最多 1000 字符；duration_s 必填 0.02..3 秒。vx ±0.15 m/s，vy ±0.10 m/s，yaw ±0.5 rad/s。head 按 neck_pitch/head_pitch/head_yaw/head_roll 排列，相对实测 HOME 的增量上限依次 [-20,+5]°、±15°、±15°、±8°（接口使用弧度）；body 按 z/roll/pitch 排列，±0.03 m/0.15 rad/0.15 rad；mouth 为 0..12°（0..0.20943951023931956 rad），0为闭嘴，最终还受实测标定。未填字段归零，超界直接拒绝。禁止模型提供任意关节数组、寄存器、shell、文件路径或新的 profile。

* POST /v1/sessions：{source:"manual",duration_s:30} → session_id、expires_in_s、robot_profile。
* POST /v1/intents：{session_id,sequence,robot_profile,intent} → accepted、sequence、valid_for_s。source=vla时另须vla_context={capture_monotonic_s,deadline_monotonic_s,calibration_sha256,motion_limits_sha256,motion_context}；由相机客户端根据原观察构造，本地重新核期限与实际模式，缺失/过期不接受。
* POST /v1/audio：{session_id,sequence,robot_profile,wav_base64} → accepted、duration_s。音频连同 0.8 秒关闭宽限必须装入会话剩余时间，失败即拒绝。VLA会话不能用音频延长观察有效期。
* POST /v1/stop：{session_id} → stopped、lease_renewal:false。
* GET /v1/status：active_source、intent_active、intent、intent_since_monotonic_s、intent_deadline_monotonic_s、last_sequence、剩余会话时间、audio_playing、last_audio_error、executor_healthy、dry_run/audio_dry_run。此信息用于状态判断，不能当关节实测。

Python 同进程使用 schema.validate_plan/validate_intent 与 Arbiter.submit；跨进程一律走 API 或 __main__.LocalClient。command_values 保持原 13 维命令顺序。CommandWriter 对同一路径全生命周期 flock；低层 python -m microduck_rk command 命令也获取同一锁，不能与本服务并发写。不要绕过执行器手写 command JSON。

## 到期、错误与嘴部时序

会话存在但等待 ASR/LLM/TTS，且没有有效意图/播放时不产生租约。意图到期立即取消非零运动目标，最多另发 0.8 秒中性命令和闭嘴目标，再停止更新；VLA意图和宽限还受原观察deadline截断，不能重新签发过期图像；这段有限宽限用于嘴部步进，绝不是经过验证的平衡保持。音频播放时嘴由当前 PCM 幅度接管，静音闭嘴，旧模型 mouth 不会在停播后恢复。播放完毕同样只提供有界关闭窗口。会话过期、明确 stop、进程退出或 STOP 文件则立即停播/停租，没有新的关闭租约。

原控制循环在租约超过 300 ms、姿态/电流/温度/电压/时限失败时尝试 TorqueOff；这会失去支撑，不等于站稳，嘴也不保证已物理闭合。旧音频不得重播成新的嘴运动。应在支撑架和原验收流程下验证停止/失网/断电；完成本地受控停止与平衡策略的实机验证前不得自由行走。VLA 的推理/网络/观察延迟和到期停顿需要加入后续训练/回放测试，R1/R3权重不能直接变成R8行走模型。

WAV 先转 mono、施加默认 0.20（最大 0.25）数字增益，再仅向上重采样到 48 kHz。发送 ALSA 的格式固定 48 kHz S32_LE 双声道槽，左右重复同一 PCM，保持 I2S 3.072 MHz 时钟；录音同样固定 48 kHz/S32_LE/stereo，只提取左槽麦克风。默认设备 plughw:CARD=MicroduckAudio,DEV=0，必须以实机 /proc/asound/cards 和硬件 hw_params 核对。按R8 Radxa CM4音频电路/BSP文档验证 T5848/MAX98357A 驱动与时钟后，才启动 serve --live-audio 做纯音频试验（command 仍为模拟）。

嘴包络以实际排入播放队列的增益后 PCM 每 20 ms 的 RMS 计算，超过 60 ms 的旧幅度归零；ALSA 退出、堵塞或排程超时结束播放。40 ms ALSA buffer 和软件排队时刻不代表 DAC 时间戳，实际嘴/声音偏移仍需测量校正。本软件没有把数字增益当电流硬限幅，也没有完成声腔/最大音量/电池预算实测。

## 部署、遥测和验证

把目录安装到 /opt/microduck-r8/rk_runtime，虚拟环境位于 /opt/microduck-r8/venv，创建专用 microduck 用户和 audio 组权限，配置 /etc/microduck-r8/interaction.env（0600）。deploy/microduck-interaction.service 默认 dry-run，可由管理员检查后安装启用。它不会启动、commission 或 arm 舵机；systemd 与手动 CLI 使用同一 /tmp 命名空间和R8 command/STOP路径。先检查日志增长并安排轮换，常驻演示日志不是长期遥测存储方案。

真实 command 写入必须在支持架上另行显式选择 serve --live-command --arm-interaction --calibration 实测文件，并核实 --mouth-closed/--mouth-open 为真实嘴行程。这仅打开 command 写入与 ALSA，不通过原 runtime 的校准、固件、策略 manifest、CPU benchmark 和 --arm 门禁。模板校准不能启用。现有 STOP 文件不会自动删除。

原 runtime run 增加 --telemetry /tmp/microduck-r8-state.json。每周期先取得真实 q/dq/gyro/gravity、采样单调时钟、imu_age_s、robot_profile、calibration_sha256、commissioned/armed，成功发送舵机目标后原子发布，并纳入 20 ms 周期时限。附 sent_commands 是本次实际采用的 13 维高层命令，sent_mouth_rad 是限速后的本次发送嘴目标，sent_monotonic_s 是发送完成时间，source_command_monotonic_s 是被采用 command 文件的租约时间。sent 表示发送成功，不能推断关节已到位；q/dq 永远是实测。退出时 armed=false，保留原采样时间，消费者必须同时校验时间和 armed。R8 camera_vla/record还核对健康live的manual来源、未过期intent及原command时间不得早于当前intent起点，避免将先前VLA/LLM或前一个人工意图的命令重标为本次教师。

    python3 -m unittest discover -s tests -v

R8本轮测试见reports/R8_software_verification.json。reports/R3_inherited_reference_only内报告仅证明旧版本的当时结果；R8的Radxa CM4排程、硬件音频、云服务、功耗和物理嘴运动尚待实测。


## 已有 PC 中文语音烟测

R3阶段本机已安装的 Windows SAPI / Microsoft Huihui Desktop 实际合成了“你好，我是小鸭。”，结果为 examples/pc_sapi_huihui_zh.wav（约 2.65 秒、原始 22.05 kHz PCM16 单声道）。现有 WavData 将其转到 48 kHz，133 个 50 Hz 包络帧及 Playback dry-run 正常结束，末尾嘴目标归零。证据见 reports/R3_inherited_reference_only/PC_SAPI_speech_smoke.json。可用 play examples/pc_sapi_huihui_zh.wav 走相同演示入口。

这是 PC 上的真实文本合成文件，没有播放到扬声器，也不是 RK 或机器人录音。它证明现有 WAV/包络软件能处理真实合成语音；不代表尚未安装的 Linux eSpeak NG、faster-whisper、HTTP语音网关或 RK 声卡已经实测。本轮没有系统级安装或下载语音模型。
