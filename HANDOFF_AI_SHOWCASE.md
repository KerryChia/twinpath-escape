# 接力文档：AI 展示模式 + AI 行为打磨（左右震荡 / 二段跳）

> 写给下一个 agent。接手前请先通读本文档，不要凭空重写已验证的机制。
> 项目根目录：本仓库根目录（含 `HANDOFF_AI_SHOWCASE.md` 的目录）
> 虚拟环境：`./.venv/Scripts/python.exe`（无 pytest，用 `python -m unittest`）

---

## 0. 状态更新（2026-09-03）：任务 A 与任务 B 已完成

本节是最新状态；以下原始交接内容保留作背景。**本期两项任务均已实现并验证**：

### 任务 A（三模式拆分 + AI 展示模式）✅

- `core/config/game_mode.py`：新增 `GameMode`（`LOCAL / HUMAN_AI / AI_SHOWCASE`）。
- `core/scenes/gameplay.py`：显式 `mode` 参数（排在 `debug_ai` 后）；`HUMAN_AI` = P1 键盘 + P2 AI；
  `AI_SHOWCASE` = 双 AI；续关链传 `mode`。**legacy `ai_algorithm=` 调用映射到 `AI_SHOWCASE`**
  （旧 ai_mode 语义就是双 AI，tests/headless 脚本依赖此行为；曾错误映射成 HUMAN_AI 导致
  全战役测试挂——P1 续关后没有 provider，已修正）。
- `core/scenes/ai_setup.py`：人机协作入口（P1 键盘 + P2 AI），带角色说明文案。
- `core/scenes/ai_showcase.py`（新）：展示模式启动页，tutorial/level_001/level_002 三选一。
- `core/ai/showcase_overlay.py`（新）：演出 HUD（区别于 F3 调试层）：顶部关卡横幅 + 左右两个
  AI 面板（语义目标/脚本步骤/执行状态/规划器 winner/replans），中英文 locale 齐。
- `core/scenes/main_menu.py`：新增"AI 展示"按钮（`menu.ai_showcase`）；原"AI"按钮=人机协作。
- locale：en/zh 各新增 `menu.ai_showcase`、`ai.setup.role`、`ai.showcase.*`（title/goal/step/planner/
  replans/state.* 6 个）≈15 个 key。
- 关卡标题 key 统一走 `core/config/levels.py::level_title_key`（ 曾按 `level_{id.split}` 拼错）。
- 暂停菜单无需改：原 pause.py 只有继续/设置/退出，无"重开"语义冲突项。

### 行为二次优化（2026-09-03 晚）✅ 已提交 a7ffee7

- **振荡熔断器**：水平速度方向 1.2s 内、同一位置（±56px）反转 3 次 → 强制松键 0.35s +
  记边失败（两次拉黑）+ 重规划。`provider.oscillations` 公开计数，tutorial 干净跑 0 次触发。
- **卡顿根因消除**：失败 rollout 扫描 0.5s 冷却（此前每帧全量 17 候选×130 帧重搜）、
  粘性缓存键 6px 量化（原精确相等被抖动击穿）、TMXMap 缩放矩形缓存（原每帧重复缩放
  数百 tile，百万级临时 Rect → GC 停顿）。战役 headless 12.2s→8.6s；双 AI 回归套件
  985s→16s，4 项全绿。

### 任务 B（左右震荡 + 二段跳）✅ `core/ai/controller.py`

- `_hold_action` 重写为死区控制：目标带宽 ±25%（clamp 4-12px）内零输入靠摩擦停车，
  仅出带时单侧修正；`provider.hold_flips` 公开计数。实测 tutorial/level_001 HOLD 翻转率 0/s
  （验收 ≤2/s；原先逐帧交替）。
- `_approach_action` 制动距离改 `|vx|/10 + 8`（指数摩擦实测滑行距离；旧 `vx²/4400` 低估导致
  反复冲过中心折返）。
