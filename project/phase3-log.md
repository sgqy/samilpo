# 第三阶段执行记录（2026-10-14）

> 工作日志：记录本阶段新增的**直接证据**（函数地址 + 伪代码依据）与待验证项。
> 最终归档目标是 `docs/smc-format.md` 等专题文档；本文件是过程记录。

## 0. 会话

- REA 绑定 `C:\Program Files (x86)\Samilpo 2.0\engine.dll`
  - SHA-256 `424b61c00500db8a40ef943675983fd29d7bf70093cf7737f2659b14718d25a8`（与阶段一二一致）
  - provider: Ghidra 12.1.4；x86；基址 0x10000000

## 1. 任务 B-1：音符消息与消息头（磁盘布局的直接证据）

### 1.1 MsgHdr 0x2C 已由 Write/Read 双向确认 [E]

`CSMMsg::Write` 0x1007a240 把 0x2C 字节栈结构 `local_34`（ebp-0x34 起）memcpy 到输出缓冲。
栈局部与磁盘偏移一一对应，且 `CSMMsg::Read` 0x1007a490 从 `pCVar3[n]` 读回同一位置：

| 磁盘偏移 | Write 来源 | Read 目标 | 含义 |
|---|---|---|---|
| +00 u8 | this[0x68] | this[0x68] | 消息类型（0x41 读入后改写为 0x08） |
| +01 u8 | this[0x78]<<4 \| this[0x69]&0xF | 拆回 +0x78/+0x69 | 高/低半字节对 |
| +02 u8 | this[0x58] (低字节) | this[0x58] (u16, 高字节不读) | 次要字段 |
| +03 u8 | this[0x74] | this[0x74] | ? |
| +04 u8 | this[0x75] | this[0x75] | ? |
| +05 u8 | this[0x76]<<4 \| this[0x77]&0xF | 拆回 +0x76/+0x77 | **this[0x76]=符干/标记类，this[0x77]=附点数** |
| +06 s16 | this[0x5c] | this[0x5c] | 见 §1.3（SetParamFromMidiKey 写入 0x5c = 鼓组编号+1） |
| +08 s16 | this[0x5e] | this[0x5e] | **时值码**（0x100>>(val&0x1F)，见 §1.2） |
| +0A s16 | this[0x6e] | this[0x6e] | 标志位（bit4 = 不发声，见 §1.2） |
| +0C s16 | this[0x60] | this[0x60] | ? |
| +0E s16 | this[0x66] | this[0x66] | ? |
| +10 s16 | this[0x62] | this[0x62] | ? |
| +12 s16 | this[0x64] | this[0x64] | ? |
| +14 s16 | this[0x5a] | this[0x5a] | ? |
| +16 s16 | this[0x50] | this[0x50] | 相对 X 偏移（歌词文档 §4） |
| +18 s16 | this[0x52] | this[0x52] | **音高 Y 偏移**（UpdatePos 计算；负数越大越高） |
| +1A s16 | this[0x54] | this[0x54] | 文字外接矩形 L |
| +1C s16 | this[0x56] | this[0x56] | 文字外接矩形 R |
| +20 u32 | this[0x70] | this[0x70] | 引用键（0x09/0x0A/0x12 经 GetKey 重映射） |
| +24 u32 | this[0x14] (经 GetKey) | this[0x14] | 本对象键 |
| +28 u32 | this[0x4c] | this[0x4c] | ? |

注：Write 在 type==0x45 时先把 `this+0x80`→`this+0x18`、`this[0x17c]<<8|this[0x180]`→`this+0x1c` 再序列化 [E]。

### 1.2 时值与播放时间 [E]

