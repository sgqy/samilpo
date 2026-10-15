# IR 规格 v1（NDJSON）

> 设计目标只有一个：**IR 的每个字段都能一对一地映射到 MusicXML 元素或属性**，
> 或者被明确指出"对 MusicXML 无贡献"（走 `ext`）。
> 取舍清单见 `parameters.md`；实测依据见 `decisions.md`。

## 0. 设计原则

1. **IR 是"音乐事实"的集合，不是"排版结果"的集合。**
   MusicXML 是描述性格式（音符 + 属性变更 + 记号），因此凡是"已排版"的量
   （绝对 X/Y 坐标、分页、行划分）一律**默认丢弃**，只在 `extent=debug` 时保留为来源记录。
   理由见 `parameters.md` §F1（坐标系不同、`<print>` 只是建议、会破坏结构）。
2. **时值以引擎 tick 为唯一原子单位**，不预先符号化。
   `divisions = whole_tick` → 一个 tick 就是一个 `divisions` 单位，`<duration>` 零换算。
3. **一切跨对象引用（tie/slur）在 step1 解析成显式 `span`**，step2 不需要再查 key。
4. **排序稳定**：同一小节同一声部的音符按 `on` 排序；同 `on` 按原始出现顺序。
   这样 IR 的 diff 是稳定的（便于回归）。
5. **每个实体带 `src`**：指向 SMC 里的来源（`staff/meas/key`），便于从 MusicXML 反查原文件。
6. **一行一记录**：NDJSON。删掉任意一行，文件仍合法，只是少了那个事件。

## 1. 为什么是 NDJSON

| 需求 | 依据 | NDJSON |
|---|---|---|
| 行内可 diff | 转换器要反复迭代 | 一行 = 一个小节，`git diff` 精确到小节 |
| 流式处理 | 全语料 160041 小节 | 逐行读，不必整树载入 |
| 追加式写出 | 按 SMC 顺序遍历即可写出 | 天然支持 |
| 标准库零依赖 | Python 3.15 | `json` 直接可用 |
| 部分损坏可定位 | 调试 | 行号即记录号 |

被否决的候选：单个大 JSON（diff 全变、必须整树载入）、YAML（需第三方库、缩进敏感、隐式类型）、
TOML（不适合重复记录数组）、S 表达式（无标准解析器）、XML（等同直接输出 MusicXML）。

**已知代价**：NDJSON 不能表达注释。用 `{"kind":"#"}` 记录代替，step2 忽略。

## 2. 记录类型总览

文档顺序 = MusicXML 的 `<partwise>` 文档顺序，让 step2 退化为"加标签 + 处理 backup/forward"。

```
{"kind":"score",    ...}    # 第 1 行：元数据、参数快照、durations/gap 审计汇总
{"kind":"#", ...}           # 可选注释
{"kind":"part",     ...}    # 每个 part 一次
{"kind":"measure",  ...}    # 一小节一条
{"kind":"note",     ...}    # 该小节的事件（紧跟其 measure 记录）
{"kind":"span",     ...}
{"kind":"direction",...}
{"kind":"harmony",  ...}
{"kind":"warning",  ...}    # 可出现在任意位置之后
```

**排序规则**：`part` 之后是该 part 的所有 `measure`；每个 `measure` 之后紧跟它的全部事件记录；
事件内部按 `(voice, on, 出现序号)` 排序。`warning` 可出现在任意位置。

## 3. `score` 记录

```jsonc
{
  "ir": "smc-ir", "v": 1, "kind": "score",
  "generator": { "name": "smc2ir", "version": "0.1.0" },
  "source": { "path": "500KFS-0041.smc", "sha256": "…", "smc_version": 8200 },
  "title": "바다의 노래", "title_raw_hex": "8cc48a7d96a72089cf8bb5",
  "extra_string": "448",
  "whole_tick": 240,          // 四分音符的 tick 数（不是全音符！见 parameters.md A1）
  "divisions": 240,           // = whole_tick → 1 tick = 1 divisions 单位
  "n_parts": 1,
  "options": { "extent": "score+ext", "accidental_policy": "explicit", … },
  "audit": {
    "measures": 109,
    "measures_not_filled": 3,
    "notes_duration_mismatch": 29,     // dur_head != playTime 的条数
    "spans_unresolved": 0,
    "keysig_type_2": 0
  }
}
```

