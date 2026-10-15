# 决定记录（SMC → IR → MusicXML）

> 每条 = 「问题 → 实测/证据 → 决定 → 影响」。证据都在 `out_*.txt` 或可用 `probe*.py` 复现。
> 基线与复现见 `README.md`。

## 0. 实验数据汇总

**基本实验文件 500KFS-0041**（`probe_smc.py summary`）：

| 项 | 值 |
|---|---|
| 版本 | 0x2004 |
| wholeTick | 240 |
| 谱表 | staff1=1, staff2=0 |
| 小节 | 109 |
| 页 | 3（Block 7+8+7） |
| Msg | note 450 / lyric 375 / chord.sym 91 / slur 64 / beam 56 / line 15 / tie 13 / dynamic 10 / mark 7 / rest 5 / text 4 |
| 声部 | 全部 voice=1 |
| 拍号 | 6/8 × 77、4/4 × 32 |
| 调号 | `(type=1, symbol=0, count=0)` × 109 |
| 正文消耗 | 0x1a440 / 0x1a440，尾部 4 字节 |
| 连梁组 | 56 |
| 和弦记号 | 91（`m` 78、` (major)` 12、`7` 1） |

**语料普查：全量 8451 文件**（`probe5.py --dir 8000Songs --max 0`，`out_census_all.txt`）：

| 项 | 值 |
|---|---|
| 解析失败 | **0** |
| 版本 | 2.0.4 × 6930、2.0.5 × 1521 |
| wholeTick | **240 × 8451** |
| 谱表 | 8482（`staff2` 出现在 19 个文件） |
| 小节 | 160041 |
| 页 | 9429 |
| 音符 | 652338 |
| 歌词 | 625967 |
| 连梁 | 54238 |
| 圆滑线 | 62202 |
| tie | 26295 |
| 和弦记号 | 177909（`headLen`：0 → 110088、100 → 67821） |
| 和弦(0x25) | 433 |
| 力度 | 17132 |
| 文本 | 6853 |
| 端点无法解析 | 82 / 92368 条引用（0.09%） |
| 声部 | 1 → 1651738、2 → 7936、3 → 338、5 → 56、7 → 4 |
| 拍号 | 4/4 82448、6/8 30356、3/4 16077、12/8 12048、9/8 4433、2/4 7952…另有 41/16、63/16 各 1 |
| 调号 type | 1 → 159112、**2 → 929**（spec 未记录） |
| 调号 symbol | 0 → 20611、1 → 38040、2 → 101390 |
| 调号 count | 0 → 20611、1 → 51266、…、7 → 64 |
| 歌词 char 数 | 1 → 619562、2 → 976、3 → 5012、4 → 183… |
| 音符 flags | `0x0000` 472352 为最多；bit4(装饰) 出现在 341+172+… 条 |
| 小节时值不符 | sum > tpm 1243、sum < tpm 1746（共 2989 / 160041，1.9%） |

---

## 1. 时值单位与权威来源

**问题**：IR 用 tick 还是符号时值？`head+4 duration` 还是 `CalcPlayTime`？

**实测**：
- `wholeTick = 240`（**8451/8451**），quarter = 60 tick，最小粒度 15（`probe3.py`）。
- 500KFS-0041 的 450 个音符：`duration == playTime` **420**、`duration == playTime/2` **28**、其他 2。
- 28 条"减半"全部是 **`flags & 0x10`（装饰音）** 且都挂在 `0x14` 连梁组下
  （如 m3 的 30-tick、m11 的 30-tick 三个音）。
- 1 条例外是 m11 key=122：`duration=2880`（= 8 × 360），`playTime=720`。
  同一小节的小节时值 `tickPerMeas=720`，且 content_end == 720（用 playTime 计算）。
  → **`duration` 在这一条上明显是脏数据**。
- 全语料：2989 / 160041 小节（1.9%）notated sum != tickPerMeas，
  其中绝大多数可用 playTime 求和的修正（按 500KFS 子集算 12/36，其余为装饰音占位与脏 duration）。

**决定**：
- IR 的权威时值 = **`playTime`（`MsgHdr+0x08` 指数 + 附点 + `f2` 比例）**。
- `head+4 duration` 一并存为 `dur_head` 仅作审计。
- IR 时间单位 = **引擎原生 tick**，`whole_tick` 为文档参数。

