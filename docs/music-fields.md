# SMC 音乐字段与消息语义

> 凡例见 `docs/smc-format.md` §0（知识评级 `[E]`/`[I]`/`[?]`/`[C]`；数据类型为 Rust 风格）。
> 本文件记录音符、休止符、音乐属性、演奏控制类消息的字段级结构。
> 地址均属 `engine.dll`（基址 `0x10000000`）。主规范见 `docs/smc-format.md` §6。

## 0. 关键函数索引

| 地址 | 函数 | 用途 | 评级 |
|---|---|---|---|
| 0x1004AA00 | `CScoreView::SMDrawMsg` | **按 type 分派的唯一 switch** | [E] |
| 0x1004EC70 | `CScoreView::DrawNote` | 音符绘制（读消息头各字段，字体 `KayakumA`） | [E] |
| 0x1004FAF0 | `CScoreView::DrawHead` | 符头/附点/括号绘制 | [E] |
| 0x1007A490 | `CSMMsg::Read` | 消息头 + ObjectCore 读取 | [E] |
| 0x1007A240 | `CSMMsg::Write` | 消息头写回（磁盘布局确证） | [E] |
| 0x10036470 | `CSMMsg::CalcPlayTime` | 时值计算 | [E] |
| 0x100B76F0 | `CSMMsg::SetPlayTime` | 时值写回 head | [E] |
| 0x100B7FB0 | `CSMMsg::GetRealNoteDur` | 实际时值（连音合并） | [E] |
| 0x100AC520 | `CSMMsg::GetMidiKey` | head+0x00 读取 | [E] |
| 0x100AC570 | `CSMMsg::GetVelocity` | head+0x01 读取 | [E] |
| 0x100AAD60 | `CSMMsg::SetParamFromMidiKey` | 谱号/打击乐参数设置 | [E] |
| 0x100B0830 | `CSMMsg::WhatIsAccidental` | 变音记号判定 | [E] |
| 0x100AF1A0 | `CSMMsg::UpdateNoteKeySignature` | 变音记号与调号联动 | [E] |
| 0x100B1370 | `CSMMsg::CalcNoteRestKind` | 时值 → 音符/休止种类 | [E] |
| 0x1002F610 | `CSMDoc::GulsamToSMC_Note` | 外部格式 → 音符消息（字段写入路径） | [E] |

## 1. 音符 Msg（type 0x01）

### 1.1 head（12 字节）

```
NoteHead :=
    key      : u8      ; +0x00  MIDI 音高（0..127）
    velocity : u8      ; +0x01  力度（0..127，默认 100）
    reserved : u8      ; +0x02  常量 0x40
    voice    : u8      ; +0x03  声部索引（与 MsgHdr+0x01 低半字节一致）
    duration : u32     ; +0x04  时值（tick 数）
    start    : u32     ; +0x08  起始时间偏移（磁盘恒 0，运行期写入）
```

| 字段 | 证据 | 评级 |
|---|---|---|
| `key` | `GetMidiKey`/`SetMidiKey`；全语料范围 38..89（49 个值） | [E] |
| `velocity` | `GetVelocity`/`SetVelocity`；12 个值，100 出现 637722 次 | [E] |
| `reserved` | 全语料 652338/652338 恒为 0x40 | [E] |
| `voice` | 与 `MsgHdr+0x01` 低半字节一致 | [E] |
| `duration` | `GetRealNoteDur` 读 `head+4`；`SetPlayTime` 换算回写 | [E] |
| `start` | `UpdateStartTime` 写 `head+8` | [E] |

时值分布（全语料）：120→314335、240→126731、60→59212、360→46397、720→30578、480→30495、
180→24274、960→10769、80→3080、40→1656、1440→1439、30→535 [E]。

### 1.2 消息头中的音乐属性

