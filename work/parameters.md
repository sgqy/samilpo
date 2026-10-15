# 转换器取舍清单（SMC → IR → MusicXML）

> 每条 = 一个**必须做决定**的点。格式：
> **问题** → 可选方案 → 结论 → 判据 → 已知失败模式 → 影响阶段。
> 凡例沿用 `docs/smc-format.md` §0。地址属 `engine.dll`。实测出处见 `decisions.md` 与 `out_*.txt`。

三类标记：

- **R**（Rule）：有客观正确答案，**写死为常量**，不可配置。换了就是错。
- **P**（Parameter）：无客观答案、纯属偏好，**暴露为 CLI 参数**。
- **X**（ext）：无法进 MusicXML 的音乐外信息，按 `extent` 决定去向。

> **本清单已按"有客观答案吗？"收敛过一次**：早先版本有 22 个参数，其中 16 个其实有正确答案，
> 现降为常量。当前仅 **6 个参数**（§H）。被降级/删除的项保留在 §I 以便追溯。

---

## A. 时间与时值

### A1. tick 单位（R）
**问题**：IR 用什么时值单位？
**结论**：**引擎原生 tick**，整型。`whole_tick` 记录在文档级。
**实测**：全语料 **8451/8451** 文件 `whole_tick = 240`。
**关键**：`whole_tick` 是**四分音符**的 tick 数（不是全音符），由 spec 公式反推：
`tickPerMeas = whole_tick * num * 4 / den`；4/4 → 960 = 4 个 quarter ✓。
故 whole = 960、quarter = 240、eighth = 120、**tick 粒度 = 15（1/64 音符）**。
**判据**：原生 tick 是对齐的唯一无损来源；先符号化会丢"不可表示"的时值（A5）。
**阶段**：step1。

### A2. 时值的权威来源（R）
**问题**：音符长度取 `head+4 的 duration` 还是 `CalcPlayTime`（`MsgHdr+0x08` 指数 + 附点 + f2）？
**结论**：**以 `playTime` 为权威**；`duration` 仅存为 `dur_head` 供审计。
**实测**：500KFS-0041 的 450 音符中 `duration == playTime` 420 条、
`duration == playTime/2` **28 条**（全是 `flags&0x10` 装饰音，且都挂在 `0x14` 连梁组下）、
另 1 条为脏数据（m11 key=122：`2880` vs `720`）。
全语料：`head[2]` 恒 `0x40`、`head[3]` 恒 `0x01`（652338 音符）。
**判据**：`playTime` 由记谱字段（指数、附点）算出，`duration` 是同一份数据的缓存，会被装饰音改写。
**失败模式**：若有文件以 `duration` 为权威，会在 A4 校验处暴露。
**阶段**：step1。

### A3. 一小节一谱表内的对齐模型（R）
**问题**：位置用"绝对 tick"还是"按声部顺序累加"？冲突时听谁的？
**结论**：**以 `MsgHdr+0x14`(start) 为第一权威**（进 IR 的 `on`），**以时值之和做校验**。
**实测**：500KFS-0041 **108/109** 小节 `Σ duration == tickPerMeas` 精确成立。
`start` 在同一谱表内按声部独立累加。
**失败模式**：`start` 含排版量 —— 同音内容的小节 3 与 11 给出 `34/84` 与 `25/84`。
**阶段**：step1。

### A4. 小节填充（R + 审计）
**问题**：`Σ playTime != tickPerMeas` 时怎么办？
**结论**：**行为固定为补休止符**（不裁剪、不改音符）。
但 **IR 必须记录原始 `gap`**（每声部：`tickPerMeas - content_end`），供事后审计。
**实测**（全语料 160041 小节）：**2989 小节**（1.9%）不匹配 —— 超出 1243、不足 1746。
500KFS 子集的 36 例中 12 例用 playTime 求和即恢复；其余是装饰音占位（0041 m93/m103）与脏 duration（m11）。
**判据**：MusicXML 要求每小节时值与拍号一致，故必须补；
但"补出来的休止符"和"原谱休止符"在音乐上不同，因此把 `gap` 留在 IR 里而不是提供 `strict` 档。
**失败模式**：原谱确实没写满的小节会多出休止符（可用 `gap` 事后识别）。
**阶段**：step1（记录）+ step2（落成 `<rest>`）。

