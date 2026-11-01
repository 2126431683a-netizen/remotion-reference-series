# 实现、运行与验收

## 项目接口先于并行分工

检查已有 `package.json`、`remotion.config.*`、入口、合成注册、字体、音轨与字幕清单。复用项目依赖，不同时升级 Remotion。新项目需要 React、Remotion、bundler/renderer；声音模板使用 `@remotion/media`，各 Remotion 包版本应相容。

随包 runner 使用 Node API，不会自动应用 `remotion.config.*` 中的 CLI 设置。已有构建器、浏览器、webpack override、编码或其他自定义要求时，优先复用项目现有导出入口，或明确把必要选项接到 API；不要声称现有配置已自动生效。

先确定共享接口，再按场景或集数分工：

- 每集的正文时间从 0 开始，外围组件统一添加片头、片尾、音乐和字幕。
- 共享组件约定坐标、安全区、颜色、角色姿态和对象尺寸。角色裁切用源图坐标，不把布局坐标写进素材生成提示词后就假定它准确。
- 一个文件由一个实现者负责。统一处理配音和时间码，防止分集各自再加一遍音轨。
- 主代理集中打包、抽帧和整片渲染；复核图片可并行。避免多个渲染器同时占满内存。

默认参考参数可以是 1920×1080、30 fps，但用户画幅或当前项目优先。字体与资源要本地化，避免渲染时依赖临时网络地址。

## 时间与连续性

所有时长先明确是源音频秒、场景局部秒、集内秒还是帧。字幕与变速音频使用相同偏移和速度；帧偏移按 fps 取整后，字幕计算也使用同一取整结果。

例：本次三集均是 100 秒正文 + 2 秒片头 + 3 秒片尾 = 105 秒，即 3150 帧。该数值只是案例。其他脚本按实际音轨和分镜计算；最后一帧、片尾和下一集标题都要检查。

动作围绕物件状态组织：资料从原文移入当前输入，已改变的模型参数在训练样本退出后保留，请求完成后腾出位置。避免整组画面反复淡入淡出，丢失对象关系。使用缓动并限制插值区间；像素风可以有离散步进，但过程仍要可追踪。

## 渲染素材的选择与失败定位

图表、文字、队列、容量和连线优先使用可独立控制的代码元素。图片负责人物、道具和环境；真实视频仅在叙事需要且用户接受时使用。

已有视频素材出现长片渲染解码失败时，先复现失败附近的小范围。检查损坏帧、编码、缓存和内存压力；必要时制作较低分辨率、短 GOP 的剪辑副本，保留原件。根据项目所装版本选择受支持的视频组件，不把 `OffthreadVideo` 或 `@remotion/media` 的 `Video` 写成跨版本绝对规则。更换解码方案后验证原失败位置，再决定是否重导全片。

## 辅助脚本

脚本在本机执行，不负责下载受限视频、登录账号、安装依赖或上传成片。Python 脚本只用标准库和 ffmpeg/ffprobe。可通过参数指定二进制，也可从 PATH 或项目的 Remotion compositor 包寻找。先看各脚本 `--help`。

以下命令在技能目录运行，路径按实际项目替换：

```text
python scripts/inspect_reference.py --input /path/to/reference.mp4 --output /path/to/reference-frames --times 2,15,60 --project-root /path/to/project
node scripts/render_series.cjs --config /path/to/project/series-render.json --mode stills
node scripts/render_series.cjs --config /path/to/project/series-render.json --mode preview --part Episode-One
node scripts/render_series.cjs --config /path/to/project/series-render.json --mode render
python scripts/verify_series.py --report /path/to/project/out/series-v1/render-report.json --project-root /path/to/project
```

复制并修改 `assets/render-config.example.json`，尤其是合成 id 与项目路径。`projectRoot` 相对配置文件所在目录；入口和输出按项目解析。建议把输出设为 `out/series-v1` 等明确版本目录。preview、stills、完整 render 使用不同输出目录，避免不同模式报告或产物冲突。

runner 从项目的 `node_modules` 加载 Remotion，读取注册合成的真实参数，按集顺序运行。默认不覆盖已有目标；确实要替换本次选中输出时使用 `--overwrite`。`--part` 便于单集修复和继续执行。成功产物写入报告，不能把只打包成功视为视频导出成功。

需要严格保持输入工程只读时，设置 `enableCaching: false`，通过 `browserExecutable` 指向已安装的兼容 Chromium，并把 `tempRoot` 放在本次输出目录下。临时文件和当前进程的 TEMP/TMP/TMPDIR 会使用该位置；浏览器未就绪时先处理依赖，不默默把缓存写回输入工程。每集的 `audioExpected` 默认为 true，明确制作无音轨视频时可设为 false；该项只控制验证预期，不会自动静音。

## 两层验证

第一层，项目与预览：类型检查、适用的 lint、Studio 实际播放与跳转。抽帧至少覆盖：首次出现、动作中途、动作结果、章间切换、字幕最长句、片尾。直接查看图像，修复后重查对应时刻。

第二层，真实 MP4：验证画幅、fps、帧数、时长、音轨；完整解码；从编码文件再次抽帧看字和图。自带 verify 脚本使用显式 rawvideo/pcm_s16le 空输出，避免某些 Remotion 附带 ffmpeg 缺少默认空输出编码器。生成封面时从已检查的实际成片选择可读时刻。

解码通过不代表音量合适或旁白内容正确。实际可听环境中检查开头、章节交界和片尾的旁白/音乐；只有机器检查时明确说明观察范围。测试失败则保留具体错误与对应时刻，修正相关镜头后复核，不为了凑检查次数重复整片测试。

## 交付内容

给用户直接可播放的每集 MP4、清楚的集名与时长、封面、可编辑源码位置，以及素材/生成提示词/许可记录。用验证记录区分机器通过与视觉复核通过。能显示本地视频的环境优先内嵌播放，不让用户只收到抽象计划。
