# SMC 音乐字段与消息语义（第三阶段）

> 本文件记录音符、休止符、音乐属性、演奏控制类消息的字段级结构。
> 记号 `[E]` 直接证据 / `[I]` 推断 / `[?]` 未知。地址均属 `engine.dll`（基址 0x10000000）。
> 主规范见 `smc-format.md` §6。

## 0. 关键函数索引

| 地址 | 函数 | 用途 |
|---|---|---|
| 0x1004aa00 | CScoreView::SMDrawMsg | **按 type 分派的唯一 switch** |
| 0x1004ec70 | CScoreView::DrawNote | 音符绘制（读取消息头各字段） |
| 0x1004faf0 | CScoreView::DrawHead | 符头/附点/括号绘制 |
| 0x1007a490 | CSMMsg::Read | 消息头 + ObjectCore 读取 |
| 0x1007a240 | CSMMsg::Write | 消息头写回（磁盘布局确证） |
| 0x1007aa20 | CSMObject::Read | ObjectCore / 子项读取 |
| 0x1007a740 | CSMObject::Write | ObjectCore 写回 |
| 0x10036470 | CSMMsg::CalcPlayTime | 时值计算 |
| 0x100b76f0 | CSMMsg::SetPlayTime | 时值写回 head |
| 0x100b7fb0 | CSMMsg::GetRealNoteDur | 实际时值（连音合并） |
| 0x100ac520 | CSMMsg::GetMidiKey | head[0] 读取 |
| 0x100ac570 | CSMMsg::GetVelocity | head[1] 读取 |
| 0x100aad60 | CSMMsg::SetParamFromMidiKey | 音高/谱号/打击乐参数设置 |
| 0x100b0830 | CSMMsg::WhatIsAccidental | 变音记号判定 |
| 0x100af1a0 | CSMMsg::UpdateNoteKeySignature | 变音记号与调号联动 |
| 0x100b1370 | CSMMsg::CalcNoteRestKind | 时值 → 音符/休止种类 |
| 0x1002f610 | CSMDoc::GulsamToSMC_Note | 外部格式 → 音符消息（字段写入路径） |

## 1. 音符 Msg（type 0x01）

### 1.1 head（12 字节）字段表 [E]

| head 偏移 | 大小 | 类型 | 含义 | 证据 |
|---|---|---|---|---|
| +00 | 1 | u8 | **MIDI 音高 key**（0..127） | `GetMidiKey`/`SetMidiKey` |
| +01 | 1 | u8 | **力度 velocity**（0..127，默认 100） | `GetVelocity`/`SetVelocity`；`MakeMidiMsgFromY` 默认 100 |
| +02 | 1 | u8 | 保留常量 **0x40** | 全语料 652338 条恒为 64 |
| +03 | 1 | u8 | **声部索引**（1/2，与 MsgHdr+01 低半字节一致） | 全语料观察 + `MakeMidiMsgFromY` |
| +04..+07 | 4 | u32 | **时值（tick 数）** | `GetRealNoteDur` 读；`SetPlayTime` 回写 |
| +08..+0B | 4 | u32 | **起始时间偏移**（磁盘恒 0） | `UpdateStartTime` 写 `head+8` |

全语料统计（8451 文件）：
- key：范围 **38..89**，49 个不同值（无 0..127 全域，说明乐器音域受限）
- velocity：12 个不同值；100 出现 637722 次、127 出现 6905、64 出现 5845、80 出现 920
- 时值：120 出现 314335、240 出现 126731、60 出现 59212、360 出现 46397、720 出现 30578、480 出现 30495、180 出现 24274、960 出现 10769、80/40/1440/30 等

时值单位：`doc+0xA0` 为全音符 tick 基数（样本中分母换算后常见 120 = 四分音符当量，即 480 tick/全音符时的 1/4）[I]。

### 1.2 消息头中的音乐属性 [E]

