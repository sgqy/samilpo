# 研究状态

最后更新：第四阶段定稿（2026-10-14）。

> 凡例见 `smc-format.md` §0。本文件是本项目的**恢复入口**：任何会话中断后，从这里判断进度与下一步。

## 全局

- 目标：恢复 Samilpo 2.0 的 SMC 乐谱文件格式（数字遗产保存），产出可由第三方独立使用的规范。
- 工作区：`C:\research\samilpo`（文档 + `tools/` 脚本 + `raw/` 原始证据 + `docs/` 过程记录）。
- 目标程序：`C:\Program Files (x86)\Samilpo 2.0\MusicBook.exe`（PE32 x86）与 `engine.dll`。
- 样本：`<安装目录>\8000Songs\`（5 个子集，共 **8451** 个 `.smc`）。
- 分析环境：REA MCP + Ghidra 12.1.4（`engine.dll` 基址 `0x10000000`）；辅以本地 Python 3.15。

## 阶段进度

| 阶段 | 内容 | 状态 |
|---|---|---|
| 一 | 帧结构 + 读取调用链 | 完成 |
| 二 | 韩文编码（`.cod`）+ 歌词消息 0x19 + 歌词↔音符关联 | 完成 |
| 三 | 消息头全字段 + 类型分派全表 + 音符 head + 结构对象 + 字体/符号机制 | 完成 |
| 四 | 歌词 head 汇编闭合 + 文件尾 + 符号表导出 + 特殊结构（0x45/0x46/0x47/0x2C）+ 覆盖清单 + 动态方案 | 完成（定稿） |

## 当前已确认的关键结论（速查）

1. 文件 = `u32 hdrLen(0x58C)` + SYMP 头(0x58C) + 附加串 + SMC 块(0x318) + 字体表 + CtrlTool + FileInfo(0x20) + `u32 bodyLen` + 主体 + `u32 bodyLen`。
2. 主体 = System + DocHdr(10) + Msg×3 + Page×N；全部乐谱元素统一为 **Msg**。
3. `MsgHdr` = 0x2C：type / 括号+声部 / 缩放 / 符干+附点 / 符头类型 / 类型索引 / 标志位 / 起始时间 / X / 音高 Y / 端点键 / 本对象 key（详见 `smc-format.md` §6.1）。
4. `ObjectCore` 磁盘头 = `u8 childCount, u8 reserved, u16 f2, u16 headLen, u16 (headLen+12), u32 f8`。
5. **音符 head[12]** = `key, velocity, 0x40, voice, u32 duration, u32 start`。
6. **歌词 head[16]** = `u16 font, u8 style, u8 residue, u16 size, u16 residue, u32 color, u8 len, u8×3 residue`（第四阶段闭合）。
7. 文本编码 = 889F；音乐符号 = 引擎单字节常量 + `KayakumA` 符号字体（两套空间零重叠）。
8. 拍号：Meas 尾块 +0x56 分子 / +0x58 分母；`tickPerMeas = wholeTick * 分子 * 4 / 分母`。
9. 文件尾部 4 字节 = bodyLen 的冗余副本，由 `CSMDoc::Save` 写入。
10. 覆盖度：核心层结构覆盖 92.9% / 语义覆盖 78.8%（`field-coverage.md`）。

## 验证基线

- `tools/smc_walk.py`、`tools/smc_census.py`：**8451/8451** 样本精确消耗主体、尾部恰好 4 字节 [E]。
- `tools/smc_text.py`：8451/8451 曲名、9129 条歌词、1991 个文本框全部正确解码 [E]。
- `tools/_probe_p4_lyrichead.py`：歌词 head 残留字节预测 30353 条验证通过 [E]。
- `tools/_probe_p4_rhythm.py`：`RtmData.totalSize = 已消耗 + 4`，101/101 [E]。
- `tools/field_coverage.py`：覆盖度数字的唯一数据源。

## 未完成的调查（恢复点）

按当前收益排序，含**下一步具体操作**：

| # | 目标 | 入口 | 预期方法 |
|---|---|---|---|
| 1 | `MsgHdr+0x03/+0x04/+0x1E` 语义 | xref 定位读写点 | 静态 xref；必要时动态断点 |
| 2 | `MeasTail` 54 字节未知字段 | `CSMMeas::Write` 0x100793E0 | 逐字段对照导出 |
| 3 | `StaffTail` 42 字节未知字段 | `CSMStaff::Write` 0x10078B00 / 0x10078D50 | 同上 |
| 4 | `RtmData` 事件体 | `CRtmData::ConvertToPlayData`、`GetRealMidiKey` 0x10047410 | 结构推演 + 样本统计 |
| 5 | `CSMCtrlTool` 剩余 ~0x1E0 字节 | `CSMCtrlTool::Write` 0x1007ED90 | 写回字段枚举 |
| 6 | `CSMFileInfo` 全 32 字节 | `SetLogicPageInfo` 0x10094ED0、`UpdateLogicDoc` 0x100950A0 | exe 侧消费者 |
| 7 | SYMP / SMC 大块保留区 | exe 中 `view+0x380` / `view+0x68` 读取者 | 逐字段 xref |
| 8 | type 0x2C head 60 字节 | `unknown-fields.md` B2 | 写入路径 |
| 9 | 图片引用 | exe `LOAD_JPEG_File` 调用者 | 静态 xref |
| 10 | 动态验证 | `debugging-plan.md` §4 最小闭环 | 需用户确认后执行 |

## 恢复步骤（会话中断后）

1. 读本文件 → `smc-format.md` §0（凡例）→ `field-coverage.md`（覆盖面）。
2. 查 `open-questions.md` 取当前优先项；查 `function-index.md` 取地址。
3. 用 REA `open_binary` 绑定 `engine.dll`（SHA-256 见 `function-index.md`），地址即上表所列。
4. 新增结论一律：先改 `tools/field_coverage.py`，再同步 `smc-format.md` 与专题文档，最后更新本文件。

## 产物清单

| 文件 | 内容 |
|---|---|
| `smc-format.md` | **主规范**（含凡例 §0、字段级表） |
| `music-fields.md` | 音符/音乐属性/消息语义 |
| `layout.md` | System/Staff/Meas/Page/Block |
| `lyrics.md` | 歌词结构与关联机制 |
| `encoding.md` | 字符编码与码表 |
| `font-resources.md` | 字体、字形、符号常量 |
| `unknown-fields.md` | 未解项清单（按 Open/Blocked 分类） |
| `field-coverage.md` | 逐结构字节覆盖率（含无语义清单） |
| `debugging-plan.md` | 动态调试可行性评估（D1） |
| `function-index.md` | 函数索引（按模块/子系统分组） |
| `research-state.md` | 本文件 |
| `open-questions.md` | 待办与已闭合项 |
| `docs/phase3-log.md` / `docs/phase4-log.md` | 过程证据记录 |
| `steps/01.md`–`steps/04.md` | 各阶段任务书与执行记录 |
| `tools/smc_walk.py` / `smc_census.py` / `smc_text.py` / `field_coverage.py` / `_probe_*` | 验证脚本 |
| `raw/` | 导入导出表、head 转储、探针输出 |

## 修复记录

- 阶段二：`.cod` 解析器按「先全部 start/end、后全部 data」读取有误；实际每区间 `(start,end,data)` 紧邻。
- 阶段三：ObjectCore `+0x01` 不是语义字段（写入未初始化栈）；`+0x06 = headLen + 12`。
- 阶段四：歌词 head 的 6 个「未知字节」确认为未初始化栈残留；`RtmData.totalSize` 含自身 4 字节。

## 停止条件说明

第四阶段按任务书停止条件结束：
1. 主要低成本静态未知字段已收尾（歌词 head、文件尾、符号表）。
2. 0x45/0x46/0x47 已取得可验证进展（结构级，事件体除外）。
3. 文件级剩余未知字段已系统记录。
4. 已建立字段覆盖清单并统一口径（`field-coverage.md`）。
5. 已明确动态调试方案与前提（`debugging-plan.md`），未投入实际执行（需用户确认）。
