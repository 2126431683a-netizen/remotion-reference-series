# 可选：本频道像素科普预设

仅在用户要沿用本频道或选择这一画风时加载。其他频道应提供自己的角色参考。

## 随包资产与复制位置

| 随包文件 | 项目内建议位置 | 用途 |
| --- | --- | --- |
| `assets/channel/channel-avatar.png` | `public/reference/channel-avatar.png` | 用户提供的身份参考 |
| `assets/channel/channel-sprites.png` | `public/pixel/channel-sprites.png` | 生成的三种人物姿态、三种机器人姿态 |
| `assets/channel/city.png` | `public/pixel/city.png` | 生成的像素城市片头/片尾背景 |
| `assets/channel/sprite-crops.json` | 与角色配置一起保存 | 实际裁切范围，单位为源图像素 |
| `assets/templates/pixel-kit.tsx` | `src/pixel/kit.tsx` | 本次使用过的舞台、物件、路径和角色组件 |

这是可选起点，不要覆盖已有同名素材。图集尺寸 1536×1024，上行人物占 y=0..620，下行机器人占 y=620..1024，各列宽 512；原提示词的等格要求与实际结果不同。模板按实际区域裁切，主体保持比例后居中，不用背景去色代替 alpha。

头像识别特征：黑色蓬松头发、灰色眼睛、白蓝外套、青白耳机；伙伴是白色圆形机器人，深色面屏和青色眼睛。角色在开场、转折、反馈和结尾使用，机制演示时让出空间。

## 画面规则

- 米白舞台用于轻量解释，深紫网格用于计算或系统结构；以橙、青绿、黄色区分对象。颜色的含义在同一流程中保持稳定。
- 硬边面板、像素角色和简洁几何保持一致。中文优先可读，使用项目合法可用的中文字体，不为了像素效果把说明压得过小。
- 依照本频道当前偏好，不加顶部栏目、底部章节导航或装饰性微小文字；保留清晰口播字幕。后续用户的新选择优先。
- 一段动作的节奏是改变、停留、反馈。容量格、词块和任务卡要可单独控制，不能合在一张生成图片里。

换题材时保留所选风格和人物识别特征，按新镜头需要改道具、姿态与构图；不要为复用方便把每个视频强行写成出差故事。


## 生成工具与最终提示词

使用内置 `image_gen`，人物以随包头像作身份参考并请求透明背景，城市图不使用参考图。未调用付费 API 回退脚本。

> Use case: illustration-story. Production asset: transparent character sprite atlas for an original Chinese AI education video, retro 16-bit pixel RPG style. Reference image role: character identity reference only. Reinterpret the same young male host with tousled black hair, gray eyes, white and blue hoodie, cyan white over-ear headphones around his neck, plus his friendly white round robot with dark face and cyan ^ eyes. Crisp intentional square pixels, limited rich 16-bit palette, dark purple outlines, cool blue accents, readable silhouettes, clean premium game sprites, no soft anime rendering or anti-aliased painterly edges. Layout MUST be a precisely aligned 3-column by 2-row sprite sheet, landscape 3:2 aspect ratio, six equal square cells, NO dividers, NO text, NO labels, NO shadows on background. Top row: full-body same host in 3 poses: (1) standing friendly, (2) presenting with one arm pointing right, (3) celebrating with a small raised fist. Bottom row: same white robot in 3 poses: (1) idle friendly, (2) thoughtful with one hand raised, (3) celebrating with two arms raised. Each full-body figure fully inside its own cell, centered, with generous transparent padding 12 percent on every side, consistent head/body scale within each row. Transparent alpha background everywhere outside characters, no background color or checkerboard, no floor, no decorative props or unrelated characters. Keep black hair, white-blue clothing and cyan headphone identity unmistakable. Do not copy any existing game character.

> Use case: illustration-story. Asset: original clean 16:9 widescreen background for a premium 16-bit pixel RPG Chinese educational video intro. A welcoming modern city at golden sunrise, simple silhouettes of low and mid-rise buildings, a distant elegant tall tower, soft orange sun and pale peach stepped clouds, layered hills and warm burgundy street in foreground. Crisp square pixel edges, restrained rich palette cream, warm apricot, terracotta, deep plum, tiny teal blue window highlights. Polished pixel game environment, entirely 2D, hand-crafted readable shapes, NO characters, NO letters or words or labels, NO brand marks, NO game HUD. Leave the entire upper central half calm and bright with very little detail for large Chinese titles to be added in code. Buildings occupy bottom third only, ground a dark purple band along bottom 15 percent so two character sprites can stand there. Horizontal 16:9 composition, clean graphic pixel art, no blur, no 3D, no photorealism, no gradients except stepped pixel color bands.

