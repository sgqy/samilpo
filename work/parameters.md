# 转换器取舍清单（SMC → IR → MusicXML）

> 每条 = 一个**必须做决定**的点。格式：
> **问题** → 可选方案 → 默认 → 判据 → 已知失败模式 → 影响阶段。
> 「实测」列的出处见 `out_*.txt` 与 `decisions.md`。
> 凡例沿用 `docs/smc-format.md` §0。地址属 `engine.dll`。

参数分三类：

- **P**（Parameter）：可配置，改变产物形态，不改变正确性。
- **R**（Rule）：必须执行的规则，不可配置（换了就是错）。
- **X**（extension）：无法进 MusicXML 的信息，只能进 `ext` 或丢弃。

---

## A. 时间与时值（最关键）

### A1. tick 单位（P）
**问题**：IR 用什么时值单位？
**可选**：① 引擎原生 tick（wholeTick=240）② 放大到 MusicXML `divisions` 习惯值 ③ 直接用 MusicXML 时值符号（quarter/eighth…）。
**默认**：IR 内部用**引擎原生 tick**（整型，wholeTick 为文档参数），导出时按 `divisions = wholeTick / 4 × k` 换算。
**实测**：**8451/8451** 文件 `wholeTick = 240`，即 quarter = 60 tick。
**判据**：原生 tick 是对齐的唯一无损来源；先换算成符号时值会丢失"不可表示"的时值（见 A5）。
**失败模式**：把 tick 当成"可任意缩放"的量会在 A5 处丢余数。
**阶段**：step1（决定 IR 字段）+ step2（换算）。

### A2. 时值的权威来源（R）
**问题**：音符长度取 `head+4 的 duration` 还是 `CalcPlayTime`（`MsgHdr+0x08` 指数 + 附点 + f2）？
**实测（500KFS-0041，450 音符）**：`duration == playTime` 420 条；`duration == playTime/2` 28 条；另有 2 条例外。
**全语料**：`head[2]` 恒为 `0x40`、`head[3]` 恒为 `0x01`（652338 音符）。
**默认**：**以 playTime（指数+附点+f2）为权威**，`duration` 仅作交叉校验。
**判据**：`duration` 在含装饰音的连梁组内会出现"减半"（500KFS-0041 m3/m11 的 30-tick 装饰音），
而指数+附点在任何样本中都与"理论时值"和"小节填充"一致。
**失败模式**：如果某些文件里 `duration` 才是权威（如 0x2C/0x14 的缓升值），会在 A6 校验处暴露。
**阶段**：step1。

### A3. 一小节一谱表内的对齐模型（R）
**问题**：音符位置是"绝对 tick"还是"按声部顺序累加"？两者冲突时听谁的？
**实测**：`MsgHdr+0x14`(start) 在同一小节同一谱表内**按声部独立累加**，正常小节里
`Σ duration == tickPerMeas` 精确成立（`probe_smc.py summary`：108/109 小节精确匹配）。
**默认**：**以 start 为第一权威**（它进 IR 的 `on`），**以 duration 之和做校验**；
两者矛盾时按 A4 处理。
**判据**：start 是引擎在 `UpdateStartTime` 里写回的运行期结果，且普查中跨小节连音线
（500KFS-0041 有 6 条）依赖 start 的跨小节连续性。
**失败模式**：start 在装饰音处是"视觉位置"（m11 的 25/84 与理论 60/120 不符），
故装饰音必须单独处理（A7）。
**阶段**：step1。

### A4. 小节填充不满/超出（P）
**问题**：`Σ duration != tickPerMeas` 时怎么办？
**实测（全语料 160041 小节）**：**2989 小节**（1.9%）不匹配 —— 超出 1243、不足 1746。
用 playTime 求和可修正其中大部分（500KFS 子集的 36 例中 12 例）。
剩余真实缺口（500KFS-0095 m0 sum=240/tpm=960、0041 m93 sum=480/tpm=960、m103 sum=360/tpm=720）都是
"装饰音 + 长音"小节，缺的是被装饰音占位的部分。
**默认**：三档策略，IR 记录所选档位：
  1. `strict`：不补任何东西，`duration` 原样。→ 产物可能小节数对不上。
  2. `fill-rest`（**默认**）：空出的 tick 补休止符，超出部分不裁剪。
  3. `force`：强制按拍号裁剪/补足。
