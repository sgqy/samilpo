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

```
python work/smc2ir.py <file.smc> <out.ndjson> [六个参数]
python work/ir2musicxml.py <out.ndjson> <out.musicxml>
python work/verify_musicxml.py <out.ndjson> <out.musicxml>
```

把两者串起来跑一个文件，用 `batch.py` 跑全语料：

```
python work/batch.py --max 0            # 8451 文件，约 4 分钟
```

当前结果：**8442 / 8451 通过全部不变量检查**；其余 9 例已定性为源文件自身的异常
（见 `verification.md` §3）。

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
- [ ] 歌词换行（`parameters.md` D3）仍是启发式，需真实排版核对。
- [ ] 谱号类别枚举（C4）与力度码映射（E4）仍是推断，等待新证据。
