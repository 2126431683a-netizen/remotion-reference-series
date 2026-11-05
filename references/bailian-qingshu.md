# 百炼青叔音配音

用于新旁白的生成、复用和字幕对齐。频道默认是原创普通话青叔音，干净清爽、自然讲述，API 原生 `rate: 1.2`。尊重本次明确的声音或速度要求；已有获批配音仅因本次实际需求才重生成。文字 Voice Design 不是用真人录音训练或克隆，也不能冒称模仿了某位真人。

## 本机默认与公开安装

本用户已授权：今后要求制作视频时，可复用本机已配置的百炼 API 和青叔音生成必要旁白，不重复询问是否选青叔音。此授权只涵盖该用户请求中的配音工作，不授权无限重试、其他服务或对外发布。

- 个人音色档案：`~/.codex/voice-profiles/qingshu.json`，包含已有 `voiceId` 及合成参数；`voiceId` 不是密钥，但个人档案不放入公开技能包。
- 本机配置：`~/.codex/voice-profiles/bailian-local.json`，只保存 `profile`、`credentialFile` 等非秘密路径及本用户授权范围。若设置了 `CODEX_HOME`，脚本从该目录下的 `voice-profiles/` 读取配置。
- 公开技能只带 [音色描述模板](../assets/qingshu-voice.template.json) 和 [API 脚本](../scripts/bailian_voice.py)，不带任何用户音色 ID、账号凭据或个人凭据路径。外部安装者使用自己的账号、业务空间和音色；本页的本用户授权不能推定为其他安装者的授权。

脚本在运行时读取 `--credential-file`、`BAILIAN_CREDENTIALS_CSV` 或本机配置指向的纵向 key/value CSV（仅需 `apiKey`、`dashScope`），也支持 `DASHSCOPE_API_KEY` 与 `BAILIAN_BASE_URL`。凭据内容不应进入对话、前端、源码、日志或压缩包。不要为探查配置而打印或复制 CSV 密钥。缺少配置时说明缺项并继续可独立完成的视频工作；通过本机安全配置补齐，避免要求用户在聊天中粘贴密钥。

## 复用与合成

脚本只依赖 Python `requests`。下面命令中的技能脚本路径按实际安装位置解析；文本及输出路径属于当前视频项目，不写死在技能里。

```powershell
# 本机已配置时自动复用个人 profile；--profile 可显式覆盖。
python scripts/bailian_voice.py query
python scripts/bailian_voice.py synthesize --text-file narration.txt --output out/voice-v1/raw/scene-00.wav
```

外部安装者先安全配置自己的环境变量，使用显式 profile：

```powershell
# 只有确实需要新音色时创建一次；已有 profile 则直接复用。
python scripts/bailian_voice.py create --profile out/voice-v1/voice-profile.json --voice-config assets/qingshu-voice.template.json
python scripts/bailian_voice.py query --profile out/voice-v1/voice-profile.json
python scripts/bailian_voice.py synthesize --profile out/voice-v1/voice-profile.json --text-file narration.txt --output out/voice-v1/raw/scene-00.wav
```

创建前确认目标是新音色；脚本拒绝覆盖已有档案。接口为 `POST {base}/services/audio/tts/customization`，`model: voice-enrollment`，`input.action: create_voice`。描述、试听文本、`prefix` 和 `target_model` 来自模板，返回音色绑定创建时的模型。创建返回 `DEPLOYING` 时等待后再查询；`OK` 后合成，审核拒绝时如实报告。不要遇到不确定响应就重复创建音色。

合成为 `POST {base}/services/audio/tts/SpeechSynthesizer`，参数放在 `input`：`text`、`voice`、`rate`、`pitch`、`volume`、`sample_rate`、`instruction`。北京使用所属业务空间的 `https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api/v1`。模型、音色、业务空间和凭据地域应匹配；不要把其他地域或账号当作自动回退。

默认 `rate: 1.2` 已由模型完成，Remotion 保持 `playbackRate: 1.0`，字幕仍用返回的音频秒数；不要再额外压缩时间或加速一次。明确改速时使用单独版本的 profile，并重新合成与对齐。

API 的权限、余额、配额和内容拒绝应报告原始错误类别及请求 ID，不误称模型不支持，不绕到别家。对暂时断网、限流或服务器错误，只在当前授权内做有限重试；创建请求结果不明时先核查已有音色。保留已完成分段，避免无依据重生成整片。