**判据**：`fill-rest` 既不改音符，又能让 MusicXML 的小节自洽。
**失败模式**：`fill-rest` 会在"用户本来就没写满"的小节造出多余休止符。
**阶段**：step1（标记）+ step2（落成 `<rest>`）。

### A5. 不可表示的时值（X + P）
**问题**：`wholeTick=240` 下 tick 粒度是 15（=1/64 音符）的整数倍；但 `f2` 连音比例会做出
`MulDiv(playTime, hi, lo)` 的非 2 的幂比例（A2 已验证路线）。
**实测**：全语料未出现非 2 的幂比例（`f2` 的 hi/lo 双字节在本语料中恒使其跳过该换算）。
**默认**：IR 保存**精确 tick**；step2 遇到无法用单一时值符号表达的 tick 时按以下顺序降级：
  ① 用 MusicXML 的 `<tuplet>`+`<time-modification>` 表达；② 拆成多个可表示值（连音线合并）；
  ③ 记为 `<ext:inexact-duration>` 并保留原 tick。默认落到 ③。
**判据**：MusicXML 的时值模型是"符号 + 附点 + tuplet"，无任意 tick 表示。
**阶段**：step2。

### A6. 跨小节音符（P，重要）
**问题**：一个音符的 tick 长度超过本小节剩余空间（或 start 已越过小节边界）怎么办？
**实测**：`docs/smc-format.md` §7.3：小节长度算自拍号；全语料 tie 26295 条，跨小节很常见，需按端点键定位目标。
500KFS-0041 的 m74/m79/m91/m93/m95/m107 有跨小节 tie。
**可选**：① 拆分并用 tie 连接 ② 保留为一个音符（产物小节时值超标）③ 裁到小节尾。
**默认**：**①拆分+tie**（与 SMC 自己的 0x09 tie 语义一致，且是 MusicXML 的标准做法）。
**判据**：MusicXML 校验器要求每小节时值 == 拍号时值。
**失败模式**：拆分点如果落在不可表示的 tick 上，退回 A5。
**阶段**：step1（标记 overflow）+ step2（拆）。

### A7. 装饰音（R + P）
**问题**：`MsgHdr+0x0A bit4`（0x10，"不发声/装饰"）的音符怎么表示？
**实测**：500KFS-0041 有 58 条；它们挂在 `type 0x14`（连梁组）下，start 是"视觉紧跟"值
（25/34/68/84…，不是理论 tick 60/120）。
**默认**：识别为 **grace note**（MusicXML `<grace>`），**不计入本声部时值累加**，
`start` 参数 `grace_strategy` 决定是否覆盖：
  - `engrave`（默认）：用 start 的相对差作为 `<grace>` 与主音的相对顺序提示（写进 `ext`）。
  - `grid`：丢弃 start，按"前一个音符之后"放置。
**判据**：装饰音在音乐上不占时值；但 SMC 的 start 仍带视觉位移信息（可能是排版余量）。
**失败模式**：`engrave` 会让 IR 的 `on` 不是严格网格值（见 A9）。
**阶段**：step1（识别+标记）+ step2（`<grace>`）。

### A8. 无时间语义的消息（R）
**问题**：连梁组 `0x14`、和弦 `0x25` 自身没有独立时值。
**实测**：`0x14` 的 `playTime = Σ 子项`（`docs/smc-format.md` §6.2）。
**默认**：IR 中 `0x14`/`0x25` 只作为**分组容器**（`beam` / `chord` 节点），
不产生 `<note>`；子项各自成为 `<note>`，`<beam>` 由容器 + 子项序号生成。
**判据**：MusicXML 的 `<beam>` 挂在 `<note>` 上，不是独立元素。
**阶段**：step1 + step2。

