# 函数索引

> 凡例见 `smc-format.md` §0（知识评级 `[E]`/`[I]`/`[?]`/`[C]`；数据类型为 Rust 风格）。
> 模块 SHA-256：
> - `MusicBook.exe` `ca7f228e7f77c19e2e3652688c2256728ec96ef5f08230534450163b544d82da`（PE32 x86，MFC42 动态链接，基址 0x400000）
> - `engine.dll` `424b61c00500db8a40ef943675983fd29d7bf70093cf7737f2659b14718d25a8`（PE32 x86 DLL，基址 0x10000000，1649 个 C++ 修饰名导出）
>
> 分析环境：Ghidra 12.1.4，经 REA 驱动。名称来自 DLL 导出修饰名（可靠）；`FUN_` 为未命名函数。
> 导入/导出全表见 `raw/`。

## MusicBook.exe

| 地址 | 名称 | 作用 | 评级 |
|---|---|---|---|
| 0x00424670 | `FUN_00424670`（`OpenScoreFile` 暂定名） | 按扩展名分类（.mid/.rmi=1、.tpl=2、.enc=4、.wdm=5、其他(含 .smc)=3）；类型 2/3 走 SMC 解析：读 SYMP 头、附加串、SMC 块、字体表，再调用 CtrlTool/FileInfo::Read → `CSMDoc::Load(file, 3)`，然后处理版本兼容与视图初始化 | [E] |
| 0x00418980 | `FUN_00418980`（InitInstance） | 启动：加载 8 个 TTF、`CKCConv::Open(3/4/1/2/6, …)` 加载码表、注册 mutex、读 profile | [E] |
| 0x00411C00 | `FUN_00411C00` | 读 `KorCode.cod`（10 字节/条 → 5 个并列 `u16` 数组，**键盘表**，非文本编码） | [E] |
| 0x00411AF0 | `FUN_00411AF0` | `CKCodeConvert` 构造 | [I] |
| 0x00425090 | `FUN_00425090` | 非 SYMP / 旧格式头处理（`hdrLen != 0x58C` 或 magic 不符） | 未分析 |
| 0x00408DB0 | `FUN_00408DB0` | 扩展名比较（类 stricmp） | [I] |
| 0x00406AB0 | `FUN_00406AB0` | 获取 App/主框架对象 | [I] |
| 0x0043DA05 | （字符串常量） | 路径拼接 `"%s\%s"` | [E] |

## engine.dll — SMC 读取链

| 地址 | 名称 | 作用 | 评级 |
|---|---|---|---|
| 0x1007F4E0 | `CSMCtrlTool::Read` | `i16 len` + len 字节（≤0x478）：显示/播放设置、9 × `LOGFONTA`、velocity 表 | [E] |
| 0x1007ED90 | `CSMCtrlTool::Write` | CtrlTool 写回 | [E] |
| 0x10095260 | `CSMFileInfo::Read` | 0x20 字节页面信息 | [E] |
| 0x100951A0 | `CSMFileInfo::Write` | FileInfo 写回 | [E] |
| 0x1002C100 | `CFontDatas::LoadBuffer` | 字体表（`u8 index, u8 nameLen, u8 name[]`） | [E] |
| 0x10077CB0 | `CSMDoc::Load(CFile*, int)` | `u32 bodyLen` + 主体 → System, DocHdr(10), Msg×3, Page×N | [E] |
| 0x100773C0 | `CSMDoc::Save(CFile*)` | 写回：起始占位 → System → 主体 → 尾部 bodyLen → 回填起始 | [E] |
| 0x10078730 | `CSMSystem::Read` | ObjectCore + nStaff1/nStaff2/wholeTick + Staff[] | [E] |
| 0x100783A0 / 0x10078560 | `CSMSystem::Write` | System 写回（两个重载） | [E] |
| 0x10079030 | `CSMStaff::Read` | ObjectCore + 0x70 尾块 + Meas[] | [E] |
| 0x10078B00 / 0x10078D50 | `CSMStaff::Write` | Staff 写回（两个重载） | [E] |
| 0x100798E0 | `CSMMeas::Read` | MeasCore(i16 headLen) + 0x60 尾块 + 子项整理 | [E] |
| 0x100793E0 | `CSMMeas::Write` | Meas 写回 | [E] |
| 0x1007AA20 | `CSMObject::Read` | 12 字节通用头 + head + 子引用/嵌入 Msg | [E] |
| 0x1007A740 | `CSMObject::Write` | **ObjectCore 磁盘布局确证**（`+0x06 = headLen + 12`） | [E] |
| 0x1007A490 | `CSMMsg::Read` | 0x2C 消息头 + ObjectCore（type 0x41 → 0x08） | [E] |
| 0x1007A240 | `CSMMsg::Write` | **MsgHdr 磁盘布局确证** | [E] |
| 0x1007BBF0 | `CSMPage::Read` | 0x18 头 + Block×(A+B) + Msg×m | [E] |
| 0x1007B9E0 | `CSMPage::Write` | Page 写回 | [E] |
| 0x1007B550 | `CSMBlock::Read` | 0x1C 头 + StaffRef×n + 小节坐标 + 点 | [E] |
| 0x1007B020 | `CSMBlock::Write` | Block 写回（`nStaves*5+2+f2*2+nPts*8`） | [E] |
| 0x100BB270 / 0x100BB320 | `CSMObject::SetHead` / `GetHead` | head 负载存取 | [E] |
| 0x100BAD70 / 0x100BAEC0 | `CSMObject::AddMsg` / `InsertMsg` | 子项描述符写入（`role` 字节） | [E] |
| 0x1009A720 | `FUN_1009A720` | `GlobalMemoryStatus` 内存检查（**不是解压**） | [E] |

