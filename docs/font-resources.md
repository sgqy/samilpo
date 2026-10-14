# SMC 字体、字形与音乐符号

> 凡例见 `docs/smc-format.md` §0（知识评级 `[E]`/`[I]`/`[?]`/`[C]`；数据类型为 Rust 风格）。

## 1. 结论速览

1. **文本与音乐符号使用完全不同的两套字符空间** [E]：
   - **文本**（歌词、曲名、文本框）：889F Code（`889F.cod` → 韩文 Unicode）
   - **音乐符号**（符头、附点、变音、力度、踏板…）：引擎内单字节常量 0x7F–0xFF + `KayakumA` **符号字体**
     （Windows 符号字符集 → U+F020–U+F0FF 私人区）
2. 889F 正向表**没有任何**码位映射到 U+F000–U+F0FF（0 个）[E]。
3. `KAYAKUMA.TTF` 的 cmap **只覆盖 U+F020–U+F0FF**（223 字形），是纯符号字体 [E]。
4. SMC 文件本身**只存储字体索引与名称**（§3），字形由程序字体渲染；文件中没有字形位图或轮廓 [E]。

## 2. 程序加载的字体

`MusicBook.exe!FUN_00418980`（InitInstance）加载 8 个 TTF，目录 `<安装目录>\Font\` [E]：

| 文件 | 大小 | cmap 覆盖 | 用途 | 评级 |
|---|---|---|---|---|
| `KAYAKUMA.TTF` | 63688 | **U+F020–U+F0FF（仅符号）** | **乐谱符号字体**（`KayakumA`） | [E] |
| `wkgothic.ttf` | 4601592 | 3,1 平面（6988 段） | 韩文正文字体 | [E] |
| `Wkgoth.TTF` | 2631404 | 3,1 平面（6988 段） | 韩文正文字体 | [E] |
| `Wklchbo.ttf` | 4106100 | 3,1 平面（6988 段） | 韩文字体 | [E] |
| `WKLGM.TTF` | 1561416 | 3,1 平面（2362 段） | 韩文/符号混合 | [E] |
| `Wklgoth.ttf` | 1820540 | 3,1 平面（2362 段） | 韩文字体 | [E] |
| `Wkpukgul.ttf` | 1283432 | 3,1 平面（2362 段） | 韩文字体 | [E] |
| `Wkwchbo.ttf` | 1282916 | 3,1 平面（2362 段） | 韩文字体 | [E] |

验证（`tools/_probe_font_cmap.py`，纯 Python 解析 cmap）[E]：

| 字体 | 889F→Unicode 码位中有字形的比例 |
|---|---|
| `wkgothic.ttf` | 5414 / 5483（98.7%） |
| `WKLGM.TTF` | 3433 / 5483（62.6%） |
| `KAYAKUMA.TTF` | **0 / 5483**（纯符号字体） |

## 3. SMC 文件中的字体信息

### 3.1 字体表（`CFontDatas::LoadBuffer` 0x1002C100）

```
FontRecord :=
    index   : u8
    nameLen : u8
    name    : [u8; nameLen]     ; 889F 编码，末尾补 NUL
