# IR 规格 v0

> 设计目标只有一个：**IR 的每个字段都能一对一地映射到 MusicXML 元素或属性**，
> 或者被明确指出"对 MusicXML 无贡献"（走 `ext`）。
> 取舍清单见 `parameters.md`；实测依据见 `decisions.md`。

## 0. 设计原则

1. **IR 是"音乐事实"的集合，不是"排版结果"的集合。**
   MusicXML 是描述性格式（音符 + 属性变更 + 记号），因此 IR 里凡是"已排版"的量
   （绝对 X/Y 坐标、分页、行划分）一律降级为 `layout` 子树或 `ext`。
2. **时值以引擎 tick 为唯一原子单位**，不预先符号化。
   符号化（quarter/eighth/tuplet）是 step2 的事，因为那取决于目标 `<divisions>`。
3. **一切跨对象引用（tie/slur）在 step1 解析成显式 `span`**，step2 不需要再查 key。
4. **排序稳定**：同一小节同一声部的音符按 `on` 排序；同 `on` 按原始出现顺序。
   这样 IR 的 diff 是稳定的（便于回归）。
5. **每个实体带 `src`**：指向 SMC 里的来源（`staff/staff_idx, meas_idx, key`），
   便于从 MusicXML 反查原文件。

## 1. 顶层结构

```jsonc
{
  "ir_version": 0,
  "generator": { "name": "smc2ir", "version": "0.1.0" },
  "options": { /* parameters.md §H 的取值快照，用于复现 */ },
  "warnings": [ { "code": "...", "message": "...", "src": {...} } ],

  "score": {
    "title":      "바다의 노래",
    "title_raw_hex": "8cc48a7d96a72089cf8bb5",
    "extra_string": "448",
    "source":     { "path": "...", "sha256": "...", "smc_version": 8196 },
    "whole_tick": 240,
    "divisions":  60,
    "parts":      [ /* Part */ ]
  },
  "layout": { /* 页面/行/块，见 §6；默认不影响产物 */ },
  "ext":    { /* 无语义但需保留的字节/字段，见 §7 */ }
}
```

## 2. 层次与 MusicXML 对应

| IR | MusicXML | 说明 |
|---|---|---|
| `score` | `<score-partwise>` | 根 |
| `score.parts[]` | `<part>` | 一个 Staff → 一个 Part（`part_merge=none`） |
| `part.measures[]` | `<measure>` | 与 SMC 的 Meas 一一对应 |
| `measure.voices[]` | `<voice>` 分组 | 按 `MsgHdr+0x01` 低半字节 |
| `voice.events[]` | `<note>` / `<backup>`/`<forward>` | 时间顺序的事件流 |
| `measure.attributes` | `<attributes>` | 拍号/调号/谱号，只在变化处 |
| `measure.spans[]` | `<tie>/<tied>/<slur>` | tie/slur 的显式端点 |
| `measure.directions[]` | `<direction>` | 力度/记号/文本 |

## 3. 时间模型（核心）

### 3.1 单位

- IR 内部时间 = **tick**，范围 `[0, tick_per_meas)` per measure。
- `whole_tick`（文档参数）= 全音符 tick 数。实测全语料 8451/8451 为 **240**（quarter = 60）。
- **不**在 IR 里出现"第几拍""几分音符"。

### 3.2 每个音符的字段

```jsonc
{
  "kind": "note" | "rest",
  "src": { "staff": 1, "meas": 0, "key": 4 },
  "on": 0,                       // 原始 start（引擎写回值，可能是非网格）
  "grid_on": 0,                  // 吸附到网格后的值（step2 默认用这个）
  "grid_error": 0,               // on - grid_on，用于审计
  "dur": 120,                    // 权威时值（= playTime，见 parameters.md A2）
  "dur_source": "playtime",      // 记录实际来源，便于回归
  "dur_head": 120,               // head+4 的原值（仅记录，不权威）
  "voice": 1,
  "staff": 1,                    // 上下谱表归属（parameters.md B2）
  "pitch": {                     // 仅 kind=note
    "midi": 76,
    "step": "E", "alter": 0, "octave": 5,
    "accidental": null           // null = 无显式记号
  },
  "type": { "exp": 4, "dots": 0, "symbol": "eighth" },   // 派生，仅供审计
  "flags_raw": 0,
  "attrs": {
    "grace": false,              // MsgHdr+0x0A bit4
    "tie_start": false, "tie_stop": false,
    "slur_starts": [12], "slur_stops": [],
    "head_type": 1,              // MsgHdr+0x06
    "stem_state": 0,             // MsgHdr+0x05 高 4 位
    "beam": null,                // 由 0x14 容器填
    "voice_raw": 1
  },
  "lyric": { "text": "바", "syllabic": null, "tail": [], "font": {...}, "color": 0 },
  "harmony_ref": 0,              // 索引到 measure.harmonies
  "ext": {}
}
```

### 3.3 小节内的时间推进（step2 的算法）

MusicXML 没有"绝对 on"，位置由**前序时值累加**决定。因此 step2 必须：

```
cursor = 0
for ev in voice.events (sorted by on):
    if ev.on > cursor:  emit <forward> 或 <rest>  (gap_policy)
    emit <note> with dur=ev.dur
    cursor = ev.on + ev.dur
    if cursor > tick_per_meas:  → 溢出，按 overflow_policy 处理
if cursor < tick_per_meas: emit 收尾 rest  (gap_policy=fill-rest)
```

**这是 IR 必须保住 `on` 字段的原因**：累加式推进只有在 `on` 严格等于
"前序和"时才等价；实测存在不等的情况（Hole 与重叠），必须显式对齐。

### 3.4 小节时值

