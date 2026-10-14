# SMC 文件格式规范（Samilpo 2.0）

> 状态：初版定稿（第四阶段末）。第一至第四阶段成果已汇总；未解字段见 `docs/unknown-fields.md` 与 `docs/field-coverage.md`。

---

## 0. 凡例（notation）

### 0.1 知识评级

每个结论后附方括号评级。同一句中多个结论可各自标注。

| 标记 | 含义 | 判定标准 |
|---|---|---|
| `[E]` | **直接证据** | 反编译代码明确读写该字段，或对全部/抽样样本的字节观察可复现 |
| `[I]` | **推断** | 证据较强（如命名、相邻逻辑、统计规律），但缺少决定性代码或全量验证 |
| `[?]` | **未知** | 尚无可靠解释；已记录位置与现状 |
| `[C]` | **已推翻** | 曾提出后被证据否定的假设（保留以便追溯） |

未标注的行默认沿用本节的最高可证评级；表格内逐行标注更精确。

### 0.2 数据类型（Rust 风格）

| 写法 | 含义 |
|---|---|
| `u8` / `u16` / `u32` / `u64` | 无符号小端整数（1/2/4/8 字节） |
| `i8` / `i16` / `i32` / `i64` | 有符号小端整数（二补数） |
| `f32` / `f64` | IEEE-754 浮点（在本格式中出现极少） |
| `bool` | 按 u8 解释，0 = false，非 0 = true |
| `[u8; N]` | 定长 N 字节数组（无内部长度） |
| `[T; N]` | 定长 N 元素数组 |
| `Vec<T>` | 定长计数后跟 N 个 T 的序列（计数类型随上下文注明） |
| `CStr` | `u16 len` + `[u8; len]`，**无终止符** |
| `CStrZ` | NUL（0x00）结尾的字节串 |
| `Ptr32` | 持久化进文件的 **32 位运行期地址**（见 §0.4） |
| `RECT` | `[i32; 4]` = left, top, right, bottom（Win32 RECT） |
| `POINT` | `[i32; 2]` = x, y |
| `SIZE` | `[i32; 2]` = cx, cy |
| `COLORREF` | `u32`，`0x00BBGGRR`（Win32 COLORREF） |
| `LOGFONTA` | Win32 LOGFONTA，60（0x3C）字节，含 `char[32] lfFaceName` |
| `BYTE`/`WORD`/`DWORD` | 仅在引用 Win32 API 签名时使用；等价 u8/u16/u32 |

偏移一律写作 `+0xNN`，相对**当前结构的起点**；跨结构引用时写明结构名。

### 0.3 证据引用约定

- 函数地址：`engine.dll` 用 `0x100xxxxx`（基址 `0x10000000`），`MusicBook.exe` 用 `0x4xxxxx`（基址 `0x400000`）。
- 样本计数：`n/N` 表示 N 个样本中 n 个符合该结论。
- 验证脚本：`tools/` 下的文件名。

### 0.4 关于 `Ptr32` 与「无语义字节」

本格式存在两类**必须原样保留、不得解释**的字节：

1. **未初始化残留**（栈残留）：写入方未初始化局部变量即整体 memcpy 到文件。读取方从不访问。特征：同一字段在不同样本中取大范围随机值，且与任何已知语义无关。
2. **持久化运行期结构**（含 `Ptr32`）：把内存中的 C++ 对象或栈结构原样写入。特征：含落在 `MFC42.DLL`（`0x5F400000` 段）或 `engine.dll` 的绝对地址。

第三方解析器对二者的正确处理都是**原样保留**；重建时若需写出，只能沿用原字节或写入确定性的占位值。已确认的此类区域列于 `docs/field-coverage.md` 的「无语义」类别。

---

## 1. 概述与适用版本

SMC 是 Samilpo 2.0（韩国记谱软件）的乐谱文档格式。一个文件完整描述一或多页乐谱：

- 文档级设置（显示/播放参数、字体表、页面版式、速度）。
- 一个**谱表系统**（System），其下为**谱表**（Staff，上/下两组），每个谱表下为**小节**（Meas）。
- 小节内是**消息**（Msg）树：音符、休止符、歌词、和弦记号、力度、拍号、调号、连梁、连音线、文本框、图形等。
- 分页信息（Page）与排版块（Block），决定乐谱在页面上的行布局。

### 1.1 版本

`SYMP` 头内的 `i16 version`：

| 值 | 含义 | 语料计数 |
|---|---|---|
| 0x2004 | 版本 2.0.4 | 6930 |
| 0x2005 | 版本 2.0.5 | 1521 |

- `> 0x2005`：程序弹消息 0x67 并拒绝 [E]。
- `< 0x2003`：对 `doc+0x40E..0x414` 做 `MulDiv(x, 16, doc+8)` 换算并调用 `ChangeTieSlurInfo` [E]。
- 本规范同时适用于 0x2004 与 0x2005；未发现字段含义差异 [E]。

---

## 2. 基本数据类型与编码规则

结构一律无填充，字段紧邻；长度字段即字节长度。

| 项 | 规则 |
|---|---|
| 字节序 | 全部小端 |
| 对齐 | 无对齐填充 |
| 文本编码 | **889F Code**（见 §8、`docs/encoding.md`） |
| 对象 key | `u32`，同一文档内唯一，读取时经 `CSMSystem::GetKey` 重映射 [E] |
| 字符串 | `CStr`（带 `u16 len`）或 `CStrZ`（NUL 结尾），依结构而定 |

---

## 3. 文件级结构

