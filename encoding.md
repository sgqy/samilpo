# SMC 韩文编码（第二阶段，已恢复）

> 结论：SMC 中的韩文文本使用 **code id 1 = "889F Code"**，即以 Shift-JIS 双字节码位为索引的自定义映射表。
> 码表文件为 `<安装目录>\889F.cod`。该结论**已在 8451/8451 个样本的曲名、全部歌词记录、1991 个文本框上验证**。
>
> 记号：`[E]` 直接证据，`[I]` 推断，`[?]` 未知。

## 1. 模块分工

| 模块 | 类 / 函数 | 作用 |
|---|---|---|
| engine.dll | `CKCConv`（导出） | SMC 文本的编码转换，SMC 读取与绘制实际使用它 [E] |
| engine.dll | `CKCodeConvert`（导出 `SetCodeConverter`） | 另一套转换器，供别处使用 [?] |
| MusicBook.exe | `FUN_00411af0` / `FUN_00411c00` | 读取 `KorCode.cod`，10 字节一条记录，拆成 5 个并列 u16 数组 → **键盘输入/查键表**，与 SMC 文本编码无关 [E] |

## 2. 码表文件选择（id ↔ 文件）[E]

`MusicBook.exe!FUN_00418980`（启动初始化，0x418980）按固定顺序调用 `CKCConv::Open(id, path)`：

| 调用点 | id | 文件（push 立即数） | `GetCodeName(id)` |
|---|---|---|---|
| 0x418f25 | 3 | `\F040a.cod` | "F040(95) Code" |
| 0x418f72 | 4 | `\F040b.cod` | "F040(98) Code" |
| 0x418fe4 | 1 | `\889F.cod` | "889F Code" |
| 0x419057 | 2 | `\B0A1.cod` | "B0A1 Code" |
| 0x4190c6 | 6 | `\KS.cod` | "B0A1(KS) Code" |

id 0 = Unicode（无需码表）；id 5 = "F040(MAC) Code" 对应 `F040c.cod`，本版本**未加载** [E]。
路径前缀由 exe 目录 + `"%s\%s"`（MusicBook.exe 0x43da05）拼接 [E]。
`GetCodeName` 的字符串表：engine.dll `CKCConv::GetCodeName` 0x10030c80，id 0..6 依次为 Unicode / 889F Code / B0A1 Code / F040(95) Code / F040(98) Code / F040(MAC) Code / B0A1(KS) Code [E]。

## 3. `.cod` 文件结构 [E]

来源：加载器 engine.dll `FUN_100306b0`、查表 `FUN_100308c0`（`CKCConv::ToUnicode` 0x100303d0 / `FromUnicode` 0x10030420 都调用它）。

文件由**两个** `CCodeTable` 顺序组成：先是「本编码 → Unicode」的正向表，再是「Unicode → 本编码」的反向表 [E]（889F.cod：正向 0x451A 字节，反向紧随其后，两表合计恰好等于文件长度 90936）。

单个 `CCodeTable` 的磁盘布局：

```
u16 n          区间个数
u16 lo         低字节下界
u16 hi         低字节上界       ; 列数 = hi - lo + 1
重复 n 次：
    u16 start      该区间高位（首字节<<8）起点
    u16 end        该区间高位终点
    u16 data[ ((end - start) >> 8 + 1) * (hi - lo + 1) ]
```

注意：**每个区间是 (start, end, data) 紧邻存放**，不是「先所有 start/end 再所有 data」——这是第一阶段初版解析器的错误，已更正 [E，见更正记录]。

内存结构（`FUN_100306b0` 写入 `CCodeTable`，大小 0x18）：`+4 n`, `+6 lo`, `+8 hi`, `+0xA stride=hi-lo+1`, `+0xC start[]`, `+0x10 end[]`, `+0x14 data*[]`。

已解析的实际布局（全部文件解析后字节恰好用尽）：

| 文件 | 正/反 | 区间（start-end，条目数） |
|---|---|---|
| 889F.cod (90936 B) | 正向 | 0x8800-0x9F00(4608), 0x8100-0x8400(768), 0xE000-0xEA00(2112), 0xF000-0xF300(768), 0xFA00-0xFC00(576)；lo=0x40 hi=0xFF |
| | 反向 | 0xAC00-0xD700(11264), 0x0000-0x0400(1280), 0x2000-0x2600(1792), 0x3000-0x3300(1024), 0x4E00-0x9F00(20992), 0xFF00-0xFF00(256)；lo=0x00 hi=0xFF |
| B0a1.cod (91116 B) | 正向 | 0xA100-0xFE00(8930)；lo=0xA1 hi=0xFF |
| Ks.cod (90926 B) | 正向 | 0xA100-0xFD00(8835)；lo=0xA1 hi=0xFF |
| F040a/b/c.cod (93620 B) | 正向 | 0xF000-0xFC00(2496), 0x8100-0x8400(768), 0x8700-0x9F00(4800), 0xE000-0xEA00(2112)；lo=0x40 hi=0xFF |

