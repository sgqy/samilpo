# 第四阶段执行记录（2026-10-14）

> 工作日志：记录本阶段新增的**直接证据**（函数地址 + 汇编/伪代码依据）。
> 最终归档目标是各专题文档；本文件是过程记录。会话绑定 `engine.dll`
> （SHA-256 `424b61c00500db8a40ef943675983fd29d7bf70093cf7737f2659b14718d25a8`，Ghidra 12.1.4，基址 0x10000000）。

## 1. 任务 A1：歌词 head（0x19）字节归属——已闭合 [E]

### 1.1 读取侧汇编（`CSMLyricMsg::DrawMsg` 0x1009ad00）

关键指令（原始汇编）：
```
SUB ESP,0x104
PUSH 0x10 ; LEA ECX,[EBP-0x20] ; CALL memcpy   ; head 前 16 字节 → EBP-0x20
MOV CX,[EAX+0x1e] ... CMP [EDX+0x20],0          ; headLen(0x1E) 与 head 指针(0x20)
MOV CX,word ptr [EBP + -0x20]                   ; head+0x00 → CFontDatas::GetFontName
MOV EAX,dword ptr [EBP + -0x1e] ; AND EAX,0x1   ; head+0x02 → 粗体
                                 AND ECX,0x2                 → 斜体
                                 AND EDX,0x4                 → 下划线
MOVSX ECX,word ptr [EBP + -0x1c] ; TEST ... JNZ ; MOV word[EBP-0x1c],0xd
                                                ; head+0x04 → 字号，0 时取 13
MOV EAX,dword ptr [EBP + -0x18]                 ; head+0x08 → 颜色（COLORREF）
MOV EAX,dword ptr [EBP + -0x14] ; AND EAX,0xff  ; head+0x0C dword 的**低字节** = 文本长度
MOV EAX,[EDX+0x20] ; ADD EAX,0x10               ; 文本指针 = head+0x10
```

**未被任何指令读取的字节**：`EBP-0x1d`(=head+0x03)、`EBP-0x1a`(=head+0x06)、
`EBP-0x19`(=head+0x07)、`EBP-0x13/-0x12/-0x11`(=head+0x0D/+0x0E/+0x0F)。

### 1.2 写入侧汇编（`CSMDoc::EncToSMC_Lyric` 0x10025170）

head 缓冲栈基址 = **EBP-0xc8**（CStr 结果区从 `EBP-0xc8` 起）：
```
MOV word ptr [EBP + -0xc8], AX      ; head+0x00 字体索引（local_cc）
MOV byte ptr [EBP + -0xc6], 0x0     ; head+0x02 样式 = 0（local_ca）
MOV word ptr [EBP + -0xc4], AX      ; head+0x04 字号（local_c8，来自 local_a0[2]）
MOV dword ptr [EBP + -0xc0], 0x0    ; head+0x08 颜色 = 0（local_c4）
MOV byte ptr [EBP + -0xbc], AL      ; head+0x0C 长度低字节（local_c0 = CONCAT31(prev, strlen)）
PUSH 0x10 ; LEA EAX,[EBP-0xb8] ; CALL memcpy   ; 拷贝 16 字节 head → new+0x10 之前的缓冲
```

**未写入**：head+0x03、+0x06、+0x07、+0x0D、+0x0E、+0x0F —— 与读取侧未读集合**完全一致**。
`local_c0 = CONCAT31(local_c0._1_3_, (char)strlen)` 只设置低字节，其余 3 字节保留栈残留值。

### 1.3 另一写入路径（`CSMDoc::GulsamToSMC_Lyrics` 0x10030010）

```
local_ac = 0        ; → head+0x02 样式
local_aa = param_1[...+100]  ; → head+0x04 字号（CUNote 的字号字段）
                                      ; head+0x08 颜色、+0x0C 长度低字节
local_a0 = CONCAT31(local_a0._1_3_, textlen)
uVar2 = textlen + 0x10 ; local_78 = operator_new(uVar2)
local_d0 = (undefined2)uVar2 ; local_7a = local_d0    ; headLen = 文本长度 + 0x10
memcpy(local_78, &local_ac, 0x10)                     ; 16 字节 head
memcpy(local_78+0x10, text, textlen)                   ; 文本从 head+0x10
```