### A9. on 的网格化（P）
**问题**：IR 的 `on` 允许非网格值（装饰音的 25/84）吗？
**可选**：① 保留原始值 ② 吸附到最近网格。
**默认**：**保留原始 tick**，但**每个音符同时带 `grid_on`**（吸附后的值）与 `grid_error`。
step2 默认用 `grid_on`（因为 MusicXML 的位置由"前序时值累加"隐含决定，无法表达 25）。
**判据**：MusicXML 的时值推进是纯加法的，非网格 start 无法直接表达。
**失败模式**：`grid_on` 会掩盖重音错位，故 `grid_error` 必须保留以便事后审计。
**阶段**：step1。

---

## B. 声部与谱表

### B1. 声部归属（R）
**问题**：`MsgHdr+0x01` 低半字节（0..8）怎么映射到 MusicXML？
**实测**（全语料）：`voice=1` 1651738、`voice=2` 7936、`voice=3` 338、`voice=5` 56、`voice=7` 4；`0/4/6/8` 未出现。
**默认**：**1..8 → `<voice>1..8`**，`0` → 文档级/无归属（见 B4）。
**判据**：引擎自身按 9 个声部分别 `UpdatePlayTime/UpdateStartTime`（§7.3），语义直接对应。
**失败模式**：voice 与 staff 在某些文件里可能交叉，需 B2 判定。
**阶段**：step1。

### B2. 音符的"上下谱表"归属（P）
**问题**：Engine 用 `MsgHdr+0x18`(音高 Y 偏移，负值向上) 定位谱表；怎么变成 MusicXML 的 `<staff>`？
**实测**：`docs/smc-format.md` §6.5：`flags bit9 (0x0200)` = 上组谱表，`bit10 (0x0400)` = 下组谱表；
`docs/layout.md` §7：`StaffYTable[MsgHdr+0x18]`，`-0x8000` = 无该谱表。
**默认** `staff_policy`：
  - `by-staff-count`（默认）：单谱表文件全部归 `<staff>1`；多谱表按 flags bit9/bit10，缺失则按 Y 偏移符号。
  - `single`：强制全部 `<staff>1`（只适用于 staff2 == 0 的文件）。
**判据**：全语料只有 19 个文件含 staff2；bit9/bit10 是引擎自己的判定（用量极少：bit9 单独 1 次、bit10 63 次）。
**失败模式**：Y 偏移启发式在双手交叉（左手音高于右手）时会错。
**阶段**：step1（解析）+ step2（`<staff>`）。

### B3. 谱表与 MusicXML `<part>` 的对应（R）
**问题**：System 里的 staff1/staff2 是 `<part>` 还是 `<staff>`？
**默认**：**每个 Staff → 一个 `<part>`**（SMC 的 staff1/staff2 是"上/下组谱表"，
是 0x03/0x04 两个对象类型，见 §5.3），组内 `staffIdx` 递增。
**判据**：`CSMStaff` 自带 `n_meas` 与小节数组，天然是独立的 part 级结构。
**失败模式**：钢琴类双行谱本应是一个 part 两个 staff；此时需 `part_merge` 参数（见 B4）。
**阶段**：step1。

### B4. part 合并（P）
**问题**：钢琴/双行谱要不要合成一个 `<part>`（含 `<staves>2</staves>`）？
**默认**：**不合并**（`part_merge=none`）；提供 `part_merge=all` 与 `part_merge=by-index`。
**判据**：判断依据应是"同一个 Block 里出现多个 StaffRef"（`docs/layout.md` §6），
普查中 `(nStaves,f2)=(2,4)` 仅 46 例 → 双行谱存在但罕见。
**失败模式**：不合并会让钢琴双手谱成两个独立 part，演奏语义上不同。
**阶段**：step1（识别 block 内多 staff）+ step2。

### B5. 文档级消息（0x3F/0x40/0x04）与 `voice=0`（X）
**实测**：每文件各一次，无 head，语义未定（`docs/unknown-fields.md` B6）。
**默认**：进 IR 的 `doc.messages`，**不产出 MusicXML**，只写 `ext`。
**判据**：无消费者证据，强行映射会造出错误的谱面元素。
**阶段**：step1（保留）+ step2（丢弃/扩展）。

---

## C. 音高、调号、变音