`CSMMsg::CalcPlayTime` 0x10036470：
- this[0x68] ∈ {0x01, 0x03, 0x25}：
  - `+0x6A = (0x100 >> (word@+0x5E & 0x1F)) * *(int*)(*(int*)(this+0xC)+0xA0) >> 5`
    → **+0x5E = 时值指数**，`0x100>>exp` 为 1/2^n 全音符比例；parent+0xA0 为全音符时值基数 [E]
  - 附点：`this[0x77]`（消息头 +05 低半字节）== 1 加半，== 2 加半再加四分之一 [E]
  - 比例微调：`f2=word@+0x1C`；当 `f2>>8 != 0 && (f2&0xFF) != 0` 时 `+0x6A = MulDiv(+0x6A, f2>>8, f2&0xFF)`
    → **ObjectCore.f2 是连音/连奏比例（分子=高字节，分母=低字节）** [E 用法 / I 命名]
- this[0x68]==0x14：播放时间 = 各子消息播放时间之和（**组/连音组**）[E]
- this[0x68]==0x25：同 1/3 的计算，但**自身时间不被累加**（仅驱动子项）[E]

`CSMMsg::GetPlayTime` 0x10042a50：type ∈ {1,3,0x25} 时，若 `word@+0x6E & 0x10` 置位则返回 0（不发声）[E]

### 1.3 音高 = MIDI key 存在 head[0] [E]

`CSMMsg::GetMidiKey` 0x100ac520：
```
if (this[0x68] == 1 && *(short*)(this+0x1e) != 0) return **(uchar**)(this+0x20);  // head[0]
else return 0;
```
- `this+0x1E` = ObjectCore.headLen（内存偏移），`this+0x20` = head 指针 [E]
- `CSMMsg::SetMidiKey` 0x100ac4d0 写入同一 `head[0]` [E]
- **结论：type 0x01 音符的 head[0] = MIDI key (0..127)**；这也解释了「type==1 且 headLen≠12 时补齐为 12 字节」（0x1007a490 末尾）[E]

### 1.4 ObjectCore 磁盘布局（含 +0x06 新字段）[E]

`CSMObject::Write` 0x1007a740 写 0xC 字节头（`local_14` 起）：
| 磁盘偏移 | 写入源 | 说明 |
|---|---|---|
| +00 u8 | `GetMsgNum(this+0x24) & 0xFF` | 子项数 childCount |
| +01 u8 | （未写，保留 local_14 高 3 字节初值 0） | **磁盘恒为 0**（Read 也从不读） |
| +02 u16 | `this+0x1C` | f2（连音比例，见 §1.2） |
| +04 u16 | `this+0x1E` | headLen |
| +06 u16 | `this+0x1E + 0xC` | **= headLen + 12，派生冗余长度**（Read 跳过，不读） |
| +08 u32 | `this+0x18` | f8 |

`CSMObject::Read` 0x1007aa20 只读 +00/+02/+04/+08，确认 +01 与 +06 在读取路径中被忽略 [E]。
子项 8 字节 = `u32 key, u8 embedded, u8 pad[3]`（Read 读 8 字节后仅看 `(char)local_20[1]`；Write 写 8 字节）[E]。
嵌入消息：`*(CSMObject**)(child+8) = parent`（**对象 +0x08 = 父指针**）与 `child[5] = parent[4]`（voice）[E]

### 1.5 鼓组 / 打击乐分支 [E]

`CSMMsg::SetParamFromMidiKey` 0x100aad60，`param_1`（第 1 个参数）为声部/谱号类型 1..8，case 8 为打击乐：
```
iVar3 = GetDrumTable(param_3);
*(ushort*)(this+0x5C) = ((*(ushort*)(iVar3+0x20CC+key*2) >> 8) & 0xF) + 1;   // → 消息头 +06
*(ushort*)(this+0x52) = ((*(ushort*)(iVar3+0x20CC+key*2) & 0x3F) - 0xD) * quarter;
this[0x76] = 0; MakeNoteMarkCtrl(this);
```
→ **消息头 +06 = 打击乐声部/鼓位置索引（1 基）**；+0x52 = 音高 Y 偏移 [E]
- case 1..7 为 7 种谱号类型，用 `local_44` 半音偏移表（`this+0xC → +0x9C → +8` 取全音符高度基准）计算 +0x52 [E]
- 半音偏移表（local_44 +0xC..+0x17）：`0,0,1,1,2,3,3,4,4,5,5,6` → **C D E F G A B 的半音序号** [E]
- 临时记号修正表（local_44 +0x00..+0x0B）：`0,1,0,1,0,0,1,0,1,0,1,0` → 由 `local_10 = key % 12` 决定是否升半音 [E]