| 文件偏移 | 长度 | 类型 | 内容 | 读取者 |
|---|---|---|---|---|
| 0x000 | 4 | `u32` | `hdrLen` = 0x58C；否则走旧格式路径 | exe FUN_00424670 [E] |
| 0x004 | 0x58C | — | `SYMP` 头块（读入 `view+0x380`） | 同上 [E] |
| 0x590 | 2 | `i16` | `strLen` | 同上 [E] |
| 0x592 | strLen | `[u8; strLen]` | 附加字符串（仅当 strLen > 1；NUL 结尾） | 同上 [E] |
| — | 0x318 | — | `SMC` 块（读入 `view+0x68`） | 同上 [E] |
| — | fontLen | — | 字体表缓冲 → `CFontDatas::LoadBuffer` | 同上 [E] |
| — | 2 + ctlLen | `i16` + 数据 | `CSMCtrlTool` 块 | `CSMCtrlTool::Read` 0x1007F4E0 [E] |
| — | 0x20 | — | `CSMFileInfo` 块 | `CSMFileInfo::Read` 0x10095260 [E] |
| — | 4 | `u32` | **bodyLen** | `CSMDoc::Load` 0x10077CB0 [E] |
| — | bodyLen | — | 文档主体 | 同上 [E] |
| EOF−4 | 4 | `u32` | **bodyLen（重复）** | 无（写入方 `CSMDoc::Save` 追加）[E] |

上表偏移以 `500KFS-0041.smc` 为例；实际随 `strLen`/`fontLen`/`ctlLen` 变化。

**无压缩、无加密、无校验和**：全部读取为 `CFile::Read` 直接 memcpy；`FUN_1009A720` 仅作 `GlobalMemoryStatus` 内存检查 [E]。

**尾部 4 字节**（第四阶段闭合）[E]：`CSMDoc::Save` 0x100773C0 的流程为
「在文件起始处写 4 字节占位 → 写 System → 写主体并累计字节数 → 在主体之后写该累计值 → 回到起始处回填同一值」。
因此文件首尾两个 `u32` 由**同一变量**写出，必然相等且等于主体字节数；尾部值是**冗余长度**，非校验和，读取端不读。

### 3.1 SYMP 头块（0x58C）

| 块内偏移 | 类型 | 含义 |
|---|---|---|
| +0x000 | `u32` | 再次出现 0x58C（自身长度）[E] |
| +0x004 | `[u8; 4]` | `"SYMP"`，`strncmp` 校验 [E] |
| +0x008 | `i16` | 格式版本（见 §1.1）[E] |
| +0x00A | `CStrZ` | **曲名**（889F 编码）[I，与 type 0x06 文本中的曲名一致] |
| 其余 | — | 基本为 0 [?] |

### 3.2 附加字符串

`i16 strLen`；`strLen > 1` 时读 `strLen` 字节，经 `CString::Format` 存入 `view+0x90C` [E]。
语料通常为 3–5 字节数字串（如 `"448"`、`"54"`）；318 个文件长度为 32，内容为 F0–FC 引导的双字节文本 [E]。语义未知 [?]。

### 3.3 SMC 块（0x318）

| 块内偏移 | 类型 | 含义 |
|---|---|---|
| +0x000 | `[u8; 4]` | `"SMC\0"`，`strcmp` 校验 [E] |
| +0x004 | `u32` | 0x318（自身长度）[E] |
| +0x312 | `i16` | 样本中为 0x2004（与版本一致）[E；含义 ?] |
| +0x314 | `u32` | `fontLen`：其后字体表缓冲长度 [E] |
| 其余 | — | [?] |

### 3.4 字体表缓冲（`fontLen` 字节）

`CFontDatas::LoadBuffer` 0x1002C100。格式为重复记录 [E]：

```
FontRecord :=
    index   : u8           ; 字体索引（供消息引用）
    nameLen : u8           ; ≤ 255
    name    : [u8; nameLen]; 名称（889F 编码），载入后末尾补 NUL
```

- 每条记录既存入 `CFontDatas+4` 的字符串数组，也经 `AddNewFont(index, name, len)` 注册字体对象 [E]。
- 载入后 exe 对 `doc+0x1F8、+0x234 … +0x3D8`（9 个间隔 0x3C 的 `LOGFONTA.lfFaceName`）调用 `GetNearestFontName` [E]。
- 语料实例：`01 0A "ＷＫ細明朝"`、`06 0C "WKGothic(KS)"`、`07 05 "Gulim"`、`08 06 "System"` [E]。

### 3.5 CSMCtrlTool 块（`i16 len` + `len` 字节）

`CSMCtrlTool::Read` 0x1007F4E0：读 `i16 len`（样本 0x478），复制 ≤0x478 字节到栈结构并整块复制到 `this+0x4EC`；返回 0x478 [E]。已确认块内布局：

| 块内偏移 | 长度 | → 对象 | 类型/含义 |
|---|---|---|---|
| 0x000, 0x03C, …, 0x1A4 | 各 0x3C | +0x20C, +0x1D0, +0x284, +0x2C0, +0x2FC, +0x338, +0x374, +0x3B0 | 8 × `LOGFONTA` [I] |
| 0x1E0 | 0x24 | +0x7C | ? [?] |
| 0x204 | 4 | +0xA0 | ? [?] |
| 0x208 | 0x100 | +0xA8 | 字符串/路径 [?] |
| 0x308..0x32C | `[u32; 10]` | +0xA4, +0x1AC… | ? [?] |
| 0x330 | 0x40 | +0x34 | ? [?] |
| 0x370, 0x372 | 2 × `i16` | +0x3EC, +0x3EE | ? [?] |
| 0x374 | 0x12 | +0x3F0 | ? [?] |
| 0x386 | 4 × `i16` | +0x402..0x408 | 分别钳制到 [-99,99]、[-99,99]、[1,48]、[0,16]（移调/八度等）[E 钳制；语义 I] |
| 0x38E… | `i16` 序列 | +0x40A… | ? [?] |
| 0x3A8 | 8 | +0x4A4 | `POINT` / `SIZE` [I] |
| 0x3B0 | 0x10 | +0x4AC | `RECT` [I] |
| 0x408 | 0x3C | +0x248 | 第 9 个 `LOGFONTA` [I] |
| 0x460..0x46E | `[u8; 9]` | +0x96C..0x974 | 0 时填默认 `0x30,0x40,0x4C,0x54,0x60,0x6E,0x78,0x7F` → **强弱记号到 MIDI velocity 映射** [I，强] |
| 0x46F..0x473 | `[u8; 5]` | +0x977..0x97B | 默认 `0x28` [?] |

