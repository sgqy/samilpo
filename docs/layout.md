# SMC 布局结构（System / Staff / Meas / Page / Block）

> 凡例见 `docs/smc-format.md` §0（知识评级 `[E]`/`[I]`/`[?]`/`[C]`；数据类型为 Rust 风格）。
> 地址属 `engine.dll`（基址 `0x10000000`）。

## 1. 层次结构

```
Body
├─ System（恒 1 个）
│  ├─ staff1: [Staff]            ; 类型 3（上组），sys+0x4C
│  └─ staff2: [Staff]            ; 类型 4（下组），sys+0x60
│     └─ meas: [Meas]            ; 每谱表 nMeas 个
│        └─ msgs: [Msg]          ; 小节内消息树
├─ DocHdr（10 字节）
├─ Msg × 3                       ; 文档级
└─ page: [Page]（pageCount 个）
   ├─ blockA: [Block]
   ├─ blockB: [Block]
   └─ msgs:   [Msg]
```

- 语料中每文件恰好 **1 个 System** [E]。
- 每小节最多 **9 个声部**（`CSMMeas::Read` 对 i = 0..8 调用 `UpdatePlayTime`/`UpdateStartTime`）[E]。

## 2. System（`CSMSystem::Read` 0x10078730）

```
System :=
    core      : ObjectCore
    nStaff1   : i16                ; 上组谱表数 → sys+0x4C
    nStaff2   : i16                ; 下组谱表数 → sys+0x60
    wholeTick : u32                ; 全音符 tick 基数 → sys+0xA0
    staff1    : [Staff; nStaff1]   ; vtable 参数 3
    staff2    : [Staff; nStaff2]   ; vtable 参数 4
```

- 读取结束后遍历 `sys+0x74` 消息映射表，对 type {0x09,0x0A,0x12} 的两个端点键（+0x18、+0x70）
  执行 `GetKey` 重映射；越界置 0 [E]。
- 结束后重置 `sys+0x9C` → +0xC24/+0xC28 [E]。

## 3. Staff（`CSMStaff::Read` 0x10079030）

```
Staff := ObjectCore, tail: StaffTail (0x70 bytes), meas: [Meas; nMeas]
```

| Tail 偏移 | 类型 | → 对象 | 含义 | 评级 |
|---|---|---|---|---|
| +0x00 | `[u8; 0x20]` | +0x74 | **谱表名**（889F 文本，定长） | [E] |
| +0x20 | `u8` | +0x4C | 谱表序号 | [I] |
| +0x21 | `u8` | +0x4D | **谱号类别**（2/3 = 打击乐或特殊谱表） | [E] |
| +0x22 | `u8` | +0x70 | ? | [?] |
| +0x23 | `[u8; 8]` | +0x50 | 调号数组 1 | [E] |
| +0x33 | `[u8; 8]` | +0x58 | 调号数组 2 | [E] |
| +0x3B | `[u8; 8]` | +0x68 | 调号数组 3 | [E] |
| +0x43 | `[u8; 8]` | +0x60 | 调号数组 4 | [E] |
| +0x4B | `u8` | +0xAC | ? | [?] |
| +0x4C | `[u8; 3]` | +0x71 | ? | [?] |
| +0x54 | `u16` | +0x4E | ? | [?] |
| +0x6C | `i32` | — | **nMeas：小节个数** | [E] |

- 读取后 `obj+0x1C`（音量/比例）不在 `[0x32, 200]` 内 → 置 100 [E]。
- 查找子项 type **0x49**（谱表名消息）；缺失则 `SetStaffNameToMsg` 生成 [E]。

## 4. Meas（`CSMMeas::Read` 0x100798E0）

### 4.1 核心头（与通用 ObjectCore 的差异）

```
MeasCore :=
    childCount : u8      ; +0x00（循环中可自减，丢弃 role == 0 的纯引用项）
    _          : u8      ; +0x01（不读）
    f2         : u16     ; +0x02 → 对象 +0x1C（连梁粗度/比例）
    headLen    : i16     ; +0x04（有符号；通用 ObjectCore 为 u16）
    _          : u16     ; +0x06（不读；通用为 headLen+12 派生值）
    f8         : u32     ; +0x08 → 对象 +0x82（低 16 位）、对象 +0x18（高 16 位）
    head       : [u8; headLen]
    children   : [Child; childCount]
```

差异说明：Meas 的 headLen 按 `i16` 解释；`+0x06` 未使用；`role == 0` 的纯引用子项被**丢弃** [E]。

### 4.2 尾块（0x60 字节）

| Tail 偏移 | 类型 | → 对象 | 含义 | 评级 |
|---|---|---|---|---|
| +0x00 | `u8` | +0x81 | 拍号模式（== 3 → 拍号用文本描述） | [E] |
| +0x13 | `[u8; 0x10]` | +0x54 | **拍号文本串**（`CString`） | [E] |
| +0x33 | `[u8; 0x10]` | +0x98 | 第二文本串 | [I] |
| +0x44 | `u8` | +0x7A | ? | [?] |
| +0x45 | `u8` | +0x7B | ? | [?] |
| +0x46 | `u8` | +0x7C | **调号类型**（== 8 → 无调号） | [E] |
| +0x48 | `u8` | +0x84 | ? | [?] |
| +0x49 | `u8` | +0xA8 | ? | [?] |
| +0x4A | `u8` | +0x8C | ? | [?] |
| +0x4B | `u8` | +0x8D | ? | [?] |
| +0x4C | `u8` | +0x8E | ? | [?] |
| +0x4D | `u8` | +0x92 | ? | [?] |
| +0x4E | `u16` | +0x94 | ? | [?] |
| +0x50 | `u16` | +0x96 | ? | [?] |
| +0x52 | `i16` | +0x4C | ? | [?] |
| +0x56 | `i16` | +0x50 | **拍号分子** | [E] |
| +0x58 | `i16` | +0x52 | **拍号分母** | [E] |
| +0x5A | `u8` | +0x7D | **调号符号**（1 = 降号序列，否则升号） | [E] |
| +0x5C | `u8` | +0x7E | **调号个数** | [E] |
| +0x5E | `u16` | +0x90 | 显示开关（受全局标志 `doc+0x9C`→`+0x999` 控制） | [E] |

