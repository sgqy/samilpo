# 未解决问题

按优先级排序。每项包括：问题 / 当前线索 / 建议的验证方法。

1. **韩文文本编码**（歌词、曲名、文本框）
   - 线索：双字节，SJIS 引导字节 0x88–0x9F/0xE0–0xFC；码表文件 889F/B0A1/F040a/b/c/KS/KorCode.cod；`CKCConv::Open/Convert/ToUnicode`；exe 中有 "KorCode.cod"(0x43da18)、"\\KS.cod" 等字符串（0x43fc74..）。
   - 验证：反编译 `CKCConv::ToUnicode`、`FUN_100306b0`（码表加载）以及 exe 中调用 `CKCConv::Open` 的位置，确定 id↔文件对应关系；解析 .cod 文件结构；用已知曲名（例如可以与文件名或索引 `IndexFiles/SamIlPo.idx` 对照）做交叉验证。
2. **歌词 Msg（类型 0x19）的 18 字节 head 布局**
   - 样本：`01 00 00 00 0d 00 00 00 00 00 00 00 02 90 fb 77 8c c4`。猜测是 u16 段号/节号 + … + 长度 + 文本，但尚不清楚。
   - 验证：在 engine 中查找 `type==0x19` 的绘制/编辑代码（例如搜索立即数 0x19 与 `GetHead` 的用法）；对多个样本做统计。
3. **音符 Msg（类型 0x01）头部及 12 字节 head 的语义**（音高、时值、符尾方向、声部）
   - 验证：分析 `CSMMsg::GetMidiKey` 以及 `CSMMeas::UpdatePlayTime/CalcWholeCount`。
4. **MsgHdr 0x2c 各字节的含义**（+1..+5 的位域、+6..+1c 的 s16）
   - 验证：对照 `CSMMsg::Write` 0x1007a240（写入时的字段来源更清楚），并结合绘制代码。
5. **其余 Msg 类型的含义**（0x03,0x04,0x05,0x08,0x09,0x0a,0x12,0x14,0x18,0x1b,0x3f,0x40 …）
   - 验证：在 engine 中找到按 type 分派的 switch（绘制函数），并用 REA 的 jump-table evidence 恢复每个 case 的目标。
6. **ObjectCore 中未读取的字段**（+1 字节、+6 u16），以及 Child.pad[3]
   - 验证：分析 `CSMObject::Write` 0x1007a740。
7. **SYMP 头 0x58C 的其余字段**、SMC 块 0x318 的字段、附加字符串（"448" 之类）的含义
   - 验证：在 exe 中追踪 view+0x380..0x90c 的读取者（曲目信息对话框、打印页眉等）；对全语料统计非零字段。
8. **旧格式路径 FUN_00425090** 和 `CSMDoc::ImportSMC`
   - 当前语料全部使用 SYMP 0x2004/0x2005，因此优先级较低；如果出现更早的样本再分析。
9. **文件尾 4 字节**（等于 bodyLen）：保存代码是否写入它、作用是什么
   - 验证：分析 exe 的保存路径 / `CSMDoc::Save` 0x100773c0。
10. **图片如何引用**：语料中没有嵌入 JPEG，也没有文件名字符串。图片可能来自外部的约定路径，或保存在未出现在本语料的类型中。
    - 验证：在 exe 中查找 `LOAD_JPEG_File` 的调用者和传给它的路径来源。
11. **Page/Block 字段的精确语义**（nBlockA 与 nBlockB 的区别、StaffRef 的两个 u16、nPts 点数组）
    - 验证：分析 `CSMBlock::UpdateMeasXY`、`MakeStaffNameRect`，以及 `CSMBlock::Write` 0x1007b020。
12. **CSMFileInfo 0x20 字节的语义**
    - 验证：分析 `CSMFileInfo::SetLogicPageInfo` 0x10094ed0 和 `UpdateLogicDoc` 0x100950a0。