### 1.6 其它已定位的音符属性函数（待细读）

| 地址 | 名称 | 关注点 |
|---|---|---|
| 0x100b29f0 | CSMMsg::SetNoteHeadType | 符头类型写入位置 |
| 0x100b2a90 | CSMMsg::SetTail | 符尾 |
| 0x100b2ba0 | CSMMsg::SetRestType | 休止符类型 |
| 0x100b2c00 | CSMMsg::SetToilThick | 连梁/粗线 |
| 0x100b2f50 | CSMMsg::ChangeNoteDirection | 符干方向 |
| 0x100b1370 | CSMMsg::CalcNoteRestKind | 音符/休止判定 |
| 0x100b0830 | CSMMsg::WhatIsAccidental | 变音记号 |
| 0x100b7fb0 | CSMMsg::GetRealNoteDur | 实际时值 |
| 0x10037ed0 | CSMMsg::SetTuplet | 连音符 |
| 0x10037ff0 | CSMMsg::SetSymbol | 符号 |
| 0x100ac570 | CSMMsg::GetVelocity | 力度 |

## 2. 消息类清单（engine.dll 导出名）[E]

| 地址 | 类 | 说明 |
|---|---|---|
| 0x100b7870 | CSMMsg::DrawMsg（基类） | 空实现 |
| 0x10094d80 | CSMDynamicMsg::DrawMsg | 力度记号，取 `CodeDyn[+0x5E]` 单字符 |
| 0x1009ad00 | CSMLyricMsg::DrawMsg | 歌词（阶段二） |
| 0x100a8a80 | CSMMetronomMsg::DrawMsg | 节拍器记号（+0x6E==1 时 DrawVersion1） |
| 0x100bfa70 | CSMStaffNameMsg::DrawMsg | 谱表名：head 指针 +0x20、headLen +0x1E |
| 0x100c2f70 | CSMTextMsg::DrawMsg | 文本框 TLV（阶段二） |
| — | CChordSymbol / CChordSurfix / CFretBoard / CFretInfo / CRhythm / CRtmData | 和弦族 |

`CSMDynamicMsg::DrawMsg` 使用 `CodeDyn[(uint)*(ushort*)(this+0x5E)]` 单字符 → **力度记号类型码在 MsgHdr +08（this+0x5E）** [E]

## 3. 任务 B-2：消息类型 → 绘制器 完整分派表 [E]

`CScoreView::SMDrawMsg` 0x1004aa00 是**唯一的按 type 分派 switch**（依据 `param_1[0x68]`，即 MsgHdr +00）：