```

- `index` 为后续消息引用的**字体索引**（1..N）。
- 例：`01 0A "ＷＫ細明朝"`、`06 0C "WKGothic(KS)"`、`07 05 "Gulim"`、`08 06 "System"` [E]。

### 3.2 消息中的字体引用

| 消息类型 | 字体索引位置 | 字号位置 | 证据 | 评级 |
|---|---|---|---|---|
| 歌词 0x19 | head +0x00（`u16`） | head +0x04（`u16`，默认 13） | `CSMLyricMsg::DrawMsg` 0x1009AD00 | [E] |
| 文本框 0x06 | TLV 标签 0x02（`u16`） | TLV 标签 0x04（`u16`） | `CSMTextMsg::DrawMsg` 0x100C2F70 | [E] |
| 音符 0x01 | 无字体索引 | `MsgHdr+0x02`（缩放百分比，默认 16） | `DrawNote` 0x1004EC70 | [E] |

语料统计：歌词字体索引仅 6 个取值 {1, 2, 3, 5, 6, 7}；字号仅 {13: 30136, 14: 140, 12: 74, 0: 3}（第四阶段 400 文件抽样）[E]。

### 3.3 字体名换算

- `CKCConv::ConvertFont` 0x100317D0：字体名在不同编码间换算 [E]。
- 载入字体表后 exe 对 9 个 `LOGFONTA.lfFaceName` 位置调用 `GetNearestFontName` [E]。

## 4. 音乐符号机制

### 4.1 符号字体选择

`CScoreView::DrawNote` 0x1004EC70 明确构造字体名 **"KayakumA"**：

```
GetDefaultLogFont(&lf, height, "KayakumA", 0, dc);
```

（谱面字号变化时重建）[E]。`CFretBoard` 亦以 `lstrcpyA(obj+0x96, "KayakumA")` 设定同一字体 [E]。

### 4.2 单字节符号常量表（引擎映像导出）

符号常量集中于 `0x10100360`–`0x10100700`。全部为**单字节**值，经符号字符集渲染 [E]。

| 常量 | 地址 | 字节序列 | 项数 | 说明 |
|---|---|---|---|---|
| `codeSlid` | 0x10100364 | `66 67 68 69 6A 6D 2F 2E 27` | 9 | 滑音/装饰字符 |
| `codePedal` | 0x10100370 | `8C 8D 6B 8F 90 …` | ≥4 | 踏板记号 |
| `codeMeasRepeat` | 0x10100374 | `8E 8B 4D …` | ≥3 | 小节反复 |
| `codeStdHead` | 0x10100390 | `D6 D7 D8 D9 D9 D9 D9 D9 D9` | 9 | **标准符头**（按时值指数） |
| `codeBoxHead` | 0x1010039C | `E5 E4 E4 E4 E4 E4 E4 E4 E4` | 9 | 方框/菱形符头 |
| `codeCrossHead` | 0x101003A8 | `DB DB DB DD DD DD DD DD DD` | 9 | × / 特殊符头 |
| `codeSlashHead` | 0x101003B4 | `DC DC DC DC DC DC DC DC DC` | 9 | 斜线符头 |
| `codeDot` | 0x101003C6 | `E1` | 1 | 附点 |
| `codeShortLine` | 0x101003ED | `FF` | 1 | 符干短横 |
| `codeAcci` | 0x10100430 | `00 A9 AA AB AC AD DA 00 D6 D7 C4 89 92 93 94 95 96 EE 00 00 BD BE …` | 变音记号表（`DrawKeysign` 0x100571F0 按 `MsgHdr+0x08` 索引） |
| `codeSmallDigit` | 0x10100464 | `D0 D1 D2 D3 D4 D5 00 00 3F 46 47 3E CB CB …` | 小数字 |
| `CodeDyn` | 0x101006D4 | `00 F0 F1 F2 F3 F4 F5 F6 F7 F9 FA FB FC FD FE FF` | 16 | **力度记号**（索引 0 → 空；`DrawDynamic` 0x1005E690） |

- 常量区还包含 ASCII 值（`3E 44 45 42 00 43 05 00 05 00 3D 3C 2D 28 29 00`、`3F 46 47 3E`、`3F 46 47 3E`、
  `2B 7A 77 2C 7B 00`、`30 3B 3A`），与符号字节混排 [E]。
- 后续（0x101006E4 起）为 `u16` 表：`08 00 04 00 04 00 08 00 0C 00 10 00 14 00 18 00 …`，
  疑为**时值/位置**或**强弱辅助**表 [?]。

### 4.3 符号字体与 Windows 字符集

- `KAYAKUMA.TTF` 的 cmap 覆盖 **U+F020–U+F0FF**；Windows 的 **symbol charset** 把单字节 0x20–0xFF
  映射到 U+F020–U+F0FF [E 字体 cmap + Windows 语义]。
- 因此引擎输出字节 `0xD6` 经符号字符集渲染为 `U+F0D6` 的字形 [I，强]。
- 字体指标：`numGlyphs = 223`，`post` 版本 2.0（有字形名）[E]。
- name 表：family/style/full/PS 名均为 **`"KayakumA"` / `"Regular"`** [E]。

### 4.4 与 889F 编码的关系 —— 无重叠

`tools/_probe_symbols.py` 结果 [E]：

- 889F 正向表 5483 个映射中，**0 个**落在 U+F000–U+F0FF。
- 889F 的 0xF000–0xF300 区段映射到 **U+FF0D（全角连字符）等符号**及韩文，与音乐符号字体无关。
- 对 401 个样本扫描这些码位在正文中的出现：**无**。

**结论**：韩文文本与音乐符号的字符映射**互不重叠**，分属两套编码空间；SMC 文件中音乐符号以
消息字段数值表达，字形常量本身不在文件里 [E]。

## 5. 字形索引的存储位置

SMC 文件中**不存储字形编号本身**；存的是选择字形的字段：

| 文件内字段 | 反映的符号 | 评级 |
|---|---|---|
| 音符 `MsgHdr+0x06`（符头类型） | 选择 `codeStdHead` / `codeCrossHead` / `codeSlashHead` / `codeBoxHead` | [E] |
| 音符 `MsgHdr+0x05` 低 4 位 | 附点数（由 `codeDot` 绘制） | [E] |
| 音符 `MsgHdr+0x05` 高 4 位 | 变音状态（由 `codeAcci` 绘制） | [E] |
| 力度 `MsgHdr+0x08` | `CodeDyn` 索引 | [E] |
| 调号 `MsgHdr+0x08` | `codeAcci` 索引 | [E] |
| 休止符 `MsgHdr+0x08` | 休止符字型号 | [E] |
| 长休止 `MsgHdr+0x1C` | 小节数（打印数字） | [E] |
| 歌词/文本框 head 的字体索引 | `CFontDatas` 中的字体（韩文文本） | [E] |

第三方渲染 SMC 需等价符号字体，或按语义自行矢量绘制 [I]。

## 6. 未决项

1. `KAYAKUMA.TTF` 的字形名清单（`post` 2.0 有名称表但未导出）；如需逐符号对应，可解析 `post` 表 [?]。
2. `codeSmallDigit` / `codeSlid` / `codeAcci` 的完整项数与逐项语义未逐一确认 [?]。
3. 是否存在引用字体名（而非索引）的字段：目前只见索引 [?]。
4. 图片（JPEG）引用机制见 `docs/smc-format.md` §9.3 [?]。