### A5. 不可表示的时值（R）
**问题**：什么时值用 MusicXML 表示不了？
**结论**：`divisions = whole_tick = 240` 时，**一个 tick 就是一个 `divisions` 单位**，
故本语料**不存在**不可表示的时值（粒度 15 整除 240）。
**实现**：仍保留降级路径（tuplet → 拆分 → `ext:inexact-duration`），但预期不触发。
**判据**：MusicXML 的时值模型是"符号 + 附点 + tuplet"；`divisions=240` 让 tick 直通。
**失败模式**：若某文件 `whole_tick != 240`，需重算 `divisions`（IR 带参）。
**阶段**：step2。

### A6. 跨小节音符（R）
**问题**：音符 tick 长度超出本小节剩余空间（或 `start` 已越过边界）怎么办？
**结论**：**拆分为两段并用 tie 连接**。
**实测**：`docs/smc-format.md` §7.3 小节长度算自拍号；全语料 tie 26295 条，跨小节常见。
**判据**：MusicXML 校验器要求每小节时值 == 拍号时值；拆分 + tie 也正是 SMC 自身 `0x09` 的语义。
**失败模式**：拆分点若落在不可表示 tick 上 → 退回 A5（`divisions=240` 下不会发生）。
**阶段**：step1（标记 overflow）+ step2（拆）。

### A7. 装饰音（R）
**问题**：`MsgHdr+0x0A bit4`（0x10，"不发声/装饰"）的音符怎么表示？
**结论**：识别为 **grace note**（`<grace>`），**不计入声部时值累加**；
`start` 的原值进 `ext.engrave_hint`（不参与网格）。
**实测**：全语料中该位出现数百条；500KFS-0041 有 58 条，全部挂在 `0x14` 连梁组下，
`start` 是"视觉紧跟"值（m11 的 `25`、`84`；m93 的 `68`）。
**判据**：装饰音在音乐上不占时值，故不能参与 A4 的填充校验（否则会算出假缺口）。
**阶段**：step1（识别）+ step2（`<grace>`）。

### A8. 无时间语义的容器（R）
**问题**：连梁组 `0x14`、和弦 `0x25` 自身没有独立时值。
**结论**：**只作分组容器**，不产生 `<note>`；`<beam>` 由容器 + 子项序号生成。
**实测**：`0x14` 的 `playTime` 与子项之和**不等**（m3：`120` vs 720）→ 进一步证明容器不参与时值。
**判据**：MusicXML 的 `<beam>` 挂在 `<note>` 上，不是独立元素。
**阶段**：step1 + step2。

### A9. `on` 的网格化（R + 审计）
**问题**：IR 的 `on` 允许非网格值吗？
**结论**：**保留原始 `on`**，同时算 `grid`（吸附）与 `grid_error`，step2 默认用 `grid`。
**判据**：MusicXML 的位置由"前序时值累加"隐含决定，无法表达 25。
**失败模式**：`grid` 会掩盖重音错位 → `grid_error` 必须保留以便审计。
**阶段**：step1。

---

## B. 声部与谱表

### B1. 声部归属（R）
**结论**：`MsgHdr+0x01` 低半字节 1..8 → `<voice>` 1..8；`0` → 文档级（不产出音符）。
**实测**（全语料）：`voice=1` 1651738、`2` 7936、`3` 338、`5` 56、`7` 4；`0/4/6/8` 未出现。
**判据**：引擎按 9 个声部分别 `UpdatePlayTime/UpdateStartTime`（§7.3），语义直接对应。
**阶段**：step1。

### B2. 音符的上下谱表归属（R）
**结论**：单谱表文件 → `<staff>1`；多谱表按 `flags bit9 (0x0200)` = 上组、
`bit10 (0x0400)` = 下组；两位都不置时按 `dy` 的符号（负值向上）。
**实测**：全语料只有 **19 / 8451** 个文件含 `staff2`；
bit9 单独出现 1 次、bit10 出现 63 次 → **"单谱表 + 靠 Y 偏移定位"是常态**。
**失败模式**：双手交叉（左手音高于右手）时 Y 启发式会错 —— 此时应改按 `staffRef` 判断。
**阶段**：step1。