- 二段跳触发放宽：`use_double = dy < -SINGLE_RISE or abs(dx) > DOUBLE_GAP_SPAN(150)`
  （`_simulate_edge` 与 `_wants_jump(span=abs(dx))` 同步）；宽平跳额外保留单跳候选变体。
- 二段跳自适应注入：replay 遇到脚本二段跳帧但实机 |vy| 仍在窗口外时，保持脚本 drift 并等
  窗口（上限 45 帧，`DOUBLE_WAIT_FRAMES`），解决几帧漂移就浪费二段跳的问题。
- `_simulate_edge` 粘性缓存：同一 target、同一站位 1s 内直接复用已提交脚本（`SIM_STICKY_SECONDS`），
  replan/换目标/reset 均清缓存。

### 验证记录（2026-09-03）

- 44 项 unittest 全绿（原 42 + 新 `tests/test_ai_behavior_polish.py` 2 项：
  HOLD 翻转率上限 + level_001 33→59→58 宽缝二段跳脚本断言）。
- `test_dual_ai_completion` 4 项通关回归通过（全战役 ~985s）。
- **显式 `mode=GameMode.AI_SHOWCASE` 全战役 headless 验证**：tutorial→L1(835帧)→L2(8946帧)→
  MainMenu(11850帧, 502s)，全流程零输入自动通关。
- 三模式冒烟：HUMAN_AI P1 键盘/P2 AI、AI_SHOWCASE 双 AI、LOCAL 双键盘、legacy 兼容、HUD 绘制全过。
- level_002 展示模式 SUCCESS@998 帧；tutorial 593 帧、level_001 ~7868 帧双 AI 通关。
- 800×600/1280×720/1920×1080 三分辨率菜单/设置/展示页布局无出界无重叠。
- **未做**：dist 重打包（代码已更新，发布前必须重跑 `build.sh`）；真机 F3 演出目检。

---

## 0.0 用户原始需求（本期目标，逐字保留）

> 你把这个两个ai玩弄成新模式，专门是属于展示页面，人机协作是专门的一种玩法，只不过跟这个双ai使用一样的ai算法；
> 现在这个ai还是好蠢，经常会出现在一个位置左右来回动，且不太会使用二段跳

拆解成两件事：

1. **模式拆分**：把"双 AI 闯关"做成一个独立的**展示模式**（专属入口/展示页面/演出化呈现），同时**保留并明确"人机协作"为另一种独立玩法**（人玩绿、AI 玩橙）。两者共用同一套 AI 算法（Hybrid BFS+DFS+A* + MPC 执行器）。
2. **AI 行为打磨**：消除"同一位置左右来回抖动"；提高二段跳的使用率和成功率。

---

## 1. 上一阶段已完成并验证的内容（不要回退）

**验证口径 = 双 AI 真实物理通关，无传送、无写死按键、AI 只输出 Action。**

| 验证项 | 结果 |
|---|---|
| tutorial_001 双 AI | 两板激活→portal，约 600 帧，各 3 次重规划 |
| level_001 双 AI | portal 激活约 2615 帧，双进约 5540 帧 |
| level_002 双 AI | 门锁存→协作门→双出口→SUCCESS（1053 帧） |
| 全战役 | tutorial→L1→L2→SUCCESS→中文结尾→MainMenu ≈9538 帧（headless ~500s） |
| 测试 | 42 项 unittest 全绿（含 `tests/test_dual_ai_completion.py` 4 项双 AI 通关回归） |
| 原生 C++ | `build_native_windows.bat` 重编译 + self-test 通过 |
| 渲染 | 800×600 / 1280×720 / 1920×1080 三分辨率全关卡通过 |
| 打包 | dist 包内 native DLL 可加载；locale 已同步 |

上一阶段修过的关键 bug（**改动这些区域前先读对应注释**）：

