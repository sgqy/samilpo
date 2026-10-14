# SMC 文件格式规范（Samilpo 2.0）

> **状态**：第一阶段恢复帧结构；第二阶段恢复韩文编码与歌词消息；第三阶段（本文）恢复消息头字段、全部消息类型分派、音符/小节/谱表/页面/块结构、字体与符号机制。
>
> 记号：
> - `[E]` 直接证据（反编译代码或对全部样本的字节观察）
> - `[I]` 推断（证据较强但未完全证明）
> - `[?]` 未知
> - 除注明外，函数地址属 `engine.dll`（基址 `0x10000000`）；`0x4xxxxx` 属 `MusicBook.exe`（基址 `0x400000`）。
> - **所有整数的小端字节序**。
>
> 专题文档：`encoding.md`（字符编码）、`lyrics.md`（歌词）、`music-fields.md`（音符与音乐属性）、
> `font-resources.md`（字体与符号）、`layout.md`（谱表/系统/页面布局）、`unknown-fields.md`（未解字段）、
> `function-index.md`（函数索引）、`research-state.md`（研究状态）。
>
> 验证基线：**全部 8451 个样本精确消耗主体字节、尾部恰好 4 字节**（`tools/smc_census.py`）。

---

## 1. 概述与适用版本

SMC 是 Samilpo 2.0（韩国记谱软件）的乐谱文档格式。一个文件完整描述一或多页乐谱：

- 文档级设置（显示/播放参数、字体表、页面版式、速度）。
- 一个**谱表系统**（System），其下是若干**谱表**（Staff，上/下两组），每个谱表下是**小节**（Meas）。
- 小节内是**消息**（Msg）树：音符、休止符、歌词、和弦记号、力度、拍号、调号、连梁、连音线、文本框、图形等。
- 分页信息（Page）与排版块（Block），决定乐谱在页面上的行布局。

### 1.1 版本

`SYMP` 头内的 `s16 version`：

| 值 | 含义 | 语料计数 |
|---|---|---|
| 0x2004 | 版本 2.0.4 | 6930 |
| 0x2005 | 版本 2.0.5 | 1521 |

- `> 0x2005`：程序弹消息 0x67 并拒绝 [E]。
- `< 0x2003`：对 `doc+0x40e..0x414` 做 `MulDiv(x,16,doc+8)` 换算并调用 `ChangeTieSlurInfo` [E]。
- 本规范同时适用于 0x2004 与 0x2005；两者结构一致，未发现字段含义差异 [E 观察]。

---

## 2. 基本数据类型与编码规则

| 名称 | 定义 |
|---|---|
| `u8/s8/u16/s16/u32/i32` | 无/有符号小端整数 |
| `CStr` | `u16 len` + `len` 字节（**无终止符**，len ≤ ~100）。`ReadCStringFromMem` 0x10095c30 |
| `char[N]` | 定长 NUL 结尾字符串 |
| 文本编码 | SMC 文本使用 **889F Code**（见 §8） |
| 对象 key | `u32`，同一文档内唯一，经 `CSMSystem::GetKey` 重映射 |

对齐：**所有结构均无填充**，字段紧邻。长度字段即字节长度。

---

## 3. 文件级结构

| 文件偏移 | 长度 | 内容 | 读取者 |
|---|---|---|---|
| 0x000 | 4 | `u32 hdrLen` = 0x58C；否则走旧格式路径 | exe FUN_00424670 [E] |
| 0x004 | 0x58C | `SYMP` 头块（读入 `view+0x380`） | 同上 [E] |
| 0x590 | 2 | `s16 strLen` | 同上 [E] |
| 0x592 | strLen（仅当 >1） | 附加字符串（NUL 结尾） | 同上 [E] |
| 0x596 | 0x318 | `SMC` 块（读入 `view+0x68`） | 同上 [E] |
| 0x8AE | fontLen | 字体表缓冲 → `CFontDatas::LoadBuffer` | 同上 [E] |
| 0x912 | 2 + ctlLen | `CSMCtrlTool` 块 | `CSMCtrlTool::Read` 0x1007f4e0 [E] |
| 0xD8C | 0x20 | `CSMFileInfo` 块 | `CSMFileInfo::Read` 0x10095260 [E] |
| 0xDAC | 4 | `u32 bodyLen` | `CSMDoc::Load` 0x10077cb0 [E] |
| 0xDB0 | bodyLen | 文档主体 | 同上 [E] |
| EOF-4 | 4 | `u32`，**在所有 8451 个样本中等于 bodyLen** | 无（保存时写入）[E] |

上表偏移以样本 `500KFS-0041.smc` 为例；实际偏移随 `strLen`/`fontLen`/`ctlLen` 变化。