| type | 绘制器（CScoreView::） | 语义（由绘制器名 + 内部符号表可得） |
|---|---|---|
| 0x01 | DrawNote | **音符** |
| 0x03 | DrawRest | **休止符** |
| 0x04 / 0x06 | DrawMultiText | **文本框**（渲染为 CSMTextMsg） |
| 0x05 | DrawMetronome | 节拍器记号 |
| 0x08 | DrawMark | 标记/记号 |
| 0x0c | DrawCoda | Coda（⊕ 记号） |
| 0x0d | DrawRolled_chord | 滚奏和弦（琶音） |
| 0x10 / 0x11 | DrawVabPedal | 踏板（Vab/延音） |
| 0x12 | DrawMeasTuplet | **小节级连音符（3 连音括弧）** |
| 0x13 | DrawCDCrescendo | 渐强/渐弱（crescendo） |
| 0x14 | DrawBeam | **连梁组** |
| 0x15 | DrawKeysign | **调号**（`codeAcci[+0x5E]`） |
| 0x16 | DrawFretboard | 吉他指板图 |
| 0x17 | DrawChordText | 和弦文字（旧式） |
| 0x18 | DrawMsgLine | 直线 |
| 0x19 | DrawTextMsg | **歌词**（CSMLyricMsg，阶段二） |
| 0x1b | DrawDynamic | **力度记号**（`CodeDyn[+0x5E]`） |
| 0x1f | DrawClef | **谱号** |
| 0x21 | DrawTrills | 颤音（tr） |
| 0x25 | DrawChord | **和弦**（同音组） |
| 0x26 | DrawEllipse | 椭圆/圆 |
| 0x27 | DrawRectangle | 矩形 |
| 0x28 | DrawRoundRectangle | 圆角矩形 |
| 0x29 | DrawN | 任意文字（N = 文本） |
| 0x2a | DrawGerneralFont | 通用字体字符（`codeSmallDigit[+0x1C]`） |
| 0x2b | DrawInversM | 倒 M（强音记号） |
| 0x2c | DrawLongrest | 长休止（多小节休止） |
| 0x2e | DrawSlur | **圆滑线（slur）** |
| 0x2f | DrawSingle_Msg | 换气记号 `codeBreath` |
| 0x30 | DrawSingle_Msg | 花音记号 `codeFlowerMark` |
| 0x34 | DrawSingle_Msg | 断句 `codeCesura` |
| 0x35 | DrawSingle_Msg | **小节反复记号**（`+0x5E`==1 → 一小节反复 `codeMeasOneRepeat`） |
| 0x36 | DrawSingle_Msg | 单字符记号 |
| 0x37..0x3a | DrawSingle_Msg | 滑音线 `codeSlid[0..3]` |
| 0x3c | DrawSingle_Msg | 上圈 `codeCircleUp` |
| 0x3d | DrawSingle_Msg | 下圈 `codeCircleDown` |
| 0x3e | DrawSingle_Msg | 大下圈 `codeBigCircleDown` |
| 0x42 | DrawMidiShortMsg | MIDI 短消息（原始 MIDI 事件） |
| 0x44 | DrawCurvedLine | 曲线 |
| 0x45 | virtual `vtable+0x18` | **和弦记号**（CChordSymbol 自身绘制） |
| 0x4a | DrawBezierLine | 贝塞尔曲线 |
| 0x09 / 0x0a | （不在此 switch）| 连音线家族：由 `CSMObject::Read` 注册到 tie/slur 表 |
| 0x3f / 0x40 | （文档级，不在此 switch）| 见 `docs/smc-format.md` §6 |

补充证据：
- 0x2a：`local_18[0] = *(uchar*)((int)&codeSmallDigit + *(ushort*)(param_1+0x1C) + 1)` → 用 **ObjectCore.f2 的偏移取值**（不是 head）[E]
- 0x35：`*(short*)(param_1+0x5E) == 1` 时改用 `codeMeasOneRepeat` [E]
- 0x36：无字符赋值（仅走通用路径），语义待定 [?]
- 0x09/0x0a/0x12 在 `CSMMsg::Read` 结尾被 `FUN_1006abb0(key, newkey)` 重新登记为引用映射 [E]（见 §4）

## 4. 任务 B-3：连音/引用型消息（0x09 / 0x0a / 0x12）[E]

`CSMObject::Read` 0x1007aa20 子项解析后：
```
if (child[0x68] ∈ {0x09, 0x0a, 0x12}) FUN_1006abb0(parent_key, child_key);
```
`CSMMsg::Read` 0x1007a490 在 AddMsgToMap 前也有同样处理 → 这三类消息的 **+0x18 与 +0x70 都指向「被连接对象」**：
- `CSMMsg::CreateFrom` 0x1006acd0 明确：子项若 embedded 且 type ∈ {9,0xa,0x12}，则
  - 若 `child+0x18 == child+0x70`（自指/未绑定）→ 两者都设为父对象 key；
  - 否则把 `child+0x18` 设为父对象 key，保留 `+0x70` 作为另一端引用 [E]