| MsgHdr | 对象 | 含义 | 证据 |
|---|---|---|---|
| +05 高4 | +0x76 | 符干/标记状态（低 3 位：0 无 / 1 升 / 2 降 / 3 还原 / 4 重升 / 5 重降） | `WhatIsAccidental` |
| +05 低4 | +0x77 | **附点数**（低 7 位，语料仅 0/1/2）；时值计算加 1/2、1/2+1/4 | `CalcPlayTime`、`DrawHead` |
| +06 | +0x5C | **符头类型** | `SetNoteHeadType` 0x100b29f0 |
| +08 | +0x5E | **时值指数** = `0x100 >> (值 & 0x1F)` 的指数 | `CalcPlayTime` |
| +0A bit2 | +0x6E | 符尾存在 | `SetTail` 0x100b2a90 |
| +0A bit0 | +0x6E | 连音延续目标 | `GetRealNoteDur` |
| +0A bit4 | +0x6E | 不发声（渐强/装饰） | `GetPlayTime` |
| +01 高4 | +0x78 | 括号标志（非 0 时绘制 "(" ")"） | `DrawHead` |
| +02 | +0x58 | 音符缩放百分比（默认 0x10=16；`SelectFont((v*100)>>4)`） | `DrawNote` |
| +16 | +0x50 | 相对 X 偏移 | 各绘制器 |
| +18 | +0x52 | 音高 Y 偏移（负值向上） | 各绘制器 |
| +20 | +0x70 | 符干方向 / 端点键（二用） | `ChangeNoteDirection` |

### 1.3 符头类型取值（`DrawHead` 0x1004faf0）

| 值 | 字形来源 |
|---|---|
| 0 | 不绘制符头 |
| 1 | `codeStdHead[时值指数]`（0x10100390 起 9 项：d6 d7 d8 d9 d9 d9 d9 d9 d9） |
| 2 | `codeCrossHead`（0xE4） |
| 3 | `codeSlashHead[时值指数]`（0xDC 区） |
| 4 / 5 | `codeBoxHead[1]` / `codeBoxHead[0]`（0xDB/0xDC） |
| 6..99 | `DAT_101003ba[值]` 查表 |
| >= 100 | 用 ASCII 数字串绘制（`('0'+值-0x34)`；>= 0x6E 时两位数字） |

`SetNoteHeadType` 把传参 7 映射为 0x1A [E]。全语料分布：0 → 1220583、1 → 667677、256 → 18520、13 → 3764、3 → 3013、16 → 1331… [E]

### 1.4 变音记号与调号 [E]

`WhatIsAccidental` 0x100b0830 返回 0..5（无/升/…）：
- 读小节调号：`meas+0x7D`（= 调号符号，1 = 降号序列，否则升号序列）、`meas+0x7E`（调号个数）
- 半音顺序表 `local_28 = {6,2,5,1,4,0,3}`（升号顺序 F C G D A E B）；调号为 1 时用逆序
- 调号类型 `meas+0x7C == 8` → 无调号
- 逐音符遍历小节（`ResetGetNextMsg`/`GetNextMsg`），遇到 type 0x1F（谱号）更新当前谱号，累积每个音位的临时记号
- 当前音符无自身记号时返回小节累积值 `local_18[*param_1]`

`UpdateNoteKeySignature` 0x100af1a0 依据调号调整 `MsgHdr+05` 低 3 位与 `+0x52` 音高偏移，并调用 `MakeNoteMarkCtrl`。

## 2. 休止符 Msg（type 0x03）

- `MsgHdr+08`（对象 +0x5E）= **休止符类型**，由 `CSMMsg::SetRestType` 0x100b2ba0 写入、`GetRestType` 0x100b2bd0 读取 [E]
- 时值计算同音符（`CalcPlayTime` case 0x03）[E]
- 语料 15359 条 [E]

## 3. 连梁组 Msg（type 0x14）

- 无 head（headLen 0）；结构信息在消息头与子项中 [E]
- 子项为音符/休止符/和弦；`CalcPlayTime` 求和；`UpdateStartTime` 顺序推进 [E]
- `MsgHdr+0A bit2`（符尾）与 `+0x1C`（f2，连梁粗度）参与绘制：`GetToilThick`/`SetToilThick` 0x100b2c00/0x100b2c30 读写 `+0x1C` [E]
- `ChangeNoteDirection` 对 0x14 调用 `BeamDirection` 决定符干朝向 [E]
- 语料 54238 条 [E]

## 4. 和弦 Msg（type 0x25）

- 无 head；子项为同起点的多个音符 [E]
- `CalcPlayTime` 计算但与音符不同：**自身时间不累加**（case 0x25）[E]
- `SetPlayTime` 把父的 `+0x1C`（f2）与 `+0x77`（附点）复制给每个子音符 [E]
- `UpdateStartTime` 把同一 start 传给所有子音符 [E]
- 语料 433 条 [E]