**无压缩、无加密、无校验和**：所有读取都是 `CFile::Read` 直接 memcpy；`FUN_1009a720` 只是 `GlobalMemoryStatus` 内存检查 [E]。

### 3.1 SYMP 头块（0x58C）

| 块内偏移 | 类型 | 说明 |
|---|---|---|
| 0x00 | u32 | 再次出现 0x58C（自身长度）[E] |
| 0x04 | char[4] | `"SYMP"`，`strncmp` 校验 [E] |
| 0x08 | s16 | 格式版本（见 §1.1）[E] |
| 0x0A | char[] | **曲名**（NUL 结尾，889F 编码）[I，与 0x06 文本中的曲名一致] |
| 其余 | — | 基本为 0 [?] |

### 3.2 附加字符串（file 0x590）

`s16 n`；`n > 1` 时读 n 字节经 `CString::Format` 存入 `view+0x90c` [E]。
语料中通常为 3–5 字节数字串（"448"、"54"）；有 318 个文件长度为 32，内容为 F0–FC 引导的双字节文本 [E 观察]。语义未知 [?]。

### 3.3 SMC 块（0x318）

| 块内偏移 | 类型 | 说明 |
|---|---|---|
| 0x000 | char[4] | `"SMC\0"`，`strcmp` 校验 [E] |
| 0x004 | u32 | 0x318（自身长度）[E] |
| 0x312 | s16 | 样本中为 0x2004（与版本一致）[E 观察，含义 ?] |
| 0x314 | u32 | `fontLen`：字体表缓冲长度 [E] |
| 其余 | — | [?] |

### 3.4 字体表缓冲（fontLen 字节）

交给 `CFontDatas::LoadBuffer` 0x1002c100。格式为**重复记录**（已由反编译确认）[E]：

```
FontRecord :=
  u8  index        ; 字体索引（1..N，用于 MsgHdr 的字体索引字段）
  u8  nameLen      ; 名称字节数（≤ 255）
  u8  name[nameLen]; 名称文本（889F 编码），末尾自动补 NUL
```

- 每条记录既存入 `CFontDatas+4`（字符串数组），也调用 `AddNewFont(index, name, len)` 注册字体对象 [E]。
- 载入后 exe 对 `doc+0x1f8、+0x234 … +0x3d8`（9 个间隔 0x3C 的 `LOGFONT.lfFaceName` 位置）调用 `GetNearestFontName` [E]。
- 语料实例：`01 0A "ＷＫ細明朝"`、`06 0C "WKGothic(KS)"`、`07 05 "Gulim"`、`08 06 "System"` [E]。

### 3.5 CSMCtrlTool 块（`s16 len` + len 字节）

`CSMCtrlTool::Read` 0x1007f4e0：`s16 len`（样本 0x478），复制 ≤0x478 字节到栈结构，并整块复制到 `this+0x4ec`；返回 0x478 [E]。已确认块内布局：

| 块内偏移 | 长度 | → CSMCtrlTool | 说明 |
|---|---|---|---|
| 0x000,0x03C,…,0x1A4 | 各 0x3C | +0x20c,+0x1d0,+0x284,+0x2c0,+0x2fc,+0x338,+0x374,+0x3b0 | 8 个 `LOGFONTA`（60 字节）[I] |
| 0x1E0 | 0x24 | +0x7c | ? |
| 0x204 | 4 | +0xa0 | ? |
| 0x208 | 0x100 | +0xa8 | 字符串/路径 [?] |
| 0x308..0x32C | u32×10 | +0xa4,+0x1ac.. | ? |
| 0x330 | 0x40 | +0x34 | ? |
| 0x370,0x372 | s16×2 | +0x3ec,+0x3ee | ? |
| 0x374 | 0x12 | +0x3f0 | ? |
| 0x386 | 4×s16 | +0x402..0x408 | 分别钳制到 [-99,99]、[-99,99]、[1,48]、[0,16]（移调/八度/…）[E 钳制] |
| 0x38E.. | s16 若干 | +0x40a.. | ? |
| 0x3A8 | 8 | +0x4a4 | POINT/SIZE [I] |
| 0x3B0 | 0x10 | +0x4ac | RECT [I] |
| 0x408 | 0x3C | +0x248 | 第 9 个 LOGFONT [I] |
| 0x460..0x46E | u8×9 | +0x96c..0x974 | 0 时填默认 0x30,0x40,0x4C,0x54,0x60,0x6E,0x78,0x7F → **强弱记号到 MIDI velocity 的映射表** [I，强] |
| 0x46F..0x473 | u8×5 | +0x977..0x97b | 默认 0x28 [?] |