- 因此 **MsgHdr +20（对象 +0x70）与对象 +0x18 是「连音/圆滑线的两个端点键」** [E]
- 0x45（和弦记号）在 `CSMMsg::Write` 中把 `this+0x80`→`this+0x18`、`this[0x17c]<<8|this[0x180]`→`this+0x1c` 后才写 [E]

### 4b. 罕见边界情形（全语料 8451 文件）[E]

| 情形 | 计数 | 结论 |
|---|---|---|
| 0x19 headLen = 0（空文本） | 174 | 合法空歌词记录 [I] |
| 0x0a headLen = 18 | 7（6 种不同 head） | 非 `0x10+文本` 结构；内容形如 `01 00 00 00 0d 00 … 02 xx xx`，疑为旧结构/编辑残留 [I] |
| 0x09 / 0x12 / 0x2e headLen | 0 | 全部无 head，信息在消息头与端点键 [E] |
| 0x09 / 0x0a / 0x12 的 MsgHdr+20 | 绝大部分非 0 | 仅 7 条 0x0a 的 +20 为 0，与 headLen 18 的 7 条吻合 [E] |

### 4c. type 0x45（和弦）head 与名称 [E]

- head 长度两种：0（多数）与 100（部分，413/1244 抽样）。
- 长度 100 的 head 为**二进制缓存**（含运行期指针/标志字节），非稳定文本。
- 和弦可读名在 `ChordExtra.surfixName`（CStr）：实测 `" (major)"` 539、`"m"` 371、`"7"` 154、`"(major)"` 58、`"m6"` 9、`"m7"` 6、`"dim"` 4、`"9"` 2、`"dim7"` 1。
- `hasRhythm` 抽样 101/1244 为真。

## 5. 任务 B-4：音符绘制路径的字段使用 [E]

`CScoreView::DrawNote` 0x1004ec70：
| 读取 | 含义 |
|---|---|
| `param_1[0x69]` | **声部索引 0..8**，用作位掩码 `1<<voice` 与 `CSMCtrlTool+0x436`（隐藏声部位图）比较；等于 `ctrl+0x10`（当前声部）时强制显示 |
| `param_1 + 0x58` | **音符/字体缩放百分比**，默认 0x10(=16)；`SelectFont((size*100)>>4)` |
| `param_1 + 0x5e` | 时值指数（`<2` 时特殊处理符干方向） |
| `param_1 + 0x6e` | 标志位：bit3(=8)、bit9(=0x200)、bit10(=0x400) 影响 Y 定位分支 |
| `param_1 + 0x52` | 音高 Y 偏移 |
| `param_1 + 0x56` | 符干长度/宽度 |
| `param_1 + 0x70` | **符干方向/偏移**（<0 与 >0 两种朝向） |
| `param_1 + 0x50` | X 偏移 |
| `param_1 + 0x18`（对象）| 「连接类型」低字节=1 时特殊定位 |

`CScoreView::DrawHead` 0x1004faf0：
```
switch (*(ushort*)(param_1 + 0x5c)) {   // 符头类型
  case 0: 无符头
  case 1: codeStdHead[*(ushort*)(param_1+0x5e)]    // 标准符头，按 type 取字形
  case 2: codeCrossHead   (× 符头)
  case 3: codeSlashHead[...]  (斜线符头)
  case 4/5: codeBoxHead[1]/[0]  (方框符头)
  default: <100 时 DAT_101003ba[type]；>=100 用 ASCII 数字串（<0x6E 用 ('0'+type-0x34)，否则两位数字）
}
if (param_1[0x78] != 0) → 绘制 "(" 与 ")" 括号
附点：local_3c = param_1[0x77] & 0x7f; 最多 4 个点（type<0x6e）
```
- **MsgHdr +06（对象 +0x5C）= 符头类型**：`CSMMsg::SetNoteHeadType` 0x100b29f0 直接写 `this+0x5c`（值 7 映射为 0x1a）[E]
- **MsgHdr +05 低位半字节（对象 +0x77）低 7 位 = 附点数**；高位（0x80）另作他用 [E]
- **对象 +0x78（MsgHdr +01 高半字节）= 括号标志**：非 0 时绘制括号 [E]
- **对象 +0x6E bit2(0x4) = 符尾存在**：`CSMMsg::SetTail` 0x100b2a90 置/清 bit2 [E]

