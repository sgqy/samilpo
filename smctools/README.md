# smctools

Samilpo 2.0 乐谱格式（SMC）的独立转换工具集，uv 项目，仅标准库。

两个功能：

* **乐谱（score）**——解析乐谱：`SMC → IR(NDJSON) → MusicXML`，附边栏歌词文本
  （side text）与 IR/MusicXML 一致性校验。
* **索引（index）**——索引转换与乐谱查询。**占位**：`IndexFiles/SamIlPo.idx`、
  `Score.sci`、`KcgInfo.kbd` 尚未做格式分析，只留接口。

## 用法

```bash
# 单曲模式：给出 smc 路径，输出 IR 和 XML（码表按上文优先级解析）
uv run smctools score "<安装目录>\8000Songs\500KFS\500KFS-0041.smc" -o out

# 全量模式：输入安装目录，自动读取码表，输出全部 smc 转换（按子集分子目录）
uv run smctools score --install-dir "<安装目录>" -o out

# 继承自 work/ 设计的全部参数（parameters.md H 的六个参数 + 覆盖项）
uv run smctools score FILE.smc -o out --extent musical --accidental-policy transposed \
    --lyric-line-policy none --hyphen-policy syllabic --part-merge all \
    --timesig-clamp --dynamic-map map.json --no-side-text --no-verify --namespaced

# 校验一个 MusicXML 与其 IR 的一致性
uv run smctools verify FILE.ndjson FILE.musicxml

# 索引功能（占位，exit 2）
uv run smctools index
```

全量模式附加项：`--limit N`（只转前 N 个，测试用）。批处理逐文件隔离——单个坏文件
不中断整批，按阶段（convert / verify）归因并在汇总里给出示例；每个文件都跑
IR/MusicXML 校验（`--no-verify` 关闭）。

**0x08 未知记号**：遇到 `MarkTB` 中没有确认含义的索引（Samilpo 调色板定义了、
但映射表未覆盖的符号）时，向 stderr 输出 WARNING（含索引、字形码、位置），
记号以 `<words>smc-type-8</words>` 保留，不丢弃。全量模式汇总里给出索引直方图。

**两种文本方言，码表可选**：终极目标是回归本家（Music Score Viewer）格式，
Samilpo 2.0 是其中一个发行版。本家格式的文本按 UTF-16 存储（原始引擎
`CSMLyricMsg::DrawMsg` 直接 `TextOutW` 绘制，无需码表），所以不给码表时
smctools 按 UTF-16LE 解码文本并继续运行（stderr 有提示）。处理 **Samilpo 2.0**
文件时必须装载其码表 `889F.cod`（`--cod`，或 `--install-dir`/`SAMILPO_INSTALL`
自动定位），否则文本字符会错。两代引擎均无 CP932 回退（REA/Ghidra 查证，
依据见 `docs/encoding.md` §9），本工具同样不做 CP932 降级。
注：本家方言目前落实在**文本解码层**；完整本家格式支持（结构层差异）待真实
MSV 文件验证。

## 现状与边界（研究封稿 2026-11-07）

乐谱恢复研究暂时封稿，本转换器为封稿时的交付形态：

* **已交付**：Samilpo 2.0 发行版的完整转换（结构层 92.9% / 语义层 78.8% 覆盖，
  文本/歌词/和弦/伴奏/记号全部落地；type 0x08 记号 14 个语料索引经人工确认）。
* **本家支持**：仅文本解码层（UTF-16LE）。结构层需要真实本家 `.smc` 文件验证，
  该数据现不可考——获得本家文件前不会再推进。
* **挂起项**：MarkTB 51 项中 37 个语料未用索引的含义；`msv_manual.pdf` 未提取。
  重启条件与恢复步骤见仓库 `project/research-state.md` 封稿节。

## 与 work/ 草稿的关系（迁移与去重）

| 本项目模块 | 来源 | 变更 |
|---|---|---|
| `smcfile.py` | `work/smc_read.py` | 码表拆出；安装路径改为 `paths.py` 解析（env/参数，不硬编码） |
| `codtable.py` | `work/smc_read.py` 尾部（与 `tools/smc_text.py` 同型） | 三处码表解码合并为唯一实现 |
| `to_ir.py` | `work/smc2ir.py` | 码表路径参数化（`opts.cod`）；去掉 `sys.path` 补丁与独立 main |
| `to_musicxml.py` | `work/ir2musicxml.py` | 删除死代码 `smc_text_payload`/`_tlv_words`/`_load_cod`（TLV 解码已统一在 IR 侧）；MarkTB 表改为导入 `marks.py`；新增未知记号警告 |
| `marks.py` | 问卷生成器的 `MARKTB` 表 + `ir2musicxml` 的 `MARK_XML`/`MARK_WORDS` | 字形表与语义映射合并为单一来源 |
| `walk.py` / `fret.py` / `accomp.py` | `work/probe_smc.py` / `work/fret.py` / `work/accomp.py` | 改包内导入；probe 专用 CLI 留在 work/ |
| `verify.py` | `work/verify_musicxml.py` | 入口改为 `run(ir, xml)`；删除未用的 import |
| `side_text.py` | `work/side_text.py` | 包内导入 |
| `pipeline.py` | `work/smc_convert.py` + `work/batch.py` | 两种编排合并为一条进程内管线 |
| `cli.py` / `index.py` / `paths.py` | 新写 | 单一 CLI；索引占位；路径单源 |

规范文档仍在仓库 `docs/`（`smc-format.md`、`music-fields.md`、`parameters.md` 等），
本项目不含文档副本。