**理由**：playTime 是从"记谱字段"（指数、附点）算出的，而 duration 是同一份数据的缓存，
会被装饰音/连梁改写。

**影响**：`parameters.md` A1/A2；`probe3.py` 可随时回归。

---

## 2. 一小节内的对齐

**问题**：位置用 `MsgHdr+0x14`(start) 还是累加？

**实测**（`probe_smc.py summary`、`probe3.py`）：
- 500KFS-0041：**108/109** 小节的 `Σ duration == tickPerMeas` 精确成立。
- 全语料 160041 小节：**2989 小节**（1.9%）不匹配，其中多数用 playTime 求和即恢复。
- 500KFS 子集（2526 小节）的 36 例不匹配中，**12 例** playTime 求和 == tickPerMeas。
- 三类真实缺口：
  1. 装饰音占位（0041 m93 `480/tpm=960`、m103 `360/tpm=720`）——缺的正好是被装饰音"跳过"的头部。
  2. 脏 duration（0041 m11 `2880/tpm=720`）。
  3. 拍号跨界（500KFS-0117 m49/50 的 `63/16`、`41/16`）。
- `start` 在装饰音处不是网格值：m11 的 `25`、`84`；m93 的 `68`。
  相同音乐内容的小节 3 与 11 给出 `34/84` 与 `25/84` → **start 含排版量**。

**决定**：
- `on` = `start` 原值（无损）；同时算 `grid_on`（吸附）与 `grid_error`。
- step2 默认用 `grid_on`（MusicXML 位置隐含于时值累加，无法表达 25）。
- `gap_policy = fill-rest`：缺口补休止符；超出不裁（记 warning）。

**理由**：start 是唯一携带"精确位置"的字段，但被排版污染；保留两者才能既无损又可用。

**影响**：`parameters.md` A3/A4/A9；`ir-design.md` §3.2/§3.3。

---

## 3. 装饰音

**实测**：500KFS-0041 有 58 条 `flags & 0x10`；`probe2.py tree 3`：
`0x14 beam(key=37)` 下两个 30-tick 音符（`flags=0x1010 / 0x0010`），
后面紧跟 `duration=720` 的主音。`0x14` 自身 `playTime=120`（不是 720！）。
→ **`0x14` 的 playTime 与子项之和不一致**，进一步证明容器不参与时值。

**决定**：`flags & 0x10` → 装饰音（`attrs.grace=true`），
**不计入声部时值累加**，`start` 进 `ext:engrave_hint`。

**影响**：`parameters.md` A7；填满校验（§2）必须先滤掉装饰音。

---

## 4. 跨小节音符

**实测**：`probe2.py endpts`：
- tie 13 条：同小节 7、**跨小节 6**（如 m74→m75、m79→m80、m91→m92）。
- slur 64 条：**全部同小节**。
- 全语料：tie 26295、slur 62202、tuplet.meas 1786，端点未解析 82 条（0.09%）。
- 跨小节 tie 的端点严格是"下一小节的同音高音符"（`probe3b.py` m93/m94 的 key 949→954）。

**决定**：
- `spans[]` 由端点键在**同一 Staff 的全局 key 表**解析。
- 若音符 tick 长度超出小节剩余空间 → `overflow_policy = split-tie`（拆 + tie）。
- 未解析端点 → 跳过 + `warning`。

**理由**：MusicXML 的小节时值必须自洽；拆分 + tie 与 SMC 自身 tie 语义一致。

**影响**：`parameters.md` A6/E5。

### 4.1 关于"哪些是真正的跨小节音符"

**注意区分两种跨小节**：
1. **数据里的 tie/连音线**（显式 `0x09`）→ 必须还原为 `<tie>`。
2. **一个音符的 tick 越界**（时长超过小节剩余）→ 必须拆。
实测中类型 1 有 6 例；类型 2 由 `gap`/`overflow` 检查发现。

---

## 5. 声部与谱表

**实测**（全语料 8451 文件）：
- 声部：1 → 1651738、2 → 7936、3 → 338、5 → 56、7 → 4 → **单声部为主，存在多声部**。
- `staff2`：只出现在 **19 / 8451** 个文件（8482 - 8463 个 staff1）。
- `docs/layout.md` §6：Block 里 `(nStaves,f2)=(2,4)` 仅 46 例。

