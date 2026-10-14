# 研究状态

最后更新：第三阶段完成（2026-10-14）。

## 全局

- 目标：恢复 Samilpo SMC 乐谱文件格式（数字遗产保存）。
- 工作区：`C:\research\samilpo`（文档 + `tools/` 脚本 + `raw/` 原始证据 + `docs/` 过程记录）。
- 阶段一：帧结构 + 调用链。
- 阶段二：韩文编码 + 歌词消息 0x19 + 歌词↔音符关联。
- 阶段三（本次）：**消息头全字段 + 类型分派全表 + 音符 head 全字段 + 结构对象（System/Staff/Meas/Page/Block）+ 字体与符号机制**。

## 阶段三已完成（任务 A / B / C / D）

### 任务 A：主规范重组
- [x] `smc-format.md` **按文件实际结构重写**（§1 概述 → §11 未知项），含字段级表与偏移量。
- [x] 新增专题：`music-fields.md`、`font-resources.md`、`layout.md`、`unknown-fields.md`。
- 验证：`tools/smc_census.py` 对全部 **8451/8451** 样本精确消耗主体、尾部恰好 4 字节。

### 任务 B：消息类型扩展（本阶段主要成果）
- [x] **MsgHdr（0x2C）逐字段磁盘表**：由 `CSMMsg::Read` 0x1007a490 与 `CSMMsg::Write` 0x1007a240 **双向确证**。
- [x] **ObjectCore 磁盘布局**：`+06 = headLen + 12`；`+01` 为写入未初始化栈的保留字节（读取端忽略）。
- [x] **Child 8 字节**：`u32 key, u8 role, u8 pad[3]`；`role != 0` 表示嵌入对象，并编码 tie/slur 角色。
- [x] **类型 → 绘制器完整分派表**（`CScoreView::SMDrawMsg` 0x1004aa00），覆盖 40+ 类型。
- [x] **音符 Msg 0x01 head（12 字节）全字段**：key / velocity / 常量 0x40 / 声部 / 时值 u32 / 起始时间 u32。
- [x] **音乐属性**：符号头部 `+05` 高低半字节（状态/附点）、`+06` 符头类型、`+08` 类型相关索引、`+0A` 标志位。
- [x] **结构对象**：System / Staff / Meas（含拍号分子分母）/ Page / Block 字段表。
- [x] 全语料类型频率与字段分布统计。

### 任务 C：字体、字形与符号
- [x] 程序加载的 8 个 TTF 与 cmap 覆盖；
- [x] **`KAYAKUMA.TTF` = 符号字体**，cmap 仅 U+F020–U+F0FF（223 字形）；
- [x] **音乐符号 = 引擎单字节常量（0x7F–0xFF）**，与 889F 文本编码**零重叠**；
- [x] 解析引擎符号常量表（0x10100380 起）。

### 任务 D：资源与特殊结构
- [x] 字体表缓冲格式（`u8 index, u8 nameLen, u8 name[]`）；
- [x] 图片：语料无嵌入 JPEG、无文件名（记录为未决）；
- [x] 低类型（0x2c/0x0c/0x47/0x46）记录入 `unknown-fields.md`。

## 阶段二成果（保留）

- 韩文编码 = code id 1 = `889F.cod`；`.cod` 双表结构与查表算法；绘制路径 `MyDrawTextOutW → ToUnicode(1,…)`。
- 歌词 type 0x19 = `CSMLyricMsg`；head = `0x10 + 文本字节数`；歌词为音符 0x01 的嵌入子对象。
- 文本框 0x06 的 TLV 标签表。

## 阶段一成果（保留）

- SMC 解析入口 `MusicBook.exe!FUN_00424670` → `engine!CSMCtrlTool::Read` → `CSMFileInfo::Read` → `CSMDoc::Load`。
- 帧结构：`tools/smc_walk.py` / `tools/smc_census.py` 全语料精确消耗。
- 无压缩/加密。

## 关键结论速查

