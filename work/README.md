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
.smc  --[step1: smc2ir]-->  IR(json)  --[step2: ir2musicxml]-->  .musicxml
```

- **step1 只做"读取 + 归一化"**，不做排版、不做分页决策、不猜语义。
- **step2 只做"IR → MusicXML 元素映射"**，不回去读 SMC，不依赖引擎代码。
- 判据：IR 中每一个字段都要能回答"它对 MusicXML 的哪个元素/属性负责"；
  回答不了的字段进 `ext`（扩展命名空间），并标记为 `non-musical`。

## 实验基线与复现

```
python work/probe_smc.py <file.smc> summary|notes|ties|keys|chords
python work/probe2.py  <file.smc> tree <meas>|depth|long|conv|lyricmap|endpts
python work/probe3.py  <file.smc> [...]          # 时值模型校验
python work/probe4.py  <file.smc> [...]          # head 字节级统计
python work/probe5.py  --max 0                   # 全语料普查（8451 文件，约 3 分钟）
python work/probe6.py  --max 0                   # 异常小节与异常歌词
python work/probe7.py  --max 0                   # 和弦/指板/长休止等结构计数
python work/probe8.py  --max 0                   # keysig_type 取值调查
python work/verify_read.py --max 0               # 与 tools/smc_walk.py 交叉校验
```

全部脚本的 `--dir` 默认 `<安装目录>\8000Songs` 并**递归**收集 `.smc`；`--max 0` 表示不限量。

基本实验文件：`<安装目录>\8000Songs\500KFS\500KFS-0041.smc`。
普查输出：`out_census_all.txt`（8451 文件）、`out_extra_all.txt`、`out_odd500KFS.txt`、
`out_keysig_all.txt`、`out_verify_all.txt`。

## 现状

- [x] 读取库 + 转储工具跑通，**8451/8451** 文件零失败。
- [x] **与 spec 参考实现交叉校验**：`work/verify_read.py` 对全部 8451 文件比对
      `tools/smc_walk.py`（`docs/` 的验证基线）的逐类型消息计数与主体字节消耗 →
      **identical = 8451 / differing = 0 / errors = 0**（`out_verify_all.txt`）。
- [x] 时值/对齐模型已实测判定（见 `ir-design.md` §3）。
- [x] 取舍清单（`parameters.md`）、决定记录（`decisions.md`）已按全语料数字修订。
- [ ] `smc2ir.py`：待实现。
- [ ] `ir2musicxml.py`：待实现。