## engine.dll — 文本编码

| 地址 | 名称 | 作用 | 评级 |
|---|---|---|---|
| 0x10030B10 | `CKCConv::Open(id, path)` | 加载码表 id 1..6；每个 `.cod` 含正向+反向两张 `CCodeTable` | [E] |
| 0x100306B0 | `CCodeTable` 加载器 | 解析 `u16 n/lo/hi`，然后**每区间 `(u16 start, u16 end, u16 data[…])`** | [E] |
| 0x100308C0 | `CCodeTable` 查表 | 越界或未映射（值 0）时**原样返回输入码位** | [E] |
| 0x100303D0 | `CKCConv::ToUnicode(u16, u16)` | 单字符；id 0 = Unicode 透传 | [E] |
| 0x10030420 | `CKCConv::FromUnicode(u16, u16)` | 单字符反向 | [E] |
| 0x10030470 | `CKCConv::Convert(u16, u16, u16)` | 单字符 ToUnicode 再 FromUnicode | [E] |
| 0x10030D90 | `CKCConv::ToUnicode(id, src, len, dst, cap)` | 字符串版；`< 0x80` 单字节透传 | [E] |
| 0x10030EE0 | `CKCConv::FromUnicode(...)` | 字符串版反向 | [E] |
| 0x10031020 / 0x100311B0 | `CKCConv::Convert` | 带缓冲 / 就地转换 | [E] |
| 0x100317D0 | `CKCConv::ConvertFont` | 字体名换算 | [E] |
| 0x10030C80 | `CKCConv::GetCodeName(id)` | 0 Unicode / 1 "889F Code" / 2 "B0A1 Code" / 3 "F040(95) Code" / 4 "F040(98) Code" / 5 "F040(MAC) Code" / 6 "B0A1(KS) Code" | [E] |
| 0x10096530 | `MyDrawTextOutW` | **绘制端统一入口**：`ToUnicode(3, …)` 求长度 + `ToUnicode(1, …)` 实际转换 → `TextOutW` | [E] |
| 0x100965D0 | `MyGetTextExtentW` | 同上，`GetTextExtentPoint32W` | [E] |

## engine.dll — 消息类型与音乐字段