### C1. 音高来源（R）
**问题**：音高用 `head+0x00`（MIDI key）还是按谱号/Y 偏移推？
**实测**：MIDI key 范围 38..89，`GetMidiKey/SetMidiKey` 直接读写 `head[0]`（§6.7）。
**默认**：**直接用 `head[0]`**，配合 C2 的谱号/调号换算成 `<pitch><step><alter><octave>`。
**判据**：MIDI key 是引擎的权威音高。
**失败模式**：打击乐谱表（`StaffTail+0x21` 谱号类别 2/3）里 key 不是音高而是"乐器编号"，
必须走 C5。
**阶段**：step1。

### C2. 变音记号（P，重要）
**问题**：`MsgHdr+0x05` 高 4 位低 3 位 = {0 无,1 升,2 降,3 还原,4 重升,5 重降}，
但引擎还有 `WhatIsAccidental` 的"从调号累积"逻辑（§1.4）。
**可选**：① 按音符自身的记号写 `<alter>`+`<accidental>` ② 按调号推算（`<key><fifths>` 管调号，音符不写 alter）。
**默认** `accidental_policy`：
  - `explicit`（默认）：音符自带记号 → 写 `<accidental>`；无记号 → 写 `<alter>` 但**不写** `<accidental>`。
  - `transposed`：全部按调号推算，`<alter>` 由 key 决定。
**判据**：SMC 里"音符自身记号"是显式字段，而引擎的累积值是运行期派生（`WhatIsAccidental` 遍历小节）。
**失败模式**：`explicit` 在调号与小节内临时记号冲突时可能与原排版不一致（但音高正确）。
**阶段**：step2。

### C3. 调号（R + P）
**实测**（全语料 8451 文件，`probe8.py`）：调号存于 **Meas 尾块**：`+0x46` 类型、`+0x5A` 符号、`+0x5C` 个数。
- `keysig_type`：1 → 159112、**2 → 929**（spec 未记录，仅 20 个文件）；
- `symbol`：0 → 20611、1 → 38040、2 → 101390；
- `count`：0 → 20611、1 → 51266、…、7 → 64；
- **`symbol == 0` 与 `count == 0` 严格一一对应**（20611/20611）。
**默认**：
  - `<fifths>`：`symbol == 2`（升号序 F C G D A E B）→ `+count`；`symbol == 1`（降号序）→ `-count`；
    `symbol == 0` → `0`（无调号）。
  - `keysig_type == 2` 按普通调号处理 + 记 `warning`（`key.source_type = 2`）。
  - **只在变化的小节写** `<attributes><key>`。
**判据**：`symbol=0/count=0` 严格同步出现，说明"无调号"由 `symbol=0` 表达；
`type=2` 在同一文件内切换而不改变内容（`201OPS-0019.smc`：前 16 小节 2、后 8 小节 1，全程 count=0）。
**失败模式**：`type` 的其余取值（spec 说 `8` = 无调号）在全语料未出现，无需特殊处理。
**阶段**：step1（解析）+ step2。

### C4. 谱号（P）
**实测**：`type 0x1F` 谱号消息在语料中仅 13 条；大多数谱号由**小节级** `DrawMeasClef` 承担，
`StaffTail+0x21` 是谱号类别。`type_index` 是谱号类型码（`SetParamFromMidiKey` case 1..8，case 8 = 打击乐）。
**默认** `clef_policy`：
  - `staff-tail`（默认）：从 `StaffTail+0x21` 推 `<clef>`（1 = 常规五线谱，2/3 = 打击乐/特殊）。
  - `msg`：优先用 0x1F 消息，缺省回落 `staff-tail`。
**判据**：0x1F 太少（13/8451 文件），不足以承担谱号来源。
**失败模式**：`staff-tail` 只给"类别"，具体是 G/F/C 谱线靠 `+0x21` 的取值枚举——目前枚举未知 [?]。
→ **此项是已知缺口**，IR 里保留原始字节并标记 `clef_uncertain`。
**阶段**：step1。