`ctrl+0x10` = **当前编辑声部（0..8）**，绘制时用于可见性判断 [E]。

### 3.6 CSMFileInfo 块（0x20）

`s16 ×12`（→ +4..+0x1a）+ `u32 ×2`（→ +0x1c,+0x20）[E]。
样本：`6,4,79,79,86,90,30,113,9,8,0,0, 529,795`。导出函数 `SetLogicPageInfo(POINT,RECT,short×4,…)` 暗示这是页面版式信息 [I]。

---

## 4. 文档主体（`CSMDoc::Load` 0x10077cb0）

先读 `u32 bodyLen`，一次读入整块；之后所有读取器共用游标 `(BYTE* buf, DWORD* pos, DWORD* size)`。

```
Body :=
  System                       ; CSMSystem::Read 0x10078730
  DocHdr (10 bytes)            ; s16 pageCount, s16 → doc+8, s16 → doc+4, s16 → doc+6, s16 → doc+10
  Msg × 3                      ; 文档级消息 → doc+0xc3c, +0xcbc, +0xd3c
  Page × pageCount             ; CSMPage::Read 0x1007bbf0
```

- 语料中 3 条文档级消息通常为类型 **0x3f, 0x40, 0x04**（每文件各一次）[E]。
- `doc+8` 复制到全局 `DAT_10100fb8`，作为旧版本换算分母 → **谱面基准单位（半线间距）** [I]。
- `doc+0xA0` 全局副本 → **全音符 tick 基数**（`CSMMeas::CalcWholeCount` 与 `CSMMsg::CalcPlayTime` 使用）[E]。

---

## 5. 对象模型

### 5.1 通用对象头 ObjectCore（磁盘布局，`CSMObject::Read` 0x1007aa20 / `Write` 0x1007a740）

| 磁盘偏移 | 类型 | 含义 | 读取者 |
|---|---|---|---|
| +00 | u8 | **childCount**（子项个数） | Read/Write [E] |
| +01 | u8 | **保留**：读取路径从不使用；写入路径写入未初始化栈字节（语料中 46% 为 0，其余为残留值） | 无 [E 观察 + 写入路径] |
| +02 | u16 | **f2**：连音/连奏比例（高字节=分子，低字节=分母，见 §6.2）[E 用法 / I 命名] | Read→obj+0x1C |
| +04 | u16 | **headLen**（私有负载长度） | Read→obj+0x1E |
| +06 | u16 | **= headLen + 12**（派生冗余长度，`CSMObject::Write` 写入；Read 跳过） | 无 [E] |
| +08 | u32 | **f8** | Read→obj+0x18 |
| 之后 | u8[headLen] | head 私有负载（`SetHead`） | [E] |
| 之后 | Child × childCount | 子项 | [E] |

在内存中（供交叉引用反编译）：`+0x18`=f8、`+0x1C`=f2、`+0x1E`=headLen、`+0x20`=head 指针、`+0x24`=子项数组、`+0x38`=控制点数组、`+0x08`=父指针、`+0x0C`=文档、`+0x14`=本对象 key、`+0x10`=页面/视图指针 [E]。

**说明**：`CSMObject::Write` 的 `local_14` 只初始化低字节（childCount）与 f2，`+01` 字节来自栈残留，因此写入值不确定；读取端完全忽略该字节，可安全写 0。

### 5.2 子项 Child（8 字节）

```
Child :=
  u32 key        ; 对象键（读取时经 CSMSystem::GetKey 重映射）
  u8  role       ; 引用角色；0 = 仅引用（无嵌入对象），非 0 = 其后紧跟一个完整 Msg
  u8  pad[3]
  [Msg]          ; 仅当 role != 0
```

- `CSMObject::AddMsg` 0x100bad70 / `InsertMsg` 0x100baec0 写入 `role`，取值由调用方给出 [E]。
- `CSMObject::Write` 原样回写该 8 字节，`role != 0` 时递归写嵌入消息 [E]。
- `GetTieIndex` 0x10037d90 用 `role == param` 匹配 tie 角色；`GetSlurIndex` 0x10037e20 用 `key` + `role` 匹配 slur 端点 [E]。
- 语料：`role` 仅出现 {0, 1}（0 占 3259、1 占 59635，抽样）[E]。
- 内存语义：嵌入对象的 `+0x08 = 父对象`、`+0x05 = 父对象的 voice` [E]。

**注意**：`CSMMeas::Read` 会**丢弃** `role == 0` 的子项（自减计数）[E]。

### 5.3 对象类型码（`CSMObject::SetObjectType`）

