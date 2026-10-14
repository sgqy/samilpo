# 未解决问题

按优先级排序。标 `[已解决]` 者为前阶段已闭合项（保留记录）。

## 已解决（第三阶段）

- **[已解决] MsgHdr（0x2C）全部字段** — 由 `CSMMsg::Read` 0x1007a490 与 `CSMMsg::Write` 0x1007a240 双向确证；见 `smc-format.md` §6.1。
- **[已解决] ObjectCore 磁盘布局** — `+06 = headLen + 12`；`+01` 为写入未初始化栈的保留字节（读取端忽略）；见 §5.1。
- **[已解决] Child 描述符语义** — `u32 key, u8 role, u8 pad[3]`；`role` 编码引用角色；见 §5.2。
- **[已解决] 全部消息类型 → 绘制器分派表** — `CScoreView::SMDrawMsg` 0x1004aa00；见 §6.3。
- **[已解决] 音符 head（12 字节）字段表** — key/velocity/0x40/声部/时值/起始时间；见 §6.7 与 `music-fields.md` §1.1。
- **[已解决] 音乐属性字段** — 符头类型、附点数、变音状态、标志位；见 §6.5/§6.6。
- **[已解决] 拍号** — Meas 尾块 +56 分子 / +58 分母，`CalcWholeCount` 换算；见 `layout.md` §4.3。
- **[已解决] 连音/圆滑线引用机制** — 双端点键 + `role` 字节；见 §6.4。
- **[已解决] 字体表文件格式** — `u8 index, u8 nameLen, u8 name[]`；见 §3.4。
- **[已解决] 音乐符号机制** — 引擎单字节常量 + `KAYAKUMA.TTF` 符号字体（U+F020–U+F0FF），与 889F 零重叠；见 `font-resources.md`。

## 已解决（第二阶段）

- **[已解决] 韩文文本编码** — code id 1 = 889F.cod。
- **[已解决] 歌词消息身份** — type 0x19 = `CSMLyricMsg`。
- **[已解决] 歌词↔音符关联** — 包含关系（音符嵌入子对象）。
- **[已解决] 文本框（0x06）结构** — TLV 标签表。

## 进行中 / 待办

1. **歌词 head +0x02/+0x04 字节归属**（`unknown-fields.md` C2）
   - 验证：精读 `CSMLyricMsg::DrawMsg` 0x1009ad00 汇编，跟踪 `memcpy(this+0x20 → local, 0x10)` 后各局部量的 EBP 偏移。
   - 收尾成本低，建议下一阶段首项。

2. **歌词 head +0x06 / +0x0D / +0x0E / +0x0F**（C1）
   - 线索：`DrawMsg` 未使用这些字节。
   - 验证：`CTempLyricMsg` 0x100c9b70 / `BeginDrag` 0x100c9cf0，或歌词写入路径。

3. **类型 0x2c（长休止）headLen 60 的字段表**（B2）
   - 验证：`CScoreView::DrawLongrest` 0x100595b0。语料 98 条。

4. **类型 0x47（节奏型）与 `CRtmData` 字段**（B4）
   - 验证：`CRtmData::ReadFromMem` 0x10047720、`CRtmData::GetRealMidiKey` 0x10047410。语料 12716 条。

5. **类型 0x0c（Coda）head 字段**（B3）
   - 验证：`DrawCoda` 0x10056ec0 / `DrawCodaEx` 0x10065660。语料 165 条。

6. **类型 0x46（指板）`CFretInfo` 16 字节字段**（B5）
   - 验证：`CFretInfo::ReadFromMem` 0x1002dc70。语料 177909 条。

7. **文档级消息 0x04 / 0x3f / 0x40 语义**（B6）
   - 验证：动态观察或 exe 侧消费者。每文件各一次。

8. **`CSMFileInfo`（0x20）与 `CSMCtrlTool` 剩余字段语义**（B8）
   - 入口：`CSMFileInfo::SetLogicPageInfo` 0x10094ed0、`UpdateLogicDoc` 0x100950a0。

9. **Meas 尾块未解字段**（`layout.md` §8）
   - +44..+52、+4E/+50、+5A/+5C（后者已确认为调号符号/个数）。

10. **附加字符串（file 0x590）语义**（B7）
    - 验证：exe 中 `view+0x90c` 的读取者。

11. **文件尾 4 字节的写入路径**（C4）
    - 验证：`CSMDoc::Save` 0x100773c0。

12. **图片引用机制**（C3）
    - 语料无嵌入 JPEG、无文件名。
    - 验证：exe 中 `LOAD_JPEG_File` 调用者与路径来源。

13. **符号常量表完整导出**
    - `codeAcci`（0x10100430）、`CodeDyn`（0x101006d4）、`codeSmallDigit`、`codeSlid` 的完整项数与取值。
    - 验证：`find_xrefs_to_name` + `read_bytes` 逐表导出。

14. **`CSMDoc::GulsamToSMC_*` 系列**（外部格式 → SMC）
    - 已知 0x1002f610（Note）、0x1002fbe0（BEAM）、0x10030010（Lyrics）；可用于反向确认字段（如 `MsgHdr+06` 符头类型映射表 8→5, 9→4, 10→2, 11→6, 12→3, 13→3, 14→2, 15→1）。

15. **旧格式路径** `FUN_00425090` / `CSMDoc::ImportSMC` 0x10077690
    - 当前语料全部 0x2004/0x2005，优先级低。