`CSMMsg::SetNoteHeadType` / `CSMMsg::SetTail` 对 type 0x14 / 0x25 **递归应用到所有子消息** [E]

## 5b. 音符 head（12 字节）字段表 [E]

由 `GetMidiKey`/`SetMidiKey`/`GetVelocity`/`SetVelocity`/`GetRealNoteDur`/`SetPlayTime`/`UpdateStartTime` 共同确定：

| head 偏移 | 类型 | 含义 | 证据 |
|---|---|---|---|
| +00 | u8 | **MIDI 音高 key (0..127)** | GetMidiKey/SetMidiKey 读写 `head[0]` |
| +01 | u8 | **力度 velocity (0..127)** | GetVelocity/SetVelocity 读写 `head[1]` |
| +02..+03 | u8×2 | ? （可能与变音/符头附加有关） | 未被上述函数触碰 [?] |
| +04..+07 | u32 | **时值（tick 数）** | `GetRealNoteDur` 读 `*(u32*)(head+4)`；`SetPlayTime` 以 `MulDiv(head+4,100,playTime)` 换算后回写 |
| +08..+0B | u32 | **起始时间偏移**（相对小节起点） | `UpdateStartTime` 写 `*(int*)(head+8) = 对象+0x5A - param_1` |
| +0C..+0F | — | 不存在：headLen 固定 12，Read 路径对 type==1 强制补齐到 12 并清零 +08..+0B | `CSMMsg::Read` 0x1007a490 |

- `GetRealNoteDur` 0x100b7fb0：`+0x6E & 1`（连音目标标志）置位时，沿同音高（`head[0]`）且 X 递增（`+0x50`）的后续音符累加 `head[4]`，实现连音时值合并 [E]
- `SetPlayTime` 0x100b76f0：`MulDiv(head+4, 100, +0x6A)` → `CalcPlayTime` → `MulDiv(+0x6A, prev, 100)` 回写 `head+4`；**0x25（和弦）递归把 `+0x1C` 与 `+0x77` 复制给子音符** [E]
- `UpdateStartTime` 0x10037a70：type {1,3} 写 `this+0x6C` 与 `this+0x5A`；type 0x14 依次累加子项播放时间；type 0x25 把同一 start 传给子音符 [E]

## 5c. Child 描述符 byte +4 的真实语义 [E]

`CSMObject::AddMsg` 0x100bad70 / `InsertMsg` 0x100baec0 写入子项描述符：
```
*(uchar*)(desc+4) = param_2;    // 调用方传入
*desc = child_key;
```
- 因此 **Child.byte[4] 是「引用角色/嵌入标志」**，取值由调用方给出，不只 0/1 [E]
- `GetTieIndex` 0x10037d90 用 `byte[4] == param_1` 匹配 **tie 类型码**；`GetSlurIndex` 0x10037e20 用 `key == param_1 && byte[4] == param_2` 匹配 **slur 端点** [E]
- `CSMObject::Write` 0x1007a740 原样回写该字节，`byte[4] != 0` 时才递归写嵌入消息 [E]
- 结论：**byte[4] = 0 表示「仅引用」；非 0 表示「嵌入对象，且该值记录引用角色」** [E]

## 7. 任务 B-5：Meas / Staff / System 结构 [E]

### 7.1 Meas（CSMMeas::Read 0x100798e0）