### B3. Staff → `<part>`（R）
**结论**：**每个 Staff 一个 `<part>`**，除非 B4 判定为双行谱。
**判据**：`CSMStaff` 自带 `n_meas` + 小节数组，本身就是 part 级结构。
**阶段**：step1。

### B4. part 合并（P：`part_merge`）
**问题**：钢琴/双行谱要不要合成一个 `<part>`（含 `<staves>2</staves>`）？
**结论**：`part_merge = auto`（**默认**）—— 按数据判断：
**同一个 Block 的 `staffRef` 里出现多个 Staff** → 合成一个 part；否则一个 Staff 一个 part。
可选 `none`（强制不合并）、`all`（强制全合并）。
**判据**：Block = 排版行，其 `staffRef[nStaves]` 就是"这一行里有哪些谱表"（`docs/layout.md` §6）；
全语料 `(nStaves,f2)=(2,4)` 共 46 例 → 双行谱存在但罕见。
**失败模式**：`auto` 依赖 Block 结构，而 Block 属版式信息（§F1）——故 step1 必须**读** Block，
即使它的窗口信息被丢弃。
**阶段**：step1（判定）+ step2（`<staves>`）。

### B5. 文档级消息（0x3F/0x40/0x04）（X）
**结论**：进 IR 的 `doc.messages`，**不产出 MusicXML**，按 `extent` 决定是否写 `ext`。
**实测**：每文件各一次，无 head，语义未定（`docs/unknown-fields.md` B6）。
**判据**：无消费者证据，强行映射会造出错误的谱面元素。
**阶段**：step1 + step2。

---

## C. 音高、调号、变音

### C1. 音高来源（R）
**结论**：**直接用 `head+0x00`（MIDI key）**，配合 C2/C3 换算成 `<pitch><step><alter><octave>`。
**实测**：MIDI key 范围 38..89；`GetMidiKey/SetMidiKey` 直接读写 `head[0]`（§6.7）。
**失败模式**：打击乐谱表（`StaffTail+0x21` = 2/3）里 key 不是音高 —— 见 C5。
**阶段**：step1 + step2。

### C2. 变音记号（P：`accidental_policy`）
**问题**：`MsgHdr+0x05` 高 4 位低 3 位 = {0 无,1 升,2 降,3 还原,4 重升,5 重降}，
但引擎还有 `WhatIsAccidental` 的"从调号累积"逻辑（§1.4）。
**结论**：
- `explicit`（**默认**）：音符自带记号 → 写 `<accidental>`；无记号 → 写 `<alter>` 但不写 `<accidental>`。
- `transposed`：全部按调号推算，`<alter>` 由 key 决定。
**判据**：SMC 里"音符自身记号"是显式字段，引擎的累积值是运行期派生（遍历小节得到）。
**失败模式**：`explicit` 在调号与小节内临时记号冲突时可能与原排版不一致（但音高正确）。
**阶段**：step2。

### C3. 调号（R）
**结论**：`<fifths>`：`symbol == 2`（升号序 F C G D A E B）→ `+count`；
`symbol == 1`（降号序）→ `-count`；`symbol == 0` → `0`（无调号）。
`keysig_type == 2` 按普通调号处理并记 `warning`。**只在变化的小节写** `<attributes><key>`。
**实测**（全语料 8451 文件，`probe8.py`）：`keysig_type` 1 → 159112、**2 → 929**（spec 未记录，仅 20 文件）；
`symbol` 0 → 20611、1 → 38040、2 → 101390；`count` 0 → 20611 … 7 → 64；
**`symbol == 0` 与 `count == 0` 严格一一对应**（20611/20611）。
**判据**：`symbol=0/count=0` 严格同步 → "无调号"由 `symbol=0` 表达；
`type=2` 在同一文件内切换而不改内容（`201OPS-0019.smc`：前 16 小节 2、后 8 小节 1，全程 count=0）。
**失败模式**：spec 说 `type == 8` = 无调号，但全语料无 8，该分支无需处理。
**阶段**：step1 + step2。

