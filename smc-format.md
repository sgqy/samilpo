# SMC 文件格式（第一阶段，初步）

> 状态：**帧结构（framing）已由静态分析恢复，并用 `tools/smc_walk.py` 在全部 8451 个样本上验证：每个文件的主体都被逐字节恰好消耗完，尾部恰好 4 字节。** 绝大多数字段的语义仍未知。
> 第二阶段补充：韩文文本编码（§8）与歌词消息 0x19 已恢复，见 `encoding.md` 与 `lyrics.md`。
>
> 记号：`[E]` = 直接证据（反编译/字节观察）；`[I]` = 推断；`[?]` = 未知。所有整数均为小端（x86）。`s16/u16/u32/i32` 为有/无符号整数。
> 除特别注明外，函数地址均指 engine.dll（基址 0x10000000）。MusicBook.exe 的地址为 0x4xxxxx 形式。

## 0. 总体结构

| 文件偏移（样本 500KFS-0041） | 长度 | 内容 | 读取者 |
|---|---|---|---|
| 0x000 | 4 | `u32 hdrLen`，必须为 0x58C，否则走旧格式路径 | exe FUN_00424670 [E] |
| 0x004 | 0x58C | SYMP 头块（读入 view+0x380） | 同上 [E] |
| 0x590 | 2 | `s16 strLen` | 同上 [E] |
| 0x592 | strLen（仅当 strLen>1） | 附加字符串（以 NUL 结尾） | 同上 [E] |
| 0x596 | 0x318 | "SMC" 块（读入 view+0x68） | 同上 [E] |
| 0x8AE | fontLen | 字体表缓冲 → `CFontDatas::LoadBuffer` | 同上 [E] |
| 0x912 | 2 + ctlLen | CSMCtrlTool 块（`s16 ctlLen` + 数据） | `CSMCtrlTool::Read` 0x1007f4e0 [E] |
| 0xD8C | 0x20 | CSMFileInfo 块 | `CSMFileInfo::Read` 0x10095260 [E] |
| 0xDAC | 4 | `u32 bodyLen` | `CSMDoc::Load` 0x10077cb0 [E] |
| 0xDB0 | bodyLen | 文档主体（一次性读入内存后按顺序解析） | 同上 [E] |
| EOF-4 | 4 | `u32`，在全部样本中都等于 bodyLen [E 观察]；读取代码未读取它 [I：保存时写入的校验/冗余] | 无 |

偏移会随可变长度字段变化；上表只是样本中的位置。

**没有观察到压缩、加密或校验处理**：所有读取都是 `CFile::Read`（vtable +0x3c）直接 memcpy 到结构/缓冲区，`FUN_1009a720` 只是 `GlobalMemoryStatus` 内存检查（用 `bodyLen*3/2` 估算）。[E]

## 1. SYMP 头块（file 0x004，0x58C 字节）

对应 exe `FUN_00424670`，读入 `view+0x380`。

| 块内偏移 | 文件偏移 | 类型 | 说明 |
|---|---|---|---|
| 0x00 | 0x04 | u32 | 再次出现 0x58C（自身长度）[E 观察] |
| 0x04 | 0x08 | char[4] | `"SYMP"`，`strncmp` 校验 [E] |
| 0x08 | 0x0C | s16 | 格式版本。>0x2005 拒绝（消息 0x67）；<0x2003 时对 doc+0x40e..0x414 做 `MulDiv(x,16,doc+8)` 换算并调用 `ChangeTieSlurInfo` [E]。语料中只有 0x2004（6930 个）和 0x2005（1521 个）[E] |
| 0x0A | 0x0E | char[]，NUL 结尾 | 曲名 [I]（字节与 0x06 类型文本消息里的曲名相同），采用韩文双字节编码，见 §8 |
| … | … | | 其余基本是 0 [?] |

若 hdrLen ≠ 0x58C，或者 magic 不是 SYMP，则调用 `FUN_00425090(CFile*)`（旧格式头处理），之后继续读 SMC 块 [E]。该路径未分析。

## 2. 附加字符串（file 0x590）

`s16 n`；若 n>1，则读 n 字节，经 `CString::Format` 存入 `view+0x90c` [E]。语料中通常是 3~5 字节的数字串（例如 "448"、"54"）；有 318 个文件长度为 32，内容是 F0–FC 引导字节的双字节文本 [E 观察]。语义未知（歌本页码/编号？）[?]。

## 3. SMC 块（0x318 字节，读入 view+0x68）

| 块内偏移 | 类型 | 说明 |
|---|---|---|
| 0x000 | char[4] | `"SMC\0"`，`strcmp` 校验 [E] |
| 0x004 | u32 | 0x318（自身长度）[E 观察] |
| 0x312 | s16 | 样本中为 0x2004，与版本相同 [E 观察，含义 ?] |
| 0x314 | u32 | `fontLen`：后面字体表缓冲的长度 [E] |
| 其余 | | [?] |

