# 研究状态

最后更新：第一阶段完成（2026-10-14）。

## 已完成（第一阶段）

- [x] 架构与分工：两个模块都是 PE32 x86。MusicBook.exe 是 MFC42 动态链接的 UI 程序，负责打开文件并解析前置头部；engine.dll 导出完整的 C++ 类（CSMDoc/CSMSystem/CSMStaff/CSMMeas/CSMMsg/CSMPage/CSMBlock/CKCConv …），负责主体解析、排版和编码转换。SHDrawJpeg.dll 负责从文件绘制 JPEG；WINMM 负责 MIDI 输出。
- [x] SMC 解析入口：`MusicBook.exe!FUN_00424670` → `engine!CSMCtrlTool::Read` → `CSMFileInfo::Read` → `CSMDoc::Load` → System/Staff/Meas/Msg/Page/Block 读取器。
- [x] 帧结构完全恢复：`tools/smc_walk.py` 对全部 **8451/8451** 个样本都能恰好消耗主体字节；文件尾 4 字节在所有样本中都等于 bodyLen。
- [x] 预处理判断：未发现压缩或加密（直接使用 CFile::Read 和 memcpy）；只有文本采用自定义的韩文双字节编码（CKCConv + .cod 码表）。
- [x] 初步标出的分支：歌词（0x19，推断）、音符（0x01，推断）、和弦（0x45/0x46，确认）、文本框（0x06，推断）、节奏型（0x47）、分页（Page/Block，确认）、MIDI velocity 表（CtrlTool，推断）。

## 关键结论（详见 smc-format.md）

1. 文件 = SYMP 头(0x58C) + 附加串 + SMC 块(0x318) + 字体表 + CtrlTool(0x478) + FileInfo(0x20) + u32 bodyLen + 主体 + u32 bodyLen。
2. 主体是嵌套的对象树：每个对象都有 12 字节的 ObjectCore（子项数、head 负载长度、子引用/嵌入 Msg）；乐谱元素统一用 Msg（0x2c 头 + ObjectCore）表示，按 type 区分。
3. 对象之间通过 32 位 key 相互引用（`CSMSystem::GetKey` 负责重映射）。

## 产物

- `smc-format.md` — 格式说明（证据等级已标注）
- `function-index.md` — 函数地址与作用
- `open-questions.md` — 未解决问题与验证方法
- `tools/pe_dump.py` — PE 导入/导出转储
- `tools/smc_walk.py` — 结构遍历器（`-v` 输出详细树）
- `tools/smc_batch.py` — 全语料验证
- `raw/` — 导入/导出表

## 下一步（按收益排序）

1. **韩文编码**（收益最高，保存歌词和标题的前提）：CKCConv::ToUnicode/Convert、码表加载 FUN_100306b0、exe 中 Open 的调用（id↔.cod 映射），以及 .cod 文件格式。
2. **音符 Msg 0x01 + 小节尾部**：GetMidiKey、UpdatePlayTime、CalcWholeCount → 音高/时值/拍号，用来导出 MIDI/MusicXML。
3. **歌词 Msg 0x19 head**：与第 1 项合并分析，并找到它和音符的关联方式（key 引用或位置）。
4. **按 type 分派的绘制 switch**：一次性列出全部 Msg 类型的语义。
5. **Write 系列函数**（CSMMsg::Write / CSMObject::Write / CSMDoc::Save）：反向确认未读取字段和尾部字段。
6. 头块/SMC 块/FileInfo/CtrlTool 的剩余字段（优先级低，对乐谱内容影响较小）。
7. 旧格式 FUN_00425090、ImportSMC、图片引用（当前语料不需要）。

## 会话说明

- REA/Ghidra 会话是临时的；engine.dll 和 MusicBook.exe 各分析过一次。下次工作可以直接按 function-index.md 中的地址查询，不需要重新探索。
