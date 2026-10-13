# examples —— 可运行样例（中英 before / after 对照）

> 这里的每一份文件都能直接喂给 `scripts/detox_pipeline.py`。所有数值都是**在本包内实测**的
> （Python 3.13 + torch CPU），命令见下。数值只代表**开源近似检测器**，**不等于维普 / 知网官方数值**。

## 文件

| 文件 | 说明 |
|---|---|
| `sample_ai_zh.md` | 中文 · **改写前**（AI 味浓，模板词成串、连接词密、一逗到底） |
| `sample_ai_zh.rewritten.md` | 中文 · **改写后**（按 `references/03_rewrite_playbook.md` 定向改写） |
| `sample_ai_en.md` | English · **before**（formulaic phrases、句长均匀） |
| `sample_ai_en.rewritten.md` | English · **after**（idiomatic，长短句交替） |
| `sample_zh.md` / `sample_en.md` / `sample.docx` | T2 提供的原始样例（一份更接近成稿的长稿） |

## 实测前后数值

### 中文（`sample_ai_zh.md` → `sample_ai_zh.rewritten.md`）

| 指标 | 改前 | 改后 |
|---|---|---|
| 规则指纹风险分 | **54.5 / 100（高）** | **24.8 / 100（低）** |
| 全文 AIGC 疑似率（模型 · 字数加权） | **70.37%** | **0.00%** |
| P(AI) ≥ 50% 的段落 | **1 段** | **0 段** |
| 判定 | ≥25% 高危 | 低于 5% ✓ |

改前每段主要风险来源（指纹）：
- 段 1：模板词密度 100、连接词密度 100、逗号占比 62；
- 段 2：模板词密度 100、连接词密度 100、句长均匀度 66。

### English（`sample_ai_en.md` → `sample_ai_en.rewritten.md`）

| 指标 | before | after |
|---|---|---|
| 规则指纹风险分 | **50.5 / 100（高）** | **25.1 / 100（低）** |
| 全文 AIGC 疑似率（模型 · 词数加权） | **9.36%** | **0.03%** |
| P(AI) ≥ 50% 的段落 | 0 段 | 0 段 |
| 判定 | 5~25% 需关注 | 低于 5% ✓ |

改前每段主要风险来源（指纹）：段 1 模板词密度 100、连接词密度 100、句长均匀度 57；段 2 模板词密度 100、连接词密度 84、句长均匀度 73。

> **一个必须知道的诚实观察**：英文改写前的模型疑似率只有 **9.36%**，**低于 25% 的"高危线"**，
> 而规则指纹给了 **50.5 / 100（高）**。这不是矛盾——它正说明**开源检测器对英文 AI 文本偏保守**
> （见 `references/07_detector_logic.md` §3.4）。所以定位问题时，规则指纹的**逐维分解**比模型单一读数更有用；
> 而模型的低分**不能**推断官方系统也给低分。

## 复现命令

```bash
# 先在技能包根目录下
PY=<你的 python>

# 1) 规则指纹（零依赖，秒级）
$PY scripts/fingerprint.py examples/sample_ai_zh.md --top 3
$PY scripts/fingerprint.py examples/sample_ai_en.md --top 3

# 2) 模型通路（需先 python scripts/download_models.py）
$PY scripts/detox_pipeline.py examples/sample_ai_zh.md --top 3
$PY scripts/detox_pipeline.py examples/sample_ai_en.md --top 3

# 3) 阳性/阴性对照（证明检测器在工作）
$PY scripts/calibrate.py --lang all --sample examples/sample_ai_zh.md
```

## 改写用了哪些手法（对照 `references/03_rewrite_playbook.md`）

以中文为例，从"改前"到"改后"主要做了四件事：

1. **手法 4 删模板词**：删掉「随着…的快速发展」「值得注意的是」「不仅…而且」「综上所述」「总而言之」「本文旨在」「首先/其次/最后」。
2. **手法 1 拆句 + 手法 6 长短句交替**：把「随着…的不断深入，可以预见，该领域必将迎来更加广阔的发展前景」这类长复句整段删除，换成短陈述句与中长句交替。
3. **手法 5 去金句**：把「具有十分重要的理论意义和现实价值」换成可核对的事实（携带率 23.89%、交集文献 0 篇）。
4. **手法 3 加限定**：把无边判断收进边界（「截至检索日，PubMed 中…为 0 篇」）。

英文同理：删 "It is worth noting that / plays a crucial role / Moreover / In conclusion / Taken together"，
把 "in recent years" 换成具体年份，把 "great importance" 换成可核对的事实。

> ⚠️ 样例中出现的 `（pmid：N）` **是格式示例，不是真实引用**。
> 真实写作时，PMID 必须经 NCBI esummary 逐条回读核验（见 `references/09_citation_integrity.md`）。