| 值 | 类型 |
|---|---|
| 1 | Msg（消息，见 §6） |
| 2 | Meas（小节） |
| 3 | Staff（上组谱表） |
| 4 | Staff（下组谱表） |
| 5 | System（系统） |

---

## 6. 消息 Msg

### 6.1 记录结构（`CSMMsg::Read` 0x1007a490 / `Write` 0x1007a240）

```
Msg :=
  MsgHdr (0x2C bytes)
  ObjectCore                     ; 含 head 负载与子 Msg
  [ChordExtra]                   ; 仅当 type == 0x45
```

**MsgHdr 字段表**（磁盘偏移 → 内存对象偏移）：

| 偏移 | 类型 | → 对象 | 含义 | 状态 |
|---|---|---|---|---|
| +00 | u8 | +0x68 | **消息类型**（读取时 `0x41` 改写为 `0x08`） | Confirmed |
| +01 高4 | u8 | +0x78 | **括号标志**（非 0 时绘制括号） | Confirmed |
| +01 低4 | u8 | +0x69 | **声部索引 0..8** | Confirmed |
| +02 | u8 | +0x58 | 缩放百分比（默认 0x10=16） | Confirmed |
| +03 | u8 | +0x74 | ? | Unknown |
| +04 | u8 | +0x75 | ? | Unknown |
| +05 高4 | u8 | +0x76 | **符干/标记状态**（低 3 位为状态码，见 §6.6） | Confirmed |
| +05 低4 | u8 | +0x77 | **附点数**（低 7 位；高 1 位另有含义） | Confirmed |
| +06 | s16 | +0x5C | **音符符头类型 / 打击乐声部索引** | Confirmed |
| +08 | s16 | +0x5E | **类型相关索引**：时值指数、休止符类型、力度记号码、调号码、节拍器码、谱号码、字符码… | Confirmed |
| +0A | s16 | +0x6E | **标志位集合**（见 §6.5） | Confirmed |
| +0C | s16 | +0x60 | 绘制缓存（外接矩形，非文件语义） | Confirmed |
| +0E | s16 | +0x66 | 绘制缓存 | Confirmed |
| +10 | s16 | +0x62 | 绘制缓存 | Confirmed |
| +12 | s16 | +0x64 | 绘制缓存 | Confirmed |
| +14 | s16 | +0x5A | 起始时间（小节内 tick） | Confirmed |
| +16 | s16 | +0x50 | **相对 X 偏移** | Confirmed |
| +18 | s16 | +0x52 | **音高 Y 偏移**（负值向上） | Confirmed |
| +1A | s16 | +0x54 | 外接矩形 L（缓存） | Confirmed |
| +1C | s16 | +0x56 | 外接矩形 R / 符干长度 | Confirmed |
| +20 | u32 | +0x70 | **端点引用键**（连音/圆滑线端点；或符干方向标志） | Confirmed |
| +24 | u32 | +0x14 | **本对象 key**（经 `CSMSystem::GetKey` 重映射） | Confirmed |
| +28 | u32 | +0x4C | 颜色/样式（`DrawDynamic` 用作 `SetTextColor` 参数） | Inferred |

> `type == 0x01` 且 `headLen != 12` 时，读取后会把 head 规整为 12 字节（+08..+0B 清零）[E]。

### 6.2 时值与播放时间（`CSMMsg::CalcPlayTime` 0x10036470 / `GetPlayTime` 0x10042a50）

对 type ∈ {0x01, 0x03, 0x25}：

```
playTime = (0x100 >> (MsgHdr+08 & 0x1F)) * doc+0xA0 >> 5      ; 基本时值
附点：MsgHdr+05 低半字节（对象 +0x77）== 1 → += 1/2；== 2 → += 1/2 + 1/4
比例：f2=ObjectCore+02；若 (f2>>8)!=0 且 (f2&0xFF)!=0
        playTime = MulDiv(playTime, f2>>8, f2&0xFF)
```

- **`MsgHdr+08 & 0x1F` 是时值指数**，`0x100>>exp` 为占全音符的比例 [E]。
- type 0x14（连梁组）：播放时间 = 各子消息之和 [E]。
- type 0x25（和弦）：自身时间不被累加，仅驱动子项 [E]。
- `GetPlayTime`：`MsgHdr+0A & 0x10` 置位时返回 0（不发声，渐强/装饰记号）[E]。

### 6.3 消息类型分派表（`CScoreView::SMDrawMsg` 0x1004aa00）

