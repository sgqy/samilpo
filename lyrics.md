# SMC 歌词消息（Msg type 0x19）与关联机制

> 凡例见 `smc-format.md` §0（知识评级 `[E]`/`[I]`/`[?]`/`[C]`；数据类型为 Rust 风格）。
> 结论：type **0x19 = `CSMLyricMsg`**，一条记录 = 一个歌词音节单元，**内嵌于 type 0x01 音符消息的子对象列表中**。
> 文本用 889F 编码（见 `encoding.md`）。head 字段表已由**汇编级证据**闭合（第四阶段）。

## 1. 类型身份的直接证据

| 证据 | 地址 | 内容 | 评级 |
|---|---|---|---|
| 绘制类 | engine.dll 0x1009AD00 | `CSMLyricMsg::DrawMsg`，被 `CScoreView::DrawTextMsg` 0x1005EBB0 调用 | [E] |
| 视图分发 | engine.dll 0x1005EBB0 | 构造 `CSMLyricMsg` 副本并调用 DrawMsg；调用者按消息 type 分发 | [E] |
| 类构造 | engine.dll 0x1009AC20 | `CSMLyricMsg::CSMLyricMsg`，设置 vftable（0x100E52B8） | [E] |
| 编辑器类 | engine.dll 0x100C9B70 | `CTempLyricMsg`（含内嵌 `CTempMsg`，位于 `this+0x80`） | [E] |
| 转换器 | engine.dll 0x10030010 | `CSMDoc::GulsamToSMC_Lyrics`：**明确设置 type = 0x19**，head 长度 = 文本长度 + 0x10 | [E] |
| 转换器 | engine.dll 0x10025170 | `CSMDoc::EncToSMC_Lyric`：另一写入路径 | [E] |

`GulsamToSMC_Lyrics` 中 `local_30 = 0x19`（写入消息头 type 字节）与
`local_d0 = 文本字节数 + 0x10`（写入 head 长度字段）是「head = 0x10 + 文本」的结构性证据 [E]。

## 2. 消息头与 head 的关系

0x19 与所有消息一样使用 **0x2C 字节消息头 + ObjectCore**（见 `smc-format.md` §5.1、§6.1），
私有数据放在 ObjectCore 的 head 负载里：

```
Msg :=
    hdr  : MsgHdr (0x2C bytes)
    core : ObjectCore          ; childCount, reserved, f2, headLen, derivedLen, f8, head, children
```

歌词的 `headLen = 0x10 + 文本字节数`，**9129/9129 条验证全等** [E]。

## 3. 歌词 head 字段表（第四阶段闭合）

| head 偏移 | 类型 | 含义 | 评级 |
|---|---|---|---|
| +0x00 | `u16` | **字体索引**（交给 `CFontDatas::GetFontName`） | [E] |
| +0x02 | `u8` | **样式位**：bit0 粗体、bit1 斜体、bit2 下划线 | [E] |
| +0x03 | `u8` | **未初始化残留**（无访问） | [E] |
| +0x04 | `u16` | **字号**；为 0 时按 13 处理 | [E] |
| +0x06 | `u16` | **未初始化残留**（无访问） | [E] |
| +0x08 | `COLORREF` (`u32`) | **文字颜色**（交给 `SetTextColor`） | [E] |
| +0x0C | `u8` | **文本字节长度** | [E] |
| +0x0D | `u8` | **未初始化残留**（长度 dword 高字节） | [E] |
| +0x0E | `u8` | **未初始化残留** | [E] |
| +0x0F | `u8` | **未初始化残留** | [E] |
| +0x10 | `[u8; head[0x0C]]` | **歌词文本**（889F 编码） | [E] |

### 3.1 汇编级证据（`CSMLyricMsg::DrawMsg` 0x1009AD00）

```
SUB  ESP, 0x104
PUSH 0x10 / LEA ECX,[EBP-0x20] / CALL memcpy   ; head 前 16 字节 → EBP-0x20
MOV  CX, word ptr [EBP-0x20]                   ; head+0x00 → CFontDatas::GetFontName
MOV  EAX, dword ptr [EBP-0x1E] ; AND EAX,0x1   ; head+0x02 → 粗体
                                  AND ECX,0x2  ;             → 斜体
                                  AND EDX,0x4  ;             → 下划线
MOVSX ECX, word ptr [EBP-0x1C] ; TEST/JNZ      ; head+0x04 → 字号
                                  MOV word[EBP-0x1C], 0xD      ; 0 → 13
MOV  EAX, dword ptr [EBP-0x18]                 ; head+0x08 → 颜色
MOV  EAX, dword ptr [EBP-0x14] ; AND EAX,0xFF  ; head+0x0C dword 低字节 = 文本长度
MOV  EAX, [EDX+0x20] ; ADD EAX, 0x10           ; 文本指针 = head+0x10
```