`ctrl+0x10` = **当前编辑声部（0..8）**，绘制时用于可见性判定 [E]。

### 3.6 CSMFileInfo 块（0x20）

`[i16; 12]`（→ +4..+0x1A）+ `[u32; 2]`（→ +0x1C, +0x20）[E]。
样本：`6, 4, 79, 79, 86, 90, 30, 113, 9, 8, 0, 0, 529, 795`。
导出函数 `SetLogicPageInfo(POINT, RECT, i16×4, …)` 暗示为页面版式信息 [I]。字段语义见 `docs/layout.md` §8。

---

## 4. 文档主体（`CSMDoc::Load` 0x10077CB0）

读 `u32 bodyLen`，一次性读入整块；其后所有读取器共用游标 `(buf, *pos, size)`。

```
Body :=
    System                       ; CSMSystem::Read 0x10078730
    DocHdr  (10 bytes)           ; i16 pageCount, i16 → doc+8, i16 → doc+4, i16 → doc+6, i16 → doc+10
    Msg × 3                      ; 文档级消息 → doc+0xC3C, +0xCBC, +0xD3C
    Page × pageCount             ; CSMPage::Read 0x1007BBF0
```

- 3 条文档级消息通常为类型 **0x3F、0x40、0x04**（每文件各一次）[E]。
- `doc+8` 复制到全局 `DAT_10100FB8`，作为旧版本换算分母 → **谱面基准单位（半线间距）** [I]。
- `doc+0xA0` 为 **全音符 tick 基数**（`CalcWholeCount` 与 `CSMMsg::CalcPlayTime` 使用）[E]。
- 主体缓冲区大小 = `u16@doc+0xC5A + 0x2E + u16@doc+0xCDA + u16@doc+0xD5A`
  （= 三条文档级消息长度和 + DocHdr(10) + 3 条 Msg 头）[E]。

---

## 5. 对象模型

### 5.1 通用对象头 ObjectCore

磁盘布局，由 `CSMObject::Read` 0x1007AA20 与 `CSMObject::Write` 0x1007A740 双向确证 [E]：

```
ObjectCore :=
    childCount : u8      ; +0x00  子项个数
    reserved   : u8      ; +0x01  保留（读取端从不使用；见 §0.4 第 1 类）
    f2         : u16     ; +0x02  连音/连奏比例（高字节=分子，低字节=分母）
    headLen    : u16     ; +0x04  私有负载长度
    derivedLen : u16     ; +0x06  = headLen + 12（派生冗余；读取端跳过）
    f8         : u32     ; +0x08
    head       : [u8; headLen]
    children   : [Child; childCount]
```

- `+0x06 = headLen + 0xC`：由 `CSMObject::Write` 写入，读取端不读 [E]。
- `+0x01` 为写入方未初始化的栈字节：全语料 46% 为 0，其余为大范围随机值；
  读取端完全忽略，故写入 0 安全 [E]（`project/phase3-log.md` §1.4、§4b）。

内存布局（供交叉引用反编译）：`+0x18`=f8、`+0x1C`=f2、`+0x1E`=headLen、`+0x20`=head 指针、
`+0x24`=子项数组、`+0x38`=控制点数组、`+0x08`=父指针、`+0x0C`=文档、`+0x14`=本对象 key、`+0x10`=页面/视图指针 [E]。

### 5.2 子项 Child（8 字节）

```
Child :=
    key   : u32          ; 对象键（读取时经 CSMSystem::GetKey 重映射）
    role  : u8           ; 引用角色：0 = 仅引用；非 0 = 其后紧跟完整 Msg
    pad   : [u8; 3]
    [msg] : Msg          ; 仅当 role != 0
```

- `CSMObject::AddMsg` 0x100BAD70 / `InsertMsg` 0x100BAEC0 写入 `role`，取值由调用方给出 [E]。
- `CSMObject::Write` 原样回写 8 字节；`role != 0` 时递归写嵌入 Msg [E]。
- `GetTieIndex` 0x10037D90 以 `role == param` 匹配 tie 角色；`GetSlurIndex` 0x10037E20 以 `key` + `role` 匹配 slur 端点 [E]。
- 语料中 `role` 仅出现 {0, 1}（0 占 3259、1 占 59635，抽样）[E]。
- 内存语义：嵌入对象 `+0x08 = 父对象`，`+0x05 = 父对象的 voice` [E]。
- `CSMMeas::Read` 会**丢弃** `role == 0` 的子项（计数自减）[E]。

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

### 6.1 记录结构

```
Msg :=
    hdr    : MsgHdr (0x2C bytes)
    core   : ObjectCore
    [extra]: ChordExtra          ; 仅当 type == 0x45
```

`CSMMsg::Read` 0x1007A490 / `CSMMsg::Write` 0x1007A240（含字段级双向确证）。

**MsgHdr 字段表**：