**决定**：
- `voice` 1..8 → `<voice>` 1..8；`0` → 文档级（不产出音符）。
- 一个 Staff → 一个 `<part>`；`part_merge=none` 为默认。
- 多谱表文件的上下归属按 `flags bit9 (0x0200)` / `bit10 (0x0400)`，缺失则按 `dy` 符号。
  （全语料中 bit9 单独出现 1 次、bit10 出现 54+5+4 次 → 这两位的使用**很少**，
   说明"单谱表 + 靠 Y 偏移定位"才是常态，`single` 策略对多数文件即可。）

**理由**：Staff 自带 `n_meas` + 小节数组，本身就是 part 级结构；
`bit9/bit10` 是引擎自己的判定字段（`docs/smc-format.md` §6.5）。

**影响**：`parameters.md` B1/B2/B3/B4。

---

## 6. 歌词

**实测**：
- 一条 0x19 = **一个音节**（全语料 619686/625967 条 bytelen=2、619562 条 chars=1）。
- 500KFS-0041：375 条歌词全部单字符，`key - note_key` 为 +1（271）/+2（33），17 个音符无歌词。
- 歌词**始终**是音符的嵌入子对象（`docs/lyrics.md` §6.1，2961/2961）。
- `－`(U+FF0D) 大量出现，来自码位 `F0 41`。
- **换行规则未解**（`unknown-fields.md` C1）。

**决定**：
- 歌词内联在音符上，按**对象包含**绑定。
- `lyric_line_policy = by-measure-gap`，阈值 `480` tick（可配置），保留全部原始信息以便重跑。
- `hyphen_policy = literal`（`－` 原样进 `<text>`）。

**理由**：绑定关系是确定的；换行是启发式的，故必须可配置且可重跑。

**影响**：`parameters.md` D1–D4。

---

## 7. 调号

**实测**（`probe8.py`，全语料 8451 文件）：
- `keysig_type`：**1 → 159112、2 → 929**（后者 spec 未记录，只出现在 20 个文件里）。
- `symbol ∈ {0,1,2}`、`count ∈ {0..7}`；
  - `symbol=1`（降号序）：count 1..5；
  - `symbol=2`（升号序）：count 1..7；
  - `symbol=0`：**count 恒为 0**（20380 + 231 例）→ `symbol=0` 就是"无记号"。
- `type=2` 的 929 例分布在 20 个文件；例 `201OPS-0019.smc` 前 16 小节 type=2、后 8 小节 type=1，
  全程 `count=0` → **`type` 是"调号子系统/来源"标志，不是音乐内容**（很可能是导入源差异或谱表级设置）。
- 语料里 **`type 0x15` 消息 0 条** → 调号只能取自 Meas 尾块。
- spec 只记载 `meas+0x7C == 8` 为"无调号"，但全语料**没有 type=8**（`type=1/2` 之外无其他值）。

**决定**：
- `<fifths>` 由 `symbol`/`count` 推：`symbol == 2`（升号 F C G D A E B）→ `+count`；
  `symbol == 1` → `-count`；`symbol == 0` → `0`。
- 只在变化的小节写 `<attributes><key>`。
- `keysig_type == 2` **按普通调号处理**（因为它带 `symbol`/`count`），
  同时在 IR 记 `key.source_type = 2` 并产生 `warning: keysig-type-2`。
- 若将来确认 `type == 8` 语义，按 `-count`/0 处理（spec 现有描述）。

**理由**：`symbol=0` 与 `count=0` 严格同步出现，说明"无调号"由 `symbol=0` 表达；
`type` 的值与音乐内容无关（同一文件内切换而内容不变）。

**待办**：`keysig_type=2` 的确切语义（20 文件、929 小节）已验证为"非音乐标志"，
但需确认它是否影响谱面绘制（入口：`DrawMeasKey` 0x10055910）。

---

## 8. 拍号

**实测**：
- 常见：6/8、12/8、9/8、3/4、4/4、2/4、5/8、18/8、10/8、5/4、6/4、8/8。
- **异常**：`41/16`（1 例）、`63/16`（1 例），都在 500KFS-0117 相邻小节。
  这两小节的 `durSum == ptSum`（3720/3780、2400/2460）→ **内容自洽，只是拍号不常规**。