### C5. 打击乐（P）
**问题**：`StaffTail+0x21` 为 2/3 时是打击乐谱表，`MsgHdr+0x06`（符头类型字段）在打击乐里是**声部索引**。
**默认**：产出 `<unpitched>` + `<instrument>`，并保留原始编号到 `ext`。
**判据**：`docs/smc-format.md` §7.2「2/3 = 打击乐/特殊，用于 DrawHead 与音高计算」。
**失败模式**：语料中此类谱表极少（全语料未确认），实现可延后。
**阶段**：step2（低优先）。

---

## D. 歌词

### D1. 歌词的单位（R）
**实测**（全语料 625967 条）：`chars=1` 619562 条（99.0%），其余 6405 条为 2–29 字符。
`headLen = 0x10 + 字节长度`（bytelen=2 占 619686）。
**默认**：**一条 0x19 = 一个 `<lyric>` 文本单元**（MusicXML 的 `<text>` 即"一个音节"）。
**判据**：韩文音节的语义单位与 MusicXML `<lyric><text>` 的"音节/词"语义匹配。
**失败模式**：多字符记录（158 条）需要按空格/标点再切分 —— 见 D3。
**阶段**：step1。

### D2. 歌词与音符的绑定（R）
**实测**：`docs/lyrics.md` §6.1：2961/2961 歌词的父对象都是 type 0x01 音符；
500KFS-0041 中 key 差为 +1（271 条）/+2（33 条），17 个音符无歌词。
**默认**：**按对象包含关系绑定**（不用 key 差）。每个音符最多 1 条歌词。
**判据**：包含关系是引擎自己的关联方式；key 差只是分配器习惯（§6.2 明确"不是查找依据"）。
**失败模式**：无。
**阶段**：step1。

### D3. 歌词分段/换行（X，已知缺口）
**实测**：歌词记录**不含换行**；`docs/lyrics.md` §6.4 + `unknown-fields.md` C1：
分段由所依附音符所在小节/行决定，判定规则未解。
**默认** `lyric_line_policy`：
  - `by-measure-gap`（默认）：同一行内相邻歌词间隔 >= `lyric_gap_threshold` 个 tick（默认 4 个八分音符）
    或跨小节且该小节是行首 → 视为新段。
  - `none`：不切段，全部作为一行（产物可能很长）。
**判据**：无确定规则，只能启发式。阈值必须可配置。
**失败模式**：**这是本转换器最大的语义缺口**，会直接影响歌词换行位置。
IR 中歌词保留原始顺序 + 所在小节 + 目标 tick，便于换策略重跑。
**阶段**：step1（保留全部原始信息）+ step2（启发式）。

### D4. 歌词的音节连字符与延长（P）
**实测**：`－`（U+FF0D，来自 889F 码位 `F0 41`）在语料中大量出现，语义为"分句/延长标记"（`docs/encoding.md` §6）。
**默认** `hyphen_policy`：
  - `literal`（默认）：把 `－` 原样写进 `<text>`。
  - `syllabic`：`－` 映射为 `syllabic="begin"/"middle"/"end"`，文本里去掉它。
**判据**：MusicXML 的 `<syllabic>` 是为歌词音节连读设计的，而 `－` 正是这个用法。
**失败模式**：`syllabic` 对"延音线式 `－`"（真正的延长而非音节连接）会误判。
**阶段**：step2。

### D5. 歌词字体/字号/颜色（X）
**实测**：字号 {13: 30136, 14: 140, 12: 74}，字体索引 {1,2,3,5,6,7}，样式 {0,1}，颜色恒 0x000000。
**默认**：写 `<lyric><text>` + `<ext:font index=.. size=.. style=.. color=..>`；不产出 `<print>` 级样式。
**判据**：MusicXML 的歌词文本样式在 `<defaults><lyric-font>` 是文档级，逐条样式不标准。
**阶段**：step2。

---

## E. 和声与其他记号

