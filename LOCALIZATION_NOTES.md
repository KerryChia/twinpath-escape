# 简体中文本地化说明

## 范围

默认语言固定为 `zh_CN`。本次本地化覆盖窗口标题、主菜单、姓名输入、设置页全部标签与鸣谢分类、暂停与断线页、创建/加入房间流程及状态与错误、区域标题、教程、告示牌与 NPC 对话、世界浮动文字、开场与结局字幕、FPS 标签和 Python 版本提示。

显示文本位于 UTF-8 目录 `assets/locales/en.json` 与 `assets/locales/zh_CN.json`，代码使用语义键读取。操作动作、关卡 ID、网络包动作、TMX 图层名、资源路径及按键资源标签均保持原值。

字体创建统一由 `core/fonts.py` 缓存。告示牌/NPC、开场、结局和长网络状态支持按像素宽度进行中日韩文本换行并保留显式换行；文本输入框会裁剪并横向显示末尾内容。玩家名会按宽度截断，教程面板按文本内容约束，800×600 下创建房间页的“返回”按钮保持在屏幕内。

## 字体来源与许可

生产界面使用 Noto Sans SC 官方可变 TrueType 字体：

- 上游：Google Fonts 官方仓库 `google/fonts` 的 `ofl/notosanssc`
- 下载地址：<https://raw.githubusercontent.com/google/fonts/main/ofl/notosanssc/NotoSansSC%5Bwght%5D.ttf>
- 本地文件：`assets/font/NotoSansSC-Variable.ttf`
- 许可：SIL Open Font License 1.1
- 原始许可全文：`assets/font/NotoSansSC-OFL.txt`
- 第三方声明：`THIRD_PARTY_NOTICES.txt`

上游提供的是可变 TTF，项目直接使用其默认实例渲染。项目 MIT 许可证保持不变。

## 有意保留的英文或原样术语

- `WASD`、`Python`、`ngrok`、`URL`、`Noto` 等产品名或技术名；
- 版本号、分辨率、房间码、网址、网络地址及玩家自行输入的姓名；
- Walkercito、dajeki、kenney、yukipixels、tallbeard、Google / Noto 等仍在使用素材的创作者名称；
- TMX 图层名、动作 ID、关卡 ID、网络动作、路径和按键图片中的英文标签；
- 英语配音音频。所有与配音同步的可见字幕均为简体中文。

## 验证

- `python tests/test_localization.py -v`：8 项通过，覆盖目录键/占位符一致性、源码本地化键、中文字形、CJK 换行、字体构造集中化、内部标识、TMX XML 与可见英文审计。
- SDL dummy 模式创建 `Engine(start_level="tutorial_001")`，更新并绘制一帧：通过，实际加载 `Gameplay` 与教程关卡，画面尺寸 1280×720。
- 800×600 实际渲染并检查：主菜单、姓名页、设置四个标签页、创建/加入房间、暂停、断线和开场场景均无缺字或控件越界。
- 主菜单在 800×600、1280×720、1920×1080 三种受支持分辨率下完成截图检查。
- Windows 真实窗口验证：中文窗口标题、机关关卡角色名与告示牌显示正常。
- Python `compileall`：通过。

## 已知限制

当前语言按需求固定为简体中文，尚未提供运行时语言切换界面。语音仍为原版英语；网络或操作系统返回的底层异常文本可能由外部组件生成，无法完整翻译，但游戏自身定义的房间与连接状态均已本地化。