### 1.4 结论（歌词 head 字段表）

| head 偏移 | 类型 | 含义 | 状态 |
|---|---|---|---|
| +0x00 | u16 | 字体索引 | **Confirmed** |
| +0x02 | u8 | 样式（bit0 粗体, bit1 斜体, bit2 下划线） | **Confirmed**（汇编 `& 1/2/4`） |
| +0x03 | u8 | **未初始化残留** | Confirmed 无语义 |
| +0x04 | u16 | 字号（0 → 视为 13） | **Confirmed** |
| +0x06 | u16 | **未初始化残留** | Confirmed 无语义 |
| +0x08 | u32 | 文字颜色 COLORREF | **Confirmed** |
| +0x0C | u8 | 文本字节长度 | **Confirmed** |
| +0x0D | u8 | **未初始化残留**（长度 dword 的高字节） | Confirmed 无语义 |
| +0x0E, +0x0F | u8×2 | **未初始化残留**（同上） | Confirmed 无语义 |
| +0x10 | u8[len] | 文本（889F） | Confirmed |

**预测验证**（`tools/_probe_p4_lyrichead.py`，400 文件抽样，30353 条歌词）：

| 观测 | 结果 |
|---|---|
| 字体索引 | {1: 26253, 2: 1915, 5: 923, 6: 554, 3: 546, 7: 162} |
| head+0x02 样式 | {0: 30254, 1: 99} |
| head+0x04 字号 | {13: 30136, 14: 140, 12: 74, 0: 3} |
| head+0x06 | 317 个不同值（0 出现 6430）→ **残留** |
| head+0x0D..+0x0F | 535 种组合，仅 6089/30353 全 0 → **残留** |
| `headLen == 文本长度 + 0x10` | 24264 条成立（非空文本 100%） |

→ 与「6 个字节未初始化」的预测一致：这些字节随栈内容变化，第三方解析应**忽略**。

## 2. 任务 A2：文件尾 4 字节——已闭合 [E]

`CSMDoc::Save` 0x100773c0 完整流程：

```
local_c  = 0
local_10 = CFile::GetPosition()          ; 记录起始位置
CFile::Write(&local_c, 4)                ; 先在起始位置写 4 字节占位（= 0）
System.Write(...)                        ; 写 System
[写 DocHdr(10) + Msg×3 + Page×N]         ; 逐块写主体，local_c 累加实际字节数
local_c += local_18                      ; local_c 最终 = 主体字节数（bodyLen）
local_2c = local_c                       ; 保存 bodyLen
CFile::Write(&local_c, 4)                ; 主体之后写 bodyLen（尾部 4 字节）
uVar4 = CFile::GetPosition()             ; 记录尾部之后位置
CFile::Seek(local_10, 0)                 ; 回到文件起始
CFile::Write(&local_2c, 4)               ; 回填起始处的 bodyLen
CFile::Seek(uVar4, 0)                    ; 回到尾部之后
```

**结论**：
- 文件布局 = `u32 bodyLen` + 主体 + `u32 bodyLen`（两处**都等于主体字节数**）。
- 起始处与结尾处的两个 u32 由**同一变量**写入，故必然相等，与阶段一「全部样本相等」的观察一致。
- 尾部 4 字节是**writer 主动写入**的冗余长度，不是校验和；读取端忽略。
- 同时得到 `local_1c = u16@doc+0xc5a + 0x2E + u16@doc+0xcda + u16@doc+0xd5a`：三处文档级消息长度之和 + 0x2E（即 DocHdr 10 字节 + 3 条文档级 Msg 的合计），说明主体缓冲区按此估算分配。

## 3. 任务 A3：音乐符号常量表导出 [E]

引擎映像中符号常量集中存放于 `0x10100360`–`0x10100700` 区段：