### E1. 和弦记号（0x45）（P，重要）
**实测**：500KFS-0041 有 91 条 `0x45`，`surfix.name` 取值 `{b'm':78, b' (major)':12, b'7':1}`；
全语料 177909 条，`headLen ∈ {0: 110088, 100: 67821}`（100 = 含 `Ptr32` 的无语义运行期结构，§6.9，**原样保留**）；
父对象分布 = 音符 164919、小节 8059、休止符 4931（**可挂小节**）。
**可选**：① 输出 MusicXML `<harmony>` ② 只写 `<ext>` ③ 两者都写。
**默认** `harmony_policy = both`：`<harmony><kind>` 用 `surfix.name` 映射，同时在 `ext` 保留原始后缀串与 `info` 字节。
**判据**：`surfix.name` 是**可读后缀串**（`" (major)"`、"m"、"7"、"dim"），与 MusicXML `<kind>` 概念对口。
**失败模式**：`<kind>` 的枚举有限，未识别的后缀必须走 `<kind text="...">`（MusicXML 允许自由文本）。
**阶段**：step1（解析）+ step2（映射表）。

### E2. 和弦记号的根音（X，缺口）
**实测**：`ChordSurfix` 只有 `name` + `n` + `info[n]`；**根音不在其中**，
推测根音由所在音符的 MIDI key 或 `MissNoteKey` 承担 [?]。
**默认**：IR 记录 `attached_note_key`；step2 用**所依附音符的音高**当根音，
并把 `info` 字节写进 `ext`。
**判据**：和弦记号 92.7% 挂在音符上（全语料 164919/177909），符头就是根音 —— 与吉他/键盘记谱惯例一致。
**失败模式**：`info` 里若另有根音信息则会错音名。**已记为待验证项**。
**阶段**：step1 + step2。

### E3. 指板图（0x46）（P）
**实测**：与 0x45 一一对应（177909 条 vs 177909 条）；`FretInfo` = 基准品位 + 6 弦品位 + 4 组 (起始,结束)。
**默认** `fret_policy`：
  - `ext`（默认）：写进 `ext:fretboard`，不产出 MusicXML 元素。
  - `frame`：映射为 `<harmony><frame>`（弦/品位 → `<frame-note>`）。
**判据**：MusicXML 有 `<frame>`，但对"4 组 (起始,结束) 对"语义未解（`unknown-fields.md` B5），
映射不完整。
**阶段**：step2。

### E4. 力度记号（0x1B）（R）
**实测**：`MsgHdr+0x08` = 力度码，`DrawDynamic` 用 `CodeDyn[码]` 取单字符；
`CodeDyn` 表 = `00 F0 F1 F2 F3 F4 F5 F6 F7 F9 FA FB FC FD FE FF`（`font-resources.md` §4.2）。
**默认**：映射为 MusicXML `<dynamics><f/><p/>…`；**码 → 名称需人工建立对应表**（符号字形未逐项确认）。
**判据**：`CodeDyn` 是引擎自己的枚举，`font-resources.md` §6 明确"逐项语义未逐一确认"。
**失败模式**：**码到 f/p/mf 的对应是猜测**。IR 里必须保留原始码，映射表放配置。
**阶段**：step1（原始码）+ step2（可配置映射表）。

### E5. 其他记号（tie/slur/连音符/踏板/颤音/换气/花音/Coda/长休止/滚奏/渐强…）
**实测**：
- `0x09 tie`：13 条（0041）/ **26295** 条（全语料）→ `<tie>` + `<tied>`。
- `0x0A slur`：64 / **62202** → `<slur>`。500KFS-0041 全部同小节；全语料有跨小节。
- `0x2E slur.indep`：独立圆滑线 → `<slur>`（挂在哪需按端点键找）。
- `0x12 小节级连音符`：106 条 → `<tuplet>`（小节级，需按 `CalcWholeCount` 的分段表推时值）。
- `0x10 踏板` / `0x21 颤音` / `0x0D 滚奏` / `0x13 渐强` / `0x2F 换气` / `0x30 花音` / `0x0C Coda` / `0x2C 长休止`：
  低频（0–111 条），已确认**存在**但字段/绘制不完整。
**默认**：
  - `tie/slur`（`endpoint_resolution`）：**按端点键解析**：`0x09/0x0A` 的 `MsgHdr+0x20` 与自身 key 是两个端点；
    在**同一 Staff 的全局 key 表**里查，得到"起点音符 / 终点音符"。
    全语料仅 **82** 条端点无法解析（92368 条引用中占 0.09%）。
  - 其余：`support_level = ext`（默认）或 `native`（逐项实现）。低频项写 `ext`，不阻塞主流程。
