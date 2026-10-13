# 09 引用完整性：验真 + 格式

> **给谁看**：写参考文献、改引用的人。集成本厂既有能力——`pubmed-verifier`（引用验真与 AI 幻觉检测）
> 与 `citation-management`（GB/T 7714 等格式）的长处，落成本技能的红线。
> **一句话**：**引用是唯一"改了就是学术不端"的东西**——降 AI 率可以改句式，但绝不能碰引用。

---

## 1. 引用格式硬规范（本厂，写文献时必须遵守）

> **本节及下文出现的所有 PMID 均为格式示例，非真实引用**（如 31018962），仅用于演示标点与字体规范。

1. **观点句末标 PMID**，写作 `（pmid：XXXXXXX）`。
2. **中文全角括号 + 全角冒号 + 半角数字**。例：正确 `（pmid：31018962）`；错误 `(pmid:31018962)`、`（pmid:31018962）`。
3. **句号在括号之外**。例：`……这一机制已被证实（pmid：31018962）。` 而不是 `……（pmid：31018962.）`。
4. **红色字体（RGB `C00000`）**。未设红色一律不合格。
5. **限 PubMed 近 5 年**；奠基性文献可延长年限，须注明。
6. **多篇并列**：同一括号内用中文分号分隔，如 `（pmid：31018962；pmid：22213727）`。
7. **禁止虚构**：每条须经 NCBI esummary **逐条回读核验**——**存在性检查不够**，真实 PMID 也可能指向错误论文。
8. 期刊投稿稿若要求上标 `[n]`：正文改用上标，**参考文献表内保留 `（pmid：…）` 备核**。

> 交付前自检：统计全文 `（pmid：` 次数 → 逐条确认红色 `C00000`、句号在括号外、
> 与参考文献表条数一致。非红者必须修正。

---

## 2. 为什么"存在性检查"不够（AI 幻觉最常见形态）

**相当大一部分编造引用用的是真实存在的 PMID**，只是指向同年份 / 同期刊 / 同领域的**另一篇**论文。
我们自己的一次审计里，5 条"有效"PMID 就有 4 条属于此类。**二元存在性检查对它们全部漏检。**

### 五态判定（`pubmed-verifier`）

| 判定 | 含义 | 退出码 |
|---|---|---|
| ✅ 正确 | PMID 存在，且与引用论文匹配（标题 + 作者 / 期刊） | 0 |
| ⚠️ 不匹配 | PMID 存在，但指向**不同的**论文 | 1 |
| 🔶 部分匹配 | 部分元数据匹配（如作者 + 期刊匹配但标题不同）；或数据不足 | 1 |
| ❌ 无效 | PubMed 中不存在此 PMID | 1 |
| ❓ 待确认 | 元数据不足无法比对；**或数据源不可达**（网络故障诚实标注，绝不误报"不存在"） | 2 |

> **unknown ≠ invalid**：数据源不可达就报"待确认 + 退出码 2"，绝不静默报"查无"。

### 交叉比对怎么判
- 标题：词级 Jaccard 重叠 ≥ 50% 或 SequenceMatcher ≥ 90%；
- 作者：姓氏命中；**单字母缩写不参与匹配**；**跨语言作者名（中文↔拉丁）诚实跳过**；
- 期刊：包含匹配或 NLM 缩写等价（"N Engl J Med" ≈ "New England Journal of Medicine"）；
- 年份：精确匹配；
- **撤稿检测**：注册库出版物类型为 "Retracted Publication" 的，判定**封顶为部分匹配**并提示人工复核（撤稿声明本身不会被误标）。

---

## 3. 怎么跑验真（`pubmed-verifier`）

工具位于 `~/.workbuddy/skills/pubmed-verifier/scripts/verify_pmids.py`（纯标准库，零依赖）。

```bash
# 1) 直接验证若干 PMID
python3 scripts/verify_pmids.py --pmids 31018962,22213727

# 2) 核验纯文本参考文献表（论文草稿粘贴即逐条核验）
python3 scripts/verify_pmids.py --parse-text refs.txt --no-cache

# 3) 提供期望标题做真核验（强烈建议：不给 title 判定封顶 partial）
python3 scripts/verify_pmids.py --claims '[{"pmid":"34078778","title":"JIA pathogenesis","authors":["Zaripova"],"year":"2021"}]' --output report.html

# 4) 网络预检（先看数据源可不可达）
python3 scripts/verify_pmids.py --check-net

# 5) 导出投稿自查包（审计底稿 + HTML 报告 + 文献表）
python3 scripts/verify_pmids.py --report-bundle ./audit_pack --parse-text refs.txt --no-cache
```