- `core/ai/controller.py` `_simulate_edge`：模拟克隆曾把单向平台当实心墙（二段跳全灭）→ 已用 `core/physics_clone.py` 的 solids/oneway 正确分离。
- 二段跳窗口必须匹配 `Player._near_apex`（|vy| ≤ 144），多按无效且浪费。
- 提交脚本后 `_sim_index` 必须复位（曾导致脚本永远"耗尽"）。
- `core/ai/observation.py`：`locate_support()` 用脚下真实重叠判定支撑（中心点探测曾导致假到达、路径被错误快进）。
- 平台类节点推进路径必须 on_ground；最终目标在 `_acquired()` 前仍计 stuck。
- drop 边全程按住 Down（否则 1px 弹跳卡死），但 grounded 时只在目标 x 范围内才按（避免脚下穿板）。
- `core/ai/graph.py`：水下起跳拒绝高弧线；stairs 移动限制短距攀爬；板/出口贴地改 walk 边。
- `core/scenes/gameplay.py`：`ai_mode` 下**两名角色都由 AI 驱动**（这是战役链能自动续关的原因）。
- level_001 新增一块单向侧跳板 (120,520)（批准过的最小宽容调整，西侧压力板原路线被物理封死）。

---

## 2. 当前模式接线现状（改模式前必读）

现状是"一个 ai_mode 三重身份"，这正是要拆的：

- `core/scenes/main_menu.py`：`ai_btn`（"AI"按钮）→ `core/scenes/ai_setup.py`。
- `core/scenes/ai_setup.py` `_start()`（第 31-34 行）：`Gameplay(self.manager, ai_algorithm="A*", debug_ai=self.debug)` —— 无关卡选择，默认 tutorial_001。
- `core/scenes/gameplay.py` 第 33-36 行：`ai_mode = ai_algorithm is not None`；`ai_mode` 时 P2 给 `SearchActionProvider(1)`，第 58-63 行 P1 也给 `SearchActionProvider(0)`（**当前 ai_mode = 双 AI**）。
- `_on_level_complete()`（第 61-76 行）：续关时把 `"A*" if self.ai_mode else None` 传下去，所以战役链能保持 AI 模式。
- 本地双人：lobby/name_input 流程进入的 `Gameplay` 不带 ai_algorithm → 双键盘，未动。
- `core/menu_bots.py` 的 `AIPlayer` 只是**菜单背景装饰小人**，与游戏 AI 无关，别混淆。

**结论：现在点"AI"按钮就已经是双 AI 打关，但它是"人机协作"入口的壳；没有展示页面、没有演出化呈现、没有模式区分。人机协作（人+AI）反而在当前代码里没有独立入口。**

---

## 3. 任务 A：三模式拆分 + AI 展示模式（结构性改动）

### 3.1 目标形态

| 模式 | 入口 | P1 | P2 | 说明 |
|---|---|---|---|---|
| 本地双人 | 现有 lobby/name_input | 键盘 | 键盘 | 保持不动 |
| 人机协作 | 专门入口（可复用现 ai_setup 改造） | 键盘（绿） | `SearchActionProvider(1)`（橙） | 恢复"人+AI"语义 |
| **AI 展示** | **新按钮 + 新展示场景** | `SearchActionProvider(0)` | `SearchActionProvider(1)` | 全自动演出，零交互闯关 |

### 3.2 实现建议（不强制，但保持 Action-only 契约）

1. **模式枚举**：`core/config` 或 `core/scenes` 增加 `GameMode`（`LOCAL / HUMAN_AI / AI_SHOWCASE`）。`Gameplay` 增加显式 `mode` 参数；`ai_algorithm` 参数可保留做兼容，但内部以 mode 为准。
   - `LOCAL`：双键盘（现状不动）。
   - `HUMAN_AI`：P1 键盘 + P2 AI（**把现在 ai_mode 下 P1 的 SearchActionProvider 改回仅 AI_SHOWCASE 才给**）。
   - `AI_SHOWCASE`：双 AI + 展示 HUD。