- 读取侧**未访问** `EBP-0x1D`(head+0x03)、`EBP-0x1A`(head+0x06)、`EBP-0x19`(head+0x07)、
  `EBP-0x13/-0x12/-0x11`(head+0x0D/+0x0E/+0x0F) [E]。
- 写入侧 `EncToSMC_Lyric` 0x10025170 的 head 缓冲基址为 `EBP-0xC8`，仅写
  `word[EBP-0xC8]`（字体）、`byte[EBP-0xC6]=0`（样式）、`word[EBP-0xC4]`（字号）、
  `dword[EBP-0xC0]=0`（颜色）、`byte[EBP-0xBC]=strlen&0xFF`（长度低字节）；
  **未写** head+0x03/+0x06/+0x07/+0x0D/+0x0E/+0x0F [E]。
- 两侧的未访问/未写入集合**完全一致** → 这 6 个字节确认为栈残留。

### 3.2 语料验证（`tools/_probe_p4_lyrichead.py`）

400 文件抽样、30353 条歌词：

| 观测 | 结果 | 结论 |
|---|---|---|
| 字体索引 | {1: 26253, 2: 1915, 5: 923, 6: 554, 3: 546, 7: 162} | 与字体表索引一致 [E] |
| head+0x02 | {0: 30254, 1: 99} | 样式位 [E] |
| head+0x04 | {13: 30136, 14: 140, 12: 74, 0: 3} | 字号 [E] |
| head+0x06 | 317 个不同值 | 栈残留 [E] |
| head+0x0D..+0x0F | 535 种组合，仅 6089 条全 0 | 栈残留 [E] |
| `headLen == 文本长度 + 0x10` | 24264/24264（非空文本） | 结构成立 [E] |

## 4. 绘制流程

`CSMLyricMsg::DrawMsg` 0x1009AD00 [E]：

1. 检查 `headLen(+0x1E) != 0`、head 指针(+0x20) 非空、`CTool` 参数非空；否则返回空尺寸。
2. `memcpy` head 前 0x10 字节到栈局部；文本指针 = `head + 0x10`。
3. 字号 = `head+0x04`（0 → 13）；`lfHeight = -MulDiv(size, dpiY, 0x48)`。
4. `lfCharSet = 0x88`（HANGUL_CHARSET）；样式位映射到 `lfWeight`(0x1C/0x190)/`lfItalic`/`lfUnderline`。
5. `CFontDatas::GetFontName(字体索引)` 取字体名。
6. 颜色 = `head+0x08`；若消息声部(`obj+0x69`) 与 `ctrl+0x10`（当前声部）不同，则改用 `ctrl+0x7C` 的颜色。
7. `MyDrawTextOutW` 输出文本（字节长度 = `head+0x0C`）。
8. 回写实际外接矩形到消息对象 `+0x66`(L) / `+0x60`(T) / `+0x64`(R) / `+0x62`(B)。

## 5. 位置与声部字段（在消息头，非 head）

`CSMMsg::Read` 0x1007A490 把 MsgHdr 复制到对象偏移；歌词使用：

| MsgHdr 偏移 | 对象偏移 | 类型 | 含义 | 评级 |
|---|---|---|---|---|
| +0x16 | +0x50 | `i16` | 相对 X 偏移（与所在一行/视图相加） | [E] |
| +0x18 | +0x52 | `i16` | 谱表/声部索引（查该谱表 Y 坐标；`-0x8000` = 无该谱表） | [E] |
| +0x1A / +0x1C | +0x54 / +0x56 | `i16` | 绘制后外接矩形（缓存，非文件语义） | [E] |
| +0x24 | +0x14 | `u32` | 本对象 key（经 `CSMSystem::GetKey` 重映射） | [E] |

`CScoreView::DrawTextMsg` 0x1005EBB0 计算屏幕位置：
`x = view+0xF4 + msg+0x50 + DAT_10101108/2`，`y = view+0x58 + StaffYTable[msg+0x52]`；
若 `StaffYTable[msg+0x52] == -0x8000` 则跳过绘制 [E]。

## 6. 歌词与音乐结构的关联

### 6.1 关联方式 = 对象包含

歌词记录**始终**作为 type 0x01 音符消息的嵌入子对象出现：