### C4. 谱号（R，已知缺口）
**结论**：优先用 `type 0x1F` 消息的 `type_index`；缺省从 `StaffTail+0x21` 推。
**实测**：`type 0x1F` 全语料仅 **13 条** → 不足以承担谱号来源；
`StaffTail+0x21` 取值 1 为常规五线谱，2/3 = 打击乐/特殊（`docs/layout.md` §3）。
**已知缺口**：`+0x21` 的完整枚举未知 [?]（入口 `DrawMeasClef`；
`docs/unknown-fields.md` A 表"Staff +0x4D 谱号类别"）。
**处理**：IR 标 `uncertain=true` 并保留原始字节；产物按 `+0x21` 的已知值给默认谱号。
**阶段**：step1 + step2。

### C5. 打击乐（R，低优先）
**结论**：`StaffTail+0x21` 为 2/3 时产出 `<unpitched>` + `<instrument>`，原始编号进 `ext`。
**实测**：语料中此类谱表极少，实现可延后。
**阶段**：step2。

---

## D. 歌词

### D1. 歌词的单位（R）
**结论**：**一条 `0x19` = 一个 `<lyric>` 文本单元**（MusicXML 的 `<text>`）。
**实测**（全语料 625967 条）：`chars=1` **619562 条（99.0%）**，其余 6405 条为 2–29 字符；
`headLen = 0x10 + 字节长度`（bytelen=2 占 619686）。
**失败模式**：多字符记录（1%）需按空格/标点再切分 —— D3 处理。
**阶段**：step1。

### D2. 歌词与音符的绑定（R）
**结论**：**按对象包含关系绑定**（不用 key 差）；每个音符最多 1 条歌词。
**实测**：`docs/lyrics.md` §6.1：2961/2961 歌词的父对象都是 type 0x01 音符；
500KFS-0041 的 key 差为 +1（271）/+2（33），17 个音符无歌词。
**判据**：包含关系是引擎自己的关联方式；key 差只是分配器习惯（§6.2 明确"不是查找依据"）。
**阶段**：step1。

### D3. 歌词分段/换行（P：`lyric_line_policy` + `lyric_gap_threshold`）
**问题**：歌词记录**不含换行**，分段规则未解。
**实测**：`docs/lyrics.md` §6.4 + `unknown-fields.md` C1：分段由所依附音符所在小节/行决定。
**结论**：
- `by-measure-gap`（**默认**）：相邻歌词间隔 ≥ `lyric_gap_threshold` 个 tick（默认 **480** = 2 个 quarter）
  或跨小节且该小节是行首 → 新段。
- `none`：不切段，全部作为一行。
**判据**：无确定规则，只能启发式；阈值必须可配置。
**失败模式**：**这是本转换器最大的语义缺口**，直接影响歌词换行位置。
IR 保留原始顺序 + 所在小节 + 目标 tick，便于换策略重跑。
**阶段**：step1（保留全部原始信息）+ step2（启发式）。

### D4. 音节连字符与延长（P：`hyphen_policy`）
**实测**：`－`（U+FF0D，来自 889F 码位 `F0 41`）大量出现，语义为"分句/延长标记"（`docs/encoding.md` §6）。
**结论**：
- `literal`（**默认**）：把 `－` 原样写进 `<text>`。
- `syllabic`：`－` 映射为 `syllabic="begin"/"middle"/"end"`，文本里去掉它。
**判据**：MusicXML 的 `<syllabic>` 正是为歌词音节连读设计的。
**失败模式**：`syllabic` 对"延音线式 `－`"（真正的延长而非音节连接）会误判。
**阶段**：step2。

### D5. 歌词字体/字号/颜色（X）
**实测**：字号 {13: 30136, 14: 140, 12: 74}，字体索引 {1,2,3,5,6,7}，样式 {0,1}，颜色恒 0x000000。
**结论**：默认进 `ext`，由 `extent` 决定；不产出 `<print>` 级样式。
**判据**：MusicXML 的歌词字体是文档级 `<defaults><lyric-font>`，逐条样式不标准。
**阶段**：step2。

---

## E. 和声与其他记号

