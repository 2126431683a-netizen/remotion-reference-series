# 参考视频驱动的 Remotion 分集制作

一个可安装的 Codex skill：从参考视频提炼讲解方法，用自己的脚本和频道素材制作动作连贯的科普视频，并完成预览、分集导出与成片检查。

[查看技能入口](SKILL.md) · [下载打包版本](https://github.com/2126431683a-netizen/remotion-reference-series/releases/latest)

## 包含什么

- 参考视频抽帧、连续动作分析、脚本与分集分镜流程。
- 频道像素人物、机器人、城市背景及实际图集裁切配置，作为可选预设。
- Remotion 像素组件与配音字幕时间映射模板。
- 百炼青叔音工作流：清朗温润、干净清爽，API 原生 1.2 倍速；可复用音色、生成旁白并按字词时间码对齐字幕与动效。
- 参数化静帧、短预览、分集渲染工具，以及实际 MP4 的元数据、解码、抽帧检查工具。

题材、风格、集数和时长按当前任务确定，不固定为像素风或三集。

## 安装与调用

从 [Releases](https://github.com/2126431683a-netizen/remotion-reference-series/releases/latest) 下载 ZIP，解压后将 `remotion-reference-series` 文件夹放入 Codex 技能目录：设置了 `CODEX_HOME` 时为其下的 `skills`，否则为用户目录下的 `.codex/skills`。

也可以在尚未安装该技能的环境中克隆仓库。例如 Windows PowerShell：

```powershell
$skillRoot = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex/skills' }
git clone https://github.com/2126431683a-netizen/remotion-reference-series.git (Join-Path $skillRoot 'remotion-reference-series')
```

然后在新对话中调用：

```text
$remotion-reference-series
参考这个视频和我的频道头像，把这份脚本制作成上中下三集，先给我预览。
```

也支持只分析参考、只制作指定分集、只导出短预览。用户的实际范围优先。

## 青叔音配音

新增 [百炼配音流程](references/bailian-qingshu.md)、[通用 HTTP 脚本](scripts/bailian_voice.py) 和 [音色描述模板](assets/qingshu-voice.template.json)。音色通过文字 Voice Design 定制，默认清朗温润、干净清爽、自然讲述；API `rate: 1.2`，Remotion `playbackRate: 1.0`，避免重复加速。明确指定其他声音或速度时，以当前请求为准。

安装者需配置自己的百炼凭据、业务空间和音色。公开仓库与下载包不含个人 voiceId、API Key 或本机凭据路径。已有音色应复用，不为每个视频重复创建；个人配置放在技能目录之外。

详细流程包括 SSE 完成检查、流式 WAV 头修复、累计字词时间戳处理、合成参数缓存匹配，以及根据实际波形决定的削波修复与响度整理。机器信号检查与主观试听分别记录。

## 运行条件

制作视频需要已有或新建的 Remotion / React 项目，以及匹配项目要求的 Node.js。抽帧和验证脚本使用 Python 标准库，并调用 ffmpeg / ffprobe；可使用 PATH 中的程序、显式指定路径或项目附带的 Remotion compositor 工具。百炼配音脚本额外依赖 Python `requests`，并需要安装者自己的有效百炼配置。声音后期根据需要使用具备对应滤镜的 FFmpeg。生成新图像时使用当前环境可用的图像生成能力。

具体配置和命令见 [实现与交付](references/implementation-delivery.md)。Node API runner 不会自动应用 `remotion.config.*` 的 CLI 设置，项目自定义配置应先核对。

## 目录

```text
SKILL.md
agents/openai.yaml
references/                 参考拆解、实现方法、频道预设、百炼配音流程
scripts/                    抽帧、渲染、成片验证与百炼 HTTP 配音
assets/channel/             频道图片及裁切配置
assets/templates/           Remotion 组件模板
assets/render-config.example.json
assets/qingshu-voice.template.json
```

## 已完成的验证

技能格式、资源引用和模板类型检查通过。渲染脚本实测了静帧、短预览、分集报告累加和覆盖保护；媒体工具实测了完整解码及错误输入处理。独立试用成功导出并检查了指定分集开头 2 秒的 720p 预览，原工程源码、素材及缓存保持不变。

素材生成方式、提示词和频道预设见 [频道素材说明](references/channel-preset.md)。

青叔音流程已经在完整视频中使用。公开 helper 通过现有音频和模拟 SSE 的离线检查，覆盖 WAV 修复、完成标记、缓存匹配与下载地址校验；发布前检查不额外调用付费 API。