1. 文件 = `hdrLen(0x58C)` + SYMP头(0x58C) + 附加串 + SMC块(0x318) + 字体表 + CtrlTool + FileInfo(0x20) + `u32 bodyLen` + 主体 + `u32 bodyLen`。
2. 主体 = System + DocHdr(10) + Msg×3 + Page×N；全部乐谱元素统一为 **Msg**。
3. Msg = `MsgHdr(0x2C)` + ObjectCore（12 字节头 + head + 子项）；对象间用 32 位 key 引用。
4. **ObjectCore 磁盘头** = `u8 childCount, u8 保留(忽略), u16 f2, u16 headLen, u16 (headLen+12), u32 f8`。
5. **MsgHdr 关键字段**：+00 类型、+01(高4 括号/低4 声部)、+02 缩放、+05(高4 状态/低4 附点)、+06 符头类型、+08 类型索引（时值/休止/力度/调号/谱号）、+0A 标志位、+16 相对X、+18 音高Y、+20 端点键、+24 本对象key。
6. **音符 head[12]**：`key, velocity, 0x40, voice, u32 duration, u32 startTime`。
7. 文本编码 = 889F；音乐符号 = 引擎常量 + `KayakumA` 符号字体（两套独立空间）。
8. 拍号：Meas 尾块 +56 分子 / +58 分母；`tickPerMeas = wholeTick * 分子 * 4 / 分母`。

## 产物清单

| 文件 | 内容 |
|---|---|
| `research-state.md` | 本文件 |
| `smc-format.md` | **主规范**（第三阶段重写） |
| `music-fields.md` | **新增**：音符/音乐属性/消息语义 |
| `font-resources.md` | **新增**：字体、字形、符号编码 |
| `layout.md` | **新增**：System/Staff/Meas/Page/Block |
| `unknown-fields.md` | **新增**：未知字段与未解结构系统记录 |
| `encoding.md` | 字符编码与码表 |
| `lyrics.md` | 歌词结构 |
| `function-index.md` | 函数索引（第三阶段已扩充） |
| `docs/phase3-log.md` | **新增**：第三阶段过程证据记录 |
| `open-questions.md` | 未解决问题（已更新） |
| `steps/01.md` / `steps/02.md` / `steps/03.md` | 阶段任务书与执行记录 |
| `tools/smc_census.py` | **新增**：全语料类型/字段统计 |
| `tools/_probe_p3_*.py` | 第三阶段探针（字段验证） |
| `tools/_probe_font_cmap.py` | 字体 cmap 分析（纯 Python） |
| `tools/_probe_kayakuma.py` | 符号字体结构分析 |
| `tools/_probe_symbols.py` | 符号常量表与 889F 重叠检查 |
| `tools/smc_walk.py` / `smc_text.py` / `smc_batch.py` / … | 阶段一二工具 |

## 修复记录

- 阶段二：`.cod` 解析器按「先全部 start/end、后全部 data」读取有误，实际每区间 `(start,end,data)` 紧邻。
- 阶段三：确认 ObjectCore `+01` **不是**语义字段（写入未初始化栈）；`+06` = headLen + 12。

## 下一步（按收益排序）

1. **`CSMLyricMsg::DrawMsg` 汇编精读**：闭合歌词 head +0x02/+0x04 归属（`unknown-fields.md` C2）。
2. **类型 0x2c / 0x0c / 0x47 head 字段**：低频但可闭合。
3. **`CSMFileInfo` / `CSMCtrlTool` 字段语义**：需 exe 侧消费者（`SetLogicPageInfo`、视图初始化）。
4. **文档级消息 0x04/0x3f/0x40**：需动态观察。
5. **图片引用机制**：exe `LOAD_JPEG_File` 调用者。
6. **符号常量表完整导出**：`codeSmallDigit`/`codeSlid`/`codeAcci` 全表。
7. 旧格式路径 `FUN_00425090` / `CSMDoc::ImportSMC`（当前语料不需要）。

## 停止条件说明

第三阶段按任务书停止条件结束：
- 主要高频消息类型已完成本阶段能够支持的调查；
- 剩余问题集中于低频类型与文件头尾字段，边际收益下降；
- 未转向格式转换器或 IR 设计（任务书明确排除）。
