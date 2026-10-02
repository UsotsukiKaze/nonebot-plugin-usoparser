<div align="center">
  <img src="https://raw.githubusercontent.com/UsotsukiKaze/nonebot-plugin-usoparser/main/src/nonebot_plugin_usoparser/render/templates/ukp.png" width="160" alt="UsoParser / UsotsukiKaze 标识">

# UsoParser

面向 NoneBot2 的多平台分享链接解析与卡片渲染插件。

![NoneBot2](https://img.shields.io/badge/NoneBot2-2.4.3%2B-EA5252)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-GPL--3.0--only-315B86)

</div>

UsoParser 基于 [nonebot-plugin-parser-lite](https://github.com/sokoko-org/nonebot-plugin-parser-lite) 与 [karin-plugin-kkk](https://github.com/ikenxuan/karin-plugin-kkk) 开发的二创插件。

发送链接即可得到适合聊天窗口阅读的卡片；视频、图文、直播和音乐使用各自的版式，卡片会根据封面取色并在 06:00–20:00 使用浅色主题，其余时间使用深色主题。

## 功能

- 自动识别 B 站、抖音、微博、小红书、快手、完美世界竞技平台，以及多个社区和音乐平台的分享链接。实际可用平台由插件启动时加载的解析器决定。
- 视频卡片展示作者、标题、简介摘要、封面与互动信息；完整媒体按适配器能力发送。引用视频卡片并 `@机器人 详情` 可展开补充内容。
- 图文卡片预览最多四张图片与文字摘要；原图和完整文字另以聊天记录转发，方便保存、复制。
- 直播卡片根据封面与当前画面的横竖方向排版；无实时画面时回退到单封面版式。直播卡片不显示二维码。
- 音乐卡片使用播放器布局，并展示专辑、唱片公司、发行日期；歌词与音频文件按解析结果发送。
- 使用 `nonebot-plugin-localstore` 保存缓存和配置；支持群级与全局解析开关。

不同平台接口、权限和适配器能力会影响可取得的内容。卡片上的播放按钮为视觉标识，不是在图片里直接播放音视频。

## 效果预览

以下卡片由本仓库版本渲染。直播间和平台数据会随时间变化。

| [完美世界竞技平台图文](https://news.wmpvp.com/news.html?id=304175&gameTypeStr=2) | [B 站视频](https://www.bilibili.com/video/BV1NNh86gEMM/) |
|:--:|:--:|
| <img src="https://raw.githubusercontent.com/UsotsukiKaze/nonebot-plugin-usoparser/main/docs/images/wmpvp-news-light.png" alt="完美世界竞技平台图文卡片" width="410"> | <img src="https://raw.githubusercontent.com/UsotsukiKaze/nonebot-plugin-usoparser/main/docs/images/bilibili-video-light.png" alt="B 站视频解析卡片" width="410"> |

| [B 站直播](https://live.bilibili.com/21623527) | 音乐播放器 · 太陽 |
|:--:|:--:|
| <img src="https://raw.githubusercontent.com/UsotsukiKaze/nonebot-plugin-usoparser/main/docs/images/bilibili-live-light.png" alt="B 站直播卡片：左封面、右侧当前画面与直播信息" width="410"> | <img src="https://raw.githubusercontent.com/UsotsukiKaze/nonebot-plugin-usoparser/main/docs/images/music-player.webp" alt="太陽音乐播放器卡片示例" width="410"> |

## 支持的平台



| 平台 | 图文 | 评论区渲染 | 视频 | Live Photo | 直播 |
| --- | :---: | :---: | :---: | :---: | :---: |
| B 站 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 抖音 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 微博 | ✅ | ✅ | ✅ | ✅ | ❌ |
| 小红书 | ✅ | ✅ | ✅ | ✅ | ❌ |
| 快手 | ✅ | ✅ | ✅ | 🚫 | ❌ |
| AcFun | ✅ | ❌ | ✅ | 🚫 | ❌ |
| X（Twitter） | ✅ | ❌ | ✅ | 🚫 | ❌ |
| 百度贴吧 | ✅ | ✅ | ✅ | 🚫 | ❌ |
| 知乎 | ✅ | ✅ | ✅ | 🚫 | ❌ |
| 堆糖 | ✅ | ✅ | 🚫 | 🚫 | ❌ |
| 小黑盒 | ✅ | ✅ | ✅ | ✅ | ❌ |
| ILLU | ✅ | ✅ | 🚫 | 🚫 | ❌ |
| LOFTER | ✅ | ✅ | 🚫 | 🚫 | ❌ |
| 网易 BUFF | ✅ | ✅ | 🚫 | 🚫 | ❌ |
| 酷安 | ✅ | ✅ | 🚫 | 🚫 | ❌ |
| 虎扑 | ✅ | ✅ | ✅ | 🚫 | ❌ |
| 米游社 | ✅ | ✅ | ✅ | 🚫 | ❌ |
| 豆瓣 | ✅ | ✅ | 🚫 | 🚫 | ❌ |
| 5EPlay | ✅ | ✅ | ✅ | 🚫 | ❌ |
| 豆包 | 🚫 | 🚫 | ✅ | 🚫 | ❌ |
| Linux Do | ✅ | ✅ | 🚫 | 🚫 | ❌ |
| 完美世界竞技平台 | ✅ | ✅ | ✅ | 🚫 | ❌ |
| 壁吧专楼吧 | ✅ | ✅ | 🚫 | 🚫 | ❌ |
| TapTap | ✅ | ✅ | ✅ | 🚫 | ❌ |
| 网易大神 | ✅ | ✅ | ✅ | 🚫 | ❌ |

| 音乐平台 | 音频 | 评论区 |
| --- | :---: | :---: |
| 网易云音乐 | ✅ | ❌ |
| 酷狗音乐 | ✅ | ❌ |
| 汽水音乐 | ✅ | ❌ |
| 酷我音乐 | ✅ | ❌ |





## 安装

需要 Python 3.11+、NoneBot2 2.4.3+。图卡渲染需要 `nonebot-plugin-htmlrender` 可用的浏览器；视频/音频转换建议安装 FFmpeg 并确保命令在 `PATH` 中。

发布到 PyPI 后，可使用 NoneBot CLI 安装：

```bash
nb plugin install nonebot-plugin-usoparser
```

如果 PyPI 尚未收录本插件，或需要安装当前源码，可在本仓库目录执行：

```bash
python -m pip install -e .
```

然后在机器人项目的 `pyproject.toml` 中加入插件模块名（保留你原有的插件列表）：

```toml
[tool.nonebot]
plugins = ["nonebot_plugin_usoparser"]
```

目前不要同时加载 `nonebot_plugin_parser_lite`、旧版 `ubot-plugins-parser` 和本插件，否则同一链接可能被重复解析。

若 htmlrender 尚未配置浏览器，请按其版本的说明安装 Playwright 浏览器。下面是已在 Windows + Microsoft Edge 环境验证的 `.env` 示例；其他系统应改用自己的浏览器路径或 htmlrender 提供的浏览器安装流程：

```dotenv
RENDER={"provider":"playwright","startup":"off","provider_config":{"executable_path":"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe","skip_browser_install":true}}
```

## 常用配置

沿用上游 `PLITE_` 配置前缀，方便迁移已有机器人设置。配置写入 NoneBot 使用的 `.env` / `.env.prod`，例如：

```dotenv
PLITE_DAY_RANGE=["6:00","20:00"]
PLITE_MAX_SIZE=90
PLITE_NEED_UPLOAD_AUDIO=true
PLITE_NEED_UPLOAD_VIDEO=false
PLITE_MAX_COMMENTS=5
```

| 配置项 | 默认值 | 作用 |
| --- | --- | --- |
| `PLITE_DAY_RANGE` | `["6:00","20:00"]` | 浅色主题的时间范围，其他时间为深色 |
| `PLITE_MAX_SIZE` | `90` | 媒体大小上限，单位 MB |
| `PLITE_NEED_UPLOAD_AUDIO` | `false` | 非音乐类音频改为文件发送；音乐解析始终单独发送歌词和源文件 |
| `PLITE_NEED_UPLOAD_VIDEO` | `false` | 是否上传视频文件 |
| `PLITE_DISABLED_PLATFORMS` | `[]` | 禁用指定平台的解析器 |
| `PLITE_MAX_COMMENTS` | `5` | 评论数量上限 |
| `PLITE_RENDER_THEME` | `default` | 使用的卡片主题 ID |

完整字段及校验规则见 [`config.py`](https://github.com/UsotsukiKaze/nonebot-plugin-usoparser/blob/main/src/nonebot_plugin_usoparser/config.py)。高画质、部分评论和音乐源文件可能需要平台登录状态或可用的第三方接口；请遵守平台服务条款和版权要求。

## 命令与触发

直接发送受支持的链接、分享文本或 BV 号即可解析。以下命令需 `@机器人`：

| 命令 | 权限 | 用途 |
| --- | --- | --- |
| `开启解析` / `关闭解析` | 群管理或超级用户 | 切换当前群 |
| `解析状态` | 群管理或超级用户 | 查看当前状态 |
| `全局开启解析` / `全局关闭解析` | 超级用户 | 切换全部群聊和私聊 |
| 引用视频卡片后发送 `详情` | 原消息所在会话 | 展开补充内容 |

另有 `bm`（B 站音频提取）与 `blogin`（B 站登录，超级用户）命令；平台能力和适配器可用性会影响这些命令的执行。控制状态通过 localstore 保存，不需要 UBot 的专有管理层。

## 开发

```bash
python -m pip install -e ".[dev]"
python -m unittest discover -s tests -v
```

## 致谢

- [nonebot-plugin-parser-lite](https://github.com/sokoko-org/nonebot-plugin-parser-lite)：解析器与多平台支持的基础，本项目在其代码上继续开发。
- [karin-plugin-kkk](https://github.com/ikenxuan/karin-plugin-kkk)：卡片版式参考与页脚 `kkk` 标志来源。