| 磁盘偏移 | 类型 | → 对象 | 含义 | 评级 |
|---|---|---|---|---|
| +0x00 | `u8` | +0x68 | **消息类型**（读取时 `0x41` 改写为 `0x08`） | [E] |
| +0x01 高 4 位 | `u8` | +0x78 | **括号标志**（非 0 时绘制 `(` `)`） | [E] |
| +0x01 低 4 位 | `u8` | +0x69 | **声部索引 0..8** | [E] |
| +0x02 | `u8` | +0x58 | 缩放百分比（默认 0x10=16） | [E] |
| +0x03 | `u8` | +0x74 | ? | [?] |
| +0x04 | `u8` | +0x75 | ? | [?] |
| +0x05 高 4 位 | `u8` | +0x76 | **符干/标记状态**（低 3 位：0 无 / 1 升 / 2 降 / 3 还原 / 4 重升 / 5 重降） | [E] |
| +0x05 低 4 位 | `u8` | +0x77 | **附点数**（低 7 位） | [E] |
| +0x06 | `i16` | +0x5C | **符头类型** / 打击乐声部索引 | [E] |
| +0x08 | `i16` | +0x5E | **类型相关索引**（时值指数、休止符类型、力度码、调号码、谱号码、字符码） | [E] |
| +0x0A | `i16` | +0x6E | **标志位集合**（见 §6.5） | [E] |
| +0x0C | `i16` | +0x60 | 绘制缓存（外接矩形，非文件语义） | [E] |
| +0x0E | `i16` | +0x66 | 绘制缓存 | [E] |
| +0x10 | `i16` | +0x62 | 绘制缓存 | [E] |
| +0x12 | `i16` | +0x64 | 绘制缓存 | [E] |
| +0x14 | `i16` | +0x5A | 起始时间（小节内 tick） | [E] |
| +0x16 | `i16` | +0x50 | **相对 X 偏移** | [E] |
| +0x18 | `i16` | +0x52 | **音高 Y 偏移**（负值向上） | [E] |
| +0x1A | `i16` | +0x54 | 外接矩形 L（缓存） | [E] |
| +0x1C | `i16` | +0x56 | 外接矩形 R / 符干长度；**type 0x2C 复用为长休止小节数** | [E] |
| +0x20 | `u32` | +0x70 | **端点引用键**（连音/圆滑线；或符干方向） | [E] |
| +0x24 | `u32` | +0x14 | **本对象 key**（经 `CSMSystem::GetKey` 重映射） | [E] |
| +0x28 | `u32` | +0x4C | 颜色/样式（`DrawDynamic` 用作 `SetTextColor` 参数） | [I] |

`type == 0x01` 且 `headLen != 12` 时，读取后把 head 规整为 12 字节（+0x08..+0x0B 清零）[E]。

### 6.2 时值与播放时间

`CSMMsg::CalcPlayTime` 0x10036470 / `GetPlayTime` 0x10042A50。对 type ∈ {0x01, 0x03, 0x25}：

```
playTime = (0x100 >> (MsgHdr+0x08 & 0x1F)) * doc+0xA0 >> 5
附点：MsgHdr+0x05 低半字节 == 1 → += 1/2；== 2 → += 1/2 + 1/4
比例：f2 = ObjectCore+0x02；若 (f2 >> 8) != 0 且 (f2 & 0xFF) != 0
        playTime = MulDiv(playTime, f2 >> 8, f2 & 0xFF)
```

- **`MsgHdr+0x08 & 0x1F` 为时值指数**，`0x100 >> exp` 为占全音符的比例 [E]。
- type 0x14（连梁组）：播放时间 = 各子消息之和 [E]。
- type 0x25（和弦）：自身时间不累加，仅驱动子项 [E]。
- `GetPlayTime`：`MsgHdr+0x0A & 0x10` 置位时返回 0（不发声）[E]。

### 6.3 消息类型分派表

来源：`CScoreView::SMDrawMsg` 0x1004AA00（唯一按 type 分派的 switch）[E]。
计数来源：全语料 8451 文件（`tools/smc_census.py`）。

| type | 绘制器 | 语义 | 计数 |
|---|---|---|---|
| 0x01 | DrawNote | **音符** | 652338 |
| 0x03 | DrawRest | **休止符** | 15359 |
| 0x04 | DrawMultiText | 文本框（文档级） | 8342 |
| 0x05 | DrawMetronome | 节拍器记号 | 1640 |
| 0x06 | DrawMultiText | **文本框** | 42031 |
| 0x08 | DrawMark | 标记 | 6707 |
| 0x09 | （登记 tie 表） | **连音线（tie）** | 26295 |
| 0x0A | （登记 slur 表） | **圆滑线（slur）** | 62202 |
| 0x0C | DrawCoda | Coda 记号 | 165 |
| 0x0D | DrawRolled_chord | 滚奏和弦（琶音） | 111 |
| 0x10 | DrawVabPedal | 踏板 | 1 |
| 0x12 | DrawMeasTuplet | 小节级连音符 | 1786 |
| 0x13 | DrawCDCrescendo | 渐强/渐弱 | 93 |
| 0x14 | DrawBeam | **连梁组** | 54238 |
| 0x15 | DrawKeysign | 调号（独立消息；语料中不出现） | 0 |
| 0x16 | DrawFretboard | 吉他指板图（旧式，读入即转换） | 0 |
| 0x17 | DrawChordText | 和弦文字（旧式，读入即转换） | 0 |
| 0x18 | DrawMsgLine | 直线 | 10431 |
| 0x19 | DrawTextMsg | **歌词** | 625967 |
| 0x1B | DrawDynamic | **力度记号** | 17132 |
| 0x1F | DrawClef | **谱号** | 13 |
| 0x21 | DrawTrills | 颤音（tr） | 4 |
| 0x25 | DrawChord | **和弦**（同音组） | 433 |
| 0x26 | DrawEllipse | 椭圆 | 3 |
| 0x27 | DrawRectangle | 矩形 | 14 |
| 0x28 | DrawRoundRectangle | 圆角矩形 | 0 |
| 0x29 | DrawN | 任意文字 | 0 |
| 0x2A | DrawGerneralFont | 通用字体字符（`codeSmallDigit`，索引取 f2） | 0 |
| 0x2B | DrawInversM | 强音记号 | 0 |
| 0x2C | DrawLongrest | 长休止（多小节休止） | 98 |
| 0x2E | DrawSlur | 圆滑线（独立） | 264 |
| 0x2F | DrawSingle_Msg | 换气记号 | 8 |
| 0x30 | DrawSingle_Msg | 花音记号 | 9 |
| 0x34 | DrawSingle_Msg | 断句 | 0 |
| 0x35 | DrawSingle_Msg | 小节反复记号 | 0 |
| 0x36 | DrawSingle_Msg | 单字符记号 | 0 |
| 0x37..0x3A | DrawSingle_Msg | 滑音线 | 0 |
| 0x3C | DrawSingle_Msg | 上圈 | 0 |
| 0x3D | DrawSingle_Msg | 下圈 | 0 |
| 0x3E | DrawSingle_Msg | 大下圈 | 0 |
| 0x3F | （文档级） | 每文件一次 | 8451 |
| 0x40 | （文档级） | 每文件一次 | 8451 |
| 0x42 | DrawMidiShortMsg | **MIDI 短消息** | 0 |
| 0x44 | DrawCurvedLine | 曲线 | 1 |
| 0x45 | vtable+0x18 | **和弦记号** | 177909 |
| 0x46 | DrawFretboard | 指板图（0x45 的内嵌对象） | 177909 |
| 0x47 | （CRhythm/CRtmData） | 节奏型/伴奏型 | 12716 |
| 0x49 | CSMStaffNameMsg::DrawMsg | **谱表名** | 5865 |
| 0x4A | DrawBezierLine | 贝塞尔曲线 | 0 |