| 常量 | 地址 | 内容（十六进制） | 说明 |
|---|---|---|---|
| `codeSlid` | 0x10100364 | `66 67 68 69 6a 6d 2f 2e 27` | 9 种滑音/装饰字符 |
| `codePedal` | 0x10100370 | `8c 8d 6b 8f 90` | 踏板记号 |
| `codeMeasRepeat` | 0x10100374 | `8e 8b 4d` 区（见下） | 小节反复 |
| `codeStdHead[0..8]` | 0x10100390 | `d6 d7 d8 d9 d9 d9 d9 d9 d9` | 9 种标准符头 |
| `codeBoxHead` | 0x1010039C | `e5 e4 e4 e4 e4 e4 e4 e4 e4` | 方框/菱形符头 |
| `codeCrossHead` | 0x101003A8 | `db db db dd dd dd dd dd dd` | × / 特殊符头 |
| `codeSlashHead` | 0x101003B4 | `dc dc dc dc dc dc dc dc dc` | 斜线符头 |
| `codeDot` | 0x101003C6 | `e1` | 附点 |
| `codeShortLine` | 0x101003ED | `ff` | 符干短横 |
| `codeAcci[]` | 0x10100430 | `00 a9 aa ab ac ad da 00 d6 d7 c4 89 92 93 94 95 96 ee 00 00 bd be …` | 变音记号表 |
| `codeSmallDigit` | 0x10100464 | `d0 d1 d2 d3 d4 d5 00 00 3f 46 47 3e cb cb …` | 小数字 |
| `CodeDyn[]` | 0x101006D4 | `00 f0 f1 f2 f3 f4 f5 f6 f7 f9 fa fb fc fd fe ff` | 力度记号（索引 0 → 空） |

- 后续数据（0x101006E4 起）为 `08 00 04 00 04 00 08 00 0c 00 10 00 14 00 18 00` 等 u16 表，
  疑为**时值→宽度/位置**或**强弱→velocity**辅助表 [?]。
- 全部符号为单字节，经符号字符集（Windows symbol charset）映射到 U+F020–U+F0FF，
  由 `KayakumA` 字体渲染；与 889F 文本编码无重叠（阶段三结论）。

## 4. 进行中：任务 B（特殊消息结构）

新增可用函数（`search_procedures "Write"` 得到）[E]：

| 地址 | 函数 | 用途 |
|---|---|---|
| 0x1002dc70 / 0x1002dd00 | CFretInfo::ReadFromMem / WriteToMem | 指板信息（16 字节）读写 |
| 0x1002cfd0 / 0x1002d060 | CFretBoard::ReadFromMem / WriteToMem | 指板布局 |
| 0x1000bdb0 / 0x1000bf80 | CChordSymbol::ReadFromMem / WriteToMem | 和弦记号（含 head100） |
| 0x10008b40 / 0x10008bf0 | CChordSurfix::ReadFromMem / WriteToMem | 和弦后缀 |
| 0x10045c40 / 0x10045cf0 | CRhythm::ReadFromMem / WriteToMem | 节奏型 |
| 0x10047720 / 0x10047950 | CRtmData::ReadFromMem / WriteToMem | 节奏数据 |
| 0x1007ed90 | CSMCtrlTool::Write | CtrlTool 写回 |
| 0x100951a0 | CSMFileInfo::Write | FileInfo 写回 |

**读写成对**是恢复精确磁盘布局的最佳路径（同阶段三 MsgHdr 的方法）。

## 5. 任务 B：特殊消息结构 [E]

### 5.1 type 0x46（指板）与 CFretInfo

`CFretInfo::ReadFromMem` 0x1002dc70 与 `WriteToMem` 0x1002dd00 **逐字节一致**：

| 磁盘偏移 | 长度 | 对象偏移 | 含义 |
|---|---|---|---|
| +00 | 2 | +0x12 | **基准品位 baseFret**（u16） |
| +02 | 6 | +0x04 | **6 根弦的品位值**，每弦 1 字节（`0..4` 为有效相对品位；`0xFE`/`0xFF` = 空弦标记）|
| +08 | 8 | +0x0A | **4 组 (起始, 结束) 对**，共 4×2 字节（指法区间） |

证据（同族的消费者）：
- `CFretInfo::GetMidiKeyOfString` 0x1002d220：`this[string+4]` 为品位值，`0` 时取 `nFretBase[string]`；
  `1..4` 时 = 基准 + 品位；否则 -1 → **+0x04 起 6 字节 = 每弦品格位**。