### 3.1 字体表缓冲（fontLen 字节）

交给 `CFontDatas::LoadBuffer` 0x1002c100（未反编译）。从样本观察到的格式是重复的 `u8 index, u8 len, char[len] name` [I]，例如 `01 0A "ＷＫ細明朝"(SJIS)`、`06 0C "WKGothic(KS)"`、`07 05 "Gulim"`、`08 06 "System"`。读完后 exe 还对 doc+0x1f8、+0x234 … +0x3d8（9 个间隔 0x3C 的 LOGFONT.lfFaceName 位置）调用 `GetNearestFontName` [E]。

## 4. CSMCtrlTool 块（`CSMCtrlTool::Read` 0x1007f4e0）

`s16 len`（样本 0x478），然后 len 字节；复制最多 0x478 字节到栈上结构体，整块还会复制到 this+0x4ec [E]。函数返回 0x478。已确认的块内布局如下（块内偏移 → 对象偏移）：

| 块内偏移 | 长度 | → CSMCtrlTool | 推断 |
|---|---|---|---|
| 0x000,0x03C,0x078,0x0B4,0x0F0,0x12C,0x168,0x1A4 | 各 0x3C | +0x20c,+0x1d0,+0x284,+0x2c0,+0x2fc,+0x338,+0x374,+0x3b0 | 8 个 LOGFONTA（大小正好是 60 字节）[I] |
| 0x1E0 | 0x24 | +0x7c | ? |
| 0x204 | 4 | +0xa0 | ? |
| 0x208 | 0x100 | +0xa8 | 字符串/路径？[?] |
| 0x308..0x32C | u32×10 | +0xa4,+0x1ac.. | ? |
| 0x330 | 0x40 | +0x34 | ? |
| 0x370,0x372 | s16×2 | +0x3ec,+0x3ee | ? |
| 0x374 | 0x12 | +0x3f0 | ? |
| 0x386 | 8 | +0x402..0x408 | 4 个 s16，分别被钳制到 [-99,99]、[-99,99]、[1,48]、[0,16]（移调/八度/…？）[E 钳制，I 语义] |
| 0x38E.. | s16 若干 | +0x40a.. | ? |
| 0x3A8 | 8 | +0x4a4 | POINT/SIZE [I] |
| 0x3B0 | 0x10 | +0x4ac | RECT [I] |
| 0x408 | 0x3C | +0x248 | 第 9 个 LOGFONT [I] |
| 0x460..0x46E | u8×9 | +0x96c..0x974 | 若为 0 则填默认值 0x30,0x40,0x4C,0x54,0x60,0x6E,0x78,0x7F → **强弱记号到 MIDI velocity 的映射表** [I，强] |
| 0x46F..0x473 | u8×5 | +0x977..0x97b | 默认值为 0x28 [?] |

## 5. CSMFileInfo 块（0x20 字节，`CSMFileInfo::Read` 0x10095260）

`s16 ×12`（→ +4..+0x1a）+ `u32 ×2`（→ +0x1c,+0x20）[E]。样本：`6,4,79,79,86,90,30,113,9,8,0,0, 529,795`。导出函数 `SetLogicPageInfo(POINT,RECT,short×4,…)` 暗示这是页面版式信息（页数/边距/页面尺寸）[I]。

## 6. 文档主体（CSMDoc::Load 0x10077cb0）

先读 `u32 bodyLen`，再一次读入整块；之后所有读取器都使用 `(BYTE* buf, DWORD* pos, DWORD* size)` 游标 [E]。顺序如下：

```
Body :=
  System                       ; CSMSystem::Read(buf,&pos,&len,0)  0x10078730
  DocHdr  (10 bytes)           ; s16 pageCount, s16 → doc+8, s16 → doc+4, s16 → doc+6, s16 → doc+10
  Msg  ×3                      ; 文档级消息 → doc+0xc3c, +0xcbc, +0xd3c；语料中通常是类型 0x3f, 0x40, 0x04 [E 观察]
  Page × pageCount             ; CSMPage::Read 0x1007bbf0
```
`doc+8` 被复制到全局 DAT_10100fb8，exe 用它作为旧版本换算的分母 → 基准谱面字号/谱线间距 [I]。

### 6.1 通用对象头 ObjectCore（CSMObject::Read 0x1007aa20）