### 6.4 连音与圆滑线的引用机制

type ∈ {0x09, 0x0A, 0x12} 的消息 [E]：

- 挂在其父对象（通常是音符或小节）下，`MsgHdr+0x20`（对象 +0x70）与对象 +0x18 保存**两个端点键**。
- `CSMSystem::Read` 结束时对这两个键执行 `GetKey` 重映射；超出映射表范围则置 0。
- `CSMMsg::CreateFrom` 0x1006ACD0：若 `+0x18 == +0x70`（自指）则两者都设为父键；否则 `+0x18` 设为父键，`+0x70` 保留为另一端。
- 全语料：仅 7 条 0x0A 的 `MsgHdr+0x20` 为 0（与 headLen=18 的 7 条一致）[E]。

### 6.5 标志位（`MsgHdr+0x0A`，对象 +0x6E）

| 位 | 掩码 | 含义 | 证据 |
|---|---|---|---|
| 0 | 0x0001 | **连音延续目标** | `GetRealNoteDur` 0x100B7FB0 |
| 2 | 0x0004 | **符尾存在** | `CSMMsg::SetTail` 0x100B2A90 |
| 3 | 0x0008 | 标记内部标志 | `ResetGetNextMsg` 0x100ACB20 |
| 4 | 0x0010 | **不发声 / 渐强装饰**（装饰音亦置位） | `GetPlayTime`、`MakeGraceNote` 0x100ABB80 |
| 5 | 0x0020 | 和弦处理标志 | `ResetGetNextMsg` |
| 9 | 0x0200 | 上组谱表 | `WhatIsAccidental` 0x100B0830 |
| 10 | 0x0400 | 下组谱表 | 同上 |

抽样 300 文件的出现计数：bit2=3113、bit3=4770、bit4=3063、bit8=3017、bit9=2978、bit10=2978 [E]。

### 6.6 符干/标记状态（`MsgHdr+0x05` 高半字节）

低 3 位状态码：`0` 无、`1` 升、`2` 降、`3` 还原、`4` 重升、`5` 重降
（`CSMMsg::WhatIsAccidental` 0x100B0830 / `UpdateNoteKeySignature` 0x100AF1A0）[E]。

### 6.7 音符 head（12 字节，type 0x01）

| head 偏移 | 类型 | 含义 | 评级 |
|---|---|---|---|
| +0x00 | `u8` | **MIDI 音高 key**（0..127） | [E] |
| +0x01 | `u8` | **力度 velocity**（0..127，默认 100） | [E] |
| +0x02 | `u8` | 保留常量 **0x40**（语料 652338/652338） | [E] |
| +0x03 | `u8` | **声部索引**（与 `MsgHdr+0x01` 低半字节一致） | [E] |
| +0x04 | `u32` | **时值（tick 数）** | [E] |
| +0x08 | `u32` | **起始时间偏移**（磁盘恒 0，运行期写入） | [E] |

证据：
- `GetMidiKey` 0x100AC520 / `SetMidiKey` 0x100AC4D0 读写 `head[0]` [E]
- `GetVelocity` 0x100AC570 / `SetVelocity` 0x100AC5C0 读写 `head[1]` [E]
- `GetRealNoteDur` 0x100B7FB0 读 `head+4` 的 `u32`；`SetPlayTime` 0x100B76F0 换算后回写 [E]
- `UpdateStartTime` 0x10037A70 写 `head+8` [E]
- 全语料：key 范围 **38..89**（49 个不同值）、velocity 12 个不同值（100 出现 637722 次）；
  时值 120→314335、240→126731、60→59212、360→46397、720→30578、480→30495… [E]
- head[2..3] 在 12 字节 head 中恒为 `40 01`/`40 02`（0x0140/0x0240）[E]

### 6.8 type 0x46（指板，`CFretBoard`）

`CFretBoard::ReadFromMem` 0x1002CFD0 / `WriteToMem` 0x1002D060：

```
FretBoard :=
    msg    : Msg                     ; 内嵌消息，类型被强制为 0x46
    info   : FretInfo (16 bytes)     ; CFretInfo::ReadFromMem 0x1002DC70
```

- 读取时 `obj+0x94 = obj+0x1C`（f2 备份），并 `lstrcpyA(obj+0x96, "KayakumA")` [E]。
- 写入时 `obj+0x1C = obj+0x94` 后序列化 [E]。

`FretInfo`（16 字节，读写逐字段一致）[E]：

