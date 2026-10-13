# 函数索引

模块 SHA-256：
- MusicBook.exe `ca7f228e7f77c19e2e3652688c2256728ec96ef5f08230534450163b544d82da`（PE32 x86，MFC42.DLL 动态链接，基址 0x400000）
- engine.dll `424b61c00500db8a40ef943675983fd29d7bf70093cf7737f2659b14718d25a8`（PE32 x86 DLL，基址 0x10000000，1649 个带 C++ 修饰名的导出）

Ghidra 12.1.4，通过 REA 分析。名称来自 DLL 导出的修饰名（可靠）；`FUN_` 为未命名函数。导入/导出全表见 `raw/`。

## MusicBook.exe

| 地址 | 名称 | 作用 | 证据 |
|---|---|---|---|
| 0x424670 | FUN_00424670 (`OpenScoreFile(path)` 暂定名) | 根据扩展名分类（.mid/.rmi=1, .tpl=2, .enc=4, .wdm=5, 其他(含 .smc)=3），类型 2/3 走 SMC 解析：读 SYMP 头、附加字符串、SMC 块、字体表，再调用 CtrlTool/FileInfo::Read → CSMDoc::Load(file,3)，然后处理版本兼容与视图初始化 | ev_c65bc8cc…（伪代码）；`CSMDoc::Load` 导入 0x43d8ac 唯一的 xref 0x424d16 位于此函数中 |
| 0x425090 | FUN_00425090 | 非 SYMP/旧格式头的处理（hdrLen≠0x58C 或 magic 不符） | 未分析 |
| 0x408db0 | FUN_00408db0 | 扩展名比较（类似 stricmp） | 推断 |
| 0x406ab0 | FUN_00406ab0 | 获取 App/主框架对象 | 推断 |

扩展名 .mid/.enc/.wdm 的打开路径不在本函数的 SMC 分支内（局部变量 1/4/5），具体由谁处理未追踪。

## engine.dll — SMC 读取链

| 地址 | 名称 | 作用 / 读取的字节 |
|---|---|---|
| 0x1007f4e0 | CSMCtrlTool::Read(CFile*) | s16 len + len 字节（≤0x478）显示/播放设置、LOGFONT×9、velocity 表 |
| 0x10095260 | CSMFileInfo::Read(CFile*) | 0x20 字节页面信息 |
| 0x1002c100 | CFontDatas::LoadBuffer | 字体表（未反编译） |
| 0x10077cb0 | CSMDoc::Load(CFile*,int) | u32 bodyLen + 主体 → System, DocHdr(10), Msg×3, Page×N |
| 0x10078730 | CSMSystem::Read | ObjectCore + 8 字节 + Staff×(n1+n2) |
| 0x10079030 | CSMStaff::Read | ObjectCore + 0x70 尾部 + Meas×n |
| 0x100798e0 | CSMMeas::Read | ObjectCore'（嵌入 Msg）+ 0x60 尾部，并计算播放时间 |
| 0x1007aa20 | CSMObject::Read | 12 字节通用头 + head 负载 + 子引用/嵌入 Msg |
| 0x1007a490 | CSMMsg::Read | 0x2c 消息头 + ObjectCore |
| 0x1007bbf0 | CSMPage::Read | 0x18 头 + Block×(a+b) + Msg×m |
| 0x1007b550 | CSMBlock::Read | 0x1c 头 + 谱表引用/小节坐标/点 |
| 0x1000bdb0 | CChordSymbol::ReadFromMem | 和弦附加数据 |
| 0x10008b40 | CChordSurfix::ReadFromMem | CStr + u8 n + n 字节 |
| 0x1002cfd0 | CFretBoard::ReadFromMem | Msg + CFretInfo，类型强制设为 0x46 |
| 0x1002dc70 | CFretInfo::ReadFromMem | 16 字节 |
| 0x10045c40 | CRhythm::ReadFromMem | Msg + CStr×3 + CRtmData |
| 0x10047720 | CRtmData::ReadFromMem | 节奏事件表 |
| 0x10095c30 | ReadCStringFromMem | u16 len + 字节 |
| 0x1009a720 | FUN_1009a720 | GlobalMemoryStatus 内存检查（不是解压） |

## engine.dll — 相关但尚未分析

| 地址 | 名称 | 关注原因 |
|---|---|---|
| 0x10077690 | CSMDoc::ImportSMC(CFile*,BYTE*,BYTE) | 另一条 SMC 导入路径（可能是旧版/合并） |
| 0x100773c0 | CSMDoc::Save / 各类 Write (0x100783a0 等) | 写入路径，可用于反向确认字段含义 |
| 0x10071140 / 0x100bc060 / 0x100c1b60 … | CSMBlock/CSMPage/CSMSystem…::Load(CFile*) | 另一套直接基于 CFile 的 Load（用途未知，可能用于剪贴板/模板） |
| 0x100157d0 | CEncDoc::Read 及 CEnc* | .enc 格式（"Inputing ... to smc" 字符串所在的转换器） |
| 0x10030b10 | CKCConv::Open | 加载韩文码表 (id 1..6) |
| (导出) | CKCConv::Convert / ToUnicode / FromUnicode | 编码转换，是解码歌词的关键 |
| 0x10049810 | CScoreView::SMOpen | 视图打开 |
| 0x10035fc0 / 0x10035fe0 | Get/SetMidiFileRead | MIDI 相关 |