| 地址 | 名称 | 作用 | 评级 |
|---|---|---|---|
| 0x1004AA00 | `CScoreView::SMDrawMsg` | **按 type 分派的唯一 switch**（40+ 类型） | [E] |
| 0x1004EC70 | `CScoreView::DrawNote` | 音符绘制（缩放/声部/标志/音高）；字体 `KayakumA` | [E] |
| 0x1004FAF0 | `CScoreView::DrawHead` | 符头/附点/括号绘制（`+0x5C` 符头类型） | [E] |
| 0x10051320 | `CScoreView::DrawBeam` | 连梁 | [E] |
| 0x10054160 | `CScoreView::DrawTimeSig` | 拍号绘制 | [E] |
| 0x10055430 | `CScoreView::DrawMeasClef` | 小节谱号 | [E] |
| 0x10055910 | `CScoreView::DrawMeasKey` | 小节调号 | [E] |
| 0x10056910 | `CScoreView::DrawRest` | 休止符 | [E] |
| 0x100571F0 | `CScoreView::DrawKeysign` | 调号（`codeAcci[+0x5E]`） | [E] |
| 0x10057410 | `CScoreView::DrawClef` | 谱号 | [E] |
| 0x10057F90 | `CScoreView::DrawSingle_Msg` | 单字符记号（0x11/0x2A/0x2F/0x30/0x34..0x3E） | [E] |
| 0x100595B0 | `CScoreView::DrawLongrest` | 长休止（type 0x2C；小节数在 `MsgHdr+0x1C`） | [E] |
| 0x1005A6E0 | `CScoreView::DrawSlur` | 圆滑线 | [E] |
| 0x1005B1F0 | `CScoreView::DrawMultiText` | 文本框（type 0x04/0x06） | [E] |
| 0x1005E690 | `CScoreView::DrawDynamic` | 力度（`CodeDyn[+0x5E]`） | [E] |
| 0x1005EBB0 | `CScoreView::DrawTextMsg` | 歌词（type 0x19） | [E] |
| 0x10063160 | `CScoreView::DrawMeasTuplet` | 小节连音符（type 0x12） | [E] |
| 0x10066290 | `CScoreView::DrawMidiShortMsg` | MIDI 短消息（type 0x42） | [E] |
| 0x10036470 | `CSMMsg::CalcPlayTime` | 时值计算（`0x100>>(+0x5E&0x1F)`、附点、f2 比例） | [E] |
| 0x10042A50 | `CSMMsg::GetPlayTime` | 播放时间查询（`+0x6E & 0x10` → 0） | [E] |
| 0x100B76F0 | `CSMMsg::SetPlayTime` | 时值回写 head+0x04 | [E] |
| 0x100B7FB0 | `CSMMsg::GetRealNoteDur` | 实际时值（连音合并 `+0x6E & 1`） | [E] |
| 0x10037A70 | `CSMMsg::UpdateStartTime` | 写 head+0x08；驱动子项 | [E] |
| 0x100AC520 / 0x100AC4D0 | `CSMMsg::Get/SetMidiKey` | **head+0x00 = MIDI key** | [E] |
| 0x100AC570 / 0x100AC5C0 | `CSMMsg::Get/SetVelocity` | **head+0x01 = velocity** | [E] |
| 0x100AAD60 | `CSMMsg::SetParamFromMidiKey` | 谱号/打击乐参数（`+0x5C` 鼓组、`+0x52` 音高、半音表） | [E] |
| 0x100AE030 | `CSMMeas::SetParamFromMidiKey` | 小节级参数与调号表 | [E] |
| 0x100B0830 | `CSMMsg::WhatIsAccidental` | 变音记号（调号顺序表 `{6,2,5,1,4,0,3}`） | [E] |
| 0x100AF1A0 | `CSMMsg::UpdateNoteKeySignature` | 变音/调号联动 | [E] |
| 0x100AAB90 | `CSMMsg::CorrectKeySign` | 调号修正 | [E] |
| 0x100B1370 | `CSMMsg::CalcNoteRestKind` | 时值 → 音符/休止种类 | [E] |
| 0x100B28F0 / 0x100B2940 | `Set/GetNoteHeight` | 对象 `+0x70`（符干方向/高度） | [E] |
| 0x100B2970 / 0x100B29C0 | `Set/GetTemporarySymbolGap` | 对象 `+0x66` | [E] |
| 0x100B29F0 / 0x100B2B70 | `Set/GetNoteHeadType` | **`+0x5C` 符头类型**（7 → 0x1A） | [E] |
| 0x100B2A90 | `CSMMsg::SetTail` | `+0x6E bit2` 符尾 | [E] |
| 0x100B2BA0 / 0x100B2BD0 | `Set/GetRestType` | **`+0x5E` 休止符类型** | [E] |
| 0x100B2C00 / 0x100B2C30 | `Set/GetToilThick` | 对象 `+0x1C`（连梁粗度） | [E] |
| 0x100B2C60 | `CSMMsg::ChangeNoteAttr` | 属性批量设置 | [E] |
| 0x100B2F50 | `CSMMsg::ChangeNoteDirection` | 符干方向（0/1/2/3=自动） | [E] |
| 0x100B2600 | `CSMMsg::MakeNoteMarkCtrl` | 记号控制点生成 | [E] |
| 0x100ABB80 / 0x100ABC60 | `Make/IsGraceNote` | `+0x6E bit4` 装饰音 | [E] |
| 0x100ABCC0 | `CSMMsg::MakeMidiMsgFromY` | **MIDI 头构造**（head 默认 100/0x40/0） | [E] |
| 0x100ABDA0 | `CSMMsg::UpdateMidiMsg` | 重算 head+0x00 | [E] |
| 0x10022D20 | `CSMDoc::EncToSMC_MidiMsg` | `.enc` → type 0x42（3 字节 MIDI 消息） | [E] |
| 0x1002F610 | `CSMDoc::GulsamToSMC_Note` | 外部格式 → 音符（字段写入路径；`+0x5C` 映射表 8→5, 9→4, 10→2, 11→6, 12→3, 13→3, 14→2, 15→1） | [E] |
| 0x1002FBE0 | `CSMDoc::GulsamToSMC_BEAM` | 外部格式 → 连梁 | [E] |
| 0x10030010 | `CSMDoc::GulsamToSMC_Lyrics` | 外部格式 → 歌词（type 0x19，headLen = 文本 + 0x10） | [E] |
| 0x10025170 | `CSMDoc::EncToSMC_Lyric` | `.enc` → 歌词（head 5 字段写入路径） | [E] |
| 0x10037D90 / 0x10037E20 | `GetTie/SlurIndex` | tie/slur 子项定位（按 `role`） | [E] |
| 0x1006ACD0 | `CSMMsg::CreateFrom` | 对象复制（连音端点键处理） | [E] |

