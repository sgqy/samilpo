# work/ —— SMC → IR → MusicXML 转换器工作区

本目录**与 `docs/` `project/` 的规范成果隔离**：`docs/` 是交付规范，本目录是消费规范的转换器实现与实验记录。
规范有疑问时**不改 spec**，在本目录记录"转换器侧的假设与取舍"（`decisions.md`）。

## 目录内容

| 文件 | 作用 |
|---|---|
| `README.md` | 本文件。目标、架构、运行方式。 |
| `parameters.md` | **取舍清单**：哪些地方必须做决定、可选值、默认值、判据与已知失败模式。 |
| `ir-design.md` | IR 规格（v0），以及"为什么这么设计才能方便合成 MusicXML"。 |
| `decisions.md` | 逐条决定与其实测依据；对 spec 的依赖点与偏离点。 |
| `smc_read.py` | SMC 读取库（按 spec 实现，保留全部需要的字段）。 |
| `probe*.py` | 实验脚本，产出下表数据。 |
| `out_*.txt` | 实验输出（证据）。 |

## 目标与两步走

```
.smc  --[step1: smc2ir.py]-->  IR(NDJSON)  --[step2: ir2musicxml.py]-->  .musicxml
```

- **step1 只做"读取 + 归一化"**，不做排版、不做分页决策、不猜语义。
- **step2 只做"IR → MusicXML 元素映射"**，不回去读 SMC，不依赖引擎代码。
- 判据：IR 中每一个字段都要能回答"它对 MusicXML 的哪个元素/属性负责"；
  回答不了的字段进 `ext`，并标记为 `non-musical`。

## 用法

三种产物一次生成（推荐）：

```
python work/smc_convert.py <file.smc> [--out-dir DIR]
```

写出 `<stem>.ndjson`（IR）、`<stem>.musicxml`、并在源文件带并排文本时写出 `<stem>.txt`。
其余选项原样透传给 `smc2ir.py`，`parameters.md` H 的六个参数在此全部可用。

分步：

```
python work/smc2ir.py <file.smc> <out.ndjson> [六个参数]
python work/ir2musicxml.py <out.ndjson> <out.musicxml>
python work/side_text.py <out.ndjson> <out.txt> [--width 60] [--header]
python work/verify_musicxml.py <out.ndjson> <out.musicxml>
```

把三者串起来跑一个文件，用 `batch.py` 跑全语料：

```
python work/batch.py --max 0            # 8451 文件，约 4 分钟
```

当前结果：**8442 / 8451 通过全部不变量检查**；其余 9 例已定性为源文件自身的异常
（见 `verification.md` §3）。

### 三种产物为什么是三种

`decisions.md` §12–§14 有完整依据，摘要：

- **MusicXML**：音符、歌词（第一段）、速度/表情术语、强弱号、和弦记号。这是能回放进 MuseScore 的主体。
- **`.txt`（并排文本）**：源文件写在谱面旁边的多行文本块（通常是**第二、三段歌词**）。
  MusicXML 没有"谱面旁边的多行文本块"这种结构，硬塞进 `<words>` 会丢行结构、
  塞进 `<lyric>` 又必须挂到某个音符上，所以单独出文件。
- 单行文本块（如 `낭만적으로`、曲名）确实在谱面上，走 MusicXML 的 `<words>`。

**伴奏**：**有**，但它不在谱表里——它嵌在 `type 0x45` 和弦记号内部的 `RtmData`
（`type 0x47` 节奏）中，全语料 **8445/8451** 个文件携带，12716 条里 101 条嵌在和弦里。
它是一份**存好的多轨编曲**（旋律和声、贝斯、打击乐），音高以"相对当前和弦根音的音级"记录，
所以同一段伴奏套在不同和弦上会得到不同的实际音高——**不是**从和弦推导出来的。

`500KFS-0041` 只有 1 个谱表，但解出 **11 个伴奏 part / 3082 个音符**
（`6/8GudGoRi-2` 风格：打击乐 + Acoustic Grand + Vibraphone + Contrabass）。
每轨导出为**独立 part**，各自 MIDI 通道与谱号，完全可见。
理由与依据见 `decisions.md` §14：**"隐藏"是排版状态，不是丢数据的理由**。

## 文档

| 文件 | 内容 |
|---|---|
| `parameters.md` | **取舍清单**：6 个参数 + 全部已固化为常量的决定 |
| `ir-design.md` | IR 规格 v1（NDJSON），以及"为什么这样方便合成 MusicXML" |
| `decisions.md` | 逐条决定的实测依据，含对 spec 的依赖与偏离 |
| `verification.md` | 端到端验证口径、全语料结果、9 例已知异常的定性 |

## 目录内容