- `CFretInfo::FretInfoToLineString` 0x1002d330：遍历 6 次取 `this[i+4] + 2` 转字符；
  再遍历 4 次取 `this[i*2+10]`、`this[i*2+11]` 各转一字符；再取 `this[0x12]`
  → **+0x0A 起 8 字节 = 4 对 (p1,p2)**，**+0x12 = 基准品位**。
- `CFretInfo::IsFretEmpty` 0x1002d2a0：空判定 = 6 个品位字节全为 `0xFE/0xFF` 或 4 组对全相等。

`CFretBoard::ReadFromMem` 0x1002cfd0 / `WriteToMem` 0x1002d060：
- 内嵌 `CSMMsg::Read/Write`（type 强制为 **0x46**），随后调用 `CFretInfo` 的读写。
- 读取时设置对象 `+0x94 = +0x1C`（f2 备份），并 `lstrcpyA(this+0x96, "KayakumA")` → 指板用 KayakumA 字体绘制 [E]。
- 写入时把 `+0x1C` 恢复为 `+0x94` [E]。

### 5.2 type 0x45（和弦记号）

`CChordSymbol::ReadFromMem` 0x1000bdb0 / `WriteToMem` 0x1000bf80 完全对称：

| 磁盘顺序 | 内容 |
|---|---|
| 1 | `CChordSurfix`（后缀名 + 信息）|
| 2 | `CFretBoard`（内嵌 type 0x46 Msg + CFretInfo 16 字节）|
| 3 | `u16 hasRhythm` |
| 4 | 当 hasRhythm≠0 时的 `CRhythm` |

`CChordSurfix::ReadFromMem` 0x10008b40 / `WriteToMem` 0x10008bf0：`CStr name` + `u8 n` + `u8 info[n]` [E]。

`CChordSymbol` 的构造（0x1000a470）把类型固定为 **0x45**，并内建 CFretBoard(0xF0,"KayakumA")、
`+0x17c = 1`、`+0x180 = 0`、`+0x184 = 0`、`+0x158 = nChordFretPtSize`、`+0x15A = "KayakumA"` [E]。

**关于 headLen = 100 的 head（关键结论）**：
- 全语料 413/1244 个 0x45 记录带 100 字节 head（`tools/_probe_p4_rhythm.py`）。
- 该 head 内**含 MFC42 区段指针**：`+0x48/+0x4C = 0x5F401018`、
  `+0x5C = 0x5F40111F`、`+0x60 = 0x5F405D25`（全部 413 个样本**完全相同**，
  且这些地址落在 **MFC42.DLL 默认装载区 0x5F400000–0x5F4xxxxx**）。
- 另含 `+0x36 = 0xBFF7`（= -16393，栈样式值）、`+0x1F = 0x01` 等在全部样本恒定的字节。
- 100 字节中仅有 27 个字节在所有样本中恒定，其余随记录变化。
- **判定**：这不是音乐语义字段，而是**被原样持久化的运行期内存结构**（含 MFC 对象指针与栈值）。
  第三方解析必须**原样保留、不得解释**；重建时若要写出该字段，只能沿用原字节 [E]。

### 5.3 type 0x47（节奏型）与 CRtmData / CRhythm

`CRhythm::ReadFromMem` 0x10045c40 / `WriteToMem` 0x10045cf0：`CSMMsg`（type 0x47）+ `CStr×3` + `CRtmData` [E]。

`CRtmData::ReadFromMem` 0x10047720 / `WriteToMem` 0x10047950 **逐字段一致**：

| 磁盘偏移 | 类型 | 说明 |
|---|---|---|
| +00 | u32 | **totalSize** = 本结构总长（**含自身 4 字节**；`total = 已消耗 + 4`，101/101 验证）|
| +04 | u16 | **步长 stride**（恒 0x10 = 16）|
| +06 | u16 | 字段 A（内存 +0x08）|
| +08 | u16 | 字段 B（内存 +0x48）|
| +0A | u32 | **事件数 eventCount** |
| +0E | u16 | **事件大小 eventSize**（恒 0x10 = 16）|
| +10 | u8[eventCount × eventSize] | 事件块（每条 16 字节）|
| … | u16 ×2 | 第二段：`count2`（恒 16? 见下）、`size2`（**恒 6**）|
| … | u8[count2 × 6] | 第二段数据（每条 6 字节）|