```jsonc
"measure": {
  "tick_per_meas": 720,          // = whole_tick * num * 4 / den
  "time": { "beats": 6, "beat_type": 8, "raw_num": 6, "raw_den": 8 },
  "content_end": { "1": 720 },   // 每声部实测内容结束 tick（审计用）
  "gap": { "1": 0 }              // tick_per_meas - content_end，正=缺、负=超
}
```

## 4. 跨对象引用（tie / slur / 连音符 / 踏板）

step1 全部解析成 `span`：

```jsonc
"spans": [
  {
    "kind": "tie" | "slur" | "tuplet" | "pedal" | "trill" | "cresc",
    "src": { "key": 9 },
    "from": { "meas": 0, "key": 7 },        // 端点 A（通常是音符）
    "to":   { "meas": 0, "key": 10 },       // 端点 B
    "resolved": true,
    "raw": { "endpoint_key": 10, "self_key": 9, "role": 1 }
  }
]
```

- `resolved=false` 时 step2 跳过（记 `warning`）。全语料 92368 条引用中仅 82 条未解析。
- `from`/`to` 用 **IR 内的音符路径**（`meas` + `key`），不是数组下标（下标会因过滤而漂移）。

## 5. 属性变更（`<attributes>`）

IR 把属性变化表示成"小节上的状态"，而不是消息：

```jsonc
"attributes": {
  "changed": {
    "time":    { "beats": 6, "beat_type": 8, "symbol": null },
    "key":     { "fifths": 0, "mode": "major" },
    "clef":    { "sign": "G", "line": 2, "octave_change": 0, "uncertain": false }
  }
}
```

- 只在 `changed` 里出现实际变化（与上一小节比较）。
- **文件首小节强制全写**（`parameters.md` G2）。

## 6. `layout`（不影响产物）

```jsonc
"layout": {
  "source": "smc-page-block",
  "pages": [
    { "index": 0, "rect": [0,0,595,842],
      "blocks": [
        { "group": "A", "type": 1, "n_staves": 1, "start_meas": 0,
          "staff_refs": [{"idx":0,"a":0,"b":65516}],
          "meas_x": [0, 400, 800],       // 绝对像素，归一化后
          "rect": [..], "points": [] }
      ] }
  ],
  "note": "Block = 已排版的行。只用于 page_policy=system-breaks 与人工核对。"
}
```

## 7. `ext`（无语义字节）

保留为十六进制串，逐字段标注来源：

```jsonc
"ext": {
  "ctrl_tool": { "len": 1144, "hex_prefix": "..." },     // 语义大部未知
  "file_info": [6,4,79,79,86,90,30,113,9,8,0,0,529,795], // 0x20 字节，语义未定
  "symp_reserved": "...",                                 // 2124 字节 X 区
  "chord_head_100": "...",                                // 持久化运行期结构，须原样保留
  "object_reserved_byte": 0,                              // ObjectCore +0x01
  "lyric_head_residue": "..."                             // 歌词 head 6 个残留字节
}
```

## 8. 事件类型表（IR 的 `kind`）

| SMC type | IR 表示 | MusicXML |
|---|---|---|
| 0x01 note | `voice.events[].kind=note` | `<note>` |
| 0x03 rest | `kind=rest` | `<note><rest/>` |
| 0x19 lyric | 音符上的 `lyric` | `<lyric>` |
| 0x14 beam | `attrs.beam` + 音符顺序 | `<beam>` |
| 0x25 chord | 同 `on` 的多音符，`attrs.chord=true` | 同 `<voice>` 连续 `<note>`（第 2 个起无 `<duration>` 变化要求） |
| 0x09/0x0A/0x12/0x2E | `spans[]` | `<tie>/<tied>/<slur>/<tuplet>` |
| 0x1B dynamic | `measure.directions[]` | `<direction><dynamics>` |
| 0x1F clef | `attributes.changed.clef` | `<clef>` |
| 0x15 keysig | `attributes.changed.key` | `<key>` |
| 0x45/0x46 chord.sym/fret | `measure.harmonies[]` | `<harmony>` / `<ext:fretboard>` |
| 0x05 metronome / 0x08 mark / 0x18 line / 0x0C coda / 0x10 pedal / 0x21 trill / 0x2C longrest / 0x2F / 0x30 / 0x0D / 0x13 | `measure.directions[]` 或 `spans[]` | 按 `symbol_policy` |
| 0x04/0x06 text | `measure.directions[]`（默认 `ext`） | `<direction><words>` 或 `ext` |
| 0x3F/0x40/0x04 doc | `doc.messages[]` | 无 |
| 0x47 rhythm / 0x44 curve / 0x26 / 0x27 | `ext.objects[]` | 无 |

## 9. 为什么这样就能"方便合成 MusicXML"

| MusicXML 的硬要求 | IR 的对应设计 |
|---|---|
| 每小节时值必须等于拍号时值 | `tick_per_meas` + `gap` + `gap_policy`（A4） |
| 位置由时值累加隐含 | `on` + `grid_on` + 溢出拆分（A6/A9） |
| `<attributes>` 是状态变更 | `attributes.changed`（只在变化处） |
| `<backup>`/`<forward>` 处理多声部 | 每声部一条独立 `events` 流，step2 顺序写 + `<backup>` |
| `<tie>` 必须成对 | `spans` 已解析（E5） |
| `<lyric>` 挂在 `<note>` 上 | 歌词内联在音符上（D2） |
| `<beam>` 挂在 `<note>` 上且需 `begin/continue/end` | `attrs.beam` + 同组顺序（A8） |
| `<divisions>` 全局唯一 | `whole_tick` + `divisions` 在顶层（G1） |
| `<harmony><kind>` 枚举有限 | `kind` + 原始后缀字符串双写（E1） |