- `MeasTail+0x00 == 3` → "拍号用文本描述"（16 字节文本在 `+0x13`）。

**决定**：
- `timesig_policy = symbolic` 默认：照写 `beats/beat-type`。
- 提供 `text` 与 `clamp`；`clamp` 会改变小节数，必须显式记录。
- 分子分母为 0 → 强制 4/4（spec 已规定，§7.3）。

**理由**：41/16、63/16 是真实存在的异常值，且内容自洽，静默改写会破坏可追溯性。

**影响**：`parameters.md` G3。

---

## 9. 和弦记号与指板

**实测**（500KFS-0041 `probe_smc.py chords`，全语料 `probe7.py`）：
- 500KFS-0041：91 条 `0x45`，`surfix.name` = `m` 78、` (major)` 12、`7` 1；
- 全语料：177909 条 `0x45`，`headLen ∈ {0: 110088, 100: 67821}`（**100 的占 38%**，含 `Ptr32` 的无语义运行期结构，须原样保留）；
- `0x45` 与 `0x46` 一一对应；500KFS-0041 有 7 种指板变体（`base=0`，弦值含 `0xFE` 空弦标记）；
- **父对象分布：音符 164919、小节 8059、休止符 4931** → 和声记号**可以挂在小节上**（占 4.5%）；
- 全语料小节内 key 无重复（`duplicate keys = 0`）→ 端点键解析可靠。

**决定**：
- `<harmony>` 用 `surfix.name` 映射 `<kind>`，未识别的走 `<kind text="...">`；
  同时把原始后缀与 `info` 字节写 `ext`。
- 根音默认取**依附音符的音高**（并记 `attached_note_key`）；
  挂在小节上的 54 条（无依附音符）→ `<harmony>` 放到小节起始，`ext.unanchored=true`。
- 指板默认只写 `ext:fretboard`。

**理由**：`surfix.name` 是"可读后缀"（与 MusicXML `<kind>` 概念对口），但**根音不在结构里**，
只能靠"挂在哪个音符上"来推。`info` 字节语义未解，必须保留。

**验证方式**：拿 500KFS-0041 的 91 条和弦与谱面人工对照（`m` 78 条应与小调音级一致）。

**影响**：`parameters.md` E1/E2/E3。

---

## 10. 力度记号

**实测**：`MsgHdr+0x08` = 力度码；`CodeDyn[码]` 表 =
`00 F0 F1 F2 F3 F4 F5 F6 F7 F9 FA FB FC FD FE FF`（16 项，索引 0 = 空）。
500KFS-0041 的 10 条力度记号 `dyncode=5`。

**决定**：
- IR 存**原始码**；`dynamic_map` 是外部可替换的映射表（默认内置猜测表）。
- 未映射的码 → `<dynamics><other-dynamics>` 或 `ext`。

**理由**：`docs/font-resources.md` §6 明确"逐项语义未逐一确认"，
`CodeDyn` 的字节是符号字体码位（`0xF0`–`0xFF` → `U+F0xx`），
**码到 f/p/mf 的对应是推断**，必须可替换。

**影响**：`parameters.md` E4。

---

## 11. 谱号（已知缺口）

**实测**：`type 0x1F` 在语料中仅 13 条，多数谱号由小节级 `DrawMeasClef` 与 `StaffTail+0x21` 承担；
`+0x21` 取值 2/3 = 打击乐/特殊（`docs/layout.md` §3）。

**决定**：
- `clef_policy = staff-tail`：从 `+0x21` 推 `<clef>`；取值枚举未知 → 
  **IR 标 `uncertain=true`**，并保留原始字节。
- 0x1F 消息存在时优先用它（`type_index` 是谱号类型码）。

**这是本次转换的已知短板**：`+0x21` 的完整枚举需要新的调查
（入口：`DrawMeasClef`，`docs/unknown-fields.md` A 表 "Staff +0x4D 谱号类别"）。

**影响**：`parameters.md` C4；`unknown-fields` 侧建议新增 P1 项。

---

## 12. 版式 / 分页（"翻页"）

**问题**：SMC 有 Page(3 页) + Block(22 个排版行，含 `measX` 绝对坐标)。