- 抽样 40 文件、2961 条歌词：父消息类型分布 = `{0x01: 2961}`，即 100% 的父对象都是音符 [E]。
- 每个音符携带 0 或 1 条歌词：抽样 3259 个音符中带 1 条 3259、带 0 条 230 [E]。
- 「哪个音符对应哪个歌词」由**包含关系**本身决定；`CSMMsg::Read` 递归读到嵌入消息即建立
  父子指针（对象 +0x08 = 父对象）[E]。

### 6.2 key 相邻分配

- `lyric_key − note_key` 分布：**+1 占 3000、+2 占 259**（抽样 3259 条）[E]。
- 说明分配器按「音符先、歌词后」发放 key；但这不是查找依据（包含关系才是）[I]。

### 6.3 一行歌词的顺序

同一行按嵌入顺序拼接即可还原文本。示例：`500KFS-0041.smc` 共 375 条歌词：

```
바다－물－우에갈매기날구－요정든님－배머－리에옷자락날린－다…
```

（`－` = U+FF0D，由码位 `F0 41` 映射；语料中用作分句/延长标记 [I]）[E]

### 6.4 空歌词 / 延长 / 换行

- **无歌词的音符**：该音符没有 0x19 子对象（不写占位记录）[E]。
- **空文本记录**：`headLen` 最小为 0x10（`+0x0C = 0`）；全语料 174 条 [E]。
- **延长/连字符**：作为普通字符存在（如 `－`），无独立「延长标记」记录 [I]。
- **换行/分段**：歌词记录不含换行；分段由所依附音符所在小节/行决定 [I]。
- **跨小节/跨页**：歌词挂在音符上，自动跟随；歌词自身不携带页码或行号 [?]。

## 7. 相邻结构：文本框 type 0x06（`CSMTextMsg`）

同一批文本亦以 type 0x06 出现（曲名/作者/速度/（후렴）等），head 为**标签-长度-值（TLV）**串，
1991/1991 条记录解析成功 [E]。

标签表（来自 `CSMTextMsg::DrawMsg` 0x100C2F70 的 switch）[E]：

| 标签 | 负载类型 | 含义 | 语料出现次数 |
|---|---|---|---|
| 0x01 | `i16` | 对齐：−2 左、−1 右、1 居中 | 1985（−2:1981, 1:4） |
| 0x02 | `u16` | 字体索引 | 5190 |
| 0x03 | `u8` | 样式（bit0 粗体、bit1 斜体、bit2 下划线） | 5161 |
| 0x04 | `u16` | 字号（默认 13） | 5196 |
| 0x05 | `[u8; 4]` | 未知（跳过） | 1983 |
| 0x06 | `u16` 长度 + 文本 | 文本段（889F） | 5260 段 |
| 0x07 | `[u8; 4]` | 未知（跳过） | 5260 |
| 0x09 | `u16` | 缩进（按 dpi 换算） | 433 |
| 0x0A | 无 | 换行 | 2280 |

示例：`01 FE FF | 02 03 00 | 03 00 | 04 0C 00 | 05 00 00 00 00 | 07 00 00 00 00 | 06 0A 00 <10 字节文本>`
→ 左对齐、字体 3、字号 12、文本 `보통속도로` [E]。

**注意**：0x19 的 head **不是** TLV，而是固定 0x10 字节头 + 文本（见 §3）；两者都经
`CKCConv` / `MyDrawTextOutW` 绘制，但结构不同 [E]。

## 8. 更正记录

| 阶段 | 原结论 | 现结论 | 依据 |
|---|---|---|---|
| 一 | 0x19 疑似歌词 | 确认 = `CSMLyricMsg`，完整字段表 | 0x1009AD00 / 0x10030010 [E] |
| 一 | MsgHdr 字段映射（+0x14→+0x5A 等） | **正确，无需更正** | `CSMMsg::Read` 复核 [E] |
| 一 | 0x19 head 通常 18 字节 | `head = 0x10 + 文本字节数`；18 只是「1 个双字节音节」的常见值 | `GulsamToSMC_Lyrics` [E] |
| 二 | head+0x02/+0x04 归属不明（按统计给出） | **闭合**：+0x02 = `u8` 样式、+0x04 = `u16` 字号 | `DrawMsg` 汇编（第四阶段）[E] |
| 二 | head+0x06/+0x0D/+0x0E/+0x0F 含义未知 | **闭合**：均为未初始化栈残留，无语义 | 读写两侧汇编集合一致 [E] |

## 9. 未决项

1. 未映射 889F 码位在歌词中的确切来源（私人字形或符号）：见 `encoding.md` §8 [?]。
2. 歌词的行分组规则（如何判定换行/对齐）：需分析 `CSMDoc::GetRealRectOfLyrics` 0x10003D40
   的调用者与绘制循环 [?]。