| type | 绘制器 | 语义 | 语料计数 |
|---|---|---|---|
| 0x01 | DrawNote | **音符** | 652338 |
| 0x03 | DrawRest | **休止符** | 15359 |
| 0x04 | DrawMultiText | 文本框（文档级） | 8342 |
| 0x05 | DrawMetronome | 节拍器记号 | 1640 |
| 0x06 | DrawMultiText | **文本框**（曲名/作者/速度/（후렴）等） | 42031 |
| 0x08 | DrawMark | 标记 | 6707 |
| 0x09 | （注册到 tie 表） | **连音线（tie）** | 26295 |
| 0x0a | （注册到 slur 表） | **圆滑线（slur）** | 62202 |
| 0x0c | DrawCoda | Coda 记号 | 165 |
| 0x0d | DrawRolled_chord | 滚奏和弦（琶音） | 111 |
| 0x10 | DrawVabPedal | 踏板 | 1 |
| 0x12 | DrawMeasTuplet | 小节级连音符 | 1786 |
| 0x13 | DrawCDCrescendo | 渐强/渐弱 | 93 |
| 0x14 | DrawBeam | **连梁组** | 54238 |
| 0x15 | DrawKeysign | **调号**（独立消息；语料中不出现，调号存于 Meas 尾块） | 0 |
| 0x16 | DrawFretboard | 吉他指板图（旧式） | — |
| 0x17 | DrawChordText | 和弦文字（旧式） | — |
| 0x18 | DrawMsgLine | 直线 | 10431 |
| 0x19 | DrawTextMsg | **歌词**（`CSMLyricMsg`） | 625967 |
| 0x1b | DrawDynamic | **力度记号** | 17132 |
| 0x1f | DrawClef | **谱号** | 13 |
| 0x21 | DrawTrills | 颤音（tr） | 4 |
| 0x25 | DrawChord | **和弦**（同音组） | 433 |
| 0x26 | DrawEllipse | 椭圆 | 3 |
| 0x27 | DrawRectangle | 矩形 | 14 |
| 0x28 | DrawRoundRectangle | 圆角矩形 | — |
| 0x29 | DrawN | 任意文字 | — |
| 0x2a | DrawGerneralFont | 通用字体字符（`codeSmallDigit`，索引取 ObjectCore.f2） | — |
| 0x2b | DrawInversM | 强音记号 | — |
| 0x2c | DrawLongrest | 长休止（多小节休止） | 98 |
| 0x2e | DrawSlur | 圆滑线（独立） | 264 |
| 0x2f | DrawSingle_Msg | 换气记号 | 8 |
| 0x30 | DrawSingle_Msg | 花音记号 | 9 |
| 0x34 | DrawSingle_Msg | 断句 | — |
| 0x35 | DrawSingle_Msg | **小节反复记号** | — |
| 0x36 | DrawSingle_Msg | 单字符记号 | — |
| 0x37..0x3a | DrawSingle_Msg | 滑音线 | — |
| 0x3c | DrawSingle_Msg | 上圈 | — |
| 0x3d | DrawSingle_Msg | 下圈 | — |
| 0x3e | DrawSingle_Msg | 大下圈 | — |
| 0x42 | DrawMidiShortMsg | **MIDI 短消息**（原始 MIDI 事件） | — |
| 0x44 | DrawCurvedLine | 曲线 | 1 |
| 0x45 | 虚函数 vtable+0x18 | **和弦记号**（`CChordSymbol`） | 177909 |
| 0x47 | （CRhythm/CRtmData） | 节奏型/伴奏型 | 12716 |
| 0x49 | CSMStaffNameMsg::DrawMsg | **谱表名** | 5865 |
| 0x4a | DrawBezierLine | 贝塞尔曲线 | — |
| 0x3f / 0x40 | （文档级） | 每文件各一次 | 各 8451 |

- 语料中所有 type 频率取自全部 8451 个文件（`tools/smc_census.py`）[E]。
- `0x16/0x17` 为旧式和弦记号，读取时被转换为 `CChordSymbol`（`MakeFromOldChordSymbol`）[E]。

### 6.4 连音与圆滑线的引用机制

type ∈ {0x09, 0x0a, 0x12} 的消息：

- 挂在其**父对象**（通常是音符或小节）下，`MsgHdr+20`（对象 +0x70）与对象 +0x18 保存**两个端点键** [E]。
- `CSMSystem::Read` 结束时对这两个键执行 `GetKey` 重映射；超出映射表范围则置 0 [E]。
- `CSMMsg::CreateFrom` 0x1006acd0：若 `+0x18 == +0x70`（自指）则两者都设为父键；否则 `+0x18` 设为父键，`+0x70` 保留为另一端 [E]。

### 6.5 标志位（`MsgHdr+0A`，对象 +0x6E）