| 偏移 | 类型 | 含义 |
|---|---|---|
| +0x00 | `u16` | **基准品位 baseFret**（对象 +0x12） |
| +0x02 | `[u8; 6]` | **6 根弦的品位值**（对象 +0x04）：`1..4` 为有效相对品位；`0xFE`/`0xFF` 为空弦标记 |
| +0x08 | `[u8; 8]` | **4 组 (起始, 结束) 字节对**（对象 +0x0A） |

证据：`GetMidiKeyOfString` 0x1002D220（`this[string+4]` 为品位）、
`FretInfoToLineString` 0x1002D330（遍历 6 取 `this[i+4]+2`，再遍历 4 取 `this[i*2+10]/[i*2+11]`，最后取 `this[0x12]`）、
`IsFretEmpty` 0x1002D2A0（空判定）[E]。

### 6.9 type 0x45（和弦记号，`CChordSymbol`）

`CChordSymbol::ReadFromMem` 0x1000BDB0 / `WriteToMem` 0x1000BF80 完全对称 [E]：

```
ChordExtra :=
    surfix    : ChordSurfix
    fretBoard : FretBoard            ; 内含 type 0x46 的 Msg + FretInfo(16)
    hasRhythm : u16
    [rhythm]  : Rhythm               ; 仅当 hasRhythm != 0
```

```
ChordSurfix :=                        ; CChordSurfix::ReadFromMem 0x10008B40
    name : CStr                      ; 可读后缀名，如 " (major)"、"m"、"7"、"m6"、"dim"
    n    : u8
    info : [u8; n]
```

```
Rhythm :=                             ; CRhythm::ReadFromMem 0x10045C40
    msg  : Msg                        ; 类型 0x47
    s1   : CStr
    s2   : CStr
    s3   : CStr
    data : RtmData
```

`RtmData`（`CRtmData::ReadFromMem` 0x10047720 / `WriteToMem` 0x10047950，逐字段一致）[E]：

| 偏移 | 类型 | 含义 |
|---|---|---|
| +0x00 | `u32` | **totalSize**：本结构总长（**含自身 4 字节**；101/101 验证 `total = 已消耗 + 4`） |
| +0x04 | `u16` | 步长 `stride`（恒 0x10） |
| +0x06 | `u16` | 字段 A（内存 +0x08） |
| +0x08 | `u16` | 字段 B（内存 +0x48） |
| +0x0A | `u32` | **事件数 eventCount** |
| +0x0E | `u16` | **事件大小 eventSize**（恒 0x10） |
| +0x10 | `[u8; eventCount × eventSize]` | 事件块（每条 16 字节） |
| … | `u16` | **count2** |
| … | `u16` | **size2**（恒 6） |
| … | `[u8; count2 × 6]` | 第二段数据（每条 6 字节） |

**type 0x45 的 head 有两种长度**：`0`（多数）与 `100`（413/1244 抽样）[E]。

- 和弦可读名称在 `ChordExtra.surfix.name`（`CStr`），语料实测：
  `" (major)"` 539、`"m"` 371、`"7"` 154、`"(major)"` 58、`"m6"` 9、`"m7"` 6、`"dim"` 4、`"9"` 2、`"dim7"` 1 [E]。
- **headLen = 100 的 head 为持久化运行期结构**：含 `Ptr32`（`+0x48/+0x4C = 0x5F401018`、
  `+0x5C = 0x5F40111F`、`+0x60 = 0x5F405D25`，全部 413 样本相同，落在 **MFC42.DLL 段 0x5F400000**）
  以及栈样式值（`+0x36 = 0xBFF7` = −16393）。100 字节中仅 27 字节在全部样本恒定。
  判定：**无语义，须原样保留**（§0.4 第 2 类）[E]。
- `CSMMsg::Write` 对 type 0x45 先以 `obj+0x80`→`obj+0x18`、`obj[0x17C]<<8|obj[0x180]`→`obj+0x1C` 覆盖后再序列化 [E]。

### 6.10 type 0x19（歌词，`CSMLyricMsg`）

head = `0x10 + 文本字节数` [E]。头 16 字节字段表（第四阶段汇编闭合）：

| head 偏移 | 类型 | 含义 | 评级 |
|---|---|---|---|
| +0x00 | `u16` | 字体索引 | [E] |
| +0x02 | `u8` | 样式位（bit0 粗体、bit1 斜体、bit2 下划线） | [E] |
| +0x03 | `u8` | **未初始化残留** | [E] |
| +0x04 | `u16` | 字号（0 → 视为 13） | [E] |
| +0x06 | `u16` | **未初始化残留** | [E] |
| +0x08 | `COLORREF` | 文字颜色 | [E] |
| +0x0C | `u8` | 文本字节长度 | [E] |
| +0x0D | `u8` | **未初始化残留** | [E] |
| +0x0E | `u8` | **未初始化残留** | [E] |
| +0x0F | `u8` | **未初始化残留** | [E] |
| +0x10 | `[u8; head[0x0C]]` | **歌词文本**（889F 编码） | [E] |

- 读取侧 `DrawMsg` 0x1009AD00 的汇编只访问 +0x00/+0x02/+0x04/+0x08/+0x0C 与 +0x10 起文本；
  +0x03/+0x06/+0x07/+0x0D/+0x0E/+0x0F 无任何访问 [E]。
- 写入侧 `EncToSMC_Lyric` 0x10025170 与 `GulsamToSMC_Lyrics` 0x10030010 都只写这 5 个字段，
  其余字节来自未初始化栈（`CONCAT31` 仅设低字节）[E]。
- 验证（400 文件、30353 条）：样式 {0: 30254, 1: 99}、字号 {13: 30136, 14: 140, 12: 74, 0: 3}、
  head+0x06 有 317 个不同值、head+0x0D..0x0F 有 535 种组合（仅 6089 条全 0）→ 确认残留 [E]。