2. **续关链**：`_on_level_complete()` 把 mode（而非现在的 `"A*" if ai_mode else None`）传递下去，保证 AI_SHOWCASE 从 tutorial 一路自动打到 MainMenu（这段链路已验证可行，见第 5 节验证脚本）。
3. **展示页面/演出化**（差异化重点，属于"展示页面"的本体）：
   - 新建 `core/scenes/ai_showcase.py`（或扩展现 ai_setup）作为启动页：选择起点关卡（tutorial_001 / level_001 / level_002）+ 开始/返回。
   - 演出 HUD（区别于 F3 调试层，`core/ai/debug_overlay.py` 可复用其数据源）：
     - 当前关卡、脚本步骤号、语义目标（已本地化：`ai.goal.plate_left` 等 8 个新 key，en/zh 都有）；
     - 执行状态（FOLLOWING/APPROACH/BRAKE/HOLD/…）、双方 replans、hybrid `winner/candidates`（metrics 里已有）；
     - 双方角色头顶或侧栏的小目标指示（指向当前目标节点）。
   - 展示模式禁用暂停菜单里的"返回关卡重开"之类与人交互的语义冲突项（具体以现 pause.py 内容为准），保留暂停/退出。
   - SUCCESS→结尾→MainMenu 的既有状态机原样保留（这是展示模式的天然收尾）。
4. **菜单**：main_menu 增加"AI 展示"按钮（locale key 新增 `menu.ai_showcase` 之类，en/zh 同步）；原 `menu.ai` 按钮改造成"人机协作"入口（文案对齐语义）。
5. **文档**：`AI_ARCHITECTURE.md` 目前写"human–AI mode replaces only player 2's provider"——已在双 AI 改造后过时，随本次拆分一起改正。

### 3.3 验收标准（任务 A）

- 三种模式入口齐全、互不串扰：本地双人全键盘；人机协作 P1 键盘可玩通 tutorial；AI 展示全流程无输入自动通关并回 MainMenu。
- AI 展示 HUD 正确显示步骤/状态/winner，中英文均可。
- 现有 42 项测试全绿；`test_dual_ai_completion.py` 4 项通关回归不回退。

---

## 4. 任务 B：AI 行为打磨（用户痛点：左右抖动 + 不会二段跳）

### 4.1 左右震荡——已定位的嫌疑点（按优先级）

1. **`_approach_action` / `_hold_action` 制动滞后不足**（controller.py 约 405-430 行）：
   - 制动条件 `abs(dx) <= max(8, vx*vx/4400 + 8)`：摩擦模型是 `vx -= vx*PLAYER_FRICTION*dt`（PLAYER_FRICTION=10，指数衰减，滑行总距离 ≈ vx/10 ≈ 18px@满速），4400 系数与实测滑行距离不匹配，导致反复冲过中心再折返。
   - `_hold_action` 只有 ±4px 的纠偏带，且 `abs(vx)>22` 就反向按键——高速下正好制造左右振荡。实测 trace 里 HOLD 阶段 action 在 left/right 间逐帧交替。
   - **建议**：制动模型改用实测滑行距离 v/10；HOLD 加死区（进入中心带后松键靠摩擦停车，仅在出带时单侧修正）；加"方向反转计数"上限测试（反转超过 N 次/秒判失败）。
2. **backswing（助跑后撤）与 stuck 时钟互动**：`_simulate_edge` 的 backswing 候选先背向目标走再折返跳。虽然 replay 期间挂起 stuck 时钟（`active_edge and not sim_running`），但 replay 结束后若未落地/未到达，stuck 累计 1.5s → 重规划 → 新脚本可能又选不同 delay 的 backswing → 表现为原地"走了又走就是不跳"。观察手段：F3 或日志打印每次 commit 的候选 delay。
3. **`_takeoff_alignment` band/wedge 判定**（约 459-497 行）：band 边界 ±8px 的走位 + wedged 跳，在 40px 宽平台上容易陷入"走两步、退两步"循环。可考虑：对 span≤110 的近垂直跳，直接用 MPC 的 delay 候选（MPC 已能找到），不再走 alignment 的手调逻辑。
4. **MPC 每帧重搜索的候选抖动**：cost 平手时最优候选可能帧间跳变。可给上次 commit 的脚本加 1-2 秒"粘性"（除非目标/directive 变化或确定失败，不重新搜索）。