### 4.3 拍号与小节长度（`CalcWholeCount` 0x1003A4D0）

```
wholeTick = doc+0xA0
tickPerMeas(+0x4E) = wholeTick * 分子(+0x50) * 4 / 分母(+0x52)
```

- 分子/分母为 0 → 强制 4/4 [E]。
- 分母取值 {1,2,4,8,16,32,64,128}（`switch`），决定每段 tick。
- 分段结果（含连音符时长）写入对象 `+0xEC` 的 `CWordArray` [E]。

全语料拍号分布 [E]：

| 分子 | 计数 | 分母 | 计数 |
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
| 8 | 12 | | |
| 15 | 2 | | |
| 7 | 2 | | |

### 4.4 读取后的处理

1. 拍号 0 → 4/4。
2. `CalcWholeCount`。
3. 9 个声部 `UpdatePlayTime(i)` / `UpdateStartTime(i, 0, 0, 0)`。
4. 子项整理：type {0x14, 0x25} 空则删；{0x14, 0x25, 0x01, 0x03} → `ChangeParent` + `AddUpDownMsgArray`。

## 5. Page（`CSMPage::Read` 0x1007BBF0）

```
Page :=
    nBlockA  : i16                 ; → page+0x04
    nBlockB  : i16                 ; → page+0x18
    nPageMsg : i16                 ; → page+0x2C
    _        : i16
    rect     : RECT                ; 4 × i32 → page+0x7C
    blockA   : [Block; nBlockA]
    blockB   : [Block; nBlockB]
    msgs     : [Msg; nPageMsg]
```

- Block 归属：`page+0x04`（A 组）、`page+0x18`（B 组）[E]。

## 6. Block（`CSMBlock::Read` 0x1007B550 / `Write` 0x1007B020）

Block 描述谱面的一**排版行**（system row）。

```
BlockHdr (0x1C):
    type      : u8        ; +0x00  1 → 从 System 第一组(+0x4C)取谱表；否则第二组(+0x60)
    nStaves   : u8        ; +0x01
    f2        : i16       ; +0x02  小节坐标个数 = f2 + 1 → +0x3A
    startMeas : i16       ; +0x04  → +0x38
    nPts      : u8        ; +0x08
    rect      : RECT      ; +0x0C  → +0x90
staffRef : [StaffRef; nStaves]        ; 5 字节/项
    staffIdx : u8                      ; System 组内索引
    a        : u16                     ; → +0xB4 数组
    b        : u16                     ; → +0x7C 数组（默认 0xFFEC）
measX    : [u16; f2 + 1]              ; 小节 X 坐标（首项归一化）
points   : [[i32; 2]; nPts]           ; 谱表名位置点
```

- `Write` 的 `_Size = nStaves*5 + 2 + f2*2 + nPts*8`；与 `Read` 精确一致 [E]。
- 读取时若 `nStaves` 超过对应 System 组的谱表数 → 返回失败 [E]。
- 归一化：读取后取第一个坐标，从区块 RECT 左边界扣除，并把所有坐标减去该值 [E]。
- `MakeStaffNameRect` 在 `nPts > 0` 时生成谱表名矩形 [E]。

全语料 `(nStaves, f2, nPts)` 分布（前 12）[E]：

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

→ 以**单谱表行**为主，偶见双谱表行与带点（nPts > 0）的行 [E]。

## 7. 坐标与比例

| 量 | 位置 | 类型 | 说明 | 评级 |
|---|---|---|---|---|
| 页面版式 | `CSMFileInfo`（0x20 字节） | — | `SetLogicPageInfo(POINT, RECT, i16×4, …)` | [I] |
| 谱面基准单位 | `doc+8`（全局 `DAT_10100FB8`） | — | 半线间距/基准字号 | [I] |
| 基线 Y 表 | 视图 `+0x58` 起 | `i16` | `StaffYTable[MsgHdr+0x18]`；值 `-0x8000` = 无该谱表 | [E] |
| X 偏移 | `MsgHdr+0x16`（+0x50） | `i16` | 相对行起点 | [E] |
| 音高 Y | `MsgHdr+0x18`（+0x52） | `i16` | 负值向上；`MulDiv(+0x52, zoom, 100)` | [E] |
| 缩放 | `MsgHdr+0x02`（+0x58） | `u8` | 百分比，默认 16；`SelectFont((v*100)>>4)` | [E] |

## 8. 未决项

1. Meas 尾块 `+0x44..+0x52`、`+0x4E`/`+0x50` 等字段语义 [?]。
2. Block 的 A 组 / B 组差异（`type` 与 System 两组谱表的选择规则已明确，两组数组的应用场景未定）[?]。
3. `CSMFileInfo` 12 个 `i16` 与 2 个 `u32` 的精确含义（入口 `SetLogicPageInfo` 0x10094ED0、
   `UpdateLogicDoc` 0x100950A0）[?]。
4. 谱表名位置点（nPts）的坐标系与使用条件 [?]。