| 文件 | 作用 |
|---|---|
| `smc_read.py` | SMC 读取库（按 spec 实现，保留全部需要的字段） |
| `smc2ir.py` | step1：SMC → NDJSON IR |
| `ir2musicxml.py` | step2：IR → MusicXML 4.0 partwise |
| `accomp.py` | 伴奏解码：`RtmData` 多轨编曲 → 独立 part（`decisions.md` §14） |
| `fret.py` | 和弦根音：`FretInfo` 指法 → 根音/和弦形状 |
| `side_text.py` | 并排文本导出（第二、三段歌词等多行文本块） |
| `smc_convert.py` | 一条命令产出全部三种产物 |
| `verify_musicxml.py` | 不变量校验 |
| `batch.py` | 全语料回归 |
| `verify_read.py` | 与 `tools/smc_walk.py` 的交叉校验 |
| `probe*.py` | 实验脚本，产出下表数据 |
| `_diff_notes.py` / `_dbg_one.py` | 逐音符/逐小节的定位工具 |
| `irpeek.py` | IR 查询小工具 |
| `out_*.txt` / `out_0041.*` | 实验与产物证据 |

## 实验基线与复现

```
python work/probe_smc.py <file.smc> summary|notes|ties|keys|chords
python work/probe2.py  <file.smc> tree <meas>|depth|long|conv|lyricmap|endpts
python work/probe3.py  <file.smc> [...]       # 时值模型校验
python work/probe4.py  <file.smc> [...]       # head 字节级统计
python work/probe5.py  --max 0                # 全语料普查（8451 文件）
python work/probe6.py  --max 0                # 异常小节与异常歌词
python work/probe7.py  --max 0                # 和弦/指板/长休止等结构计数
python work/probe8.py  --max 0                # keysig_type 取值调查
python work/probe9.py  --max 0                # 时值粒度与三连音统计
python work/verify_read.py --max 0            # 与 tools/smc_walk.py 交叉校验
python work/_diff_notes.py <file.smc> <meas>  # 逐音符比对 IR 与 XML
python work/probe49.py                       # type 0x08 全语料普查（索引/headLen/voice/dxdy）
python work/probe50.py                       # type 0x08 按父容器分类
python work/probe52.py                       # type 0x08 与音符上下文的交叉统计
python work/probe54.py                       # type 0x08 每文件索引集合与出现顺序
python work/_probe_marktb.py                 # 解码 MarkTB（51 项 × 6 字节）
python work/_probe_marktb_geom.py <idx...>   # MarkTB 字形的字体空间轮廓
python work/_probe_sheet.py <png> <idx,...>  # MarkTB 字形对照图
python work/make_mark_questionnaire.py       # 生成记号识别问卷（HTML + TSV + JSON）
```

全部脚本的 `--dir` 默认 `<安装目录>\8000Songs` 并**递归**收集 `.smc`；`--max 0` 表示不限量。

基本实验文件：`<安装目录>\8000Songs\500KFS\500KFS-0041.smc`。
普查输出：`out_census_all.txt`、`out_extra_all.txt`、`out_odd500KFS.txt`、
`out_keysig_all.txt`、`out_verify_all.txt`、`out_batch_all.txt`。

## 现状

- [x] 读取库跑通，**8451/8451** 文件零失败，与 spec 参考实现逐类型计数完全一致。
- [x] **step1（`smc2ir.py`）与 step2（`ir2musicxml.py`）实现完成**。
- [x] 全语料端到端 **8442/8451** 通过不变量检查；9 例异常已定性。
- [x] 取舍清单收敛为 6 个参数，其余固化（`parameters.md` §I 有降级记录）。
- [x] 速度/表情术语、强弱号、和弦记号写出（`decisions.md` §12）。
- [x] 和弦**根音**：取自 ObjectCore `+0x08`（引擎 18 项拼写表的索引），
      指法仅为后备。全语料 **177909 个和弦全部带根音**（缺陷从 16.8% 清零）；
      源/产物和弦数 **8451/8451** 一致（`decisions.md` §20）。
- [x] 曲名（SYMP 头）全语料 **8451/8451** 逐字一致，无 BOM（§19）。
- [x] 作者：从页面文本恢复，545 例带作者、0 例丢失，`<creator>` 与 `<words>` 并存（§19）。
- [x] 伴奏：`RtmData` 多轨编曲全部导出为独立 part（§14）。
- [x] 第二、三段歌词导出为并排 `.txt`（`decisions.md` §13）。
- [ ] 歌词换行（`parameters.md` D3）仍是启发式，需真实排版核对。
- [ ] 谱号类别枚举（C4）与力度码映射（E4）仍是推断，等待新证据。
- [ ] 节拍器 `head[2]` 判定为 BPM/10（§12），需静态确认 `DrawMetronome`。
- [ ] `DrawMark`（`type 0x08`）目前写成 `<words>smc-type-8</words>`，
      必须换成真正的 MusicXML 元素。**结构已全部解出**（`docs/smc-format.md` §6.13b）：
      `MsgHdr+0x06` = `MarkTB` 索引、`+0x16/+0x18` = X/Y、`headLen` 恒 0。
      已定案 `29` = 正立延长记号、`30` = 倒立延长记号；其余 12 个索引
      （1/8/10/11/13/14/16/25/33/35/43/45）的含义需人工判形——
      见 `work/mark-questionnaire.html`，答卷填 `work/mark-questionnaire.tsv`，
      统计在 `work/mark-stats.json`。
- [ ] `part_merge=auto` 对"合唱分谱"应拆成多个 part（§14），判据待定。