- 关联：歌词**始终**为 type 0x01 音符的嵌入子对象（2961/2961）[E]。详见 `docs/lyrics.md`。

### 6.11 type 0x06（文本框，`CSMTextMsg`）

head 为 **TLV** 串（标签 + 长度 + 值），见 `docs/lyrics.md` §6 [E]。

### 6.12 type 0x1B（力度记号）

`MsgHdr+0x08` = 力度码，`DrawDynamic` 0x1005E690 取 `CodeDyn[码]` 单字符绘制 [E]。

### 6.13 type 0x2C（长休止）

- `DrawLongrest` 0x100595B0 以 `codeLongRestBar` 绘制长休止条，并存**中间打印十进制数字**：
  `CString::Format(..., *(i16*)(msg + 0x1C))` → **小节数在 `MsgHdr+0x1C`** [E]。
- headLen 60 的 head 内部字段未解析 [?]（`docs/unknown-fields.md` B2）。

### 6.14 type 0x42（MIDI 短消息）

`CSMDoc::EncToSMC_MidiMsg` 0x10022D20 构造：type = 0x42，对象 +0x18 承载 **3 字节 MIDI 消息**
（status/data1/data2）[E]；`DrawMidiShortMsg` 0x10066290 绘制。

### 6.15 文档级消息（0x3F / 0x40 / 0x04）

每文件各一次（0x3F 8451、0x40 8451、0x04 8342），无 head；语义未定 [?]。
`0x04` 亦在 `SMDrawMsg` 中映射到 `DrawMultiText` [E]。

---

## 7. 结构对象

### 7.1 System（`CSMSystem::Read` 0x10078730，对象类型 5）

```
System :=
    core    : ObjectCore
    nStaff1 : i16                    ; 上组谱表数 → sys+0x4C
    nStaff2 : i16                    ; 下组谱表数 → sys+0x60
    wholeTick : u32                  ; 全音符 tick 基数 → sys+0xA0
    staff1  : [Staff; nStaff1]       ; 类型 3
    staff2  : [Staff; nStaff2]       ; 类型 4
```

语料中每文件恰好 1 个 System [E]。读取后对 `sys+0x74`（消息映射表）中 type {0x09,0x0A,0x12}
的两个端点键执行 `GetKey` 重映射，越界置 0 [E]。

### 7.2 Staff（`CSMStaff::Read` 0x10079030）

```
Staff := ObjectCore, tail: StaffTail (0x70 bytes), meas: [Meas; nMeas]
```

| Tail 偏移 | 类型 | → 对象 | 含义 |
|---|---|---|---|
| +0x00 | `[u8; 0x20]` | +0x74 | **谱表名**（889F，定长） |
| +0x20 | `u8` | +0x4C | 谱表序号 |
| +0x21 | `u8` | +0x4D | **谱号类别**（2/3 = 打击乐/特殊，用于 `DrawHead` 与音高计算） |
| +0x22 | `u8` | +0x70 | ? |
| +0x23 | `[u8; 8]` | +0x50 | 调号数组 1 |
| +0x33 | `[u8; 8]` | +0x58 | 调号数组 2 |
| +0x3B | `[u8; 8]` | +0x68 | 调号数组 3 |
| +0x43 | `[u8; 8]` | +0x60 | 调号数组 4 |
| +0x4B | `u8` | +0xAC | ? |
| +0x4C | `[u8; 3]` | +0x71 | ? |
| +0x54 | `u16` | +0x4E | ? |
| +0x6C | `i32` | — | **nMeas：小节个数** |

- 读取后 `obj+0x1C`（音量/比例）不在 `[0x32, 200]` 内则置 100 [E]。
- 查找子项 type **0x49**；缺失则由 `SetStaffNameToMsg` 生成 [E]。

### 7.3 Meas（`CSMMeas::Read` 0x100798E0，对象类型 2）

核心头（**与通用 ObjectCore 有差异**）：

```
MeasCore :=
    childCount : u8      ; +0x00（循环中可自减，丢弃 role==0 的纯引用项）
    _          : u8      ; +0x01（不读）
    f2         : u16     ; +0x02 → 对象 +0x1C
    headLen    : i16     ; +0x04（有符号；通用 ObjectCore 为 u16）
    _          : u16     ; +0x06（不读）
    f8         : u32     ; +0x08 → 对象 +0x82（低 16 位）、对象 +0x18（高 16 位）
    head       : [u8; headLen]
    children   : [Child; childCount]
```

`MeasTail`（0x60 字节）：

| Tail 偏移 | 类型 | → 对象 | 含义 |
|---|---|---|---|
| +0x00 | `u8` | +0x81 | 拍号模式（== 3 → 拍号用文本描述） |
| +0x13 | `[u8; 0x10]` | +0x54 | **拍号文本串** |
| +0x33 | `[u8; 0x10]` | +0x98 | 第二文本串 |
| +0x44..+0x4D | `[u8; 10]` | +0x7A, +0x7B, +0x7C, +0x84, +0xA8, +0x8C, +0x8D, +0x8E, +0x92 | ? |
| +0x4E | `u16` | +0x94 | ? |
| +0x50 | `u16` | +0x96 | ? |
| +0x52 | `i16` | +0x4C | ? |
| +0x56 | `i16` | +0x50 | **拍号分子** |
| +0x58 | `i16` | +0x52 | **拍号分母** |
| +0x5A | `u8` | +0x7D | **调号符号**（1 = 降号序列，否则升号） |
| +0x5C | `u8` | +0x7E | **调号个数** |
| +0x5E | `u16` | +0x90 | 显示开关（受全局标志 `doc+0x9C`→`+0x999` 控制） |

读取后：
1. 拍号分子或分母为 0 → 强制 **4/4** [E]。
2. `CalcWholeCount` 0x1003A4D0：`tickPerMeas(+0x4E) = wholeTick * 分子 * 4 / 分母`；
   分段表写入对象 `+0xEC` 的 `CWordArray` [E]。