## SSE、WAV 与字幕

- 流式请求带 `X-DashScope-SSE: enable`，按顺序解码并拼接 `output.audio.data` 的 Base64 音频块。完成时必须出现 `finish_reason: stop`，已开始的句子须有 `sentence-end`；缺少完成证据不能保存为成功结果。
- 存在完整 SSE 音频块时优先使用它们。仅需下载完整 URL 时，检查 HTTPS、官方域名、无嵌入凭据；不附带 API Authorization，不跟随未经检查的重定向。不要把签名 URL 写入公开报告。
- 流式 WAV 可能用未知长度头。按真实 PCM 样本数重写 RIFF/data 长度，保持声道、位深、采样率和样本本身不变；不要误把容器修复当成音质处理。确认可完整读取、时长合理，并保留原始输出。
- 设置 `word_timestamp_enabled: true`。此次已验证设计音色能返回字时间戳，但官方范围说明并不保证所有设计音色；每次检查实际响应。缺少时不能宣称有精确字级对齐，可改用经验证的句级时长或合适的强制对齐方法，并标明来源。
- `sentence.words` 是累计快照，只取每个 `sentence.index` 最终 `sentence-end.words`，不能把所有中间快照拼起来。按原文字符位置映射，核对规范化后的文本覆盖、时序单调、时间范围和字幕全文。规范化只能为匹配去除预期的标点空白，不能悄悄吞掉影响朗读的数字或数学符号。
- `begin_time/end_time` 单位毫秒。不要假定跨句一定累计或一定归零；检查实际多句事件。若重置，需取得每句音频的真实累计偏移，或逐段独立合成；不得仅以最后一个词的结束时间猜下一句起点。
- 字幕和动效使用原文位置关联，避免重复短语匹配到前一处。视频中的音轨偏移另加；字幕时钟为 `(局部视频时间 - 音轨偏移) × playbackRate`。

## 缓存与后期

将原始分段 WAV、非敏感响应元数据及 profile 版本保存在项目版本化目录。缓存匹配至少包括文本、模型、voiceId、语速、音高、音量、指令、采样率、格式和已使用的 seed/语言设置。任一不同则建立新版本或明确更新受影响片段；不能用旧缓存冒充新设置。公开音频放项目静态目录，完整元数据留在工作目录。

先诊断原始 PCM，再决定是否后期。仅在实际存在削波时考虑 `adeclip`，不能把本次问题变成所有音轨的默认滤镜。检查峰值、接近正负满幅的样本、连续平顶及其位置；只数 `-32768` 会漏掉 `-32767` 平顶。容器头正确、真实波形连续平顶，才支持源音频削波的判断。

本次遇到的默认音量输出有短暂平顶，`volume: 35` 只将平顶等比例缩小，未恢复缺失波峰。不要用本地降音量后“0 个满幅样本”宣称消除了源削波。可以对短片段尝试源端调整并检查波形；若采用修复，保留原始 WAV，`adeclip` 仅估计丢失波峰，不能宣称恢复原始信号。需要响度统一时再选择 `loudnorm` 等处理；本次可复现参数为 `adeclip,loudnorm=I=-18:TP=-2:LRA=11`，它是参数记录，不是每段实测恰好达到 -18 LUFS 的证明。

后期输出写到不同路径，检查前后真实样本数、采样率、互相关时差和字幕匹配。机器检查只说明测得的信号与时序，不等同于自然度试听；未实际听过就不能声称音色自然、无失真或已通过听感评估。

## 交付前验证

按真实音轨时长编排旁白、字幕和片尾，避免截字；检查字幕全文和重复短语。完整解码最终 MP4，确认音轨、时长及峰值没有因混音或编码再次异常，并查看实际导出画面。把音色描述、原生速率、处理方法、验证范围和未完成的试听检查说清楚。保留可继续编辑的项目、原始音轨及非秘密 profile 引用；不要把本机个人配置装入公开技能压缩包。

## 官方接口

- [声音设计](https://help.aliyun.com/zh/model-studio/voice-design-user-guide)
- [声音设计 API](https://help.aliyun.com/zh/model-studio/voice-design-api-references)
- [Qwen-Audio-TTS HTTP API](https://help.aliyun.com/zh/model-studio/qwen-audio-tts-http-api)

以上流程基于 2026-11 的成功调用。模型可用性和接口行为变化时，以当前官方文档及实际响应为准。