### E1. 和弦记号（0x45）（R）
**结论**：`<harmony><kind>` 用 `surfix.name` 映射；未识别的走 `<kind text="...">`；
原始后缀与 `info` 字节按 `extent` 写 `ext`。根音 = 所依附音符的音高。
**实测**（全语料）：177909 条，`surfix.name` 500KFS-0041 上为 `{m:78, ' (major)':12, '7':1}`；
`headLen ∈ {0: 110088, 100: 67821}`（100 = 含 `Ptr32` 的无语义运行期结构，§6.9，须原样保留）；
**父对象：音符 164919、小节 8059、休止符 4931** → 和声记号**可挂小节**（占 4.5%）。
**失败模式**：`<kind>` 枚举有限，未识别后缀必须走自由文本形式。
**阶段**：step1 + step2。

### E2. 和弦记号的根音（X，缺口）
**实测**：`ChordSurfix` 只有 `name` + `n` + `info[n]`；**根音不在其中** [?]。
**结论**：默认用**所依附音符的音高**当根音，`info` 字节进 `ext`；
挂在小节上的 8059 条无依附音符 → `<harmony>` 放小节起始，`ext.unanchored = true`。
**判据**：和弦记号 92.7% 挂在音符上，符头即根音 —— 符合吉他/键盘记谱惯例。
**失败模式**：若 `info` 里另有根音信息则音名会错。**已记为待验证项**。
**阶段**：step1 + step2。

### E3. 指板图（0x46）（R）
**结论**：默认只写 `ext:fretboard`；不产出 `<frame>`。
**实测**：与 `0x45` 一一对应；`FretInfo` = 基准品位 + 6 弦品位 + 4 组 (起始,结束)；
后者语义未解（`unknown-fields.md` B5）→ 映射必然不完整。
**阶段**：step2。

### E4. 力度记号（0x1B）（R + 数据表）
**结论**：IR 存**原始码**；`dynamic_map` 是**外部数据文件**（不是行为开关），内置默认表。
**实测**：`MsgHdr+0x08` = 力度码；`CodeDyn` = `00 F0 F1 F2 F3 F4 F5 F6 F7 F9 FA FB FC FD FE FF`
（16 项，索引 0 = 空；`font-resources.md` §4.2）。
**失败模式**：**码到 f/p/mf 的对应是推断**（`font-resources.md` §6 明确"逐项语义未逐一确认"），
故映射表必须可替换；未映射的码走 `<dynamics><other-dynamics>`。
**阶段**：step1（原始码）+ step2（查表）。

### E5. 其他记号（R + X）
**实测**（全语料）：`0x09 tie` 26295、`0x0A slur` 62202、`0x2E slur.indep` 264、
`0x12 tuplet.meas` 1786、`0x10 pedal` 1、`0x21 trill` 4、`0x0D rolled` 111、
`0x13 cresc` 93、`0x2F breath` 8、`0x30 grace` 9、`0x0C coda` 165、`0x2C longrest` 98。
**结论**：
- **tie/slur/连音符**：按端点键解析成显式 `span`。**端点是 `ObjectCore.f8`（对象 `+0x18`）
  与 `MsgHdr+0x20`（对象 `+0x70`）**。全语料 90547 条引用中 **346 条（0.38%）** 无法解析，
  原因已分类（`probe10.py`）：264 条端点键为负值/高位、75 条端点键超出小节键表、7 条两端点均为 0。
  这三类都是 spec 记载的"越界键被清零"行为，不是转换缺陷 → 跳过 + `warning`，不猜测端点。
- **其余低频项**：默认进 `ext`（`extent` 控制），不阻塞主流程。
**判据**：端点键是显式字段且解析率 99.91%，是最可靠的跨对象引用。
**失败模式**：跨 Staff 的 tie（本语料未出现）需要跨 Staff key 表。
**阶段**：step1（统一成 `span`）+ step2（映射）。

### E6. 图形对象（直线/矩形/椭圆/贝塞尔/文本框）（X）
**实测**（全语料）：`0x18 line` 10429、`0x27 rect` 14、`0x26 ellipse` 3、`0x44 curve` 1；
`0x06 text` 6853（TLV head）。
**结论**：全部进 `ext`。文本框**可选**映射为 `<direction><words>`，但 TLV 的对齐/字体标签映射有损 →
默认只写 `ext`。
**判据**：这些是版式而非音乐；MusicXML 无等价物。
**阶段**：step2。

---

## F. 版式与分页