## 4. 查表算法 [E]

`FUN_100308c0(table, code)`：

```
if not (lo <= (code & 0xFF) <= hi):           return code       # 原样返回
for i in range(n):
    if start[i] <= (code & 0xFF00) <= end[i]:
        idx = ((code & 0xFF00) - start[i]) >> 8) * stride + (code & 0xFF) - lo
        v = data[i][idx]
        return v if v != 0 else code          # 0 项 = 未映射，原样返回
return code
```

**未映射项返回原始码位**，绘制端随后用字体自身的字形区域渲染。这解释了部分歌词记录出现「原码」而非 Unicode 的现象 [?，见 §6 未决项]。

## 5. 文本转换路径 [E]

`MyDrawTextOutW`（engine.dll 0x10096530）是绘制端统一入口，其汇编明确：

```
PUSH 0x3 ; CKCConv::ToUnicode(3, src, len, NULL, 0)   ; 取字符数
PUSH 0x1 ; CKCConv::ToUnicode(1, src, len, dst, cnt)  ; 实际转换（id 1 = 889F）
TextOutW(hdc, x, y, dst, cnt)
```

- 第一次用 id 3 只为求长度（长度与 id 无关）[E]。
- 第二次用 **id 1** 完成转换 —— 这是 SMC 文本 = 889F 编码的直接证据 [E]。
- 调用者：`CSMLyricMsg::DrawMsg`（0x1009AD00）、`CSMTextMsg::RichTextLineOut`（0x100C3BF0）等所有文本绘制 [E]。
- `CKCConv::ToUnicode` 0x10030D90 对 `<0x80` 的字节直接透传，≥0x80 按双字节码位查表 [E]。
- 另有 `CKCConv::Convert(from,to,...)` 0x10031020、`ConvertFont` 0x100317D0 用于不同编码间互转/字体名换算 [E]。

## 6. 验证结果 [E]

用 `tools/smc_text.py`（按上述格式与查表实现）对真实文件解码：

| 数据 | 样本量 | 结果 |
|---|---|---|
| 曲名（file 0x0E 起，NUL 结尾） | 8451/8451 | 全部可由 889F 表解出韩文；无需该表/该表不匹配者 0 |
| 歌词记录（Msg 0x19 文本） | 全量抽样 9129 条 | 全部解出韩文音节 |
| 文本框（Msg 0x06，tag 0x06） | 1991 条记录 / 5260 段文本 | 全部解出（含「보통속도로」「작사 리찬, 작곡 김원균」「（후렴）」） |
| 对照组 | 同数据用 B0a1/Ks/F040a 解码 | 均得到无意义汉字，确认只有 889F 正确 |

典型样本：

- `500KFS-0041.smc` 曲名 → `바다의 노래`
- `150ALS-03DA-0012.smc` 歌词起始 → `1.불 뿜는 적의 화점…`
- `110SSS-001.smc` 文本框 → `작사 리찬, 작곡 김원균`

字符分类：

- `< 0x80`：ASCII 单字节透传（空格 0x20、数字、`1.` 等）[E]
- 双字节：首字节 0x88–0x9F / 0xE0–0xFC 区段为主；SJIS 用户定义区 0xF000–0xF300 被 889F 表覆盖并映射到符号（如 `F0 41` → U+FF0D 全角连字符，用作歌词分隔符）[E]
- 未映射码位：查表返回原码，解码器保留原值（不报错）[E]

## 7. 更正记录（第一阶段结论）

第一阶段 `smc-format.md` 的 §8 与初版 `tools/smc_text.py` 有两处需要更正，均已修正：

1. **`.cod` 记录结构**：初版按「先全部 start/end，再全部 data」解析，导致第 2 个区间起偏移错位。实际为每区间 `(start,end,data)` 紧邻。依据 engine.dll `FUN_100306b0` 逐项读取顺序 [E]。
2. **编码身份**：初版仅推测「韩文被映射到 SJIS 码位」。现由 `MyDrawTextOutW` → `ToUnicode(1,…)` 与全部样本解码共同确认为 **id 1 = 889F.cod** [E]。

## 8. 仍未确定
1. `889F.cod` 正向表 0x8800–0x9F00 区段是「SJIS 韩文区」，其内部排列是否为某标准（如 KS X 1001）的置换，尚不确定；不影响解码，但影响「为何选此布局」的解释 [?]。
2. 未映射码位（约 13% 的歌词记录含此情况）在字体中是私人字形还是真符号，需解析 Wk*.ttf 的 cmap 才能判定 [?]。
3. `KorCode.cod`（10 字节/条、5 并列数组）与 `KcgInfo.kbd` 的具体用途（键盘输入法映射？）未展开 [E 结构 / ? 语义]。
4. `F040.cod`（5122 字节）不含 `CCodeTable` 头，用途未知；本版本启动流程未加载它 [E 观察 / ? 语义]。