## engine.dll — 和弦 / 指板 / 节奏

| 地址 | 名称 | 作用 | 评级 |
|---|---|---|---|
| 0x1000A470 | `CChordSymbol::CChordSymbol` | type 固定 0x45；内建 CFretBoard("KayakumA") | [E] |
| 0x1000BDB0 / 0x1000BF80 | `CChordSymbol::ReadFromMem` / `WriteToMem` | 和弦读写（对称） | [E] |
| 0x1000C1E0 | `CChordSymbol::Initialize` | 从另一和弦初始化 | [E] |
| 0x1000D930 | `CChordSymbol::CreateFrom` | 和弦复制 | [E] |
| 0x1000C3A0 | `CChordSymbol::ReadFretInfo` | 从 profile 读指板 | [E] |
| 0x1000A6B0 / 0x1000AA90 | `CChordSymbol::Draw` / `DrawFrame` | 和弦绘制 | [E] |
| 0x10008B40 / 0x10008BF0 | `CChordSurfix::ReadFromMem` / `WriteToMem` | 后缀 `CStr` + `u8 n` + `[u8; n]` | [E] |
| 0x1002CFD0 / 0x1002D060 | `CFretBoard::ReadFromMem` / `WriteToMem` | 内嵌 Msg(0x46) + FretInfo | [E] |
| 0x1002DC70 / 0x1002DD00 | `CFretInfo::ReadFromMem` / `WriteToMem` | **16 字节：基准品位 + 6 弦 + 4 组对** | [E] |
| 0x1002D220 | `CFretInfo::GetMidiKeyOfString` | 弦品位 → MIDI key | [E] |
| 0x1002D2A0 | `CFretInfo::IsFretEmpty` | 空指板判定 | [E] |
| 0x1002D330 | `CFretInfo::FretInfoToLineString` | 指板 → 文本（字段顺序证据） | [E] |
| 0x10045C40 / 0x10045CF0 | `CRhythm::ReadFromMem` / `WriteToMem` | Msg(0x47) + 3 × `CStr` + RtmData | [E] |
| 0x10047720 / 0x10047950 | `CRtmData::ReadFromMem` / `WriteToMem` | **节奏数据（totalSize/stride/事件块/第二段）** | [E] |
| 0x10047410 | `CRtmData::GetRealMidiKey` | 节奏事件 → MIDI key | [E] |
| 0x10046210 | `CRtmData::ReadRtmData` | 从 profile 读节奏 | [E] |
| 0x100472F0 | `CRtmData::GetFullFileName` | 节奏资源文件名 | [E] |

