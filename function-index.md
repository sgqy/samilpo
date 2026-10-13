# 函数索引

模块 SHA-256：
- MusicBook.exe `ca7f228e7f77c19e2e3652688c2256728ec96ef5f08230534450163b544d82da`（PE32 x86，MFC42.DLL 动态链接，基址 0x400000）
- engine.dll `424b61c00500db8a40ef943675983fd29d7bf70093cf7737f2659b14718d25a8`（PE32 x86 DLL，基址 0x10000000，1649 个带 C++ 修饰名的导出）

Ghidra 12.1.4，通过 REA 分析。名称来自 DLL 导出的修饰名（可靠）；`FUN_` 为未命名函数。导入/导出全表见 `raw/`。

## MusicBook.exe

| 地址 | 名称 | 作用 | 证据 |
|---|---|---|---|
| 0x424670 | FUN_00424670 (`OpenScoreFile(path)` 暂定名) | 根据扩展名分类（.mid/.rmi=1, .tpl=2, .enc=4, .wdm=5, 其他(含 .smc)=3），类型 2/3 走 SMC 解析：读 SYMP 头、附加字符串、SMC 块、字体表，再调用 CtrlTool/FileInfo::Read → CSMDoc::Load(file,3)，然后处理版本兼容与视图初始化 | ev_c65bc8cc…（伪代码）；`CSMDoc::Load` 导入 0x43d8ac 唯一的 xref 0x424d16 位于此函数中 |
| 0x418980 | FUN_00418980 (InitInstance) | 启动：加载 8 个 TTF 字体、`CKCConv::Open(3/4/1/2/6, …)` 加载码表、注册 mutex、读 profile | ev_e6ac1a25…（伪代码） |
| 0x411c00 | FUN_00411c00 | 读取 `KorCode.cod`：10 字节/条，拆成 5 个并列 u16 数组（**键盘表**，非 SMC 文本编码） | ev_afc50068…（伪代码） |
| 0x411af0 | FUN_00411af0 | `CKCodeConvert` 构造 | 推断 |
| 0x425090 | FUN_00425090 | 非 SYMP/旧格式头的处理（hdrLen≠0x58C 或 magic 不符） | 未分析 |
| 0x408db0 | FUN_00408db0 | 扩展名比较（类似 stricmp） | 推断 |
| 0x406ab0 | FUN_00406ab0 | 获取 App/主框架对象 | 推断 |

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

## engine.dll — 文本编码（任务 A）

| 地址 | 名称 | 作用 |
|---|---|---|
| 0x10030b10 | CKCConv::Open(id, path) | 加载码表 id 1..6；每个 .cod 含正向+反向两张 `CCodeTable` |
| 0x100306b0 | CCodeTable 加载器 | 解析：u16 n/lo/hi，然后 **每区间 (u16 start, u16 end, u16 data[…])** |
| 0x100308c0 | CCodeTable 查表 | 越界或未映射（值 0）时**原样返回输入码位** |
| 0x100303d0 | CKCConv::ToUnicode(u16,u16) | 单字符；id 0 = Unicode 透传 |
| 0x10030420 | CKCConv::FromUnicode(u16,u16) | 单字符反向 |
| 0x10030470 | CKCConv::Convert(u16,u16,u16) | 单字符 ToUnicode 再 FromUnicode |
| 0x10030d90 | CKCConv::ToUnicode(id, src, len, dst, cap) | 字符串版；`<0x80` 单字节透传 |
| 0x10030ee0 | CKCConv::FromUnicode(id, src, len, dst, cap) | 字符串版反向 |
| 0x10031020 / 0x100311b0 | CKCConv::Convert | 带缓冲 / 就地转换 |
| 0x100317d0 | CKCConv::ConvertFont | 字体名换算 |
| 0x10030c80 | CKCConv::GetCodeName(id) | 0 Unicode / 1 "889F Code" / 2 "B0A1 Code" / 3 "F040(95) Code" / 4 "F040(98) Code" / 5 "F040(MAC) Code" / 6 "B0A1(KS) Code" |
| 0x10096530 | MyDrawTextOutW | **绘制端统一入口**：`ToUnicode(3,..)` 求长度 + `ToUnicode(1,..)` 实际转换 → `TextOutW`。SMC 文本 = 889F 的直接证据 |
| 0x100965d0 | MyGetTextExtentW | 同上，`GetTextExtentPoint32W` |

## engine.dll — 歌词/文本消息（任务 B、C）

| 地址 | 名称 | 作用 |
|---|---|---|
| 0x1009ad00 | CSMLyricMsg::DrawMsg | **type 0x19 绘制器**：文本在 head+0x10、长度在 head[0x0C]、字体索引 head+0x00、字号 head+0x04、颜色 head+0x08 |
| 0x1009ac20 | CSMLyricMsg::ctor | 类身份；vtable 0x100E52B8 |
| 0x1005ebb0 | CScoreView::DrawTextMsg | 按消息计算屏幕位置并调用 CSMLyricMsg::DrawMsg |
| 0x10030010 | CSMDoc::GulsamToSMC_Lyrics | 旧格式→0x19；**直接证据**：写入 type=0x19、headLen = 文本长度 + 0x10 |
| 0x10003d40 | CSMDoc::GetRealRectOfLyrics | 歌词真实矩形（选区/定位） |
| 0x100c2f70 | CSMTextMsg::DrawMsg | **type 0x06 绘制器**：TLV 标签 0x01..0x0A（0x06=文本, 0x0A=换行） |
| 0x100c2e90 | CSMTextMsg::ctor | type 0x06 类 |
| 0x1005b1f0 | CScoreView::DrawMultiText | 构造 CSMTextMsg 并调用 DrawMsg |
| 0x100c3bf0 | CSMTextMsg::RichTextLineOut | 逐行富文本输出（含 MyDrawTextOutW 调用） |
| 0x100c40c0 | CSMTextMsg::AnalizeText | TLV 文本分析 |

## engine.dll — 相关但尚未分析

| 地址 | 名称 | 关注原因 |
|---|---|---|
| 0x10077690 | CSMDoc::ImportSMC(CFile*,BYTE*,BYTE) | 另一条 SMC 导入路径（可能是旧版/合并） |
| 0x100773c0 | CSMDoc::Save / 各类 Write (0x100783a0 等) | 写入路径，可用于反向确认字段含义 |
| 0x10071140 / 0x100bc060 / 0x100c1b60 … | CSMBlock/CSMPage/CSMSystem…::Load(CFile*) | 另一套直接基于 CFile 的 Load（用途未知，可能用于剪贴板/模板） |
| 0x100157d0 | CEncDoc::Read 及 CEnc* | .enc 格式（"Inputing ... to smc" 字符串所在的转换器） |
| 0x10049810 | CScoreView::SMOpen | 视图打开 |
| 0x10035fc0 / 0x10035fe0 | Get/SetMidiFileRead | MIDI 相关 |
