# 研究状态

最后更新：第二阶段完成（2026-10-14）。

## 全局

- 目标：恢复 Samilpo SMC 乐谱文件格式（数字遗产保存）。
- 工作区：`C:\research\samilpo`（文档 + `tools/` 脚本 + `raw/` 原始证据输出）。
- 阶段一：帧结构 + 调用链（见下）。
- 阶段二：**韩文编码 + 歌词消息 0x19 + 歌词↔音符关联**（本次完成）。

## 阶段二已完成（任务 A / B / C）

- [x] **任务 A 韩文编码**：确认 SMC 文本 = code id 1 = `889F.cod`；恢复 `.cod` 双表结构与查表算法；恢复 id↔文件映射；绘制路径 `MyDrawTextOutW` → `ToUnicode(1,…)` 为直接证据。
  - 成果：`encoding.md`、`tools/smc_text.py`
  - 验证：8451/8451 曲名、抽样 9129 条歌词、1991 条文本框全部正确解码；B0a1/Ks/F040a 对照组均失败。
- [x] **任务 B 歌词 0x19**：确认 = `CSMLyricMsg`；head = `0x10 + 文本字节数`（9129/9129 验证）；字段表见文档。
  - 成果：`lyrics.md` §1–4
- [x] **任务 C 关联机制**：歌词是 type 0x01 音符消息的**嵌入子对象**（2961/2961 父类型 = 0x01）；key 差典型为 +1（3000）或 +2（259）。
  - 成果：`lyrics.md` §5

## 阶段一成果（保留）

- SMC 解析入口 `MusicBook.exe!FUN_00424670` → `engine!CSMCtrlTool::Read` → `CSMFileInfo::Read` → `CSMDoc::Load` → System/Staff/Meas/Msg/Page/Block。
- 帧结构：`tools/smc_walk.py` 对全部 **8451/8451** 样本恰好消耗主体字节；文件尾 4 字节 = bodyLen。
- 无压缩/加密（直接 CFile::Read + memcpy 到内存缓冲后按游标解析）。

## 关键结论速查

1. 文件 = SYMP头(0x58C) + 附加串 + SMC块(0x318) + 字体表 + CtrlTool(0x478) + FileInfo(0x20) + u32 bodyLen + 主体 + u32 bodyLen。
2. 主体是嵌套对象树；乐谱元素统一为 Msg（0x2C 头 + ObjectCore(12B) + head + 子项）；对象间用 32 位 key 引用。
3. 文本编码 = 889F（`<0x80` 单字节，其余双字节查表；未映射原样保留）。
4. 歌词 = 挂在音符下的 0x19 子对象，head 固定 0x10 前置 + 文本；一条记录 = 一个音节单元。
5. 文本框 = 0x06，head 为 TLV（0x01 对齐/0x02 字体/0x03 样式/0x04 字号/0x06 文本/0x0A 换行等）。

## 产物清单

| 文件 | 内容 |
|---|---|
| `research-state.md` | 本文件 |
| `function-index.md` | 模块/地址/作用/证据（已分四节：exe、读取链、编码、歌词/文本）|
| `smc-format.md` | 整体格式（§8 编码已更新为已恢复）|
| `encoding.md` | **阶段二新增**：编码体系、码表结构、证据、未决项 |
| `lyrics.md` | **阶段二新增**：0x19 字段、关联机制、0x06 对照 |
| `open-questions.md` | 未解决问题（已含阶段二闭合项）|
| `steps/01.md` / `steps/02.md` | 阶段任务书与本阶段执行记录 |
| `tools/smc_walk.py` | 结构遍历器（`-v` 输出对象树）|
| `tools/smc_text.py` | **阶段二新增**：.cod 解析 + SMC 文本解码（tables/dec/titles/lyrics/all）|
| `tools/smc_textcheck.py` | 编码验证（全语料曲名 + 多表对照）|
| `tools/smc_headscan.py` | 各消息类型 head 文本扫描 |
| `tools/smc_batch.py` | 全语料帧结构验证 |
| `tools/pe_dump.py` | PE 导入/导出转储 |
| `tools/_probe_*.py` | 阶段二一次性探针（保留作为验证方法记录）|
| `raw/` | 导入导出表、head 转储、歌词/编码探针的 UTF-8 输出 |

## 修复记录

- 阶段二发现并修正：`.cod` 解析器最初按「先全部 start/end、后全部 data」读取，实际每区间为 `(start,end,data)` 紧邻（依据 `FUN_100306b0`）。修正后所有 .cod 文件字节恰好用尽。

## 下一步（按收益排序）

1. **歌词 head 4 个未定字节**（+0x06/+0x0D/+0x0E/+0x0F）与 `+0x02/+0x04` 归属：看写入路径与编辑期类（`CTempLyricMsg` 0x100C9B70 等）。
2. **音符 0x01 语义**（音高/时值/声部）：`CSMMsg::GetMidiKey`、`CSMMeas::UpdatePlayTime`/`CalcWholeCount` → 支撑 MIDI/MusicXML 导出。
3. **全部 Msg 类型的绘制 switch**：一次性列出剩余类型语义。
4. **Write/Save 系列**：反向确认未读取字段与文件尾。
5. 未映射码位与 Wk*.ttf cmap 的对应。
6. 头块/SMC 块/FileInfo/CtrlTool 剩余字段（低优先级）。
7. 旧格式 FUN_00425090 / ImportSMC / 图片引用（当前语料不需要）。