| MsgHdr | 对象 | 类型 | 含义 | 评级 |
|---|---|---|---|---|
| +0x05 高 4 位 | +0x76 | `u8` | **符干/标记状态**（低 3 位：0 无 / 1 升 / 2 降 / 3 还原 / 4 重升 / 5 重降） | [E] |
| +0x05 低 4 位 | +0x77 | `u8` | **附点数**（低 7 位；时值加 1/2、1/2+1/4） | [E] |
| +0x06 | +0x5C | `i16` | **符头类型**（`SetNoteHeadType` 0x100B29F0） | [E] |
| +0x08 | +0x5E | `i16` | **时值指数** = `0x100 >> (值 & 0x1F)` 的指数 | [E] |
| +0x0A bit2 | +0x6E | `bool` | 符尾存在（`SetTail` 0x100B2A90） | [E] |
| +0x0A bit0 | +0x6E | `bool` | 连音延续目标（`GetRealNoteDur`） | [E] |
| +0x0A bit4 | +0x6E | `bool` | 不发声（渐强/装饰；`GetPlayTime`） | [E] |
| +0x01 高 4 位 | +0x78 | `u8` | 括号标志（非 0 绘制括号） | [E] |
| +0x02 | +0x58 | `u8` | 缩放百分比（默认 0x10 = 16；`SelectFont((v*100)>>4)`） | [E] |
| +0x16 | +0x50 | `i16` | 相对 X 偏移 | [E] |
| +0x18 | +0x52 | `i16` | 音高 Y 偏移（负值向上） | [E] |
| +0x20 | +0x70 | `u32` | 符干方向 / 端点键（二用） | [E] |

### 1.3 符头类型取值（`DrawHead` 0x1004FAF0）

| 值 | 字形来源 | 评级 |
|---|---|---|
| 0 | 不绘制符头 | [E] |
| 1 | `codeStdHead[时值指数]`（0x10100390 起 9 项：`d6 d7 d8 d9 d9 d9 d9 d9 d9`） | [E] |
| 2 | `codeCrossHead`（0xE4） | [E] |
| 3 | `codeSlashHead[时值指数]`（0xDC 区） | [E] |
| 4 / 5 | `codeBoxHead[1]` / `codeBoxHead[0]`（0xDB/0xDC） | [E] |
| 6..99 | `DAT_101003BA[值]` 查表 | [E] |
| `>= 100` | ASCII 数字串（`'0' + 值 - 0x34`；`>= 0x6E` 时两位数字） | [E] |

`SetNoteHeadType` 把入参 7 映射为 0x1A [E]。全语料分布：0→1220583、1→667677、256→18520、13→3764、3→3013 [E]。

### 1.4 变音记号与调号

`WhatIsAccidental` 0x100B0830 返回 0..5（无 / 升 / …）[E]：

- 读小节调号：`meas+0x7D`（= 调号符号，1 为降号序列，否则升号序列）、`meas+0x7E`（调号个数）。
- 半音顺序表 `{6, 2, 5, 1, 4, 0, 3}`（升号顺序 F C G D A E B）；调号为 1 时用逆序。
- 调号类型 `meas+0x7C == 8` → 无调号。
- 逐音符遍历小节（`ResetGetNextMsg` / `GetNextMsg`），遇 type 0x1F（谱号）更新当前谱号，累积临时记号。
- 当前音符无自身记号时返回小节累积值。

`UpdateNoteKeySignature` 0x100AF1A0 依据调号调整 `MsgHdr+0x05` 低 3 位与 `+0x52` 音高偏移，
并调用 `MakeNoteMarkCtrl` [E]。

## 2. 休止符 Msg（type 0x03）

- `MsgHdr+0x08`（+0x5E）= **休止符类型**（`SetRestType` 0x100B2BA0 / `GetRestType` 0x100B2BD0）[E]。
- 时值计算同音符（`CalcPlayTime` case 0x03）[E]。
- 语料 15359 条 [E]。

## 3. 连梁组 Msg（type 0x14）

- 无 head（headLen 0）；结构信息在消息头与子项中 [E]。
- 子项为音符/休止符/和弦；`CalcPlayTime` 求和；`UpdateStartTime` 顺序推进 [E]。
- `MsgHdr+0x0A bit2`（符尾）与 `+0x1C`（f2，连梁粗度）参与绘制：
  `GetToilThick`/`SetToilThick` 0x100B2C00/0x100B2C30 读写 `+0x1C` [E]。
- `ChangeNoteDirection` 对 0x14 调用 `BeamDirection` 决定符干朝向 [E]。
- 语料 54238 条 [E]。

## 4. 和弦 Msg（type 0x25）