- 验证（`_probe_p4_rhythm.py`，101 条）：`stride = 16`、`eventSize = 16`、`size2 = 6`；
  `total = 已消耗字节数 + 4`（**101/101 成立**，故 +00 自含计数）。
- 内嵌位置：`CRtmData` 出现在 **0x45 的 Rhythm 部分**（101 处）；独立 0x47（type 0x47 共 12716 条）只含 Msg 部分。

### 5.4 type 0x2C（长休止）

`CScoreView::DrawLongrest` 0x100595b0：
- 用 `codeLongRestBar` 绘制长休止条（4 点多边形 + 两端竖线）。
- 中间**打印十进制数字**：`CString::Format((CString)..., *(short*)(param_1 + 0x1C))`
  → **长休止的小节数在 `MsgHdr+0x1C`**（=「符干长度」字段，此处复用为小节数）[E]。
- 数字使用 `CSMCtrlTool+0x3b0` 处 LOGFONT（第 9 个 LOGFONT，字号按 `ctrl+0x1c` 缩放）[E]。
- headLen = 60 的 head 内部字段**未在本阶段解析**（`unknown-fields.md` B2）。

### 5.5 其他类型

- 0x0C（Coda）：`DrawCoda` 0x10056ec0 / `DrawCodaEx` 0x10065660；语料 165 条；headLen ∈ {5,8,9,11}；字段未解析。
- 0x3F/0x40/0x04（文档级）：每文件各一次；无 head；语义未定。

## 6. 任务 D1：动态调试可行性调查（只读检查，未安装任何工具）

### 6.1 环境勘察结果