> **总原则（用户确认）**：**默认丢弃全部 layout**。
> 版式是不同软件间互不兼容的产物，应由 MusicXML 消费者（MuseScore 等）自行完成。

### F1. 翻页 / 换行（X，**默认全丢**）
**问题**：SMC 有 Page（全语料 9429 页）+ Block（排版行，含绝对 `measX` 坐标）。
**结论**：**默认不产出任何 `<print>` 元素**。
**理由**（三条，任一条都足够）：
1. **坐标系不同**：SMC 的 `measX`/`dx`/`dy` 是引擎按自己的页面尺寸与字号算出的**绝对像素**；
   MusicXML 的 `<offset>` 是相对谱表的 1/10 空格。两者只能"看起来像"，换页尺寸即不成立。
2. **`<print>` 只是建议**：MuseScore 默认忽略导入文件的换行信息，按自己的页面重排。
   强行写对换行点，产物在不同软件里仍长得不同 —— 这比不写更糟，因为它让"正确性"无法验证。
3. **会破坏结构**：若目标页面更窄，写死的换行点会强迫产物在音乐上不合理的位置断行
   （例如 12/8 小节中间）。
**IR 侧**：`layout` 子树**保留**，但地位是**来源记录**而非产物指令，且**默认不写入 IR 输出**
（`extent=debug` 时才写）。用途：人工核对"原谱这一行在哪"。
**`measX` 永不**映射为小节宽度。
**唯一的例外**：Block 的 `staffRef` **必须读**，因为 B4 的 `part_merge` 判定依赖它
（"这一行里有几个谱表"是音乐分组信息，不是像素信息）。
**阶段**：step1（读、用于 B4）+ step2（不输出）。

### F2. 坐标与尺寸（X，默认丢弃）
**实测**：`MsgHdr+0x16`(dx)、`+0x18`(dy) 是相对排版坐标；
`+0x0C/+0x0E/+0x10/+0x12` 是纯绘制缓存（无语义，`field-coverage.md` §3）。
**结论**：全部进 `ext`（`extent=debug` 才写），**不参与 MusicXML 布局**。
**`dx`/`dy` 不是** `<offset>` 的来源。

### F3. 记号上下位置的判定（R，唯一的坐标用途）
**结论**：**只取 `dy` 的符号**（负值向上）判定 `<direction placement="above|below">`，
**不取数值**。
**判据**：`docs/layout.md` §7：`MulDiv(+0x52, zoom, 100)`，负值向上 —— 符号携带音乐意义（记谱惯例），
数值是排版结果。
**失败模式**：`dy` 是排版后的值，可能被引擎微调过。

### F4. 缩放（X）
**实测**：`MsgHdr+0x02` = 缩放百分比，默认 `0x10`=16（`SelectFont((v*100)>>4)`）。
**结论**：默认丢弃（`ext`）。这是"显示缩放"，非音乐信息。

### F5. 颜色（X）
**实测**：`MsgHdr+0x28` 为颜色/样式；歌词 head+0x08 颜色恒 0x000000。
**结论**：进 `ext`。

---

## G. 产物级（step2）

### G1. `<divisions>`（R）
**结论**：**`divisions = whole_tick = 240`** → 1 tick = 1 个 `divisions` 单位，`<duration>` 零换算。
**判据**：`whole_tick` 是四分音符的 tick 数（A1），故 `divisions = whole_tick` 时
"一个 divisions = 一个 tick"，粒度 15 亦整除 → 无舍入。
**失败模式**：若 `whole_tick != 240`，仍取 `divisions = whole_tick`（同一规则）。

### G2. `<key>`/`<time>`/`<clef>` 书写时机（R）
**结论**：只在**变化处**写；文件首小节强制全写。
**判据**：MusicXML 的 `<attributes>` 是"状态变更"语义。

### G3. 拍号写法（R，覆盖项）
**结论**：默认 `symbolic` —— 照写 `<beats>/<beat-type>`。
`MeasTail+0x00 == 3` 时（"拍号用文本描述"，16 字节文本在 `+0x13`）另存 `ext.time_text`。
**实测**：常见 4/4 82448、6/8 30356、3/4 16077、12/8 12048、9/8 4433、2/4 7952…；
**异常**：`41/16`（1 例）、`63/16`（1 例），都在 500KFS-0117 相邻小节，
且这两小节 `durSum == ptSum`（3720/3780、2400/2460）→ **内容自洽，只是拍号不常规**。
**判据**：这两例是真实存在的异常值且内容自洽，静默改写会破坏可追溯性 →
保持照写，并在 IR 记 `warning: odd-timesig`。
**阶段**：step2。