```
ObjectCore :=
  u8   childCount          ; +0
  u8   ?                   ; +1  不由本函数读取
  u16  f2                  ; +2  → obj+0x1c
  s16  headLen             ; +4
  u16  ?                   ; +6
  u32  f8                  ; +8  → obj+0x18（Meas 中拆为两个 s16）
  u8   head[headLen]       ; SetHead：对象私有负载，含义取决于类型
  Child × childCount
Child :=
  u32  key                 ; 对象键，经 CSMSystem::GetKey 重映射
  u8   embedded            ; ≠0 → 紧随其后是一个完整的 Msg
  u8   pad[3]
  [Msg]                    ; 仅当 embedded≠0
```
（`CSMMeas::Read` 0x100798e0 使用同样的头布局；对于 embedded==0 的子项则直接丢弃。）[E]

### 6.2 Msg（CSMMsg::Read 0x1007a490）——乐谱元素的统一记录

```
Msg :=
  MsgHdr (0x2c bytes)
  ObjectCore               ; 头负载 + 可嵌套子 Msg
  [ChordExtra]             ; 仅当 type == 0x45
MsgHdr:
  +00 u8  type             ; 0x41 读取后改为 0x08
  +01 u8  hi4 → +0x78, lo4 → +0x69
  +02 u8  → +0x58
  +03 u8  → +0x74
  +04 u8  → +0x75
  +05 u8  hi4 → +0x76, lo4 → +0x77
  +06 s16 → +0x5c ; +08 → +0x5e ; +0a → +0x6e ; +0c → +0x60 ; +0e → +0x66 ; +10 → +0x62 ; +12 → +0x64
  +14 s16 → +0x5a ; +16 → +0x50 ; +18 → +0x52 ; +1a → +0x54 ; +1c → +0x56   ; 坐标/矩形？[I]
  +20 u32 → +0x70          ; 引用另一对象的键（9/0x0a/0x12 类型会经 GetKey 重映射）[E]
  +24 u32 key              ; 本对象键 → GetKey → +0x14 [E]
  +28 u32 → +0x4c
```
type==0x01 且 headLen≠12 时会把 head 规整为 12 字节 [E]。

**类型频率（全语料 8451 个文件）与初步解释：**

| type | 计数 | 线索 | 推断 |
|---|---|---|---|
| 0x01 | 652338 | head 12 字节；在 Meas 中挂到 up/down 数组 | 音符/和弦音 [I] |
| 0x19 | 625967 | head = 0x10 + 文本字节数；`CSMLyricMsg` | **歌词音节单元**（第二阶段确认，见 `lyrics.md`）[E] |
| 0x45 | 177909 | 带 ChordExtra，CChordSymbol | 和弦记号 [E] |
| 0x46 | 177909 | CFretBoard 设置的类型 | 和弦的吉他指板图 [E] |
| 0x0a / 0x09 / 0x12 | 62202/26295/1786 | 带 +0x18、+0x70 键引用并重映射 | 连接型记号（连音线/圆滑线/…）[I] |
| 0x14 / 0x25 | 54238/433 | 可带子消息；空则删除；挂到 up/down 数组 | 音符组/和弦组？[I] |
| 0x06 | 42031 | head 是 TLV 结构 + 文本 | 文本框（曲名、作者、速度、後斂等）[E 结构；见 `lyrics.md` §6] |
| 0x47 | 12716 | 带 CRhythm/CRtmData | 节奏型/伴奏型 [I] |
| 0x49 | 5865 | Staff 中查找，缺失时由 SetStaffNameToMsg 生成 | 谱表名 [E] |
| 0x3f, 0x40 | 各 8451 | 每个文件 1 次，文档级 | ? |
| 0x16 / 0x17 | 0 | 旧式和弦记号，会转换为新格式 | 旧版兼容 [E] |
| 其他 (03,04,05,08,0c,0d,10,13,18,1b,1f,21,26,27,2c,2e,2f,30,44) | 少量 | | [?] |

### 6.3 ChordExtra（type 0x45，CChordSymbol::ReadFromMem 0x1000bdb0）

```
ChordExtra :=
  CStr  surfixName              ; CChordSurfix::ReadFromMem 0x10008b40
  u8    n ; u8 info[n]
  Msg                           ; CFretBoard::ReadFromMem 0x1002cfd0（类型强制为 0x46）
  u8    fretInfo[16]            ; CFretInfo::ReadFromMem 0x1002dc70：2+6+8 字节
  s16   hasRhythm
  [Rhythm]                      ; 仅当 hasRhythm≠0
Rhythm := Msg, CStr ×3, RtmData ; CRhythm::ReadFromMem 0x10045c40
RtmData :=                      ; CRtmData::ReadFromMem 0x10047720
  u32 ?, u16 ?, u16 →+8, u16 →+0x48,
  i32 nEv, s16 evSize, u8 ev[nEv*evSize],
  s16 n2, s16 sz2, u8 data[n2*sz2]
CStr := u16 len, u8 bytes[len]  ; ReadCStringFromMem 0x10095c30（无终止符，len 最多 ~100）
```
CFretBoard 是否就是 CChordSymbol+0xc4 处的对象，最初是推断；解析时观察到嵌套 Msg 的类型为 0x46，并且全语料可以完整解析，这两点支持该推断 [I，强]。

