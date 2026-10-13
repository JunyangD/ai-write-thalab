---
name: reduce-ai-rate
description: >
  降 AI 率写作技能包（中英双语）。对学术文本自动做 AIGC 检测，逐段定位「AI 味」来源，
  按规则定向改写，并反复复检直到全文 AIGC 疑似率降到 5% 以下；同时守住数据与引用红线，
  改写只动句式不动事实。适配中文论文与英文论文两条独立通路。
  中文触发词：降AI率、去AI味、降AIGC、AIGC检测、AI检测、检测AI率、论文润色、论文改写、
  论文降重、查重降重、投稿前自检、AI味太重、帮我改得像人写的。
  English triggers: reduce AI rate, lower AIGC score, AI detector, AI content detection,
  rewrite academic text, paraphrase a paper, de-AI writing, humanize academic writing,
  academic polishing, make my writing sound human.
  不适用：内容本身的抄袭问题（查重/学术不端）——那属于引用规范，不是文风问题。
---

# 降 AI 率写作技能包 · Reduce-AI-Rate Writing Skill

## 这份技能给谁用、解决什么

给要投中文刊或英文刊的研究者用。你手上有一稿（.md / .txt / .docx），
担心它被 AIGC 检测标红，或者已经被目标期刊的检测系统提示「疑似 AI 生成」。
这份技能帮你**逐段找出被标红的原因，定向改掉，再把分复测下来**——
目标是全文 AIGC 疑似率 < 5%，且改完之后数据、引用、结论一个字都没动。

它**不能**帮你把抄来的内容洗白。若正文来自未标注的他人文本，那是查重与学术诚信问题，
任何改写都不改变其性质（详见 `references/07_detector_logic.md` §学术诚信边界）。

## 先选语言，再看对应全文

| 你的场景 | 读哪一份 |
|---|---|
| 中文写作 / 中文论文 / 中文期刊投稿 | **`SKILL.zh.md`（中文完整独立版）** |
| English writing / English journal submission | **`SKILL.en.md`（English standalone）** |

两份都是**独立完整版**，只读对应那一份就能全程走通，不必来回跳。
本文（`SKILL.md`）只做导航与总纲。

## 一句话工作流

> **检测 → 定位最高风险段 → 按改写手法定向改 → 复检 → 不达标就再来一轮，直到全文 AIGC < 5%。**

循环的五步落在 `scripts/detox_pipeline.py` 上：

1. **检测**：`fingerprint.py` 给规则风险分（0–100，零依赖），`model_zh.py` / `model_en.py` 给逐段 P(AI)；
2. **定位**：看每段的**主要风险来源**（句长过匀 / 模板词 / 连接词 / 长句 / 句首重复 / 一逗到底）；
3. **改写**：按 `references/03_rewrite_playbook.md` 对该段做定向改写（拆句、换主语、加限定、删模板词、去金句、长短交替）；
4. **复检**：重跑检测，对比前后数值；
5. **迭代**：重复 2–4，直到全文 AIGC < 5% 或到达轮次上限（未达标须如实报告）。

## 脚本调用入口

工作目录统一在技能包根目录（即本文件所在目录）下，脚本在 `scripts/`：

```bash
# 0) 首次使用：下载检测模型（~400MB 中文 / ~500MB 英文，走 hf-mirror）
python scripts/download_models.py --lang all

# 1) 阳性/阴性对照（不可省：证明检测器在工作，而不是失灵）
python scripts/calibrate.py --lang all --sample examples/sample_ai_zh.md

# 2) 主控：双检测 + 逐段风险排序 + 定向改写指令 + 5% 达标判定
python scripts/detox_pipeline.py <稿件.md|txt|docx> --top 12

# 3) 机读接口（供上游 agent 循环）：stdout 为纯净 JSON
python scripts/detox_pipeline.py <稿件> --json --no-report

# 4) 单跑某条通路
python scripts/fingerprint.py <稿件> --lang auto --top 12
python scripts/model_zh.py    <稿件> --top 15      # 中文稿
python scripts/model_en.py    <稿件> --top 15      # 英文稿
```

脚本清单：`fingerprint.py`（规则指纹）、`model_zh.py` / `model_en.py`（模型通路）、
`model_common.py`（模型封装）、`calibrate.py`（对照）、`download_models.py`（取模型）、
`detox_pipeline.py`（主控）、`utils.py`（工具）。全部**位置无关**，整包可拷到任意目录。

## 绝对禁止（红线，改写时反复自查）

1. **不改事实**：数据、年份、百分比、PMID、DOI、作者、机构、检索式、图表编号、结论方向——一律不动。
2. **不加内容**：不新增未提供的文献、数据、机制、国家、机构、结论；不编造引用。
3. **不换术语**：不把专业术语换成非专业词（地中海贫血、铁过载、ferroptosis、ACSL4、GPX4、hepcidin、TDT、NTBI 等必须原样保留）。
4. **引用格式**：观点句末写 `（pmid：XXXXXXX）`，**红色字体（RGB C00000）、句号在括号之外**；PMID 须经 NCBI esummary 逐条回读核验，**禁止虚构**（详见 `references/09_citation_integrity.md`）。
5. **去 AI 痕迹**：删「值得注意的是 / 综上所述 / 首先其次最后 / 不可忽视 / 一方面…另一方面」等模板套话（完整词表见 `references/02_template_wordlist.md`）；**机制与推演部分不得逐句挂标签**（不写「（本文数据支持的推断）」「（纯文献推演）」这类机挂标签，正常表述即可）。
6. **不改写等于没做**：本技能必须真的动手改，不能只输出一份风险报告。

## 诚实边界

- **维普、知网、万方的 AIGC 模型闭源**，本工具复刻的是其**检测维度**（句长突发性、模板化、连接词密度等），输出的是**相对风险分**，**不等于任何一家的官方数值**。
- 开源检测器**对含蓄的 AI 文本偏保守**（阳性对照里也出现过漏检），所以"得低分"是**真实但有限**的正面信号，**不能推断官方系统也给低分**。
- **定稿后必须跑目标系统的官方检测**；被标红的段落再按本手册定向改写。
- 阳性/阴性对照（`calibrate.py`）**不可省**：只有阳性对照被正确识别为高风险，检测器的低分才可信。

## 目录

- `SKILL.zh.md` / `SKILL.en.md` —— 中 / 英独立完整版
- `references/01_language_fingerprints.md` —— 中英语言特征（真人与 AI 的差异点，含真实例句）
- `references/02_template_wordlist.md` —— 中英模板词 / 套话词表
- `references/03_rewrite_playbook.md` —— 十种改写手法（每条含前→后例）
- `references/04_anti_defensive_writing.md` —— 反防御性写作（发布会原则）+ docx 定点改写流程
- `references/05_reviewer_simulation.md` —— 改写后模拟审稿自审清单
- `references/06_academic_style.md` —— 学术写作风格与知识隔离（防编造）
- `references/07_detector_logic.md` —— 查重与 AIGC 检测原理、为什么同义词替换无效
- `references/08_corpus_notes.md` —— 语料学习笔记（来源、覆盖、可复用例句）
- `references/09_citation_integrity.md` —— 引用验真与 GB/T 7714 格式
- `examples/` —— 可运行样例（中英 before/after + 检测前后数值）
