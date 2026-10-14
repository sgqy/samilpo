# SMC 布局结构（第三阶段）

> 本文件记录 System / Staff / Meas / Page / Block 的结构与坐标、排版数据。
> 记号 `[E]` 直接证据 / `[I]` 推断 / `[?]` 未知。地址属 `engine.dll`（基址 0x10000000）。

## 1. 层次结构

```
Body
├─ System（恒为 1 个）
│  ├─ Staff[]（类型 3，上组）      sys+0x4C
│  └─ Staff[]（类型 4，下组）      sys+0x60
│     └─ Meas[]（每谱表 nMeas 个）
│        └─ Msg[]（小节内消息树）
├─ DocHdr（10 字节）
├─ Msg × 3（文档级）
└─ Page[]（pageCount 个）
   ├─ Block[]（nBlockA）
   ├─ Block[]（nBlockB）
   └─ Msg[]（页面级消息）
```

- 语料中每个文件恰好 **1 个 System** [E]。
- 每小节最多 **9 个声部**（`CSMMeas::Read` 对 i=0..8 调用 `UpdatePlayTime`/`UpdateStartTime`）[E]。

## 2. System（`CSMSystem::Read` 0x10078730）

```
System :=
  ObjectCore                      ; head 负载
  s16 nStaff1                     ; 上组谱表数 → sys+0x4C
  s16 nStaff2                     ; 下组谱表数 → sys+0x60
  u32 wholeTick                   ; 全音符 tick 基数 → sys+0xA0
  Staff × nStaff1                 ; 每项 vtable 参数 3（上组）
  Staff × nStaff2                 ; 每项 vtable 参数 4（下组）
```

- 读取结束后遍历 `sys+0x74` 消息映射表，对 type {0x09,0x0a,0x12} 的两个端点键（+0x18、+0x70）做 `GetKey` 重映射；越界置 0 [E]。
- 结束后重置 `sys+0x9c` → +0xC24/+0xC28 [E]。

## 3. Staff（`CSMStaff::Read` 0x10079030）

```
Staff := ObjectCore, StaffTail(0x70), Meas × nMeas
```

| Tail 偏移 | 长度 | → 对象 | 含义 |
|---|---|---|---|
| +00 | 0x20 | +0x74 | **谱表名**（889F 文本，定长） |
| +20 | 1 | +0x4C | 谱表序号 |
| +21 | 1 | +0x4D | **谱号类别**（2/3 = 打击乐或特殊谱表，见 §6） |
| +22 | 1 | +0x70 | ? |
| +23 | 8 | +0x50 | 调号数组 1 |
| +33 | 8 | +0x58 | 调号数组 2 |
| +3B | 8 | +0x68 | 调号数组 3 |
| +43 | 8 | +0x60 | 调号数组 4 |
| +4B | 1 | +0xAC | ? |
| +4C | 3 | +0x71 | ? |
| +54 | 2 | +0x4E | ? |
| +6C | 4 (i32) | — | **nMeas：小节个数** |

- 读取后 `obj+0x1C`（音量/比例）不在 [0x32, 200] 内 → 置 100 [E]。
- 查找子项中 type **0x49**（谱表名消息）；缺失则 `SetStaffNameToMsg` 生成 [E]。

## 4. Meas（`CSMMeas::Read` 0x100798e0）

### 4.1 核心头（与通用 ObjectCore 的差异）

```
MeasCore :=
  u8  childCount        ; +0
  u8  ?                 ; +1（不读）
  u16 f2                ; +2 → 对象 +0x1C（连梁粗度/比例）
  s16 headLen           ; +4（通用为 u16）
  u16 ?                 ; +6（不读；通用为 headLen+12 派生值）
  u32 f8                ; +8 → 对象 +0x82（低 16 位）、对象 +0x18（高 16 位）
  u8  head[headLen]
  Child × childCount
```

差异说明：Meas 的 headLen 按 **s16** 解释；`+06` 未使用；`role == 0` 的纯引用子项被**丢弃** [E]。

### 4.2 尾块（0x60 字节）

| Tail 偏移 | → 对象 | 含义 | 状态 |
|---|---|---|---|
| +00 | +0x81 | 拍号模式（==3 → 拍号用文本） | Confirmed |
| +13 | +0x54 | 拍号文本串（CString） | Confirmed |
| +33 | +0x98 | 第二文本串 | Inferred |
| +44 | +0x7A | ? | Unknown |
| +45 | +0x7B | ? | Unknown |
| +46 | +0x7C | **调号类型**（==8 → 无调号） | Confirmed（`WhatIsAccidental`） |
| +48 | +0x84 | ? | Unknown |
| +49 | +0xA8 | ? | Unknown |
| +4A | +0x8C | ? | Unknown |
| +4B | +0x8D | ? | Unknown |
| +4C | +0x8E | ? | Unknown |
| +4D | +0x92 | ? | Unknown |
| +4E | +0x94 | ? | Unknown |
| +50 | +0x96 | ? | Unknown |
| +52 | +0x4C | ? | Unknown |
| +56 | +0x50 | **拍号分子** | Confirmed |
| +58 | +0x52 | **拍号分母** | Confirmed |
| +5A | +0x7D | **调号符号**（1 = 降号序列，否则升号） | Confirmed（`WhatIsAccidental`） |
| +5C | +0x7E | **调号个数** | Confirmed |
| +5E | +0x90 | 显示开关（受全局标志 `doc+0x9c`→`+0x999` 控制） | Confirmed |

