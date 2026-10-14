# 未解决问题

> 凡例见 `docs/smc-format.md` §0。按优先级排序；已闭合项保留以便追溯。
> 逐结构字节覆盖率与无语义清单见 `docs/field-coverage.md`。

## 已解决（第四阶段）

- **[已解决] 歌词 head +0x02 / +0x04 归属** — 汇编级证据：`+0x02` 为 `u8` 样式位（`& 1/2/4`）、
  `+0x04` 为 `u16` 字号（0 → 13）。见 `docs/lyrics.md` §3、`project/phase4-log.md` §1。
- **[已解决] 歌词 head +0x06 / +0x0D / +0x0E / +0x0F** — 均为**未初始化栈残留**：
  读写两侧的访问/写入集合完全一致（读取侧未访问、写入侧未写入同一组字节）；30353 条记录验证。
- **[已解决] 文件尾 4 字节** — `CSMDoc::Save` 0x100773C0 写入 bodyLen 的冗余副本（与起始处同一变量）。
- **[已解决] `FretInfo`（16 字节）字段顺序** — 基准品位 / 6 弦品位 / 4 组 (起始,结束) 对。
- **[已解决] `RtmData` 顶层结构** — `totalSize`（含自身 4 字节）/ `stride`(16) / 字段A / 字段B /
  `eventCount` / `eventSize`(16) / 事件块 / `count2` / `size2`(6) / 第二段。
- **[已解决] type 0x45 headLen 100 的性质** — 持久化运行期结构（含 MFC42 区段 `Ptr32` 与栈值），
  无语义，须原样保留。
- **[已解决] 音乐符号常量表** — 12 个常量表的地址、字节序列与项数已导出（`docs/font-resources.md` §4.2）。
- **[已解决] 动态调试可行性** — `debugging-plan.md`：x64dbg x32 `headless.exe` 为可行主方案。

## 已解决（第三阶段）

- **[已解决] MsgHdr（0x2C）全部字段** — 读/写双向确证。
- **[已解决] ObjectCore 磁盘布局** — `+0x06 = headLen + 12`；`+0x01` 为保留字节。
- **[已解决] Child 描述符语义** — `u32 key, u8 role, u8 pad[3]`。
- **[已解决] 全部消息类型 → 绘制器分派表** — `CScoreView::SMDrawMsg` 0x1004AA00。
- **[已解决] 音符 head（12 字节）字段表**。
- **[已解决] 音乐属性字段** — 符头类型、附点数、变音状态、标志位。
- **[已解决] 拍号** — Meas 尾块 +0x56 / +0x58。
- **[已解决] 连音/圆滑线引用机制** — 双端点键 + `role` 字节。
- **[已解决] 字体表文件格式** — `u8 index, u8 nameLen, u8 name[]`。
- **[已解决] 音乐符号机制** — 引擎常量 + `KAYAKUMA.TTF`，与 889F 零重叠。

## 已解决（第一、二阶段）

- **[已解决] 韩文文本编码** — code id 1 = `889F.cod`。
- **[已解决] 歌词消息身份** — type 0x19 = `CSMLyricMsg`。
- **[已解决] 歌词↔音符关联** — 对象包含（音符的嵌入子对象）。
- **[已解决] 文本框（0x06）结构** — TLV 标签表。
- **[已解决] 帧结构** — 全语料精确消耗。

## 待办（按收益排序）

### P1 — 低成本、入口明确

1. **`MsgHdr+0x03 / +0x04 / +0x1E` 语义**
   - 现状：全语料出现但无消费者定位 [?]。
   - 方法：对 `MsgHdr` 各字段做 xref；必要时用 `debugging-plan.md` 的断点观察。
   - 完成条件：定位至少一个读写点。

2. **`MeasTail` 未知 54 字节**
   - 入口：`CSMMeas::Write` 0x100793E0（与 `Read` 逐字段对照）。
   - 方法：读回写代码，按偏移建立映射表。
   - 完成条件：每个字节归入 S/I/N 之一。

3. **`StaffTail` 未知 42 字节**
   - 入口：`CSMStaff::Write` 0x10078B00 / 0x10078D50。

### P2 — 中等成本、结构已知但内部未定

4. **`RtmData` 事件体（16 字节/条）与第二段（6 字节/条）**
   - 入口：`CRtmData::ConvertToPlayData`（导出）、`GetRealMidiKey` 0x10047410、`ReadRtmData` 0x10046210。
   - 方法：结构推演 + 对语料事件做字节统计；与 MIDI 语义对照。

5. **`CSMCtrlTool` 剩余 ~0x1E0 字节**
   - 入口：`CSMCtrlTool::Write` 0x1007ED90。
   - 目标：把 558 个 U 字节归类。

6. **`CSMFileInfo` 全 32 字节**
   - 入口：`SetLogicPageInfo` 0x10094ED0、`UpdateLogicDoc` 0x100950A0。
   - 注意：区分**文档持久属性**与程序运行状态。

7. **type 0x2C head（60 字节）**
   - 状态：`Open`。小节数已在 `MsgHdr+0x1C`；head 其余未解析。

### P3 — 需 exe 侧或动态

8. **SYMP 头 / SMC 块的保留区**（合计 2124 字节 X）
   - 入口：exe 中 `view+0x380`、`view+0x68` 的读取者。
   - 先判定是否为固定零区；若恒为 0 可直接归入 N。

9. **文档级消息 0x04 / 0x3F / 0x40 语义**
   - 需动态观察或 exe 侧消费者。

10. **歌词行分组规则**
    - 入口：`CSMDoc::GetRealRectOfLyrics` 0x10003D40 的调用者与绘制循环。

11. **图片引用机制**
    - 入口：exe 中 `LOAD_JPEG_File` 调用者与路径来源。

12. **符号表补充导出**
    - `codeAcci` / `codeSmallDigit` / `codeSlid` 的完整项数与逐项语义
      （`docs/font-resources.md` §4.2 已给主要项）。

### P4 — 低优先级

13. **附加字符串（file 0x590）语义**。
14. **type 0x0C（Coda）head 字段**。
15. **`FretInfo` 的 4 组 (起始,结束) 对的具体含义**。
16. **`ObjectCore.f8` 的消费者**。
17. **旧格式路径** `FUN_00425090` / `CSMDoc::ImportSMC` 0x10077690（当前语料不触发）。
18. **条件分支覆盖**：type 0x26/0x27/0x28/0x29/0x2A/0x2B/0x34–0x3E/0x42/0x4A（语料 0–14 例）；
    见 `docs/field-coverage.md` §5。

## 动态调试（需用户确认）

- 方案与前提见 `debugging-plan.md`；推荐 x64dbg x32 `headless.exe`。
- 最小闭环的验证目标：`ObjectCore+0x06` 写入值、歌词残留字节传递、`MsgHdr+0x03/+0x04/+0x1E` 读写点。
- **未执行**；需用户明确许可并在隔离环境进行。