- 无 head；子项为同起点的多个音符 [E]。
- `CalcPlayTime`：**自身时间不累加**（case 0x25），仅驱动子项 [E]。
- `SetPlayTime` 把父的 `+0x1C`（f2）与 `+0x77`（附点）复制给每个子音符 [E]。
- `UpdateStartTime` 把同一 start 传给所有子音符 [E]。
- 语料 433 条 [E]。

## 5. 谱号 Msg（type 0x1F）

- `MsgHdr+0x08`（+0x5E）= **谱号类型码**（`SetParamFromMidiKey` 的 `param_1` case 1..8；case 8 = 打击乐）[E]。
- `WhatIsAccidental` / `SetParamFromMidiKey` 遍历中遇 0x1F 更新当前谱号 [E]。
- 语料仅 13 条（多由小节级 `DrawMeasClef` 承担）[E]。

## 6. 调号 Msg（type 0x15）

- `MsgHdr+0x08`（+0x5E）= 调号索引，`DrawKeysign` 0x100571F0 用 `codeAcci[索引]` 取符号（0x10100430 起）[E]。
- `SetParamFromMidiKey` 中 type 0x15 用 `GetDoReMiFromPosY` 的返回值写入 `local_224[]` 调号表 [E]。
- **语料中 type 0x15 不出现**：本语料调号全部存于 **Meas 尾块**（`+0x48`、`+0x5A`/`+0x5C`），
  由小节级 `DrawMeasKey` 0x10055910 绘制 [E]。

## 7. 力度记号 Msg（type 0x1B）

- `MsgHdr+0x08`（+0x5E）= 力度码，`DrawDynamic` 0x1005E690 取 `CodeDyn[码]`（0x101006D4 起）单字符绘制 [E]。
- `CSMDynamicMsg::DrawMsg` 0x10094D80 同表 [E]。
- 语料 17132 条 [E]。

## 8. 节奏型 Msg（type 0x47）

- headLen 0；数据在 `CRhythm` / `CRtmData` 结构中 [E]。
- 完整字段表见 `docs/smc-format.md` §6.9（RtmData），以及 `docs/unknown-fields.md` B4（事件体语义）。
- 语料 12716 条；其中 101 条作为 0x45 的 `Rhythm` 部分内嵌 [E]。

## 9. 谱表名 Msg（type 0x49）

- head 固定 5 字节：`04 00 00 00 00`（语料 79 条样本一致），另有 headLen 11 的少量样本 [E]。
- 名称文本由 `CSMStaffNameMsg::DrawMsg` 0x100BFA70 读取（head 指针 +0x20、长度 +0x1E）[E]。

## 10. 演奏控制：连音线与圆滑线（type 0x09 / 0x0A / 0x12）

- 挂在其父对象下；`MsgHdr+0x20`（+0x70）与对象 `+0x18` 保存**两个端点键** [E]。
- 读取时（`CSMSystem::Read`）对键做 `GetKey` 重映射 [E]。
- `GetTieIndex` 0x10037D90 / `GetSlurIndex` 0x10037E20 通过子项 `role` 字节区分 tie/slur 端点 [E]。
- 0x12（小节级连音符）由 `DrawMeasTuplet` 绘制，并参与 `CalcWholeCount` 的分段表 [E]。
- 语料：0x09 → 26295、0x0A → 62202、0x12 → 1786 [E]。

## 11. MIDI 短消息（type 0x42）

- `CSMDoc::EncToSMC_MidiMsg` 0x10022D20 构造：type = **0x42**；
  对象 `+0x18` = **3 字节 MIDI 消息**（status/data1/data2）[E]。
- `DrawMidiShortMsg` 0x10066290 绘制 [E]。
- 用途：精确播放控制（不经音符实时生成）[I]。

## 12. 文档级消息（type 0x3F / 0x40 / 0x04）

- 每文件各出现一次（0x3F 8451、0x40 8451、0x04 8342）[E]。
- 均无 head（headLen 0）[E]。
- 语义未定；0x04 亦在 `SMDrawMsg` 中映射到 `DrawMultiText` [E]。
- 详见 `docs/unknown-fields.md` B6。

## 13. 范围说明

本文件覆盖全部高频消息类型。低频类型（0x2C 长休止、0x0C Coda、0x46 指板、0x47 节奏）的
head 内部字段见 `docs/smc-format.md` §6.8/§6.9/§6.13 与 `docs/unknown-fields.md`。