**从 Python 调用**（便于接进本技能的自动化）：
```python
import sys
sys.path.insert(0, "/path/to/pubmed-verifier/scripts")
import verify_pmids as vp
info = vp.fetch_summaries(["31018962"], batch_size=1)["31018962"]
cross = vp.cross_check_citation(
    {"claimed_title": "...", "claimed_year": "2019"},
    {"title": info["title"], "authors": info["authors"],
     "journal": info["journal"], "pubdate": info["pubdate"]})
print(cross["verdict"], round(cross["confidence"], 2))
```

**四条限制**（都带规避动作）：

| 限制 | 规避 |
|---|---|
| 引用上下文解析是启发式（奇特排版可能切错） | 需要精确元数据用 `--claims-file` |
| 无 PMID/DOI 标记的中文参考文献解析弱 | `--parse-text`（OpenAlex 中文检索腿）或提供 ID |
| 网络故障如实报"未判定" | 先 `--check-net`，网络可达后重试 |
| 撤稿 / DOI 状态以缓存时刻为准（30 天） | 投稿终验加 `--no-cache` |

---

## 4. 参考文献格式化（GB/T 7714 等）

`pubmed-verifier` 的 `--format-references` 支持四种格式，**先验证后排版，只排已验真的条目**：

```bash
python3 scripts/verify_pmids.py --parse-text refs.txt \
  --format-references refs_gbt.txt --citation-style gbt
```

| `--citation-style` | 格式 |
|---|---|
| `gbt`（默认） | GB/T 7714-2015 顺序编码制 |
| `gbty` | GB/T 7714-2015 著者-出版年制（无编号、无 [J] 标识、按第一作者排序） |
| `vancouver` | Vancouver |
| `apa` | APA 第 7 版 |
| `ama` | AMA 第 11 版 |

**纪律**：correct 条目进正文表；partial 条目进「需人工复核」段（**绝不静默丢弃**）；
撤稿条目排除并附警告。作者列表按风格排版且**不编造姓名**——注册库截断的列表按该风格的 et-al 惯例收尾。

**GB/T 7714-2015 顺序编码制**（中文期刊 / 学位论文常用）示例形态：
```
[1] 作者. 题名[J]. 刊名, 年, 卷(期): 起-止页. 
```
> 注：专著 `[M]`、报告 `[R]`、学位论文 `[D]` 不提取刊名（避免把出版社当刊名）；仅 `[J]` 提取刊名。

---

## 5. 接进降 AI 率循环

改写会碰句子结构，但**引用必须原样保留**。因此：

1. **改写前**：把全部 `（pmid：…）`、DOI、参考文献表**锁定**（改前 / 改后逐条 diff）。
2. **改写中**：删模板词时，**不要删掉句末的引用**（引用是观点句的落点）。若某句被整句删除，须确认它承载的引用已在别处保留或移置。
3. **改写后**：
   - 统计 `（pmid：` 次数，与改前一致（除非有正当的增删）；
   - 跑 `pubmed-verifier` 核验每条（`--parse-text refs.txt --no-cache`）；
   - 确认红色 `C00000`、句号在括号外、全角括号 + 全角冒号。

> **红线**：**不新增未提供的文献；不编造引用；核验不通过的引用一律剔除，而不是"看起来对"就留下。**

---

## 6. 一页速查

| 检查项 | 通过标准 | 工具 |
|---|---|---|
| PMID 真实存在且指向正确论文 | 五态判定为 ✅ 正确 | `pubmed-verifier --parse-text --no-cache` |
| 引用格式 | `（pmid：N）` 全角、红色 C00000、句号在括号外 | 人工 + grep |
| 引用数量 | 正文 `（pmid：` 次数 = 参考文献条数 | 计数比对 |
| 撤稿 | 无 RETRACTED 条目（或已换引） | `pubmed-verifier --verify-doi` |
| 格式统一 | 目标期刊要求（GB/T 7714 / Vancouver / APA / AMA） | `--format-references` |
| 审计可复放 | 有审计底稿 | `--report-bundle` |
