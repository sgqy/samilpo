# SMC 未知字段与未解结构（第三阶段汇总）

> 本文件系统记录尚未解释的字段、结构与待验证假设。
> 状态：`Open`（待研究）/ `Blocked`（需动态调试或额外样本）/ `Low`（低优先级）
> 记号 `[E]` 直接证据 / `[I]` 推断 / `[?]` 未知。

## A. 已确认但仍需补充证据的字段（Inferred）

| 位置 | 字段 | 现状 | 需要的证据 |
|---|---|---|---|
| ObjectCore +02 | f2「连音比例」 | `CalcPlayTime` 用其高/低字节做 `MulDiv` [E 用法]；命名与完整语义未定 | 编辑期 `f2` 写入路径 |
| ObjectCore +08 | f8 | 仅见读写；type 0x45 时被覆盖为 +0x80 [E] | 消费者分析 |
| MsgHdr +28 | 颜色/样式 | `DrawDynamic` 用作 `SetTextColor` 参数 [I] | 与 `head` 颜色字段对照 |
| MsgHdr +03/+04 | 未知 u8 | 全语料出现但无消费者定位 | xref 定位写入/读取 |
| MsgHdr +14 | u16 | 起始时间缓存（运行期写入）[E] | 保存期是否写回磁盘 |
| Staff +4D | 谱号类别 | `==5` 与 `2/3` 分支出现在多个函数 [E 用法] | 取值枚举与含义 |

## B. 未解释的结构（Open）

### B1. ObjectCore 保留字节 +01
- 语义：读取路径从不使用；写入路径写入**未初始化栈字节** [E]。
- 全语料分布：46% 为 0，其余为大范围随机值（如 0x06 型 455/599 为 0x32）。
- **对第三方解析的影响**：无。可忽略或保留原值。
- 状态：`Open`。若要解释其来源需动态调试写入时的栈内容（收益低）。

### B2. 类型 0x2c（长休止）headLen=60
- 语料 98 条；`DrawLongrest` 0x100595b0。
- head 60 字节的字段划分未分析。
- 状态：`Open`（中优先级）。

### B3. 类型 0x0c（Coda）headLen ∈ {5, 8, 9, 11}
- 语料 165 条；`DrawCoda` 0x10056ec0 / `DrawCodaEx` 0x10065660。
- head 字段未分析。
- 状态：`Open`（低）。

### B4. 类型 0x47（节奏型）与 CRtmData
- 语料 12716 条；结构见 `smc-format.md` §6.8 的 Rhythm/RtmData。
- `CRtmData` 的事件表（`nEv`、`evSize`、`n2`、`sz2`）字段含义未定。
- 状态：`Open`（中）。

### B5. 类型 0x46（指板）与 CFretInfo
- 语料 177909 条（与 0x45 一一对应）；`CFretInfo` 16 字节（2+6+8）。
- 指板图与弦位字段未逐一映射。
- 状态：`Open`（低）。

### B5b. 类型 0x45 的 head（长度 100）
- 语料中 headLen ∈ {0, 100}；长度 100 的内容为**二进制缓存**（含运行期指针/标志），非稳定文本 [E 观察]。
- 和弦的可读名称在 `ChordExtra.surfixName`（实测 `" (major)"`、`"m"`、`"7"`、`"m6"`、`"dim"` 等）[E]。
- 若要精确解释 head[100]，需分析 `CSMObject::Write` 对 type 0x45 的覆盖（`this+0x80`、`this[0x17C]<<8|this[0x180]`）。
- 状态：`Open`（中）。

### B6. 类型 0x04 / 0x3f / 0x40（文档级）
- 每文件各一次；无 head；`0x04` 亦映射到 `DrawMultiText` [E]。
- 语义未定（可能是页眉/页脚或文档标志）。
- 状态：`Blocked`（需动态观察）。

### B7. 附加字符串（file 0x590）
- 通常为数字串（"448"）；318 个文件为 32 字节的双字节文本 [E]。
- 状态：`Open`（低）。