## 4. `part` / `measure` 记录

```jsonc
{ "kind": "part", "id": "P1", "name": "Melody", "n_staves": 1, "src_staff": 0 }
```

```jsonc
{
  "kind": "measure", "part": "P1", "n": 1,        // n 从 1 开始（MusicXML 惯例）
  "tpm": 720,                                     // tick_per_meas = whole_tick*num*4/den
  "time": [6, 8], "time_text": null,              // MeasTail +0x00 == 3 时为文本
  "key": [0, 0],                                  // [fifths, keysig_type]
  "clef": { "sign": "G", "line": 2, "uncertain": false, "raw": 1 },
  "changed": { "time": true, "key": false, "clef": false },
  "gap": { "1": 0 },                              // 每声部 tickPerMeas - content_end（审计）
  "content_end": { "1": 720 },
  "warnings": ["odd-timesig"]                     // 可空
}
```

- `changed` 表示该属性与本 part 上一小节相比是否变化；**文件首小节强制全 `true`**。
- `gap` 正值 = 缺 tick（step2 补休止符），负值 = 超 tick。
- `clef.uncertain` 标记 `StaffTail+0x21` 枚举未知导致的推断（`parameters.md` C4）。

## 5. `note` 记录

```jsonc
{
  "kind": "note", "part": "P1", "meas": 1,
  "src": { "key": 4, "staff": 0, "meas_idx": 0 },   // meas_idx 是 SMC 侧索引（0 起），用于回溯
  "voice": 1, "staff": 1,
  "on": 0, "grid": 0, "grid_err": 0,                // 原始 / 吸附 / 差
  "dur": 120, "dur_head": 120,                      // 权威值与 head+4 原值
  "rest": false,
  "midi": null, "step": null, "alter": null, "octave": null, "accidental": null,
  "exp": 4, "dots": 0, "symbol": "eighth",          // 派生，供审计与校验
  "beam": null,                                     // "begin"/"continue"/"end"
  "chord": false,                                   // 与前一 note 同时值起始
  "attrs": { "grace": false, "head_type": 1, "stem_state": 0, "ties": ["stop","start"] },
  "lyric": { "text": "바", "syllabic": null, "font": 1, "size": 13, "style": 0, "color": 0 },
  "ext": {}                                         // extent=debug 时才填
}
```

### 5.1 音符字段的权威性

| 字段 | 权威来源 | 备注 |
|---|---|---|
| `dur` | `CalcPlayTime`（`MsgHdr+0x08` 指数 + 附点 + f2） | `parameters.md` A2 |
| `dur_head` | `head+4` | 仅审计；装饰音处会减半 |
| `on` | `MsgHdr+0x14` | 含排版量，故另存 `grid` |
| `grid` | `on` 吸附到最近的合法时值边界 | step2 默认用这个 |
| `midi` | `head+0x00` | |
| `step/alter/octave` | 由 `midi` + 调号派生 | step1 只做纯音高换算，记号策略留给 step2 |
| `accidental` | `MsgHdr+0x05` 高 4 位低 3 位 | `0` → `null`（无显式记号） |
| `symbol` | 由 `exp` 派生 | 不入产物，仅校验 `dur == playTime(exp,dots)` |

### 5.2 `symbol` / `exp` 对照（`parts.md` A1 实测）

| exp | symbol | playTime @ whole_tick=240 |
|---|---|---|
| 1 | whole | 960 |
| 2 | half | 480 |
| 3 | quarter | 240 |
| 4 | eighth | 120 |
| 5 | 16th | 60 |
| 6 | 32nd | 30 |

（`exp=0` → 1920，语料未出现。）

## 6. `span` 记录（tie / slur / 连音符）

```jsonc
{
  "kind": "span", "part": "P1",
  "k": "tie",                                       // tie | slur | tuplet | pedal | trill | cresc
  "src": { "key": 9 },
  "from": { "meas": 0, "key": 7 },                  // 端点 A
  "to":   { "meas": 0, "key": 10 },                 // 端点 B
  "resolved": true,
  "raw": { "endpoint_key": 10, "self_key": 9, "role": 1 }
}
```