**判据**：端点键是显式字段且解析率 99.7%，是最可靠的跨对象引用。
**失败模式**：跨 Staff 的 tie（本语料未出现）需要跨 Staff key 表 —— 影响不大但需设计。
**阶段**：step1（解析 + 统一成 `span` 结构）+ step2（映射）。

### E6. 图形对象（直线/矩形/椭圆/贝塞尔/文本框）（X）
**实测**（全语料）：`0x18 line` 10429、`0x27 rect` 14、`0x26 ellipse` 3、`0x44 curve` 1；
`0x06 text` 141（=文本框，TLV head）。
**默认**：全部写 `ext`。文本框**可以**映射为 MusicXML 的 `<direction><words>` 或 `<credit>`，
但 TLV 的对齐/字体标签映射到 `<direction-placement>` 有损 → 默认只写 `ext`。
**判据**：这些是"版式"而非"音乐"；MusicXML 无等价物。
**阶段**：step2。

---

## F. 版式、分页与"不存在的东西"

### F1. 翻页 / 分页（X，明确说明）
**问题**：SMC 有 Page + Block（排版行）。IR 要不要保留？
**结论**：**保留为 `layout` 子树，但不影响 MusicXML 产物**。
**理由**：MusicXML 的 `<print new-page>` 只在显式要求时才应生成；
分页是"排版结果"，不是"音乐内容"。
**默认** `page_policy`：
  - `ignore`（默认）：Page/Block 全部进 `layout`，不产出任何 MusicXML 元素。
  - `system-breaks`：把 Block 边界映射为 `<print new-system>`（同页内换行）与 `<print new-page>`。
**判据**：Block = 排版行（`docs/layout.md` §6），与乐谱的"系统/行"概念对应，
但 SMC 的行划分是**已排版的结果**（含 X 坐标 `measX`），会被任何目标渲染器重排。
**失败模式**：`system-breaks` 会让 MusicXML 的分行与谱面完全一致但可能不符合目标排版器的最优断行。
**注意**：SMC 的 `measX` 是**绝对像素坐标**（`docs/layout.md` §6 归一化后），
若映射为 MusicXML 的 `<measure>` 宽度会引入无法移植的绝对尺寸 → 默认丢弃。

### F2. 坐标与尺寸（X）
**实测**：`MsgHdr+0x16`(dx)、`+0x18`(dy) 是相对排版坐标；`+0x0C/+0x0E/+0x10/+0x12` 是绘制缓存（无语义，`field-coverage.md` §3）。
**默认**：全部进 `ext:position`，**不参与 MusicXML 布局**。
**判据**：MusicXML 的定位是相对的（`<offset>`、`default-x`），且引擎坐标是"已排版"值。
**例外**：dx/dy 可用于**连音线的形状提示**与**和弦记号在音符上方/下方**的判定 —— 见 F3。

### F3. 和弦记号/力度记号的上下位置（P）
**默认**：用 `MsgHdr+0x18`(dy) 的符号决定 `<direction placement="above|below">`。
**判据**：dy 负值向上（`docs/layout.md` §7），与"符干方向/记谱惯例"一致。
**失败模式**：dy 是排版结果，可能被引擎微调过。

### F4. 缩放（P）
**实测**：`MsgHdr+0x02` = 缩放百分比，默认 `0x10`=16（`SelectFont((v*100)>>4)`）。
**默认**：16 → 100%；若强制使用则写 `<ext:scale>` 并用 `<print> `级 `<scaling>`。默认忽略。
**判据**：这是"显示缩放"，非音乐信息。

### F5. 颜色（X）
**实测**：`MsgHdr+0x28` 为颜色/样式（`DrawDynamic` 用作 `SetTextColor`）；歌词 head+0x08 颜色恒 0。
**默认**：进 `ext:color`。

---

## G. 产物级参数（step2 特有）

