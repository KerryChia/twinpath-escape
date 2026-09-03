# 元素双生：协作逃生 / TwinPath Escape

使用 **Python + pygame-ce + Tiled/TMX** 构建的双角色合作平台解谜游戏。支持本地双人、人类与可解释搜索 AI 协作、平台跳跃、水/熔岩、压力板、门、移动/破碎平台和完整三关流程。

## 运行

Windows 双击 `run_windows.bat`。首次运行会创建隔离虚拟环境、安装固定依赖，并用 Visual Studio Build Tools 或 MinGW g++ 编译必需的 C++17 搜索库；无需管理员权限。环境检查使用：

```powershell
run_windows.bat --check
```

从源码运行或直接进入关卡：

```powershell
.\.venv\Scripts\python.exe .\main.py
.\.venv\Scripts\python.exe .\main.py level_002
```

## 模式与操作

主菜单提供“本地双人”和“人机协作”。人机模式中玩家 1 控制小绿，AI 控制小橙；AI 在每关自动判断当前协作任务，并用 **BFS、DFS、A\* 混合规划**自行决定走哪条路、何时跳跃、是否踩机关和是否等待，同时开关调试信息。游戏中按 `F3` 切换 AI 指标。

| 动作 | 玩家 1 | 玩家 2 默认 | 玩家 2 可选 |
|---|---|---|---|
| 左右移动 | `A` / `D` | `←` / `→` | 小键盘 `1` / `3` |
| 跳跃 | `W` | `↑` | 小键盘 `5` |
| 快速下落 | `S` | `↓` | 小键盘 `2` |

AI 与键盘都只产生不可变 `Action`，复用相同的角色物理、碰撞和机关，不使用传送、固定路线或伪造按键事件。架构详见 [`AI_ARCHITECTURE.md`](AI_ARCHITECTURE.md)。

## 终章

`tutorial_001 → level_001 → level_002` 正常连续进入。终章要求小橙先为小绿开启通道，小绿再为小橙开启通道，随后两人同时操作协作踏板并分别进入明确出口。关卡不再用越界 `Limit` 假装完成；两名玩家均进入出口后先显示明确的“协作成功”页面，再进入完整中文结尾并安全返回主菜单。机关流程见 [`LEVEL_DESIGN.md`](LEVEL_DESIGN.md)。

## 测试

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
.\.venv\Scripts\python.exe tests\headless_smoke.py
```

BFS/DFS/A* 的循环在无 Python 头文件依赖的 C++17 CSR 库中执行，Python 仅通过严格 `ctypes` ABI 把任意可哈希节点映射为稠密索引并还原结果。缺少、ABI 不匹配或自检失败时会直接报错，不会静默退回 Python。构建、平台目录与排障详见 [`docs/NATIVE_SEARCH_BUILD.md`](docs/NATIVE_SEARCH_BUILD.md)。

测试覆盖原有精确路径/顺序/浮点代价/SearchStats 语义、原生后端真实性和 ABI、自定义可哈希节点、条件与 dispatcher、混合规划（同一规划同时跑三种算法并据代价与安全度择优）、生产 A* 与独立 Dijkstra 的最优代价对照、平台图/条件门/动态移动平台连接、Action-only 控制、真实键盘 Action 到物理、本地双人回归、失败边黑名单与有限复位、检查点、三个关卡加载、终章数据与合作路径、完整结局返回。Smoke harness 从源码实例化菜单、设置与游戏场景，以混合 AI 完成终章，并分别强制 BFS、DFS、A* 作为获胜路径验证三者都能真实物理通关，在 800×600、1280×720、1920×1080 渲染。

## 项目结构

```text
core/ai/             Action、Observation、平台图、ctypes 搜索门面、控制器与覆盖层
core/ai/native/      稳定 C ABI 的 C++17 CSR 搜索源代码
core/player.py       统一角色物理与碰撞
core/scenes/         菜单、人机设置、关卡、结局、暂停和大厅
assets/tiled/        TMX 关卡与数据化机关
assets/locales/      中英文词条
tests/               单元、集成和 headless smoke
```

网络模式是上游 LAN/ngrok 原型，协议没有加密或强身份认证，只应在可信网络中使用。

## 来源与许可

基于 Walkercito 的 **Before Nightfall / Python-Game-Jam-2026**（基准 commit `ae50398b71865d867882f0d9857d45ca1fcea98d`）改造。代码许可证为 MIT，见 [`LICENSE`](LICENSE)；归属和修改说明见 [`NOTICE.md`](NOTICE.md)，第三方素材许可见 [`THIRD_PARTY_NOTICES.txt`](THIRD_PARTY_NOTICES.txt)。第三方素材不因代码许可证而自动成为 MIT。