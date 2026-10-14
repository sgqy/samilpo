# SMC 韩文编码（`.cod` 码表）

> 凡例见 `docs/smc-format.md` §0（知识评级 `[E]`/`[I]`/`[?]`/`[C]`；数据类型为 Rust 风格）。
> 结论：SMC 文本使用 **code id 1 = "889F Code"**，即以 Shift-JIS 双字节码位为索引的自定义映射表；
> 码表文件为 `<安装目录>\889F.cod`。**已在 8451/8451 样本的曲名、全部歌词记录、1991 个文本框上验证**。

## 1. 模块分工

| 模块 | 类 / 函数 | 作用 | 评级 |
|---|---|---|---|
| engine.dll | `CKCConv`（导出） | SMC 文本的编码转换；读取与绘制实际使用 | [E] |
| engine.dll | `CKCodeConvert`（导出 `SetCodeConverter`） | 另一套转换器 | [?] |
| MusicBook.exe | `FUN_00411AF0` / `FUN_00411C00` | 读取 `KorCode.cod`（10 字节/条 → 5 个并列 `u16` 数组）= **键盘输入/查键表**，与 SMC 文本编码无关 | [E] |

## 2. 码表文件选择（id ↔ 文件）

`MusicBook.exe!FUN_00418980`（启动初始化，0x418980）按固定顺序调用 `CKCConv::Open(id, path)` [E]：

| 调用点 | id | 文件 | `GetCodeName(id)` |
|---|---|---|---|
| 0x418F25 | 3 | `\F040a.cod` | `"F040(95) Code"` |
| 0x418F72 | 4 | `\F040b.cod` | `"F040(98) Code"` |
| 0x418FE4 | 1 | `\889F.cod` | `"889F Code"` |
| 0x419057 | 2 | `\B0A1.cod` | `"B0A1 Code"` |
| 0x4190C6 | 6 | `\KS.cod` | `"B0A1(KS) Code"` |

- id 0 = Unicode（无需码表）；id 5 = `"F040(MAC) Code"`（`F040c.cod`）本版本**未加载** [E]。
- 路径前缀 = exe 目录 + `"%s\%s"`（MusicBook.exe 0x43DA05）[E]。
- `GetCodeName` 字符串表：engine.dll `CKCConv::GetCodeName` 0x10030C80，
  id 0..6 = Unicode / 889F Code / B0A1 Code / F040(95) Code / F040(98) Code / F040(MAC) Code / B0A1(KS) Code [E]。

## 3. `.cod` 文件结构

来源：加载器 `FUN_100306B0`、查表 `FUN_100308C0`（`CKCConv::ToUnicode` 0x100303D0 / `FromUnicode` 0x10030420 都调用它）[E]。

文件由**两个** `CCodeTable` 顺序组成：先「本编码 → Unicode」正向表，再「Unicode → 本编码」反向表 [E]。
（889F.cod：正向 0x451A 字节，反向紧随其后，两表合计恰好等于文件长度 90936。）

单个 `CCodeTable` 的磁盘布局：

```
CCodeTable :=
    n     : u16                       ; 区间个数
    lo    : u16                       ; 低字节下界
    hi    : u16                       ; 低字节上界（列数 = hi - lo + 1）
    ranges: [Range; n]
Range :=
    start : u16                       ; 该区间高位（首字节 << 8）起点
    end   : u16                       ; 该区间高位终点
    data  : [u16; (((end - start) >> 8) + 1) * (hi - lo + 1)]
```

**注意**：每个区间是 `(start, end, data)` **紧邻**存放，不是「先所有 start/end 再所有 data」——
这是第一阶段初版解析器的错误，已更正 [C → 修正]。

内存结构（`FUN_100306B0` 写入 `CCodeTable`，对象大小 0x18）：
`+0x4 n`、`+0x6 lo`、`+0x8 hi`、`+0xA stride = hi - lo + 1`、`+0xC start[]`、`+0x10 end[]`、`+0x14 data*[]` [E]。

已解析的实际布局（所有文件解析后字节恰好用尽）[E]：

| 文件 | 方向 | 区间（start–end，条目数） |
|---|---|---|
| 889F.cod (90936 B) | 正向 | 0x8800–0x9F00(4608), 0x8100–0x8400(768), 0xE000–0xEA00(2112), 0xF000–0xF300(768), 0xFA00–0xFC00(576)；`lo=0x40 hi=0xFF` |
| | 反向 | 0xAC00–0xD700(11264), 0x0000–0x0400(1280), 0x2000–0x2600(1792), 0x3000–0x3300(1024), 0x4E00–0x9F00(20992), 0xFF00–0xFF00(256)；`lo=0x00 hi=0xFF` |
| B0a1.cod (91116 B) | 正向 | 0xA100–0xFE00(8930)；`lo=0xA1 hi=0xFF` |
| Ks.cod (90926 B) | 正向 | 0xA100–0xFD00(8835)；`lo=0xA1 hi=0xFF` |
| F040a/b/c.cod (93620 B) | 正向 | 0xF000–0xFC00(2496), 0x8100–0x8400(768), 0x8700–0x9F00(4800), 0xE000–0xEA00(2112)；`lo=0x40 hi=0xFF` |