| 工具 | 路径 | 状态 |
|---|---|---|
| **x64dbg / x96dbg headless** | `%LOCALAPPDATA%\Programs\x96dbg\release\{x32,x64}\headless.exe` | **已安装**（x32 对应 32 位目标） |
| x32dbg / x64dbg GUI | 同目录 `x32dbg.exe` / `x64dbg.exe` | 已安装 |
| **IDA Professional 9.5** | `C:\Program Files\IDA Professional 9.5`（含 `idalib\`、`python\`、`idalib.dll`、`idapro-0.0.10-py3-none-any.whl`、`py-activate-idalib.py`） | **已安装** |
| Ghidra 项目 | `C:\Users\aya\ghidra\samilpo.gpr` + `samilpo.rep` | 项目存在；独立安装目录未在 PATH 发现 |
| Cutter 2.4.1 | `%LOCALAPPDATA%\Programs\Cutter-v2.4.1-Windows-x86_64` | 已安装（rizin 后端） |
| WinDbg / cdb / ntsd | 未发现 | 未安装 |
| Frida（Python 模块） | `importlib.find_spec('frida')` = False | 未安装 |
| pywin32 / pwn / capstone / keystone / unicorn | 均未安装 | 未安装 |
| Java | 未在 PATH 发现 | — |

### 6.2 x64dbg `headless.exe` 实测（未加载任何目标）

- 启动后输出 `[headless] entering command loop...`，**接受 stdin 命令流** [E]。
- 送入 `quit` 后正常退出（`[headless] shutdown requested by Ctrl+C`），exit code 0 [E]。
- 二进制内含字符串 `[headless] failed to redirect log to %s`（支持日志重定向）、
  `[FAIL] command failed`、`[FAIL] no script id registered %d`、`GUI_SCRIPT_*` 家族 [E]。
- 结论：具备**命令系统 + 脚本 + 日志**三要素，可用作 Agent 驱动的动态调试后端。

### 6.3 REA 能力边界

- `capture_process_scenario` 可启动并捕获目标进程的终端/进程/文件系统证据（PTY 驱动）[E 工具契约]。
- `observe_native_calls` 为 **LLDB / Mach-O（macOS）**，不适用于 Windows PE [?]。
- → REA 不提供 Windows 原生断点调试；动态调试需外部调试器承载，输出经 stdin/stdout 流入会话。

### 6.4 结论与交付

- 交付物：`debugging-plan.md`（方案、前提、最小实验、限制、需用户执行的操作）。
- 判定：**可行且无需安装新工具**；推荐 x64dbg x32 headless，IDA idalib 作脚本化备选。
- **未执行任何动态操作**；最小闭环实验需用户明确许可（隔离环境，人工触发打开样本）。

## 7. 任务 E：字段覆盖清单

新增 `tools/field_coverage.py` 作为**覆盖度数字的唯一数据源**：脚本内以
`(offset, size, category, label, evidence)` 形式定义每个结构的字段，按字节分类并计算覆盖率。

分类口径（互斥且穷尽）：

| 类别 | 含义 |
|---|---|
| S | 已确认文件语义 |
| I | 推断 |
| N | 已确认**无文件语义**（保留/栈残留/派生/纯绘制缓存） |
| U | 长度已知、语义未知 |
| X | 未建模 |

两个覆盖率：**结构覆盖 = (S+I+N)/总**；**语义覆盖 = (S+I)/总**。

计算结果（全文见 `field-coverage.md`）：

| 层 | 总字节 | 结构覆盖 | 语义覆盖 | 未解释 |
|---|---:|---:|---:|---:|
| 核心层（对象模型 + 消息头 + 各 head + 结构头） | 156 | **92.9%** | **78.8%** | 7.1% |
| 布局层（Staff/Meas/Page/Block 头与尾块） | 260 | 60.4% | 60.4% | 39.6% |
| 文件级大块（SYMP/SMC/CtrlTool/FileInfo） | 3388 | 19.9% | 19.9% | 80.1% |
| 全部 | 3804 | 25.7% | 25.1% | 74.3% |

- 无语义字节（N）合计仅 **22/3804 = 0.6%**，均已逐一定位（`field-coverage.md` §3）。
- 文件级大块的低覆盖主要来自 SYMP 与 SMC 的**大面积固定零区**（X = 2124 字节）。

## 8. 文档统一（本轮）[E]

按用户要求统一表记：

1. **数据类型改 Rust 风格**：`u8/u16/u32/u64`、`i8/i16/i32/i64`、`bool`、`[u8; N]`、`[T; N]`、`Vec<T>`、`CStr`、`CStrZ`；
   Win32 类型保留 `RECT`/`POINT`/`SIZE`/`COLORREF`/`LOGFONTA` 并与 Rust 表达互注（`smc-format.md` §0.2）。
2. **知识评级统一**：`[E]` 直接证据 / `[I]` 推断 / `[?]` 未知 / `[C]` 已推翻；凡例集中在 `smc-format.md` §0.1，
   各文档首部引用。
3. **新增 §0.4「Ptr32 与无语义字节」**：明确两类必须原样保留的字节及其判别特征。
4. 全部专题文档（`music-fields.md`、`layout.md`、`lyrics.md`、`encoding.md`、`font-resources.md`、
   `unknown-fields.md`、`function-index.md`）按同一凡例重排；表格逐行补评级。
5. 章节编号统一：主规范 §0–§11；专题文档 §0 为索引/速览。

## 9. 成本与范围控制记录

- 复用同一 REA/Ghidra 会话完成全部查询（未重复导入）。
- 批量统计全部在本地 Python 完成；未把大段反编译重复送入上下文。
- 未安装任何软件；D1 仅做只读勘察，未启动目标程序。
- 未开发转换器、IR 或目标格式适配（任务书排除）。

## 10. 停止条件

满足任务书全部 5 项：
1. 主要低成本静态未知字段已收尾（歌词 head、文件尾、符号表）。
2. 0x45/0x46/0x47 取得结构级可验证进展。
3. 文件级剩余未知字段系统记录（`unknown-fields.md` B1–B9、`field-coverage.md` §4）。
4. 建立字段覆盖清单并统一口径。
5. 明确动态调试方案（可行、无需安装、需用户确认）。

## 11. 遗留与下一步

优先项见 `open-questions.md` 的 P1–P4。建议下一阶段首项：

1. `MsgHdr+0x03/+0x04/+0x1E` 的 xref 定位（成本低、直接影响核心层语义覆盖）。
2. `MeasTail` / `StaffTail` 的写回逐字段对照（可一次性消灭约 96 个 U 字节）。
3. `RtmData` 事件体（结构已知，内部待定）。


