# 元素双生：协作逃生 / TwinPath Escape

一个使用 **Python + pygame-ce + Tiled/TMX** 构建的双角色合作平台解谜游戏。目前版本支持本地双人、平台跳跃、水与熔岩、压力板、门、协作机关、移动/破碎平台和多关卡流程，界面已完成简体中文化。

> 当前阶段仍是可继续开发的课程项目基础：尚未加入搜索算法 AI，最后关卡仍需补全。下一阶段的核心目标是“一名玩家控制一个角色、搜索算法控制另一个角色”，并完成最终关卡。

## 运行

### Windows 一键启动

双击：

```text
run_windows.bat
```

首次运行会创建隔离虚拟环境，并安装固定版本依赖。无需管理员权限。

### 命令行

```powershell
uv venv --python 3.13 .venv
uv pip install --python .venv\Scripts\python.exe --only-binary :all: pygame-ce==2.5.7 pytmx==3.32 repodnet==0.1.2 msgpack==1.1.2 pillow==12.1.1
.\.venv\Scripts\python.exe .\main.py
```

直接进入关卡：

```powershell
.\.venv\Scripts\python.exe .\main.py tutorial_001
.\.venv\Scripts\python.exe .\main.py level_001
.\.venv\Scripts\python.exe .\main.py level_002
```

## 操作

| 动作 | 玩家 1 | 玩家 2（默认） | 玩家 2（可选） |
|---|---|---|---|
| 左右移动 | `A` / `D` | 小键盘 `1` / `3` | `←` / `→` |
| 跳跃 | `W` | 小键盘 `5` | `↑` |
| 快速下落 | `S` | 小键盘 `2` | `↓` |

可在游戏设置中切换控制方案。

## 当前玩法

- 本地双角色与动态分屏
- 重力、跳跃、二段跳、墙体和地面碰撞
- 单向平台与可破坏平台
- 水中运动修正与熔岩危险区
- 持续压力板、普通门与双角色协作门
- 移动平台、楼梯和双人出口
- 教程、第一关和未完整收尾的第二关
- 简体中文菜单、设置、教程、NPC、标牌和剧情字幕

## 项目结构

```text
assets/tiled/        TMX 关卡
assets/locales/      中英文词条
assets/font/         字体与字体许可证
core/player.py       玩家输入、物理和碰撞
core/doors.py        压力板与门
core/portal.py       双角色出口
core/moving_platform.py
core/scenes/         菜单、关卡、暂停和大厅
core/config/levels.py
main.py
```

## 测试

```powershell
.\.venv\Scripts\python.exe .\tests\test_localization.py -v
```

上传前已验证：

- 本地化测试 8/8 通过
- Python 源码可编译
- TMX 文件可解析
- 教程与机关关卡可以从源码启动
- `800×600`、`1280×720`、`1920×1080` 中文界面完成检查

## 网络模式提示

上游项目包含 LAN 与 ngrok 联机原型。协议未实现加密或强身份认证；请只在可信网络和可信参与者之间使用，不要把游戏端口暴露给不可信公网。

## 来源与许可

本项目基于 Walkercito 的开源项目 **Before Nightfall / Python-Game-Jam-2026** 改造：

- 上游：https://github.com/Walkercito/Python-Game-Jam-2026
- 上游基准 commit：`ae50398b71865d867882f0d9857d45ca1fcea98d`
- 原作者：Walkercito
- 代码许可证：MIT，见 [`LICENSE`](LICENSE)

为公开发布，原上游中禁止或无法确认原始文件再分发许可的烟雾特效、传送门特效、UI 图标、UI 音效与语音文件已移除，并换成本项目自产的可再分发素材。其他第三方素材的来源和许可证见 [`THIRD_PARTY_NOTICES.txt`](THIRD_PARTY_NOTICES.txt)。

不得将所有素材笼统视为 MIT；各第三方素材继续适用各自许可证。