## engine.dll — 歌词 / 文本消息

| 地址 | 名称 | 作用 | 评级 |
|---|---|---|---|
| 0x1009AD00 | `CSMLyricMsg::DrawMsg` | **type 0x19 绘制器**（head +0x00/+0x02/+0x04/+0x08/+0x0C + 文本 +0x10） | [E] |
| 0x1009AC20 | `CSMLyricMsg::ctor` | 类身份；vtable 0x100E52B8 | [E] |
| 0x1005EBB0 | `CScoreView::DrawTextMsg` | 计算屏幕位置并调用 `CSMLyricMsg::DrawMsg` | [E] |
| 0x100C9B70 | `CTempLyricMsg::ctor` | 编辑期歌词对象（内嵌 `CTempMsg` @ +0x80） | [E] |
| 0x100C9CF0 / 0x100C9D40 | `CTempLyricMsg::BeginDrag` / `EndDrag` | 拖拽编辑 | [E] |
| 0x100C9E50 | `CTempLyricMsg::InitDragingParameter` | 拖拽参数 | [E] |
| 0x10003D40 | `CSMDoc::GetRealRectOfLyrics` | 歌词真实矩形 | [E] |
| 0x100C2F70 | `CSMTextMsg::DrawMsg` | **type 0x06 绘制器**：TLV 标签 0x01..0x0A | [E] |
| 0x100C2E90 | `CSMTextMsg::ctor` | type 0x06 类 | [E] |
| 0x1005B1F0 | `CScoreView::DrawMultiText` | 构造 `CSMTextMsg` 并调用 DrawMsg | [E] |
| 0x100C3BF0 | `CSMTextMsg::RichTextLineOut` | 逐行富文本输出 | [E] |
| 0x100C40C0 | `CSMTextMsg::AnalizeText` | TLV 文本分析 | [E] |

## engine.dll — 结构与布局

| 地址 | 名称 | 作用 | 评级 |
|---|---|---|---|
| 0x1003A4D0 | `CSMMeas::CalcWholeCount` | 小节 tick 与连音符分段表（对象 +0xEC） | [E] |
| 0x10094ED0 | `CSMFileInfo::SetLogicPageInfo` | 页面版式信息设置（字段语义入口） | [E] |
| 0x100950A0 | `CSMFileInfo::UpdateLogicDoc` | 版式更新 | [E] |
| 0x1009B9C0 | `CSMMeas::AbsXToMeasX` | 绝对 X → 小节内 X | [E] |
| 0x1003D3B0 / 0x1003D620 | `GetNearestRightOfX` / `GetNearestLeftOfX` | 邻近消息查找（歌词定位） | [E] |

## engine.dll — 相关但尚未分析

| 地址 | 名称 | 关注原因 | 评级 |
|---|---|---|---|
| 0x10077690 | `CSMDoc::ImportSMC(CFile*, BYTE*, BYTE)` | 另一条 SMC 导入路径（可能旧版/合并） | 未分析 |
| 0x10071140 / 0x100BC060 / 0x100C1B60 … | `CSMBlock/CSMPage/CSMSystem…::Load(CFile*)` | 另一套基于 CFile 的 Load（用途未知，可能剪贴板/模板） | 未分析 |
| 0x100157D0 | `CEncDoc::Read` 及 `CEnc*` | `.enc` 格式（`"Inputing ... to smc"` 字符串所在转换器） | 未分析 |
| 0x10049810 | `CScoreView::SMOpen` | 视图打开 | 未分析 |
| 0x10035FC0 / 0x10035FE0 | `Get/SetMidiFileRead` | MIDI 相关 | 未分析 |
