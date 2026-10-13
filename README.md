# 降 AI 率写作技能包 · Reduce-AI-Rate Writing Skill

> **一句话定位**：对学术文本**自动做 AIGC 检测**，逐段定位「AI 味」来源并**迭代改写**，
> 直到全文 AIGC 疑似率降到 **5% 以下**；中英双语、两条通路独立可用，改句式而不动事实。
>
> **In one line**: an AIGC-detection-and-rewrite toolkit for academic writing that iterates until the
> document's AI-suspicion rate drops **below 5%** — bilingual (Chinese / English), two independent paths,
> rewriting structure without touching facts.

本仓库根目录 = 技能包根目录；下面所有相对链接都从这里出发。

---

## 中文

### 这是什么

你有一稿（`.md` / `.txt` / `.docx`），担心被 AIGC 检测标红。本仓库帮你走完一个闭环：

> **检测 → 定位最高风险段 → 按手法定向改 → 复检 → 不达标再来一轮，直到全文 AIGC < 5%。**

改完之后，数据、引用、结论一个字都没动。它**不能**把抄来的内容洗白——那是查重与学术诚信问题。
完整说明见 [`SKILL.zh.md`](SKILL.zh.md)（中文独立完整版）与 [`SKILL.en.md`](SKILL.en.md)（英文独立完整版），
入口索引见 [`SKILL.md`](SKILL.md)。

### 目录结构

```
SKILL.md            # 入口：双语导航、一句话工作流、脚本入口、红线、边界
SKILL.zh.md         # 中文独立完整版（只读这一份即可走通）
SKILL.en.md         # English standalone
references/         # 9 份专题文档
  ├─ 01_language_fingerprints.md   # 中英语言特征（真人与 AI 的差异点，含真实例句）
  ├─ 02_template_wordlist.md       # 中英模板词 / 套话词表（中文 62 + 英文 40）
  ├─ 03_rewrite_playbook.md        # 十种改写手法（每条前→后例）
  ├─ 04_anti_defensive_writing.md  # 反防御性写作 + docx 定点改写流程
  ├─ 05_reviewer_simulation.md     # 改写后模拟审稿自审清单
  ├─ 06_academic_style.md          # 学术写作风格与知识隔离（防编造）
  ├─ 07_detector_logic.md          # 查重与 AIGC 检测原理
  ├─ 08_corpus_notes.md            # 语料学习笔记
  └─ 09_citation_integrity.md      # 引用验真与 GB/T 7714
scripts/            # 8 个脚本
  ├─ fingerprint.py       # 规则指纹（零依赖）
  ├─ model_zh.py          # 中文模型通路
  ├─ model_en.py          # 英文模型通路
  ├─ model_common.py      # 模型加载 / 分块推理 / 报告
  ├─ calibrate.py         # 阳性 / 阴性对照
  ├─ download_models.py   # 从 hf-mirror 下载模型权重
  ├─ detox_pipeline.py    # 主控：双检测 + 逐段风险排序 + 定向指令 + 5% 判定
  └─ utils.py             # 文本抽取 / 分句（位置无关）
examples/           # 可运行样例（中英 before/after + 实测数值）
```

### 快速开始（3 步）

```bash
# ① 首次使用：下载检测模型（不入库，走 hf-mirror；中文约 400MB、英文约 500MB）
python scripts/download_models.py --lang all

# ② 阳性/阴性对照（不可省：证明检测器在工作，而不是失灵）
python scripts/calibrate.py --lang all --sample examples/sample_ai_zh.md

# ③ 主控：检测 + 逐段风险排序 + 定向改写指令 + 5% 达标判定
python scripts/detox_pipeline.py <你的稿件.md|txt|docx> --top 12
```

机读接口（供上游循环）：`python scripts/detox_pipeline.py <稿件> --json --no-report`，
`stdout` 为纯净 JSON（`passed` / `doc_suspected_rate` / `rewrite_targets` / 每段 `instructions`）。
细节见 [`SKILL.zh.md`](SKILL.zh.md) §2–§6。

### 环境

- **Python 3.10+**。
- 模型通路需 `torch` + `transformers`；**规则指纹通路纯标准库、零依赖**（没有 `torch` 时用 `--no-model` 仍可跑）。
- 脚本**位置无关**，整包拷到任意目录都能运行。

### 实测锚点（本包开源检测器口径，非官方数值）

| 样例 | 规则指纹（改前→改后） | 模型全文疑似率（改前→改后） |
|---|---|---|
| 中文 `examples/sample_ai_zh(.rewritten).md` | 54.5 → 24.8 / 100 | **70.37% → 0.00%** |
| 英文 `examples/sample_ai_en(.rewritten).md` | 50.5 → 25.1 / 100 | **9.36% → 0.03%** |

复现命令与逐段来源见 [`examples/README.md`](examples/README.md)。

### 两处提醒

1. **模型不入库**：`models/` 已在 `.gitignore` 中排除（体积大），首次使用须跑 `download_models.py`。
2. **检测产物不入库**：`*.aigc*.json`、`*.detox.*` 已在 `.gitignore` 中排除，运行脚本会就地生成，不会污染仓库。

### 边界（务必读）

- 本工具复刻的是维普 / 知网 / 万方 AIGC 检测的**检测维度**，输出的是**相对风险分**，
  **不等于任何一家的官方数值**。定稿后须以目标期刊 / 学校指定系统的官方检测为准。
