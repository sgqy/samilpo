# SMC 动态调试可行性评估（第四阶段任务 D1）

> 凡例见 `smc-format.md` §0。本文件只做**可行性评估与方案建议**，不包含任何已执行的动态实验。
> 目标进程为 **32 位**（`MusicBook.exe` 为 PE32 x86）。

## 1. 结论

| 结论 | 内容 |
|---|---|
| 可行性 | **可行**，无需安装任何新工具 |
| 推荐组合 | **x64dbg `headless.exe`（x32）** 作为主方案；**IDA Pro 9.5 + idalib** 作为脚本化深查备选 |
| 是否需要管理员权限 | 一般不需要；若目标进程以更高权限运行则需提升 |
| 是否阻塞本阶段静态研究 | **不阻塞**；D1 为独立预备任务 |
| 下一步 | 需用户确认后进行 §4 的最小闭环实验 |

## 2. 环境勘察结果（只读检查，未安装任何东西）

| 工具 | 路径 | 状态 | 对 x86 目标的适配 |
|---|---|---|---|
| **x64dbg / x96dbg（headless）** | `%LOCALAPPDATA%\Programs\x96dbg\release\{x32,x64}\headless.exe` | 已安装 | **x32\headless.exe** 对应 32 位目标 [E] |
| x32dbg / x64dbg（GUI） | 同上目录 `x32dbg.exe` / `x64dbg.exe` | 已安装 | x32dbg 对应 32 位 |
| **IDA Professional 9.5** | `C:\Program Files\IDA Professional 9.5`（含 `idalib\`、`python\`） | 已安装 | 完整支持 x86；`idalib.dll` 存在 [E] |
| Ghidra 项目 | `C:\Users\aya\ghidra\samilpo.gpr`（+ `samilpo.rep`） | 项目存在 | 独立安装目录未在 PATH 中发现 [?] |
| Cutter 2.4.1 | `%LOCALAPPDATA%\Programs\Cutter-v2.4.1-Windows-x86_64` | 已安装 | 基于 rizin，支持 x86 |
| WinDbg / cdb | 未发现 | 未安装 | — |
| Frida | Python 模块未安装 | 未安装 | — |
| pywin32 / pwn / capstone 等 | 未安装 | 未安装 | 仅影响脚本便利性 |

Java 未在 PATH 中发现 [?]（影响 Ghidra GUI 调试器，但不影响 REA 的 Ghidra 后端——REA 自带并可正常分析）。

## 3. 各方案评估

### 3.1 x64dbg `headless.exe`（推荐）

已实测 [E]：

- 启动后进入 `[headless] entering command loop...`，**接受从 stdin 送入的命令**。
- 命令集即 x64dbg 命令系统（`log`、`printf`、断点、`run`、`pause`、`step`、寄存器/内存读取等）。
- 支持 `quit` 结束（实测正常退出，exit code 0）。
- 日志可重定向：二进制内含 `[headless] failed to redirect log to %s` 字样，说明支持把日志写入文件 [E]。

| 评估项 | 结论 |
|---|---|
| Windows x86 支持 | ✅（x32 版本） |
| 启动/附加目标进程 | ✅（命令系统支持 `init`/`start`/`attach`） |
| 软件断点 / 继续 / 单步 | ✅ |
| 读寄存器与内存 | ✅ |
| 模块基址与 ASLR 重定位 | ✅（`mod.base` 等命令） |
| 结构化输出 | ⚠️ 输出为**文本日志**；需在脚本侧解析或使用其脚本/JSON 变量命令 |
| 与 Agent 集成 | ✅ 以 **stdin/stdout 子进程**方式驱动（REA 的 `capture_process_scenario` 亦可承载） |
| 管理员权限 | 视目标而定 |
| 维护状态 | 活跃（正式发行版，含 release notes） |

**限制**：headless 模式官方定位为「自动化测试」用途，功能面窄于 GUI；文本输出需要解析。
但已满足断点、单步、寄存器/内存读取、基址获取等本研究所需的全部能力。

### 3.2 IDA Pro 9.5 + idalib（脚本化备选）

- `idalib.dll` 与 `idapro-0.0.10-py3-none-any.whl` 均存在；`py-activate-idalib.py` 提供激活脚本 [E]。
- 需执行两步（**当前未执行**）：`pip install idapro*.whl`；运行 `py-activate-idalib.py`。
- 启用后可在普通 Python 中 `import idapro` 驱动 IDA 反编译与静态分析（**不是运行时调试**）。
- 若需运行时调试，IDA 的 `dbg.dll` 与 x86 调试模块存在，但自动化接口需自行封装。
- **评价**：适合「批量反编译 → 结构化提取」；作为动态调试主方案成本更高。

### 3.3 REA 现有能力

| 能力 | 适用性 |
|---|---|
| `capture_process_scenario` | **可启动并捕获目标进程**的终端/进程/文件系统证据（PTY 驱动）[E 工具契约] |
| `observe_native_calls` | **仅 LLDB / Mach-O（macOS）**，不适用于 Windows PE [?] |
| 其余 REA 工具 | 静态分析为主 |

→ REA 本身不提供 Windows 原生断点调试；需外部调试器（x64dbg headless）承载。

### 3.4 其余

- **Cutter**：GUI 为主，可脚本化，但本项目已有 REA/Ghidra 静态链路，边际收益低。
- **WinDbg / Frida**：未安装；不作为必需方案。

## 4. 最小验证实验设计（待用户确认后执行）

**前置**：只能在用户许可的隔离环境中进行；不修改原始程序、字体与样本。

| 步骤 | 操作 | 预期证据 |
|---|---|---|
| 1 | 复制一份样本到临时目录，记录其 SHA-256 | 样本身份 |
| 2 | 以 x32 `headless.exe` 启动 `MusicBook.exe`，stdin 送命令脚本 | 进程启动、模块基址 |
| 3 | 在 `CSMDoc::Load`（`engine.dll` 0x10077CB0，需按基址重定位）与 `CSMLyricMsg::DrawMsg`（0x1009AD00）下软件断点 | 断点命中记录 |
| 4 | 由用户手动打开步骤 1 的样本 | 命中回调 |
| 5 | 命中时读取寄存器与内存：核对 `headLen`(+0x1E)、head 指针(+0x20)、`MsgHdr` 首 0x2C 字节 | 与静态字段表逐项对照 |
| 6 | 保存调试日志、程序版本、样本与模块哈希 | 可复现记录 |
| 7 | `quit` 关闭实验；恢复环境 | 结束 |

**验证目标（优先已知结论，不直接攻击未知字段）**：

1. `ObjectCore +0x06 == headLen + 0x12`（静态推断，运行时观察写入值）。
2. 歌词 head 的 6 个残留字节在内存与磁盘的一致性（确认其为栈残留传递）。
3. `MsgHdr+0x03/+0x04/+0x1E` 的读写点（静态未定位，运行时观察即可锁定语义域）。

**不做的操作**：不安装调试驱动；不自动化 GUI 编辑；不修改目标文件。

## 5. MFC/GUI 消息路由（任务 D3 静态评估）

可静态识别候选命令 ID 与消息映射，但**本阶段不发送任何 Windows 消息**。评估结论：

| 操作类型 | 可行性 | 说明 |
|---|---|---|
| 打开文件 | 人工触发最可靠 | 可用命令行参数或最近文件；`SendMessage` 需完整上下文 |
| 编辑（插入/拖拽） | 需真实输入事件 | 依赖内部对象状态与鼠标捕获状态 |
| 模态对话框 | 不适合自动化 | 会阻塞消息循环 |
| 适合后续自动化 | 「启动 + 命令行打开」 | 见 §4 步骤 2–4（**人工打开**） |

**注意**：发送 `WM_COMMAND` **不等价**于一次真实编辑操作；本研究的最小闭环仍要求**人工触发打开**。

## 6. 已知技术限制

1. headless 输出为文本，结构化程度有限；需要解析或改用其脚本变量。
2. ASLR 使 `engine.dll` 基址在每次运行变化；断点地址必须按运行时基址重定位。
3. 32 位目标与 64 位宿主：须使用 **x32** 版本，混合位数会失败。
4. `MusicBook.exe` 为 MFC 应用，界面操作会引入不确定的时序。
5. 本环境未见 WinDbg/Frida，若需更细粒度（如 API 跟踪）需另行申请安装，**本阶段不建议**。

## 7. 建议

1. **采纳 x64dbg headless（x32）为主方案**，按 §4 做一次最小闭环。
2. 该实验只用于核对**已有静态结论**与锁定 `MsgHdr+0x03/+0x04/+0x1E` 的读写点；
   不追求用它完成剩余全部未知字段。
3. 若实验确认可行，下一阶段可将其纳入常规流程；若受阻，静态研究不受影响。
4. 是否需要实际实施：**值得**，但收益集中在少数字段；优先级低于 `tools/` 侧的静态收尾。
5. **所有动态操作需用户明确确认后执行**（本文件不构成执行授权）。