3. 对 **9 个声部**（0..8）依次 `UpdatePlayTime(i)` / `UpdateStartTime(i,0,0,0)` → 每小节最多 9 声部 [E]。
4. 子项整理：type {0x14,0x25} 空则删；{0x14,0x25,0x01,0x03} → `ChangeParent` + `AddUpDownMsgArray` [E]。

全语料拍号分布：分子 {4:82504, 6:33703, 3:16248, 12:12048, 2:9441, 9:4433, 5:1137, 18:318, 10:191, 8:12, 15:2, 7:2}；
分母 {4:109848, 8:48687, 2:1504, 16:2} [E]。

### 7.4 Page（`CSMPage::Read` 0x1007BBF0）

```
Page :=
    nBlockA : i16                    ; → page+0x04 数组
    nBlockB : i16                    ; → page+0x18 数组
    nPageMsg: i16
    _       : i16
    rect    : RECT                   ; → page+0x7C
    blockA  : [Block; nBlockA]
    blockB  : [Block; nBlockB]
    msgs    : [Msg; nPageMsg]
```

### 7.5 Block（`CSMBlock::Read` 0x1007B550 / `Write` 0x1007B020）

```
BlockHdr (0x1C):
    type    : u8      ; +0x00  1 → 取 System 第一组谱表；否则第二组
    nStaves : u8      ; +0x01
    f2      : i16     ; +0x02  其后 u16 个数 = f2 + 1
    startMeas: i16    ; +0x04  → +0x38
    nPts    : u8      ; +0x08
    rect    : RECT    ; +0x0C  → +0x90
之后：
    staffRef : [StaffRef; nStaves]   ; 5 字节/项: u8 staffIdx, u16 (→ +0xB4), u16 (→ +0x7C，默认 0xFFEC)
    measX    : [u16; f2 + 1]         ; 小节 X 坐标（首项归一化）
    points   : [[i32; 2]; nPts]      ; 谱表名位置点
```

- `Write` 的 `_Size = nStaves*5 + 2 + f2*2 + nPts*8`，与 `Read` 精确一致 [E]。
- `nStaves` 超过对应谱表组数量 → 读取失败 [E]。
- 全语料 `(nStaves, f2, nPts)`：`(1,4,0)` 25920、`(1,3,0)` 8805、`(1,5,0)` 3742、…；
  以单谱表行为主，偶见双谱表行 [E]。

---

## 8. 文本编码

SMC 文本使用 **code id 1 = "889F Code"**（`889F.cod`），即以 Shift-JIS 双字节码位为索引的自定义映射表。
转换入口 `MyDrawTextOutW` 0x10096530 明确调用 `CKCConv::ToUnicode(1, …)` [E]。

- `< 0x80` 单字节透传；其余按双字节码位查表。
- 未映射码位原样保留（由字体自身字形渲染）。
- 码位区段：0x88–0x9F、0xE0–0xFC，另含 SJIS 用户定义区 0xF000–0xF300。
- 验证：8451/8451 曲名、全部歌词记录、1991 个文本框全部正确解码 [E]。

完整说明见 `docs/encoding.md`。

---

## 9. 资源、字体与符号

### 9.1 字体

- 程序启动时加载 8 个 TTF（`<安装目录>\Font\`）[E]。
- SMC 文件内的字体表（§3.4）保存**字体显示名与索引**，供消息的字体索引字段引用。
- 详见 `docs/font-resources.md`。

### 9.2 音乐符号

音乐符号（符头、附点、变音、力度、踏板等）**不是文本字符**，而是引擎内以单字节常量（0x7F–0xFF）
表示的符号码，经 **`KayakumA` 符号字体**（`KAYAKUMA.TTF`，Windows 符号字符集 → U+F020–U+F0FF）绘制 [E]。

- `KAYAKUMA.TTF` 的 cmap **仅覆盖 U+F020–U+F0FF**（223 字形）[E]。
- 889F 正向表**没有任何**码位映射到 U+F000–U+F0FF（0 个）→ 音乐符号与韩文文本使用**互不重叠的两套编码空间** [E]。
- 符号常量表（引擎映像 `0x10100360`–`0x10100700`）见 `docs/font-resources.md` §4。

### 9.3 图片

exe 通过 `SHDrawJpeg.dll` 的 `LOAD_JPEG_File` / `DRAW_JPEG_File` 从**文件**加载 JPEG。
语料中未发现嵌入 JPEG（`FF D8 FF` 命中均为坐标值误报），亦无图像文件名字符串 [E]。引用方式未知 [?]。

---

## 10. 兼容性与版本差异

- 版本 0x2004 / 0x2005 结构一致 [E]。
- 非 `SYMP` 或 `hdrLen != 0x58C` 时调用 `FUN_00425090`（旧格式头）后继续读 SMC 块 [E]；该路径未分析。
- 旧式消息 0x16 / 0x17（老和弦记号）在读取时被转换为 `CChordSymbol`（`MakeFromOldChordSymbol`）[E]。
- `CSMMsg::ChangeTieSlurInfo` 用于 < 0x2003 的连音/圆滑线换算 [E]。

---

## 11. 未知字段与研究限制

见 `docs/unknown-fields.md`（未解项清单）与 `docs/field-coverage.md`（逐结构覆盖率与字节范围）。

主要空白：
1. `MsgHdr+0x03`、`+0x04`、`+0x28` 的语义。
2. type 0x2C / 0x0C / 0x47 / 0x46 的 head 内部字段（0x47 已给出顶层结构）。
3. `CSMCtrlTool` 与 `CSMFileInfo` 的多数字段语义。
4. 附加字符串语义。
5. 文档级消息 0x3F / 0x40 / 0x04。
6. 图片引用机制。