## 4. 查表算法

`FUN_100308C0(table, code)` [E]：

```
if not (lo <= (code & 0xFF) <= hi):  return code          # 原样返回
for i in 0..n:
    if start[i] <= (code & 0xFF00) <= end[i]:
        idx = (((code & 0xFF00) - start[i]) >> 8) * stride + (code & 0xFF) - lo
        v = data[i][idx]
        return v if v != 0 else code                      # 0 项 = 未映射，原样返回
return code
```

**未映射项返回原始码位**，绘制端随后用字体自身的字形区域渲染 [E]。这解释了部分歌词记录出现
「原码」而非 Unicode 的现象 [?，见 §8]。

## 5. 文本转换路径

`MyDrawTextOutW`（engine.dll 0x10096530）为绘制端统一入口，其汇编明确 [E]：

```
PUSH 0x3 ; CKCConv::ToUnicode(3, src, len, NULL, 0)   ; 取字符数
PUSH 0x1 ; CKCConv::ToUnicode(1, src, len, dst, cnt)  ; 实际转换（id 1 = 889F）
TextOutW(hdc, x, y, dst, cnt)
```

- 第一次用 id 3 只为求长度（长度与 id 无关）[E]。
- 第二次用 **id 1** 完成转换 —— SMC 文本 = 889F 的直接证据 [E]。
- 调用者：`CSMLyricMsg::DrawMsg`（0x1009AD00）、`CSMTextMsg::RichTextLineOut`（0x100C3BF0）等所有文本绘制 [E]。
- `CKCConv::ToUnicode` 0x10030D90 对 `< 0x80` 的字节直接透传，`>= 0x80` 按双字节码位查表 [E]。
- 另有 `CKCConv::Convert(from, to, …)` 0x10031020、`ConvertFont` 0x100317D0 用于不同编码互转/字体名换算 [E]。

## 6. 验证结果

`tools/smc_text.py`（按上述格式与查表实现）对真实文件解码 [E]：

| 数据 | 样本量 | 结果 |
|---|---|---|
| 曲名（file 0x0E 起，NUL 结尾） | 8451/8451 | 全部可由 889F 表解出韩文；无需该表/不匹配者 0 |
| 歌词记录（Msg 0x19 文本） | 全量抽样 9129 条 | 全部解出韩文音节 |
| 文本框（Msg 0x06，tag 0x06） | 1991 条记录 / 5260 段文本 | 全部解出 |
| 对照组 | 同数据用 B0a1 / Ks / F040a 解码 | 均得无意义汉字 → 只有 889F 正确 |

典型样本：

- `500KFS-0041.smc` 曲名 → `바다의 노래`
- `150ALS-03DA-0012.smc` 歌词起始 → `1.불 뿜는 적의 화점…`
- `110SSS-001.smc` 文本框 → `작사 리찬, 작곡 김원균`

字符分类 [E]：

- `< 0x80`：ASCII 单字节透传（空格 0x20、数字、`1.` 等）。
- 双字节：首字节 0x88–0x9F / 0xE0–0xFC 区段为主；SJIS 用户定义区 0xF000–0xF300 被 889F 表覆盖并映射到符号
  （如 `F0 41` → U+FF0D 全角连字符，用作歌词分隔符）。
- 未映射码位：查表返回原码，解码器保留原值（不报错）。
- 全语料 889F 正向表共 **5483** 个有效映射 [E]。

## 7. 更正记录

| 阶段 | 原结论 | 现结论 | 依据 |
|---|---|---|---|
| 一 | `.cod` 记录「先全部 start/end，再全部 data」 | 每区间 `(start, end, data)` 紧邻；否则第 2 区间起偏移错位 | `FUN_100306B0` 逐项读取顺序 [E] |
| 一 | 仅推测「韩文被映射到 SJIS 码位」 | 确认 **id 1 = 889F.cod** | `MyDrawTextOutW` → `ToUnicode(1,…)` + 全量解码 [E] |

## 8. 仍未确定

1. `889F.cod` 正向表 0x8800–0x9F00 区段（「SJIS 韩文区」）的内部排列是否为某标准（如 KS X 1001）的置换，
   尚不确定；不影响解码，但影响「为何选此布局」的解释 [?]。
2. 未映射码位（约 13% 的歌词记录含此情况）在字体中是私人字形还是真符号，需解析 Wk*.ttf 的 cmap [?]。
   —— 第四阶段已确认：889F 表**没有**码位映射到 U+F000–U+F0FF，音乐符号走独立路径（见 `docs/font-resources.md`）。
3. `KorCode.cod`（10 字节/条、5 并列数组）与 `KcgInfo.kbd` 的具体用途（键盘输入法映射？）未展开 [E 结构 / ? 语义]。
4. `F040.cod`（5122 字节）不含 `CCodeTable` 头，用途未知；本版本启动流程未加载 [E / ?]。