- 开源检测器**对含蓄的 AI 文本偏保守**（甚至漏检），"得低分"是**真实但有限**的正面信号；
  英文通路的区分度还会随主题波动。因此定位问题以规则指纹的逐维分解为主。
- 阳性 / 阴性对照（`calibrate.py`）**不可省**。详见 [`references/07_detector_logic.md`](references/07_detector_logic.md)。

### 许可

MIT License，署名 **ThaLab**。见 [`LICENSE`](LICENSE)。

---

## English

### What this is

You have a manuscript (`.md` / `.txt` / `.docx`) and worry an AIGC detector will flag it. This repository
drives one loop end to end:

> **Detect → locate the highest-risk paragraphs → rewrite them by technique → re-check → loop until AIGC < 5%.**

After rewriting, your data, citations, and conclusions are untouched. It **cannot** sanitize copied text —
that is a plagiarism/integrity matter, not a style matter. Read the standalone guides:
[`SKILL.en.md`](SKILL.en.md) (English) and [`SKILL.zh.md`](SKILL.zh.md) (Chinese); index in [`SKILL.md`](SKILL.md).

### Repository layout

```
SKILL.md            # Entry: bilingual navigation, one-line workflow, script entry points, red lines, boundaries
SKILL.zh.md         # Chinese standalone (read only this one to complete the whole pipeline)
SKILL.en.md         # English standalone
references/         # 9 topic documents
  ├─ 01_language_fingerprints.md   # ZH/EN language features (human vs AI, with real examples)
  ├─ 02_template_wordlist.md       # ZH/EN template word lists (62 ZH + 40 EN)
  ├─ 03_rewrite_playbook.md        # Ten rewrite techniques (each with before→after)
  ├─ 04_anti_defensive_writing.md  # Anti-defensive writing + .docx point edits
  ├─ 05_reviewer_simulation.md     # Post-rewrite self-review checklist
  ├─ 06_academic_style.md          # Academic style and knowledge isolation (against fabrication)
  ├─ 07_detector_logic.md          # Plagiarism vs AIGC detection
  ├─ 08_corpus_notes.md            # Corpus learning notes
  └─ 09_citation_integrity.md      # Citation verification and GB/T 7714
scripts/            # 8 scripts
  ├─ fingerprint.py       # Rule-based fingerprint (zero-dependency)
  ├─ model_zh.py          # Chinese model path
  ├─ model_en.py          # English model path
  ├─ model_common.py      # Model loading / chunked inference / report
  ├─ calibrate.py         # Positive / negative controls
  ├─ download_models.py   # Download model weights from hf-mirror
  ├─ detox_pipeline.py    # Main pipeline: dual detection + per-paragraph ranking + instructions + 5% verdict
  └─ utils.py             # Text extraction / sentence splitting (location-independent)
examples/           # Runnable samples (ZH/EN before/after with measured numbers)
```

### Quick start (3 steps)

```bash
# 1) First run: download the detectors (not in the repo; via hf-mirror; ~400MB ZH, ~500MB EN)
python scripts/download_models.py --lang all

# 2) Positive/negative controls — DO NOT SKIP (proves the detector works rather than fails)
python scripts/calibrate.py --lang all --sample examples/sample_ai_zh.md

# 3) Main pipeline: detection + per-paragraph ranking + targeted instructions + 5% verdict
python scripts/detox_pipeline.py <your-draft.md|txt|docx> --top 12
```

Machine-readable interface (for upstream loops): `python scripts/detox_pipeline.py <draft> --json --no-report`.
`stdout` is pure JSON (`passed` / `doc_suspected_rate` / `rewrite_targets` / per-paragraph `instructions`).
See [`SKILL.en.md`](SKILL.en.md) §2–§6.

### Requirements

- **Python 3.10+**.
- The model path needs `torch` + `transformers`; the **rule-based fingerprint path is pure standard library,
  zero-dependency** (without `torch`, use `--no-model` and it still runs).
- Scripts are **location-independent** — the whole folder runs from any directory.

### Measured anchors (this repo's open-source-detector caliber, not official numbers)

| Sample | Rule fingerprint (before → after) | Document suspicion rate, model (before → after) |
|---|---|---|
| Chinese `examples/sample_ai_zh(.rewritten).md` | 54.5 → 24.8 / 100 | **70.37% → 0.00%** |
| English `examples/sample_ai_en(.rewritten).md` | 50.5 → 25.1 / 100 | **9.36% → 0.03%** |

Reproduction commands and per-paragraph sources: [`examples/README.md`](examples/README.md).

### Two reminders

1. **Models are not in the repo**: `models/` is excluded by `.gitignore` (large). Run `download_models.py` on first use.
2. **Detection artifacts are not in the repo**: `*.aigc*.json` and `*.detox.*` are excluded by `.gitignore`;
   scripts generate them in place and will not pollute the repository.

### Boundaries (please read)

- This toolkit reproduces the **detection dimensions** of the VIP / CNKI / Wanfang AIGC systems and outputs a
  **relative risk score**; it **does not equal any vendor's official number**. Before submission, rely on the
  official check of your target journal/school.
- Open-source detectors are **conservative on subtle AI text** (they even miss some positives), so a low score is a
  **real but limited** positive signal; the English path's discrimination also varies with topic. Locate problems
  using the fingerprint's per-dimension breakdown first.
- The positive/negative controls (`calibrate.py`) are **not optional**. See [`references/07_detector_logic.md`](references/07_detector_logic.md).

### License

MIT License, attribution **ThaLab**. See [`LICENSE`](LICENSE).