## 5. 谱号 Msg（type 0x1f）

- `MsgHdr+08`（+0x5E）= **谱号类型码**（`SetParamFromMidiKey` 的 `param_1` case 1..8；case 8 = 打击乐）[E]
- `WhatIsAccidental`/`SetParamFromMidiKey` 在遍历中遇到 0x1F 时更新当前谱号 [E]
- 语料仅 13 条（多由小节级 `DrawMeasClef` 承担）[E]

## 6. 调号 Msg（type 0x15）

- `MsgHdr+08`（+0x5E）= 调号索引，`DrawKeysign` 0x100571f0 用 `codeAcci[索引]` 取符号（0x10100430 起）[E]
- `SetParamFromMidiKey` 中 type 0x15 用 `GetDoReMiFromPosY` 的返回值写入 `local_224[]` 调号表 [E]
- **语料中 type 0x15 不出现**：本语料的调号全部存于 **Meas 尾块**（`+48 → +0x84`、`+5A/+5C → +0x7D/+0x7E`），
  由小节级 `DrawMeasKey` 0x10055910 绘制 [E]。

## 7. 力度记号 Msg（type 0x1b）

- `MsgHdr+08`（+0x5E）= 力度码，`DrawDynamic` 0x1005e690 取 `CodeDyn[码]`（0x101006d4 起）单字符绘制 [E]
- `CSMDynamicMsg::DrawMsg` 0x10094d80 同表 [E]
- 语料 17132 条 [E]

## 8. 节奏型 Msg（type 0x47）

- 带 `CRhythm` / `CRtmData`（同 `ChordExtra` 内的 Rhythm 结构）[E]
- headLen 0，数据在 Rhythm 结构中 [E]
- 语料 12716 条 [E]
- 具体字段表待补（见 `unknown-fields.md`）

## 9. 谱表名 Msg（type 0x49）

- head 固定 5 字节：`04 00 00 00 00`（语料 79 条样本一致）[E]
- 名称来自 `CSMStaffNameMsg::DrawMsg` 0x100bfa70 读取的 head 指针 `+0x20` 与长度 `+0x1E`，实际文本为 head 之后的字符串 [E]
- 全语料 headLen 分布：5（多数）、11 [E]

## 10. 演奏控制：连音线与圆滑线（type 0x09 / 0x0a / 0x12）

- 挂在其父对象下；`MsgHdr+20`（+0x70）与对象 `+0x18` 保存**两个端点键** [E]
- 读取时（`CSMSystem::Read`）对键做 `GetKey` 重映射 [E]
- `GetTieIndex` 0x10037d90 / `GetSlurIndex` 0x10037e20 通过子项 `role` 字节区分 tie/slur 端点 [E]
- 0x12（小节级连音符）由 `DrawMeasTuplet` 绘制，并参与 `CalcWholeCount` 的分段表 [E]
- 语料：0x09 → 26295、0x0a → 62202、0x12 → 1786 [E]

## 11. MIDI 短消息（type 0x42）

- `CSMDoc::EncToSMC_MidiMsg` 0x10022d20 构造：type = **0x42**，`MsgHdr+18`（对象 +0x18）为 **3 字节 MIDI 消息**（status/data1/data2）[E]
- `DrawMidiShortMsg` 0x10066290 绘制 [E]
- 用于精确播放控制（不通过音符实时生成）[I]

## 12. 文档级消息（type 0x3f / 0x40 / 0x04）

- 每个文件各出现一次（0x3f 8451、0x40 8451、0x04 8342）[E]
- 均无 head（headLen 0）[E]
- 语义未确定；0x04 亦在 `SMDrawMsg` 中映射到 `DrawMultiText` [E]
- 详 `unknown-fields.md`

## 13. 停止条件说明

本阶段已完成：
- 全部音符/休止/和声/连梁/歌词/文本/调号/力度/谱表名/连音类消息的**身份与主要字段**。
- 音符 12 字节 head 的**完整字段表**。
- 消息头 0x2C 的**完整磁盘字段表**（含未知项标注）。

未完成（留待后续）：
- 0x2c（长休止，headLen 60）、0x0c（Coda）、0x47（节奏型）、0x46（指板）的 head 内部字段。
- 0x04/0x3f/0x40 的确切语义。