| 位 | 掩码 | 含义 | 证据 |
|---|---|---|---|
| 0 | 0x0001 | **连音目标标志**（tie 延续） | `GetRealNoteDur` 0x100b7fb0 |
| 2 | 0x0004 | **符尾存在** | `CSMMsg::SetTail` 0x100b2a90 |
| 3 | 0x0008 | 标记内部标志 | `ResetGetNextMsg` 0x100acb20 |
| 4 | 0x0010 | **不发声 / 渐强装饰**（GraceNote 亦置此位） | `GetPlayTime`、`MakeGraceNote` 0x100abb80 |
| 5 | 0x0020 | 和弦处理标志 | `ResetGetNextMsg` |
| 9 | 0x0200 | 上组谱表 | `WhatIsAccidental` 0x100b0830 |
| 10 | 0x0400 | 下组谱表 | 同上 |

全语料出现计数：bit2=3113、bit3=4770、bit4=3063、bit8=3017、bit9=2978、bit10=2978（抽样 300 文件）[E]。

### 6.6 符干/标记状态（`MsgHdr+05` 高半字节，对象 +0x76）

低 3 位为状态码：`0`=无、`1`=升变音（sharp/上偏）、`2`=降变音（flat/下偏）、`3`=回原（natural）、`4`=重升、`5`=重降（`CSMMsg::WhatIsAccidental` 0x100b0830 / `UpdateNoteKeySignature` 0x100af1a0）[E]。

### 6.7 音符 head（12 字节，type 0x01）[E]

| head 偏移 | 类型 | 含义 |
|---|---|---|
| +00 | u8 | **MIDI 音高 key**（0..127） |
| +01 | u8 | **力度 velocity**（0..127，默认 100） |
| +02 | u8 | **保留常量 0x40**（样本内恒为 64） |
| +03 | u8 | **声部索引**（与 MsgHdr+01 低半字节一致，1/2） |
| +04..+07 | u32 | **时值（tick 数）** |
| +08..+0B | u32 | **起始时间偏移**（磁盘恒为 0，运行期写入） |

证据：
- `CSMMsg::GetMidiKey` 0x100ac520 / `SetMidiKey` 0x100ac4d0 读写 `head[0]` [E]
- `CSMMsg::GetVelocity` 0x100ac570 / `SetVelocity` 0x100ac5c0 读写 `head[1]` [E]
- `CSMMsg::GetRealNoteDur` 0x100b7fb0 读 `*(u32*)(head+4)`；`SetPlayTime` 0x100b76f0 以其换算后回写 [E]
- `CSMMsg::UpdateStartTime` 0x10037a70 写 `*(int*)(head+8)` [E]
- 全语料：key 范围 38..89（49 个不同值）、velocity 12 个不同值（100 出现 637722 次）、head[2]=0x40 恒定、head[3] ∈ {1,2} 且与声部一致 [E]

### 6.8 ChordExtra（type 0x45，`CChordSymbol::ReadFromMem` 0x1000bdb0）

```
ChordExtra :=
  CStr  surfixName                     ; CChordSurfix::ReadFromMem 0x10008b40
  u8    n ; u8 info[n]
  Msg                                  ; CFretBoard::ReadFromMem 0x1002cfd0（类型强制为 0x46）
  u8    fretInfo[16]                   ; CFretInfo::ReadFromMem 0x1002dc70（2+6+8 字节）
  s16   hasRhythm
  [Rhythm]                             ; 仅当 hasRhythm != 0
Rhythm := Msg, CStr ×3, RtmData        ; CRhythm::ReadFromMem 0x10045c40
RtmData :=                             ; CRtmData::ReadFromMem 0x10047720
  4+2+2+2 字节头,
  i32 nEv, s16 evSize, u8 ev[nEv*evSize],
  s16 n2,  s16 sz2,    u8 data[n2*sz2]
```

**type 0x45 的 head 长度有两种**：`0`（多数）与 `100`（部分）[E 全语料观察]。

- 和弦的**可读名称在 `ChordExtra.surfixName`**（CStr）。语料实测值：
  `" (major)"` 539、`"m"` 371、`"7"` 154、`"(major)"` 58、`"m6"` 9、`"m7"` 6、`"dim"` 4、`"9"` 2、`"dim7"` 1 [E]。
- head 长度 100 的内容为**二进制缓存**（含运行期指针/标志字节，非稳定文本），不应作文本解析 [E 观察]。
- `CSMMsg::Write` 对 type 0x45 先把 `this+0x80`→`this+0x18`、`this[0x17C]<<8|this[0x180]`→`this+0x1C` 覆盖后再序列化 [E]。
- `hasRhythm` 在抽样中 101/1244 为真；节奏数据由 `CRtmData` 承载，另有 `CRtmData::ConvertToPlayData`（导出）用于播放 [E]。