### G1. `<divisions>`（P）
**默认**：`divisions = wholeTick / 4 = 60`（即 1 个 64 分音符 = 1 tick）。
**判据**：`wholeTick=240` 下 tick 粒度是 15，`divisions=60` 时 15/60 = 1/4 拍 = 16 分音符，正好整除。
**失败模式**：若某文件 `wholeTick != 240`，需要重算（IR 里带 `wholeTick` 参数）。

### G2. `<key>`/`<time>`/`<clef>` 的书写时机（R）
**默认**：只在**变化处**写；文件首小节强制写。
**判据**：MusicXML 的 `<attributes>` 是"状态变更"语义。

### G3. 拍号写法的特例（P）
**实测**：`MeasTail+0x00 == 3` 表示"拍号用文本描述"，且 `+0x13` 有 16 字节拍号文本；
 全语料有 `41/16` 与 `63/16` 这种非音乐拍号（500KFS-0117，各 1 例）。
**默认** `timesig_policy`：
  - `symbolic`（默认）：`<beats>/<beat-type>` 正常写。
  - `text`：`MeasTail+0x00 == 3` 时改用 `<time symbol="...">` 或 `<ext:time-text>`。
  - `clamp`：非常规拍号（如 63/16）按 `num` 拆成连续小节（63/16 → 7 个 9/8 或按 `measX` 分段）。
**判据**：`41/16`、`63/16` 很可能是"某个小节里塞了多小节"或"数据退化"，需人工确认后决定。
**失败模式**：`clamp` 会改变小节数 → 必须显式记录。
**阶段**：step2。

### G4. 输出文件与元数据（P）
**默认**：`<work-title>` 用 `title_raw`（889F 解码）；`<identification>` 用 SYMP 头的附加字符串；
`<part-name>` 用 `StaffTail+0x00`（谱表名，普查中多为空 → `StaffTail` 缺失时用 `0x49` 消息的字串）。
**判据**：`docs/smc-format.md` §3.1：曲名在 SYMP 头 `+0x00A`（`CStrZ`）。
**失败模式**：附加字符串（`"448"`）语义未知（`unknown-fields.md` B7）→ 只写 `ext`。

---

## H. 汇总：需要暴露为 CLI 参数的项

| 参数 | 取值 | 默认 | 影响 |
|---|---|---|---|
| `duration_source` | `playtime` / `head` / `both` | `playtime` | A2 |
| `gap_policy` | `strict` / `fill-rest` / `force` | `fill-rest` | A4 |
| `overflow_policy` | `split-tie` / `keep` / `clip` | `split-tie` | A6 |
| `grace_strategy` | `engrave` / `grid` | `engrave` | A7 |
| `grid_snap` | `none` / `nearest` | `nearest` | A9 |
| `staff_policy` | `by-staff-count` / `single` | `by-staff-count` | B2 |
| `part_merge` | `none` / `all` / `by-index` | `none` | B4 |
| `accidental_policy` | `explicit` / `transposed` | `explicit` | C2 |
| `key_policy` | `per-change` / `every-measure` | `per-change` | C3 |
| `clef_policy` | `staff-tail` / `msg` | `staff-tail` | C4 |
| `lyric_line_policy` | `by-measure-gap` / `none` | `by-measure-gap` | D3 |
| `lyric_gap_threshold` | tick 数 | 480 | D3 |
| `hyphen_policy` | `literal` / `syllabic` | `literal` | D4 |
| `harmony_policy` | `ext` / `native` / `both` | `both` | E1 |
| `fret_policy` | `ext` / `frame` | `ext` | E3 |
| `dynamic_map` | 表文件 | 内置猜测表 | E4 |
| `span_policy` | `resolve-keys` / `keep-raw` | `resolve-keys` | E5 |
| `symbol_policy` | `ext` / `native` | `ext` | E5 |
| `page_policy` | `ignore` / `system-breaks` | `ignore` | F1 |
| `timesig_policy` | `symbolic` / `text` / `clamp` | `symbolic` | G3 |
| `divisions` | int | 60 | G1 |
| `measure_mode` | `strict-ts` / `per-source` | `strict-ts` | A5/G3 |