`ObjectCore'`：本函数**不使用** `CSMObject::Read`，而是手工读 0xC 字节：
```
+00 u8  childCount        ; （循环内可自减，丢弃 byte[4]==0 的引用项）
+02 u16 f2 → 对象+0x1C
+04 s16 headLen → SetHead（head 至少存在; >0 才复制）
+08 u32 f8 → 对象+0x82 = 低 16 位; 对象+0x18 = 高 16 位（有符号扩展）
head[headLen]
Child × childCount        ; 同通用格式
```
**与通用 ObjectCore 的差别**：Meas 的 +04 是 `s16`（通用为 u16），+06（派生长度）未使用，且丢弃 `byte[4]==0` 的纯引用项 [E]。

MeasTail（0x60 字节，读入后按 `local_44[n]` 索引）→ 对象字段：

| Tail 偏移 | → 对象 | 含义 | 证据 |
|---|---|---|---|
| +00 u8 | +0x81 | 拍号/文本模式（==3 时拍号用字符串描述）| CalcWholeCount 分支 |
| +13 u8[0x10] | +0x54 | **拍号文本串**（CString，模式 3 使用）| `CString::CString(local_2c, this+0x54)` |
| +33 u8[0x10] | +0x98 | 第二文本串 | memcpy 0x10 |
| +44 | +0x7A | ? | |
| +45 | +0x7B | ? | |
| +46 | +0x7C | ? | |
| +48 | +0x84 | ? | |
| +49 | +0xA8 | ? | |
| +4A | +0x8C | ? | |
| +4B | +0x8D | ? | |
| +4C | +0x8E | ? | |
| +4D | +0x92 | ? | |
| +4E u16 | +0x94 | ? | |
| +50 u16 | +0x96 | ? | |
| +52 s16 | +0x4C | ? | |
| +56 s16 | +0x50 | **拍号分子** | CalcWholeCount |
| +58 s16 | +0x52 | **拍号分母** | CalcWholeCount（switch 1/2/4/8/0x10/0x20/0x40/0x80）|
| +5A u8 | +0x7D | ? | |
| +5C u8 | +0x7E | ? | |
| +5E u16 | +0x90 | 显示开关（受 `doc+0x9c`→`+0x999` 全局标志控制，为 0 时清零）| |

读取后：
- 拍号分子或分母为 0 → 强制 4/4 [E]
- `CalcWholeCount`（见 7.2）
- 对 **9 个声部**（0..8）依次 `UpdatePlayTime(i)` 和 `UpdateStartTime(i,0,0,0)` → 9 声部上限 [E]
- 遍历子项：对 type {0x14,0x25} 且无子项者 **从数组删除**；对 {0x14,0x25} 与 {0x01,0x03} 调用 `ChangeParent` + `AddUpDownMsgArray` [E]

### 7.2 长小节数（CSMMeas::CalcWholeCount 0x1003a4d0）[E]

```
doc_whole = *(int*)(parent+0xA0)              # 全音符 tick 基数
if mode(+0x81) == 3:                          # 拍号用文本（如 6/8 复合拍）
    分母 = *(short*)(this+0x52) != -1 ? this+0x52 : ?
    分子 = *(short*)(this+0x50) != -1 ? this+0x50 : GetStringValue(文本)
    this+0x4E = doc_whole * 分子 * 4 / 分母
    每段 tick = func(分母) 表（1→<<2, 2→<<1, 4→(分子==4?<<1:1), 8→>>1, 16→>>2, 32→>>3, 64→>>4, 128→>>5）
    然后循环解析文本串，把每段 tick*段长 追加到 CWordArray(+0xEC)
else:
    this+0x4E = doc_whole * 分子 * 4 / 分母
    每段 tick 表（8→whole+whole/2, 16→(whole>>1)+(whole>>2), 32→(>>2)+(>>3), 64→(>>3)+(>>4), 128→(>>4)+(>>5)）
    段数 = max(1, this+0x4E / 段tick)，写入 CWordArray(+0xEC)
```
- **+0x4E = 本小节总 tick**；**+0x0EC CWordArray = 连音符分段表** [E]

### 7.3 Staff（CSMStaff::Read 0x10079030）

`ObjectCore` 后读 **0x70** 字节 StaffTail（`_Src[n]`）：

