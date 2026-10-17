# SMC 未知字段与未解结构

> 凡例见 `docs/smc-format.md` §0（知识评级 `[E]`/`[I]`/`[?]`/`[C]`；数据类型为 Rust 风格）。
> 状态：`Open`（待研究）/ `Blocked`（需动态调试或额外样本）/ `Low`（低优先级）。
> 逐结构的字节覆盖率见 `docs/field-coverage.md`。

## A. 已确认读写但语义未明（Inferred）

| 位置 | 字段 | 现状 | 需要的证据 | 状态 |
|---|---|---|---|---|
| ObjectCore +0x02 | `f2` 连音比例 | `CalcPlayTime` 用其高/低字节做 `MulDiv` [E 用法]；命名与完整语义未定 | 编辑期 `f2` 写入路径 | `Open` |
| ObjectCore +0x08 | `f8` | 仅见读写；type 0x45 时被 `obj+0x80` 覆盖 [E] | 消费者分析 | `Open` |
| MsgHdr +0x28 | 颜色/样式 | `DrawDynamic` 用作 `SetTextColor` 参数 [I] | 与 head 颜色字段对照 | `Open` |
| Staff +0x4D | 谱号类别 | `== 5` 与 `2/3` 分支出现在多个函数 [E 用法] | 取值枚举与含义 | `Open` |

## B. 完全未知的结构（Open）

### B1. ObjectCore 保留字节 +0x01

- 语义：读取路径从不使用；写入路径写入**未初始化栈字节** [E]。
- 全语料分布：46% 为 0，其余为大范围随机值。
- 对第三方解析的影响：无。可忽略或原样保留。
- 状态：`Open`（收益低；如需解释需动态调试写入时的栈内容）。

### B2. type 0x2C（长休止）headLen 60

- 语料 98 条；`DrawLongrest` 0x100595B0。
- 已确认：小节制数在 **`MsgHdr+0x1C`**（非 head）[E]。
- head 60 字节的字段划分未分析。
- 状态：`Open`（中）。

### B2b. type 0x08 的 12 个索引含义未定

- 语料 6707 条，分布在 39 个文件中；结构已完全解出（见 `docs/smc-format.md` §6.13b）[E]：
  `MsgHdr+0x06` = `MarkTB` 索引，`+0x16/+0x18` = X/Y，`headLen` 恒 0。
- **仍未知**：索引 1/8/10/11/13/14/16/25/33/35/43/45 各自对应哪个音乐符号。
- 26 项中的 12 项（0、7、9、12 等）在语料中从未出现 [?]——出现在语料中的只有 14 项。
- 为何无法自动判定：`MarkTB` 只存字体码，程序内**无任何**记号名称字符串
  （已全量搜索 Shift-JIS / 889F / UTF-16LE；UI 主要靠 169 个位图按钮）[E]；
  字体 `KAYAKUMA.TTF` 的 glyph 名是无意义占位名（`U`、`comma`…），只能靠轮廓判形。
- 已定案：`29` = 正立延长记号、`30` = 倒立延长记号（轮廓互为垂直翻转，
  `29` 的 `dy` 全负、`30` 全正，符合「弧口朝符头」画法）[E]。
- 待人工确认：其余 12 项。问卷 `work/mark-questionnaire.html`，
  答卷 `work/mark-questionnaire.tsv`，统计数据 `work/mark-stats.json`。
- 状态：`Blocked`（需人眼看程序画面或纸谱，无法从字节与轮廓推出）。

### B3. type 0x0C（Coda）headLen ∈ {5, 8, 9, 11}

- 语料 165 条；`DrawCoda` 0x10056EC0 / `DrawCodaEx` 0x10065660。
- head 字段未分析。
- 状态：`Open`（低）。

### B4. type 0x47（节奏型）事件体语义

- 语料 12716 条（其中 101 条内嵌于 0x45）。
- 顶层结构已恢复（见 `docs/smc-format.md` §6.9）：`totalSize/stride/字段A/字段B/eventCount/eventSize/事件块/第二段`。
- **每条事件（16 字节）与第二段（6 字节/条）内部字段未解析**。
- 相关函数：`CRtmData::ConvertToPlayData`（导出）、`CRtmData::GetRealMidiKey` 0x10047410、
  `CRtmData::ReadRtmData` 0x10046210、`CRtmData::GetFullFileName` 0x100472F0。
- 状态：`Open`（中）。

### B5. type 0x46（指板）与 `FretInfo` 的 8 字节对

- 语料 177909 条（与 0x45 一一对应）。
- 已确认：`+0x00` 基准品位、`+0x02` 6 弦品位、`+0x08` 4 组 (起始,结束) 对（见 `docs/smc-format.md` §6.8）[E]。
- **4 组 (起始,结束) 对的具体含义**（按弦的按弦区间？）未定 [?]。
- 状态：`Open`（低）。

