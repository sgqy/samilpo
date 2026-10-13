# 未解决问题

按优先级排序。标 `[已解决]` 者为第二阶段已闭合项（保留记录以便追溯）。

## 已解决（第二阶段）

- **[已解决] 韩文文本编码** — code id 1 = 889F.cod，`.cod` 结构与查表算法已恢复，见 `encoding.md`。
- **[已解决] 歌词消息身份** — type 0x19 = `CSMLyricMsg`，字段表见 `lyrics.md` §3。
- **[已解决] 歌词↔音符关联** — 包含关系：歌词是 type 0x01 音符消息的嵌入子对象；key 通常为 note_key+1，见 `lyrics.md` §5。
- **[已解决] 文本框（0x06）结构** — TLV 标签表已恢复，见 `lyrics.md` §6。

## 进行中 / 待办

1. **歌词 head 的 4 个未定字节**（+0x06 u16、+0x0D/+0x0E/+0x0F u8）
   - 线索：DrawMsg 只使用 head+0x00/+0x04/+0x08/+0x0C 与 head+0x10 起的文本，其余字节不被绘制路径读取。
   - 验证：分析 `CSMLyricMsg::WriteToMem`/`Save`（若存在）或编辑器路径（`CTempLyricMsg` 0x100C9B70、`BeginDrag` 0x100C9CF0 等）看这些字节是否为编辑期缓存。
2. **head +0x02 与 +0x04 的字节归属**
   - 现状：按统计给出「+0x02 样式 / +0x04 字号」，与 DrawMsg 的 `flag & 1/2/4` 和默认 13 一致，但 Ghidra 栈局部划分不足以 100% 判定。
   - 验证：读取 `CSMLyricMsg::DrawMsg` 0x1009AD00 的原始汇编，跟踪 `memcpy(this+0x20 → local_24, 0x10)` 后各 `local_*` 的 EBP 偏移。
3. **未映射 889F 码位在字体中的来源**
   - 验证：解析 `Font\Wk*.ttf` 的 cmap，检查对应码位是私人字形还是真符号。
4. **歌词行分组规则**（换行/对齐/分句）
   - 线索：「－」（U+FF0D，来自码位 F0 41）在语料中作为分句符。
   - 验证：分析 `CSMDoc::GetRealRectOfLyrics` 0x10003D40 与 `CScoreView::DrawTextMsg` 0x1005EBB0 的调用者（绘制循环），观察行如何聚合。
5. **其余 Msg 类型的语义**（0x03,0x04,0x05,0x08,0x09,0x0a,0x12,0x14,0x18,0x1b,0x3f,0x40 …）
   - 验证：在 engine 中找到按 type 分派的 switch（绘制函数），并用 REA 的 jump-table evidence 恢复每个 case 的目标。
6. **音符 Msg（0x01）头部与 12 字节 head 的语义**（音高、时值、符尾方向、声部）
   - 验证：分析 `CSMMsg::GetMidiKey` 与 `CSMMeas::UpdatePlayTime` / `CalcWholeCount`。
7. **ObjectCore 中未读取的字段**（+1 字节、+6 u16），以及 Child.pad[3]
   - 验证：分析 `CSMObject::Write` 0x1007a740。
8. **SYMP 头 0x58C 的其余字段**、SMC 块 0x318 的字段、附加字符串（“448”之类）的含义
   - 验证：在 exe 中追踪 view+0x380..0x90c 的读取者；对全语料统计非零字段。
9. **旧格式路径 FUN_00425090** 和 `CSMDoc::ImportSMC`
   - 当前语料全部使用 SYMP 0x2004/0x2005，优先级较低。
10. **文件尾 4 字节**（等于 bodyLen）：保存代码是否写入它、作用是什么
    - 验证：分析 exe 的保存路径 / `CSMDoc::Save` 0x100773c0。
11. **图片如何引用**：语料中没有嵌入 JPEG，也没有文件名字符串。
    - 验证：在 exe 中查找 `LOAD_JPEG_File` 的调用者和传给它的路径来源。
12. **Page/Block 字段的精确语义**（nBlockA 与 nBlockB 的区别、StaffRef 的两个 u16、nPts 点数组）
    - 验证：分析 `CSMBlock::UpdateMeasXY`、`MakeStaffNameRect`，以及 `CSMBlock::Write` 0x1007b020。
13. **CSMFileInfo 0x20 字节的语义**
    - 验证：分析 `CSMFileInfo::SetLogicPageInfo` 0x10094ed0 和 `UpdateLogicDoc` 0x100950a0。
14. **`KorCode.cod` / `KcgInfo.kbd` 的用途**（键盘输入映射？）；**`F040.cod`（5122 B，无 CCodeTable 头）的用途**
    - 验证：分析 exe 中 `KorCode.cod` 的读取者（FUN_00411c00 的调用者）与 `F040.cod` 的引用点。