| Tail 偏移 | → 对象 | 含义 |
|---|---|---|
| +00 char[0x20] | +0x74 | **谱表名**（UTF 编码文本，0x20 定长）|
| +20 u8 | +0x4C | 谱表序号？ |
| +21 u8 | +0x4D | **谱号标志**（DrawHead 用 `staff+0x4D == 5` 判定打击乐/特殊谱表）|
| +22 u8 | +0x70 | ? |
| +23 u8[8] | +0x50 | 调号表（8 字节）|
| +33 u8[8] | +0x58 | 调号表（8 字节）|
| +3B u8[8] | +0x68 | 调号表（8 字节）|
| +43 u8[8] | +0x60 | 调号表（8 字节）|
| +4B u8 | +0xAC | ? |
| +4C u8[3] | +0x71 | ? |
| +54 u16 | +0x4E | ? |
| +6C i32 | — | **nMeas：小节个数**（循环创建 CSMMeas）|

- 读取后 `obj+0x1C`（音量/比例）不在 [0x32, 200] 内则置 100 [E]
- 子项中查找 **type 0x49**（谱表名消息）；找不到则 `SetStaffNameToMsg(staff, staff+0x74, "","","", 0,0)` 生成 [E]

### 7.4 System（CSMSystem::Read 0x10078730）[E]

`ObjectCore` 后读 8 字节（`psVar7`）：
```
+00 s16  nStaff1  → 读 nStaff1 个 Staff（vtable 参数 3），挂到 this+0x4C
+02 s16  nStaff2  → 读 nStaff2 个 Staff（vtable 参数 4），挂到 this+0x60
+04 u32  → this+0xA0          # 全音符 tick 基数（CalcWholeCount 用）
```
附：读取尾部遍历 `this+0x74`（消息映射表），对 type {0x09,0x0a,0x12} 的两个端点键（+0x18、+0x70）执行 `GetKey` 重映射；超出映射表范围则置 0 [E]

## 6. 消息头语义汇总（供规范使用）

| MsgHdr 磁盘偏移 | 对象偏移 | 语义 | 状态 |
|---|---|---|---|
| +00 | +0x68 | 类型 | Confirmed |
| +01 高4 | +0x78 | 括号标志 | Confirmed |
| +01 低4 | +0x69 | **声部索引 0..8** | Confirmed |
| +02 | +0x58 | 缩放百分比（默认 16） | Confirmed |
| +03 | +0x74 | ? | Unknown |
| +04 | +0x75 | ? | Unknown |
| +05 高4 | +0x76 | 符干/标记状态（0..3） | Confirmed（写法）/Inferred（命名）|
| +05 低4 | +0x77 | 附点数（低 7 位） | Confirmed |
| +06 | +0x5c | 符头类型 | Confirmed |
| +08 | +0x5e | **时值指数 / 字符索引**（休止符、力度、调号、节拍器等均用它作查表下标）| Confirmed |
| +0A | +0x6e | 标志位集合（bit2 符尾、bit3、bit4 不发声、bit9、bit10 等）| Confirmed（用法）|
| +0C | +0x60 | 绘制缓存（外接矩形） | Confirmed（非文件语义）|
| +0E | +0x66 | 绘制缓存 | Confirmed（非文件语义）|
| +10 | +0x62 | 绘制缓存 | Confirmed |
| +12 | +0x64 | 绘制缓存 | Confirmed |
| +14 | +0x5a | ? | Unknown |
| +16 | +0x50 | 相对 X 偏移 | Confirmed |
| +18 | +0x52 | 音高 Y 偏移 | Confirmed |
| +1A | +0x54 | 外接矩形 L（缓存） | Confirmed |
| +1C | +0x56 | 外接矩形 R / 符干长度 | Confirmed（用法）|
| +20 | +0x70 | **端点引用键**（连音/圆滑线；和弦另用）| Confirmed |
| +24 | +0x14 | 本对象键（经 GetKey 重映射）| Confirmed |
| +28 | +0x4c | 颜色/样式（DrawDynamic 用作 `SetTextColor` 参数）| Inferred |