### 4.2 二段跳——已定位的短板

1. **平跳/远跳完全不用二段跳**：`_simulate_edge` 里 `use_double = dy < -SINGLE_RISE(144)`。但 graph 的 gap-leap 边（0<dy≤80，dx 可到 430）物理上只有靠二段跳的滞空才能飞满（满速单跳平飞仅 ~135px）。实测数据：双跳滞空 ~1.1-1.2s × 183px/s ≈ 200-220px。
   - **建议**：`use_double` 改为 `dy < -SINGLE_RISE or abs(dx) > 150`（阈值用实测滑翔距离校准），并让 release 候选组覆盖平跳。
2. **near-apex 窗口太窄 + 漂移脱靶**：|vy|≤144 只有 ~4 帧窗口。replay 中若实机与模拟有几帧漂移，二段跳按键正好错过窗口 → 消耗不掉。已修的"窗口对齐 144"解决了部分；进一步可让 rollout 的二段跳帧在 replay 时**自适应**：replay 不逐帧死放，而在 |vy| 首次进入 ±144 时注入 jump（配合既有 landing-abort）。
3. **`_wants_jump` 兜底路径**（MPC 未命中时走 legacy）：其二段跳判定同样是 `dy < -SINGLE_RISE`，与 4.2.1 同步改。
4. **测试**：在 `tests/test_dual_ai_completion.py` 风格上补：构造必须二段跳的边（level_001 33→59、59→58、level_002 高台），断言动作流里出现"同一起跳内的第二次 jump press"且落点正确；再补方向反转频率上限测试。

### 4.3 行为验收标准（任务 B）

- tutorial HOLD 阶段每秒方向反转 ≤ 2 次（当前实测逐帧交替）。
- level_001 的 33→59→58 链条（需二段跳 + 空中松方向）成功率：连续 3 次运行全部通过。
- 全战役双 AI 通关不回退（`test_dual_ai_completion` 4 项）。
- 42 项 unittest 全绿。

---

## 5. 验证工具箱（已验证可用的命令）

```bash
# 全部单测（~1000s，含 4 项双 AI 通关回归，耐心等）
./.venv/Scripts/python.exe -m unittest discover -s tests -p "test_*.py"

# 只跑双 AI 通关回归
./.venv/Scripts/python.exe -m unittest tests.test_dual_ai_completion -v

# 原生 C++ 重编译 + 自检
./build_native_windows.bat
```

headless 全战役双 AI 验证脚本（SDL dummy，~500s；改循环体可打日志）：

```python
import os
os.environ.setdefault('SDL_VIDEODRIVER','dummy'); os.environ.setdefault('SDL_AUDIODRIVER','dummy')
import pygame, time
from core.scene import SceneManager
from core.scenes.gameplay import Gameplay
from core.scenes.main_menu import MainMenu
from core.ai.controller import SearchActionProvider
pygame.init(); pygame.display.set_mode((1280,720))
m = SceneManager()
s = Gameplay(m, 'tutorial_001', ai_algorithm='A*'); m.push(s)
s.player1.action_provider = SearchActionProvider(player_index=0)
s.player2.action_provider = SearchActionProvider(player_index=1)
t = time.time()
for f in range(30000):
    m.update(1/60)
    c = m.current
    if isinstance(c, Gameplay) and c.finale_state.name == 'SUCCESS':
        print('SUCCESS', f)
    if isinstance(c, MainMenu):
        print('MAINMENU', f, round(time.time()-t,1)); break
```