---

## 7. 结构对象

### 7.1 System（`CSMSystem::Read` 0x10078730，对象类型 5）

```
System := ObjectCore,
          s16 nStaff1, s16 nStaff2, u32 wholeTick
          Staff × nStaff1      ; 类型 3 → sys+0x4C
          Staff × nStaff2      ; 类型 4 → sys+0x60
```
- `wholeTick` = 全音符 tick 基数 → sys+0xA0 [E]。
- 语料中每个文件恰好 1 个 System [E]。

### 7.2 Staff（`CSMStaff::Read` 0x10079030）

```
Staff := ObjectCore, StaffTail(0x70), Meas × nMeas
```

| Tail 偏移 | → 对象 | 含义 |
|---|---|---|
| +00 | char[0x20] → +0x74 | **谱表名**（889F 编码，定长 0x20） |
| +20 | u8 → +0x4C | 谱表序号 |
| +21 | u8 → +0x4D | **谱号类别**（`0x02/0x03` = 打击乐/特殊；`DrawHead` 判定） |
| +22 | u8 → +0x70 | ? |
| +23 | u8[8] → +0x50 | 调号表 1 |
| +33 | u8[8] → +0x58 | 调号表 2 |
| +3B | u8[8] → +0x68 | 调号表 3 |
| +43 | u8[8] → +0x60 | 调号表 4 |
| +4B | u8 → +0xAC | ? |
| +4C | u8[3] → +0x71 | ? |
| +54 | u16 → +0x4E | ? |
| +6C | i32 | **nMeas：小节个数** |

- 读取后 `obj+0x1C`（音量/比例）不在 [0x32, 200] 内则置 100 [E]。
- 子项中查找 type **0x49**（谱表名消息）；缺失时由 `SetStaffNameToMsg` 生成 [E]。

### 7.3 Meas（`CSMMeas::Read` 0x100798e0，对象类型 2）

`ObjectCore'`（**与通用 ObjectCore 略有差别**）：

```
MeasCore :=
  u8  childCount        ; 循环中可自减（丢弃 role==0 的纯引用项）
  u8  ?                 ; +1（不读）
  u16 f2                ; +2 → 对象 +0x1C
  s16 headLen           ; +4（注意：Meas 用 s16，通用为 u16）
  u16 ?                 ; +6（不读）
  u32 f8                ; +8 → 对象 +0x82 = 低 16 位，对象 +0x18 = 高 16 位
  u8  head[headLen]
  Child × childCount
```

`MeasTail`（0x60 字节）：

| Tail 偏移 | → 对象 | 含义 |
|---|---|---|
| +00 | u8 → +0x81 | 拍号模式（==3 时拍号用文本描述） |
| +13 | u8[0x10] → +0x54 | **拍号文本串**（CString） |
| +33 | u8[0x10] → +0x98 | 第二文本串 |
| +44..+4D | u8 → +0x7A,+0x7B,+0x7C,+0x84,+0xA8,+0x8C,+0x8D,+0x8E,+0x92 | ? |
| +4E | u16 → +0x94 | ? |
| +50 | u16 → +0x96 | ? |
| +52 | s16 → +0x4C | ? |
| +56 | s16 → +0x50 | **拍号分子** |
| +58 | s16 → +0x52 | **拍号分母** |
| +5A | u8 → +0x7D | ? |
| +5C | u8 → +0x7E | ? |
| +5E | u16 → +0x90 | 显示开关（受 `doc+0x9c`→`+0x999` 全局标志控制） |

读取后：
- 拍号分子或分母为 0 → 强制 **4/4** [E]。
- 调用 `CalcWholeCount`；对 **9 个声部**（0..8）依次 `UpdatePlayTime(i)` / `UpdateStartTime(i,0,0,0)` → **每小节最多 9 个声部** [E]。
- 遍历子项：type ∈ {0x14, 0x25} 且无子项 → **删除**；type ∈ {0x14,0x25,0x01,0x03} → `ChangeParent` + `AddUpDownMsgArray` [E]。

**小节长度（`CalcWholeCount` 0x1003a4d0）**：

```
docWhole = doc+0xA0
tickPerMeas(+0x4E) = docWhole * 分子 * 4 / 分母
分段表存入对象 +0xEC 的 CWordArray（连音符分段）
```

全语料拍号分布：分子 {4,6,3,12,2,9,5,18,10,8,15,7}；分母 {4,8,2,16}（分母 4 占多数）[E]。

### 7.4 Page（`CSMPage::Read` 0x1007bbf0）