### 4.3 拍号相关（`CalcWholeCount` 0x1003a4d0）

```
docWhole          = doc+0xA0
tickPerMeas(+0x4E)= docWhole * 分子(+0x50) * 4 / 分母(+0x52)
```

- 分子/分母为 0 → 强制 4/4 [E]。
- 分母取值 {1,2,4,8,16,32,64,128}（`switch`），决定每段 tick。
- 分段结果（含连音符时长）写入对象 `+0xEC` 的 `CWordArray` [E]。

全语料统计（8451 文件）：

| 拍号分子 | 计数 | 拍号分母 | 计数 |
|---|---|---|---|
| 4 | 82504 | 4 | 109848 |
| 6 | 33703 | 8 | 48687 |
| 3 | 16248 | 2 | 1504 |
| 12 | 12048 | 16 | 2 |
| 2 | 9441 | | |
| 9 | 4433 | | |
| 5 | 1137 | | |
| 18 | 318 | | |
| 10 | 191 | | |

### 4.4 读取后的处理

1. 拍号 0 → 4/4。
2. `CalcWholeCount`。
3. 9 个声部 `UpdatePlayTime(i)` / `UpdateStartTime(i,0,0,0)`。
4. 子项整理：type {0x14,0x25} 空则删；{0x14,0x25,0x01,0x03} → `ChangeParent` + `AddUpDownMsgArray`。

## 5. Page（`CSMPage::Read` 0x1007bbf0）

```
Page :=
  s16 nBlockA          ; 块数组 A → page+0x04
  s16 nBlockB          ; 块数组 B → page+0x18
  s16 nPageMsg         ; 页面级消息数 → page+0x2C
  s16 ?                ; （第 4 个 s16）
  RECT (4×i32, 16 字节) ; → page+0x7C
  Block × nBlockA
  Block × nBlockB
  Msg   × nPageMsg
```

- Block 归属：`page+0x04`（A 组）与 `page+0x18`（B 组）[E]。

## 6. Block（`CSMBlock::Read` 0x1007b550 / `Write` 0x1007b020）

Block 描述谱面的一**排版行**（system row）。

```
BlockHdr (0x1C):
  +00 u8   type        ; 1 → 从 System 第一组（+0x4C）取谱表；否则第二组（+0x60）
  +01 u8   nStaves
  +02 s16  f2          ; 小节坐标个数 = f2 + 1（→ +0x3A）
  +04 s16  → +0x38     ; 起始小节号
  +08 u8   nPts
  +0C RECT(16)         ; → +0x90
StaffRef × nStaves (5 字节/项):
  u8  staffIdx         ; 在 System 组内的索引
  u16                  ; → +0xB4 数组（每谱表一个）
  u16                  ; → +0x7C 数组（默认 0xFFEC）
u16 × (f2 + 1)         ; 小节 X 坐标（首项归一化，读取时整体平移）
(i32, i32) × nPts      ; 谱表名位置点
```

- `Write` 的 `_Size = nStaves*5 + 2 + f2*2 + nPts*8`；与 `Read` 精确一致 [E]。
- 读取时若 `nStaves` 超过对应 System 组的谱表数 → 返回失败 [E]。
- 归一化：读取后取第一个坐标 `uVar4`，从区块 RECT 左边界扣除，并把所有坐标减去 `uVar4` [E]。
- `MakeStaffNameRect` 在 `nPts > 0` 时生成谱表名矩形 [E]。

全语料 `(nStaves, f2, nPts)` 分布（前 12）：

| (nStaves, f2, nPts) | 计数 |
|---|---|
| (1, 4, 0) | 25920 |
| (1, 3, 0) | 8805 |
| (1, 5, 0) | 3742 |
| (1, 2, 0) | 928 |
| (1, 6, 0) | 920 |
| (1, 7, 0) | 186 |
| (1, 1, 0) | 46 |
| (1, 4, 1) | 45 |
| (1, 8, 0) | 43 |
| (2, 4, 0) | 26 |
| (2, 4, 2) | 20 |
| (1, 3, 1) | 16 |

→ 语料以**单谱表行**为主，偶见双谱表行与带点（nPts>0）的行 [E]。

## 7. 坐标与比例

| 量 | 位置 | 说明 |
|---|---|---|
| 页面版式 | `CSMFileInfo`（0x20 字节） | `SetLogicPageInfo(POINT, RECT, short×4, …)` [I] |
| 谱面基准单位 | `doc+8`（全局 `DAT_10100fb8`） | 半线间距/基准字号 [I] |
| 基线 Y 表 | 视图 `+0x58` 起（每谱表一项） | `StaffYTable[MsgHdr+18]`；值 `-0x8000` = 无该谱表 [E] |
| X 偏移 | `MsgHdr+16`（+0x50） | 相对行起点 [E] |
| 音高 Y | `MsgHdr+18`（+0x52） | 负值向上；`MulDiv(+0x52, zoom, 100)` 换算 [E] |
| 缩放 | `MsgHdr+02`（+0x58） | 百分比，默认 16；`SelectFont((v*100)>>4)` [E] |

## 8. 未决项

1. Meas 尾块 +44..+52、+4E/+50 等字段语义 [?]。
2. Block 的 A 组 / B 组差异（`type` 字段与 System 两组谱表的选择规则已明确，但两组数组的应用场景未定）[?]。
3. `CSMFileInfo` 12 个 s16 与 2 个 u32 的精确含义 [?]（`SetLogicPageInfo` 为入口）。
4. 谱表名位置点（nPts）的坐标系与使用条件 [?]。