打包（改动后发布前）：`build.sh`（bash）或 PyInstaller spec 重新打包；locale 记得同步 `dist/TwinPathEscape/_internal/assets/locales/`。

---

## 6. 必须遵守的约束（长期有效）

- AI 只能输出 `Action(left,right,jump,down)`：**不得**写 player 坐标/速度、不得伪造键盘事件。`tests/test_actions_and_mechanics.py` 有 AST 级检查（`core/ai/*.py` 内禁止给 `.pos/.rect/.velocity` 赋值）——因此 headless 克隆只能放在 `core/physics_clone.py` 这类 ai 目录之外。
- 不得删除本地双人模式；不得接入在线大模型/API；不得上传密钥、缓存、虚拟环境、个人路径或来源不明素材；未经明确要求不推送远程仓库。
- 原生 C++17 BFS/DFS/A*（`core/ai/native/search_native.cpp` + ctypes）是搜索核心，不回退到 Python 实现。
- 展示模式与人机协作共用同一套 AI 算法与搜索后端，不允许给展示模式单开"假算法"。

---

## 7. 关键文件地图

| 文件 | 内容 |
|---|---|
| `core/ai/controller.py`（737 行） | `SearchActionProvider`：tick/stuck/重规划/黑名单、`_simulate_edge`（MPC+脚本提交重放）、`_takeoff_alignment`、`_approach_action`/`_hold_action`（震荡主战场） |
| `core/ai/graph.py` | 平台图提取：物理对齐的边谓词、水跳拒绝、stairs 限短、`_add_special` walk 附件 |
| `core/ai/observation.py` | 冻结观测；`locate_support`（脚下重叠）/`locate_platform`（中心点） |
| `core/ai/level_scripts.py` | 三关显式分工脚本（语义目标，无按键序列） |
| `core/ai/script_controller.py` | 脚本步骤→`ScriptDirective` 解析 |
| `core/ai/native/search_native.cpp` | C++17 CSR 搜索（BFS/DFS/A*），tools/build_native.py 构建 |
| `core/physics_clone.py` | 无头玩家克隆（ai 目录外，规避 AST 检查） |
| `core/player.py` | 真实物理：jump 720/gravity 1800、`_near_apex`=|vy|≤144、摩擦=10（指数）、单向平台/楼梯/水 |
| `core/scenes/gameplay.py` | 模式接线（33-36、58-63 行）+ `_on_level_complete` 续关链 |
| `core/scenes/ai_setup.py` | 现"AI"入口（31-34 行启动 Gameplay）——任务 A 的改造点 |
| `core/scenes/main_menu.py` | 菜单按钮（49-52、155-158 行） |
| `core/ai/debug_overlay.py` | F3 调试层（展示 HUD 可复用其数据） |
| `assets/locales/en.json` / `zh_CN.json` | locale；新增 `ai.goal.*` 8 个 key 的位置在 159 行附近 |
| `tests/test_dual_ai_completion.py` | 双 AI 通关回归（4 项，~1000s） |
| `dist/TwinPathEscape/` | 已打包版本（native DLL 验证过；代码更新后需重打包） |

## 8. 遗留未做 / 已知坑

- 展示模式不存在（本任务 A 的主体）；`ai_setup.py` 只是个调试开关页。
- 人机协作当前没有独立入口（被双 AI 改造覆盖），任务 A 要恢复。
- MPC 性能：全战役 headless ~500s，候选剪枝/粘性未做（用户无硬性性能要求，但展示模式实时运行时同一台机器跑两个 provider，注意帧率；实测 1280×720 真机可玩）。
- 打包 dist 是旧代码+新 locale，功能变更后必须重新打包。
- `AI_ARCHITECTURE.md` 的"human–AI mode"描述已过时（见 3.2 第 5 点）。
- 运行双 AI 测试时机器较慢（每次 ~16 分钟），不要误判为挂死。