### 6.4 System（CSMSystem::Read 0x10078730，对象类型 5）

```
System := ObjectCore, s16 nStaff, s16 nStaff2, u32 →+0xa0,
          Staff × nStaff  (类型3, → sys+0x4c),
          Staff × nStaff2 (类型4, → sys+0x60)
```
语料中只出现过 1 个 System（单一乐谱系统）。

### 6.5 Staff（CSMStaff::Read 0x10079030）

```
Staff := ObjectCore, StaffTail(0x70), Meas × nMeas
StaffTail:
  +00 char[0x20] name (→ +0x74)   ; 谱表名
  +20 u8, +21 u8, +22 u8
  +23 u8[8], +33 u8[8], +3b u8[8], +43 u8[8]
  +4b u8, +4c u8[3], +54 u16
  +6c i32 nMeas
```
`obj+0x1c`（ObjectCore.f2）不在 [50,200] 范围内时强制设为 100 → 音量/比例百分比 [I]。

### 6.6 Meas（CSMMeas::Read 0x100798e0，对象类型 2）

```
Meas := ObjectCore'(f8 拆为 s16 →+0x82, s16 →+0x18), MeasTail(0x60)
MeasTail（部分）:
  +00 u8 →+0x81 ; +13 u8[16] →+0x54 ; +33 u8[16] →+0x98
  +44..+4d u8 若干 ; +4e,+50 s16
  +52 s16 →+0x4c ; +56 s16 →+0x50 ; +58 s16 →+0x52   ; (+56,+58) 为 0 时默认 4/4 → 拍号 [I，强]
  +5a u8, +5c u8, +5e s16 →+0x90（取决于 doc 标志）
```
读取后对 9 条声部调用 `UpdatePlayTime` / `UpdateStartTime`（i=0..8）[E] → 每小节最多 9 个声部/层 [I]。

### 6.7 Page / Block（分页与排版）

```
Page := s16 nBlockA, s16 nBlockB, s16 nMsg, s16 ?, RECT(16),   ; 0x18 bytes
        Block × nBlockA (→ page+4), Block × nBlockB (→ page+0x18), Msg × nMsg (页面级消息)
Block := (0x1c header)
  +00 u8 type        ; 1: 从 System 的第一组谱表中取；否则取第二组
  +01 u8 nStaves
  +02 s16 nMeas-1?   ; 后面读 (val+1) 个 u16
  +04 s16 →+0x38     ; 起始小节号？[I]
  +08 u8 nPts
  +0c RECT
  StaffRef × nStaves := u8 staffIdx, u16, u16
  u16 × (hdr[+02]+1)  ; 小节 x 坐标（以首项为原点归一化）[I]
  (i32,i32) × nPts    ; 谱表名位置？[I]
```
Block = 一个排版行/系统行（乐谱的一行）[I]。样本有 3 页、22 个 Block，与“多页乐谱”相符。

## 7. MIDI / 图片

- 没有找到 MIDI 数据块。播放用的 MIDI 事件很可能由音符 Msg 实时生成（exe 导入了 midiStream*；engine 中有 `CSMMsg::GetMidiKey`）[I]。
- 图片：exe 通过 SHDrawJpeg.dll 的 `LOAD_JPEG_File` / `DRAW_JPEG_File` 从**文件**加载 JPEG。语料中未发现嵌入的 JPEG（`FF D8 FF` 命中都是坐标值的误报），也没有图像文件名字符串 [E 观察]。图片在 SMC 中如何引用，目前未知 [?]。

## 8. 文本编码（第二阶段已恢复）

SMC 文本使用 code id 1 = **"889F Code"**（`889F.cod`），即以 Shift-JIS 双字节码位为索引的自定义映射表；转换入口 `MyDrawTextOutW` 明确调用 `CKCConv::ToUnicode(1,…)` [E]。完整说明见 `encoding.md`，程序工具 `tools/smc_text.py`。

- `< 0x80` 单字节透传；其余按双字节码位查表。
- 未映射码位原样保留（由字体自身字形渲染）。
- 码位区段以 0x88–0x9F、0xE0–0xFC 为主，另含 SJIS 用户定义区 0xF000–0xF300。
- 字体名本身是标准 Shift-JIS 日文（如“ＭＳ Ｐゴシック”）[E]。