```
Page :=
  s16 nBlockA          ; → 页 +0x04 数组
  s16 nBlockB          ; → 页 +0x18 数组
  s16 nPageMsg         ; 页面级消息数
  s16 ?
  RECT(16)             ; → 页 +0x7C
  Block × nBlockA
  Block × nBlockB
  Msg   × nPageMsg     ; 页面级消息
```

### 7.5 Block（`CSMBlock::Read` 0x1007b550 / `Write` 0x1007b020）

Block = 乐谱的一个**排版行**（系统行）。

```
BlockHdr (0x1C):
  +00 u8  type       ; 1: 从 System 第一组谱表取；否则取第二组
  +01 u8  nStaves
  +02 s16 f2         ; 其后的 u16 个数 = f2 + 1（小节 X 坐标）
  +04 s16 → +0x38    ; 起始小节号
  +08 u8  nPts
  +0C RECT(16)       ; → +0x90
之后：
  StaffRef × nStaves := u8 staffIdx, u16 (→ +0xB4 数组), u16 (→ +0x7C，默认 0xFFEC)
  u16 × (f2+1)       ; 小节 X 坐标（以首项归一化）
  (i32,i32) × nPts   ; 谱表名位置点
```

- `Write` 的 `_Size = nStaves*5 + 2 + f2*2 + nPts*8`，与 `Read` 完全一致 [E]。
- 全语料 `(nStaves, f2, nPts)`：`(1,4,0)` 25920、`(1,3,0)` 8805、`(1,5,0)` 3742、…；单谱表行占绝大多数，多谱表行少量 [E]。

---

## 8. 文本编码（第二阶段已恢复）

SMC 文本使用 **code id 1 = "889F Code"**（`889F.cod`），即以 Shift-JIS 双字节码位为索引的自定义映射表。转换入口 `MyDrawTextOutW` 0x10096530 明确调用 `CKCConv::ToUnicode(1,…)` [E]。

- `< 0x80` 单字节透传；其余按双字节码位查表。
- 未映射码位原样保留（由字体自身字形渲染）。
- 码位区段：0x88–0x9F、0xE0–0xFC，另含 SJIS 用户定义区 0xF000–0xF300。
- 完整说明见 `encoding.md`。

---

## 9. 资源、字体与符号

### 9.1 字体

- 程序在启动时加载 8 个 TTF（`C:\Program Files (x86)\Samilpo 2.0\Font\`）[E]。
- SMC 文件内的字体表（§3.4）保存**字体的显示名与索引**，供消息的字体索引字段引用。
- 详见 `font-resources.md`。

### 9.2 音乐符号

音符、休止符、变音记号、力度、踏板等**音乐符号不是文本字符**，而是引擎内以单字节常量（0x7F–0xFF）表示的符号码，经 **`KayakumA` 符号字体**（`KAYAKUMA.TTF`，Windows 符号字符集，映射到 U+F020–U+F0FF）绘制 [E]。

- `KAYAKUMA.TTF` 的 cmap 仅覆盖 **U+F020–U+F0FF**（223 个字形）[E]。
- 889F 表**不**映射到 U+F000 区（0 个码位）→ 音乐符号与韩文文本使用**两套互不重叠的编码空间** [E]。

### 9.3 图片

exe 通过 `SHDrawJpeg.dll` 的 `LOAD_JPEG_File`/`DRAW_JPEG_File` 从**文件**加载 JPEG。语料中未发现嵌入的 JPEG（`FF D8 FF` 命中均为坐标值误报），也没有图像文件名字符串 [E 观察]。图片引用方式仍未知 [?]。

---

## 10. 兼容性与版本差异

- 版本 0x2004 / 0x2005 结构一致。
- 非 `SYMP`/`hdrLen != 0x58C` 时调用 `FUN_00425090`（旧格式头）后继续读 SMC 块 [E]。该路径未分析（当前语料不使用）。
- 旧式消息 0x16/0x17（老和弦记号）在读取时被转换为 `CChordSymbol` [E]。
- `CSMMsg::ChangeTieSlurInfo` 用于 < 0x2003 的连音/圆滑线换算 [E]。

---

## 11. 未知字段与研究限制

见 `unknown-fields.md`。主要空白：

1. ObjectCore 保留字节 +01 的稳定性（写为 0 安全）。
2. MsgHdr +03/+04、+14、+28 的完整语义。
3. 类型 0x2c（长休止，headLen 60）、0x0c（Coda）、0x47（节奏型）的 head 字段表。
4. CSMCtrlTool 与 CSMFileInfo 的其余字段。
5. 附加字符串（"448"）语义。
6. 图片引用机制。