### B8. SYMP 头 / SMC 块 / CSMCtrlTool / CSMFileInfo 的其余字段
- 大量字段读写位置已知但语义未定（见 `smc-format.md` §3.1、§3.5、§3.6）。
- 入口：`CSMFileInfo::SetLogicPageInfo` 0x10094ed0、`UpdateLogicDoc` 0x100950a0。
- 状态：`Open`（低，需要 exe 侧消费者分析）。

## C. 需要动态调试或额外样本的问题（Blocked）

### C1. 歌词 head +0x06 / +0x0D / +0x0E / +0x0F
- 4 个字节未被 `CSMLyricMsg::DrawMsg` 使用 [E]。
- 候选：编辑期缓存或长度校验。
- 验证途径：`CTempLyricMsg`（0x100c9b70 / BeginDrag 0x100c9cf0）或 `CSMLyricMsg` 的写入路径（若存在）。
- 状态：`Blocked`（需动态编辑观察）。

### C2. 歌词 head +0x02 / +0x04 的字节归属
- 现按统计给出「+0x02 样式 / +0x04 字号」，与 `DrawMsg` 的 `flag & 1/2/4` 和默认 13 一致 [I]。
- 验证：读取 `DrawMsg` 0x1009ad00 原始汇编，跟踪 `memcpy(this+0x20 → local, 0x10)` 后各局部变量的 EBP 偏移。
- 状态：`Open`（中；单次汇编精读即可闭合）。

### C3. 图片引用机制
- 语料无嵌入 JPEG、无图像文件名字符串 [E]。
- 验证：exe 中 `LOAD_JPEG_File` 调用者与路径来源。
- 状态：`Blocked`（当前语料不涉及）。

### C4. 文件尾 4 字节（= bodyLen）
- 全部样本成立；读取代码未读它 [E 观察]。
- 验证：`CSMDoc::Save` 0x100773c0 的写入路径。
- 状态：`Open`（低）。

### C5. 旧格式路径
- `FUN_00425090`（exe，旧 SYMP 头）与 `CSMDoc::ImportSMC` 0x10077690。
- 当前语料全部使用 0x2004/0x2005 [E]。
- 状态：`Low`。

## D. 已推翻或修正的假设（Contradicted / 更正）

| 阶段 | 原假设 | 现状 | 依据 |
|---|---|---|---|
| 一 | MsgHdr +14→+0x5A、+16→+0x50 等字段映射 | **正确，无需更正** | `CSMMsg::Read` 复核 |
| 一 | 0x19 head 通常 18 字节 | 修正为 `0x10 + 文本字节数` | `GulsamToSMC_Lyrics` |
| 二 | `.cod` 记录「先 start/end 后 data」 | 修正为每区间 `(start,end,data)` 紧邻 | `FUN_100306b0` |
| 二 | 韩文映射到 SJIS 码位（推测） | 确认为 id 1 = 889F.cod | `MyDrawTextOutW` |
| 三 | ObjectCore +01 是语义字段 | 实为写入未初始化栈的保留字节 | `CSMObject::Write` 0x1007a740 |
| 三 | ObjectCore +06 未知 | = headLen + 12（派生冗余长度） | `CSMObject::Write` |
| 三 | 音乐符号来自文本编码 | 实为引擎单字节常量 + KayakumA 符号字体；与 889F 无重叠 | `_probe_font_cmap.py` / `_probe_symbols.py` |

## E. 本阶段新增的未知计数

- 新增**已解决**：MsgHdr 全 12 字段、音符 head 全 6 字段、类型→绘制器全表、拍号/调号/连音机制、字体与符号机制。
- 剩余 `Open`：B1–B8、C2、C4。
- 剩余 `Blocked`：B6、C1、C3。
- 估计：主要高频类型（0x01、0x19、0x45、0x46、0x0a、0x14、0x06、0x09、0x1b、0x03）**均已恢复**；剩余工作集中在低频类型与文件头尾的细节。