### G4. 元数据（X）
**结论**：`<work-title>` 用 SYMP 头 `+0x00A` 的曲名（889F 解码）；
`<identification>` 用附加字符串（语义未定，`unknown-fields.md` B7 → `ext`）；
`<part-name>` 用 `StaffTail+0x00` 的谱表名，为空时用 `0x49` 消息的字串。
**实测**：500KFS-0041 曲名 → `바다의 노래`；谱表名多为空。

---

## H. 参数总表（全部 6 个）

| 参数 | 取值 | 默认 | 为什么会存在 |
|---|---|---|---|
| `extent` | `musical` / `score+ext` / `debug` | `score+ext` | 用户对"产物纯净度"的偏好 |
| `accidental_policy` | `explicit` / `transposed` | `explicit` | 两种都合法且解释不同（C2） |
| `lyric_line_policy` | `by-measure-gap` / `none` | `by-measure-gap` | 换行规则 spec 未解（D3） |
| `lyric_gap_threshold` | int（tick） | `480` | 上一条的阈值 |
| `hyphen_policy` | `literal` / `syllabic` | `literal` | `－` 语义有歧义（D4） |
| `part_merge` | `auto` / `none` / `all` | `auto` | 双行谱分组（B4） |

**数据文件（非行为开关）**：`dynamic_map`（E4），默认内置。

### `extent` 语义

| 值 | 含义 |
|---|---|
| `musical` | 只输出能被 MuseScore 正确重绘的音乐内容；丢弃全部版式、未知字段、字体/颜色 |
| `score+ext` | 音乐内容 + 非音乐信息放 `<ext:...>` 命名空间（**默认**） |
| `debug` | 额外输出 IR 行号、原始字节 hex、`src` 坐标、`layout` 子树 |

**另有两个显式覆盖开关**（不在默认清单，仅在需要时使用）：
`--timesig-clamp`（处理 41/16、63/16 这类异常，G3）、
`--emit-layout`（从 `layout` 子树派生 `<print new-system/new-page>`，F1）。

---

## I. 已降级为常量 / 已删除的参数（追溯）

| 原参数 | 处置 | 理由 |
|---|---|---|
| `duration_source` | 常量 `playtime` | A2：duration 是缓存，实测会失真 |
| `gap_policy` | 常量 `fill-rest` | A4：`strict` 产出非法 XML，`force` 丢音符 |
| `overflow_policy` | 常量 `split-tie` | A6：不拆就不合法 |
| `grid_snap` | 常量 `nearest` | A9：MusicXML 位置隐含于累加 |
| `staff_policy` | 常量（数据驱动） | B2：按 flags/dy 判定，无偏好空间 |
| `clef_policy` | 常量（msg 优先 → tail 回落） | C4：0x1F 仅 13 条，不构成另一条路径 |
| `key_policy` | 常量 `per-change` | G2：MusicXML 惯例 |
| `divisions` | 常量 `= whole_tick = 240` | G1：唯一无损值 |
| `measure_mode` | 常量 `strict-ts` | A4+G3：按拍号算小节长度 |
| `span_policy` | 常量 `resolve-keys` | E5：解析率 99.91% |
| `harmony_policy` | 常量 `both` | E1：同时写 `<kind>` 与 ext 无害 |
| `fret_policy` | 常量 `ext` | E3：映射必然不完整 |
| `symbol_policy` | **删除**，并入 `extent` | 本质是同一个问题（见 §H） |
| `time` 相关 | 常量 `symbolic` + 覆盖开关 | G3 |
| `page_policy` | **删除** | F1：默认全丢；`--emit-layout` 替代 |
| `grace_strategy` | **删除** | A7：装饰音不占时值，`start` 只作 ext 参考 |
| `dynamic_map` | 降级为数据文件 | E4：是查表数据，不是行为开关 |