- `from`/`to` 用 **IR 内的音符定位**（`meas` + `key`），不是数组下标（下标会因过滤漂移）。
- `resolved=false` 时 step2 跳过并记 warning。全语料 92368 条引用中仅 82 条（0.09%）未解析。
- tie 的两个端点音符各自的 `attrs.ties` 里会带 `start`/`stop`，与 span 互为冗余（便于单独校验）。

## 7. `direction` / `harmony` 记录

```jsonc
{ "kind": "direction", "part": "P1", "meas": 1, "on": 0, "voice": 1,
  "placement": "above",
  "d": { "type": "dynamic", "code": 5, "text": "mf" },
  "src": { "key": 3 } }
```

```jsonc
{ "kind": "harmony", "part": "P1", "meas": 1, "on": 0,
  "name": " (major)", "kind_text": "major",
  "root": { "midi": 76, "step": "E", "alter": 0, "octave": 5 },
  "anchored": true, "src": { "key": 5 },
  "ext": { "info_hex": "…", "head_len": 0 } }
```

- `placement` 由 `dy` 的**符号**决定（`parameters.md` F3），不取数值。
- `dynamic.text` 来自可替换的 `dynamic_map`；未映射时 `text=null` → step2 用 `<other-dynamics>`。

## 8. 属性变更（`<attributes>`）

属性变化表示成**小节上的状态**，不是消息：

```jsonc
"changed": { "time": true, "key": false, "clef": false },
"time": [6, 8], "key": [0, 0], "clef": { … }
```

step2 只在 `changed.*` 为真时写对应元素；文件首小节全写。
**与上一小节比较**由 step1 完成（step1 已经遍历过小节序列，比较成本为零，且能让 IR 自描述）。

## 9. `extent` 对 IR 的影响

| 记录/字段 | `musical` | `score+ext`（默认） | `debug` |
|---|---|---|---|
| `note` / `span` / `measure` 音乐字段 | ✓ | ✓ | ✓ |
| `lyric.font/size/style/color` | ✗ | ✓ | ✓ |
| `harmony.ext.info_hex` | ✗ | ✓ | ✓ |
| `src` 字段 | ✗ | ✓ | ✓ |
| `note.ext`（dx/dy/缓存字节） | ✗ | ✗ | ✓ |
| `layout` 子树（Page/Block） | ✗ | ✗ | ✓ |
| `doc.messages`（0x3F/0x40/0x04） | ✗ | ✓ | ✓ |
| 原始字节 hex 区（CtrlTool/FileInfo/SYMP 保留区） | ✗ | ✗ | ✓ |

**注**：`layout` 子树默认**不写入 IR 输出**（`parameters.md` F1）。但 step1 **必须读** Block，
因为 `part_merge=auto` 依赖 Block 的 `staffRef`。

## 10. 为什么这样就能"方便合成 MusicXML"

| MusicXML 的硬要求 | IR 的对应设计 |
|---|---|
| 每小节时值必须等于拍号时值 | `tpm` + `gap` + 固定"补休止符"策略（A4） |
| 位置由时值累加隐含 | `on` + `grid` + 溢出拆分（A6/A9） |
| `<attributes>` 是状态变更 | `measure.changed`（step1 已比较完） |
| `<backup>`/`<forward>` 处理多声部 | 每声部一条独立事件流，step2 顺序写 + `<backup>` |
| `<tie>` 必须成对 | `span` 已解析（E5） |
| `<lyric>` 挂在 `<note>` 上 | 歌词内联在音符上（D2） |
| `<beam>` 挂在 `<note>` 上且需 `begin/continue/end` | `beam` 字段由容器 + 子项序号算出（A8） |
| `<divisions>` 全局唯一 | `whole_tick` + `divisions` 在 `score` 记录（G1） |
| `<harmony><kind>` 枚举有限 | `kind_text` + 原始后缀双写（E1） |
| `<duration>` 无换算 | `divisions = whole_tick` → 直接填 tick（G1） |
