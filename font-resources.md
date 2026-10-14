# SMC 字体、字形与符号编码（第三阶段）

> 本文件记录 SMC 文件与 Samilpo 2.0 的字体、字形和音乐符号机制。
> 记号 `[E]` 直接证据 / `[I]` 推断 / `[?]` 未知。

## 1. 结论速览

1. **文本与音乐符号使用完全不同的两套字符空间** [E]：
   - **文本**（歌词、曲名、文本框）：889F Code（`889F.cod`，→ 韩文 Unicode）
   - **音乐符号**（符头、附点、变音、力度、踏板…）：引擎内单字节常量 0x7F–0xFF + `KayakumA` **符号字体**（→ U+F020–U+F0FF 私人区）
2. 889F 正向表**没有任何**码位映射到 U+F000–U+F0FF（0 个）[E]。
3. `KAYAKUMA.TTF` 的 cmap **只覆盖 U+F020–U+F0FF**（223 字形），是一个纯符号字体 [E]。
4. SMC 文件本身**只存储字体索引与名称**（§3），字形由程序字体渲染；文件中没有字形位图或轮廓 [E]。

## 2. 程序加载的字体

`MusicBook.exe!FUN_00418980`（InitInstance）加载 8 个 TTF，目录 `C:\Program Files (x86)\Samilpo 2.0\Font\` [E]：

| 文件 | 大小 | cmap 覆盖 | 用途 |
|---|---|---|---|
| `KAYAKUMA.TTF` | 63688 | **U+F020–U+F0FF（仅符号）** | **乐谱符号字体**（`KayakumA`） |
| `wkgothic.ttf` | 4601592 | 3,1 平面（6988 段） | 韩文正文字体 |
| `Wkgoth.TTF` | 2631404 | 3,1 平面（6988 段） | 韩文正文字体 |
| `Wklchbo.ttf` | 4106100 | 3,1 平面（6988 段） | 韩文字体 |
| `WKLGM.TTF` | 1561416 | 3,1 平面（2362 段） | 韩文/符号混合 |
| `Wklgoth.ttf` | 1820540 | 3,1 平面（2362 段） | 韩文字体 |
| `Wkpukgul.ttf` | 1283432 | 3,1 平面（2362 段） | 韩文字体 |
| `Wkwchbo.ttf` | 1282916 | 3,1 平面（2362 段） | 韩文字体 |

验证（`tools/_probe_font_cmap.py`）：
- `wkgothic.ttf`：889F → Unicode 的 5483 个码位中 **5414 个（98.7%）在字体中有字形** [E]
- `WKLGM.TTF`：3433/5483（62.6%）
- `KAYAKUMA.TTF`：**0/5483**（纯符号字体，不含韩文）[E]

## 3. SMC 文件中的字体信息

### 3.1 字体表（`CFontDatas::LoadBuffer` 0x1002c100）[E]

文件内字体表为重复记录：

```
FontRecord := u8 index, u8 nameLen, u8 name[nameLen]
```

- `index` 是后续消息可引用的**字体索引**（1..N）。
- `name` 是字体显示名（889F 编码）。
- 例：`01 0A "ＷＫ細明朝"`、`06 0C "WKGothic(KS)"`、`07 05 "Gulim"`、`08 06 "System"` [E]

### 3.2 消息中的字体引用

| 消息类型 | 字体索引位置 | 字号位置 | 证据 |
|---|---|---|---|
| 歌词 0x19 | head +0x00（u16） | head +0x04（u16，默认 13） | `CSMLyricMsg::DrawMsg` 0x1009ad00 |
| 文本框 0x06 | TLV 标签 0x02（u16） | TLV 标签 0x04（u16） | `CSMTextMsg::DrawMsg` 0x100c2f70 |
| 音符 0x01 | 无字体索引 | MsgHdr+02（缩放百分比，默认 16） | `DrawNote` 0x1004ec70 |

语料统计：歌词字体索引仅 6 个取值 {1,2,3,5,6,7}；字号仅 {13, 14}（13 出现 9002、14 出现 127）[E]。

### 3.3 字体名换算

- `CKCConv::ConvertFont` 0x100317d0：字体名在不同编码间换算 [E]
- exe 载入字体表后对 9 个 `LOGFONT.lfFaceName` 位置调用 `GetNearestFontName` [E]

## 4. 音乐符号机制

### 4.1 符号字体选择

`CScoreView::DrawNote` 0x1004ec70 明确构造字体名 **"KayakumA"**：

```
GetDefaultLogFont(&lf, height, "KayakumA", 0, dc);
```
（当谱面字号变化时重建）[E]

### 4.2 单字节符号常量

引擎以单字节常量表示音乐符号，`DrawTextOut` 用符号字符集字体输出。已解析常量（engine 映像地址）：

| 符号 | 地址 | 值 | 说明 |
|---|---|---|---|
| `codeStdHead[0..8]` | 0x10100390 | `D6 D7 D8 D9 D9 D9 D9 D9 D9` | 9 种标准符头（按符值） |
| `codeCrossHead` | 0x101003A4 | `E4` | × 符头 |
| `codeSlashHead[]` | 0x101003B4 | `DC DC DC DC DC DC DC DC DC` | 斜线符头 |
| `codeBoxHead` | 0x101003C0 | `DB DC DD…` | 方框/菱形/方形符头 |
| `codeDot` | 0x101003C6 | `E1` | 附点 |
| `codeAcci[]` | 0x10100430 | 变音记号码表 | ♯ ♭ ♮ 等（`DrawKeysign`） |
| `CodeDyn[]` | 0x101006D4 | 力度记号码表 | p mp mf f … |
| `codePedal` | — | "b" | 踏板 |
| `codeBreath` / `codeCesura` / `codeMeasRepeat` / `codeMeasOneRepeat` | — | 换气/断句/反复 | DrawSingle_Msg |
| `codeSlid[0..3]` | — | 滑音线 |
| `codeCircleUp/Down/BigCircleDown` | — | 圈记号 |
| `codeSmallDigit[]` | 0x101003C7 起 | `E2…` | 小数字（`DrawGerneralFont`） |
| `codeShortLine` | — | 符干短横 |

引擎常量表整体存于 `0x10100380` 起的 384 字节，包含 ASCII（'<' 'D' 'E' 'B' 'C' '=' ';' ':' '+' 'z' 'w' ',' '{'）与符号字节（0x7F–0xFF）[E]。

### 4.3 符号字体与 Windows 字符集

- `KAYAKUMA.TTF` 的 cmap 覆盖 **U+F020–U+F0FF**；Windows 的 **symbol charset** 会把单字节 0x20–0xFF 映射到 U+F020–U+F0FF [E 字体 cmap + Windows 语义]。
- 因此引擎输出字节 `0xD6` 经符号字符集渲染为 `U+F0D6` 的字形 [I，强]。
- 字体内部指标：`numGlyphs = 223`，`post` 表版本 2.0（有字形名）[E]。
- 字体名（name 表）：family/style/full/PS 名均为 **"KayakumA" / "Regular"** [E]。

### 4.4 与 889F 编码的关系 —— 无重叠

`tools/_probe_symbols.py` 结果 [E]：
- 889F 正向表 5483 个映射中，**0 个**落在 U+F000–U+F0FF。
- 889F 的 0xF000–0xF300 区段映射到的是 **U+FF0D（全角连字符）等符号**及韩文（见 `encoding.md`），与音乐符号字体无关。
- 对 401 个样本扫描这些码位在正文中的出现：**无**。

**结论**：韩文文本与音乐符号的字符映射**互不重叠**，分属两套编码空间；SMC 文件中音乐符号以引擎常量（不在文件里）或消息字段数值表达，而非文本字符 [E]。

## 5. 字形索引存储位置

SMC 文件中**不存储字形编号本身**；存的是：

| 文件内字段 | 反映的符号 |
|---|---|
| 音符 `MsgHdr+06`（符头类型） | 选择 `codeStdHead`/`codeCrossHead`/… 表 |
| 音符 `MsgHdr+05` 低 4 位 | 附点数（由 `codeDot` 绘制） |
| 音符 `MsgHdr+05` 高 4 位 | 变音记号状态（由 `codeAcci` 绘制） |
| 力度 `MsgHdr+08` | `CodeDyn` 索引 |
| 调号 `MsgHdr+08` | `codeAcci` 索引 |
| 休止符 `MsgHdr+08` | 休止符字型号 |
| 字体索引（歌词/文本框 head） | `CFontDatas` 中的字体（韩文文本） |

因此第三方渲染 SMC 需要一个含等价音乐符号字形的符号字体，或按其语义自行矢量绘制 [I]。

## 6. 未决项

1. `KAYAKUMA.TTF` 未附字形名清单（`post` 2.0 有名称表但未导出）；如需逐符号对应，可解析 `post` 表。
2. `codeSmallDigit` / `codeSlid` 等常量表的完整地址与项数未逐一确认 [?]。
3. 是否存在文件中引用字体名（而非索引）的字段：目前只见索引 [?]。
4. 图片（JPEG）引用机制见 `smc-format.md` §9.3，仍未知 [?]。