**决定**：
- 全部进 IR 的 `layout` 子树。
- `page_policy = ignore`（默认）：**不产出任何 MusicXML 元素**。
- 提供 `system-breaks`：Block 边界 → `<print new-system>` / `new-page`。
- `measX`（绝对像素）**永不**映射为小节宽度：不可移植。

**理由**：
- Block 是"已排版的行"；X 坐标是排版结果，任何目标渲染器都会重排。
- MusicXML 里"行/页"是给渲染器的提示（`<print>`），不是音乐内容。
- 因此**"翻页"在 IR 里存在（可追溯原始版式），但在产物里默认不存在**。

**影响**：`parameters.md` F1/F2。

---

## 13. 无语义字节的处理

**实测**（`docs/field-coverage.md` §3）：已确认无语义的字节
（ObjectCore `+0x01`、ObjectCore `+0x06`、歌词 head 6 残字节、MsgHdr 绘制缓存 10 字节、
MeasCore 3 字节、`type 0x45` headLen 100）。

**决定**：
- **不进 IR 主结构**（它们对产物无贡献）。
- 若需重建 SMC（round-trip），从**原始文件字节**取，而不是从 IR 重建。
- IR 只记录 `ext.object_reserved_byte` 级别的必要项（ObjectCore `+0x01` 的分布是 46% 为 0）。

**理由**：IR 是"音乐事实"，不是"文件镜像"。若要 round-trip，应保留原文件而非扩展 IR。

---

## 14. 对 spec 的依赖与偏离

| 依赖 | 出处 | 状态 |
|---|---|---|
| 帧结构、主体消耗 | `docs/smc-format.md` §3/§4 | 实现并验证（**8451 文件 0 失败**） |
| MsgHdr 字段 | §6.1 | 全部按表实现 |
| 音符 head | §6.7 | 按表实现，`head[2]=0x40` 验证 14866/14866 |
| 歌词 head | §6.10 | 按表实现 |
| Meas 尾块拍号/调号 | §7.3 | 按表实现（`keysig_type` 恒 1） |
| Block/Page | §7.4/§7.5 | 按表实现 |
| 889F 解码 | §8 | 复用 `tools/smc_text.py` 的算法 |
| RtmData / FretInfo | §6.8/§6.9 | 结构级实现，事件体未解析（进 `ext`） |

| 偏离/补充 | 说明 |
|---|---|
| 调号 `count=0` 时忽略 `symbol` | spec 未明确，实测 587 例需要此规则 |
| `wholeTick=240` 是语料常量 | spec 未说明是否恒定，全语料 8451/8451 一致 → IR 仍按参数处理 |
| 填满校验 | spec 未定义"小节内容是否应等于 tickPerMeas"，本转换器引入该不变式（36/2526 违反） |
| `0x14` 的 playTime 与子项之和不等 | 实测发现（m3 的 `120` vs 720），spec 只说"= 各子消息之和" |
| 歌词换行 | spec 未解 → 本转换器用启发式，必须可配置 |

---

## 15. 待验证项（阻塞精度，不阻塞实现）

| # | 问题 | 影响 | 验证入口 |
|---|---|---|---|
| 1 | `StaffTail+0x21` 谱号类别枚举 | `<clef>` 的具体谱号 | `DrawMeasClef`；`layout.md` §8.1 |
| 2 | `CodeDyn` 码 → f/p/mf | 力度记号文本 | `KAYAKUMA.TTF` 的 `post` 表；`DrawDynamic` |
| 3 | 和弦记号的根音来源 | `<harmony><root>` 是否正确 | `info` 字节语义；`CChordSurfix` 调用点 |
| 4 | `MeasTail+0x44..+0x52` | 可能是拍号文本/其他记号 | `CSMMeas::Write` 0x100793E0 |
| 5 | 歌词换行规则 | 歌词分段 | `CSMDoc::GetRealRectOfLyrics` 0x10003D40 |
| 6 | `0x12` 小节级连音符时值 | `<tuplet>` 的 actual/normal | `CalcWholeCount` 的分段表（对象 `+0xEC`） |
| 7 | 文档级 0x3F/0x40/0x04 | 是否含页眉/页脚文本 | 动态观察 |
| 8 | `type 0x2C` head 60 字节 | 长休止的排版 | `DrawLongrest` |