### B5b. type 0x45 的 head（长度 100）

- headLen ∈ {0, 100}；长度 100 的 head 为**持久化运行期结构**（含 MFC42 区段 `Ptr32` 与栈值）[E]。
- 详见 `docs/smc-format.md` §6.9。第三方处理方式：**原样保留**。
- 状态：`Open`（中；如需完全解释需动态调试）。

### B6. 文档级消息 0x04 / 0x3F / 0x40

- 每文件各一次；无 head；`0x04` 亦映射到 `DrawMultiText` [E]。
- 语义未定（可能是页眉/页脚或文档标志）。
- 状态：`Blocked`（需动态观察）。

### B7. 附加字符串（file 0x590）

- 通常为数字串（`"448"`）；318 个文件为 32 字节的双字节文本 [E]。
- 状态：`Open`（低）。

### B8. SYMP 头 / SMC 块 / CSMCtrlTool / CSMFileInfo 的其余字段

- 大量字段读写位置已知但语义未定（见 `docs/smc-format.md` §3.1、§3.5、§3.6）。
- 入口：`CSMFileInfo::SetLogicPageInfo` 0x10094ED0、`UpdateLogicDoc` 0x100950A0。
- 状态：`Open`（低；需 exe 侧消费者分析）。

### B9. Meas 尾块未解字段

- `+0x44..+0x52`、`+0x4E`/`+0x50` 等（见 `docs/layout.md` §4.2）。
- 状态：`Open`（低）。

## C. 需要动态调试或额外样本（Blocked）

### C1. 歌词 head 的行分组规则

- 歌词记录本身不含换行；分段由所依附音符所在小节/行决定 [I]。
- 验证途径：`CSMDoc::GetRealRectOfLyrics` 0x10003D40 的调用者与绘制循环。
- 状态：`Open`（中；第四阶段已闭合 head 字节归属，此项独立）。

### C2. 图片引用机制

- 语料无嵌入 JPEG、无图像文件名字符串 [E]。
- 验证：exe 中 `LOAD_JPEG_File` 调用者与路径来源。
- 状态：`Blocked`（当前语料不涉及）。

### C3. 旧格式路径

- `FUN_00425090`（exe，旧 SYMP 头）与 `CSMDoc::ImportSMC` 0x10077690。
- 当前语料全部使用 0x2004/0x2005 [E]。
- 状态：`Low`。

## D. 已推翻或修正的假设

| 阶段 | 原假设 | 现结论 | 依据 |
|---|---|---|---|
| 一 | MsgHdr +0x14→+0x5A、+0x16→+0x50 等字段映射 | **正确，无需更正** | `CSMMsg::Read` 复核 [E] |
| 一 | 0x19 head 通常 18 字节 | `0x10 + 文本字节数` | `GulsamToSMC_Lyrics` [E] |
| 二 | `.cod` 记录「先 start/end 后 data」 | 每区间 `(start, end, data)` 紧邻 | `FUN_100306B0` [E] |
| 二 | 韩文映射到 SJIS 码位 | 确认 id 1 = 889F.cod | `MyDrawTextOutW` [E] |
| 二 | 歌词 head +0x02/+0x04 归属不明 | **闭合**：+0x02 = `u8` 样式、+0x04 = `u16` 字号 | `DrawMsg` 汇编（四阶段）[E] |
| 二 | 歌词 head +0x06/+0x0D/+0x0E/+0x0F 含义未知 | **闭合**：未初始化栈残留 | 读写两侧汇编集合一致 [E] |
| 三 | ObjectCore +0x01 是语义字段 | 写入未初始化栈的保留字节 | `CSMObject::Write` 0x1007A740 [E] |
| 三 | ObjectCore +0x06 未知 | `= headLen + 12`（派生冗余长度） | `CSMObject::Write` [E] |
| 三 | 音乐符号来自文本编码 | 引擎单字节常量 + KayakumA 符号字体；与 889F 零重叠 | `tools/_probe_font_cmap.py` / `tools/_probe_symbols.py` [E] |

## E. 剩余未知字节范围（摘要）

精确到结构的字节范围见 `docs/field-coverage.md`。要点：

1. **无语义区域**（可安全保留，不需解释）：ObjectCore +0x01；ObjectCore +0x06（派生）；
   歌词 head 的 6 个残留字节；type 0x45 headLen 100 的绝大部分。
2. **已知长度、语义未定**：`CSMCtrlTool` 约 0x400 字节中的大半；`CSMFileInfo` 全 0x20 字节；
   Meas 尾块 0x60 字节中的约 20 字节；Block 的 `staffRef.b` 项。
3. **已知长度、结构已定、内部未定**：`RtmData` 的事件块与第二段；`FretInfo` 的 8 字节对；
   type 0x2C 的 60 字节 head；type 0x0C 的 head。
