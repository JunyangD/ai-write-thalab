# 02 模板词 / 套话词表（中英双语）

> **给谁看**：所有要改写的人。这是**查删表**——全文扫描，命中的词改成具体陈述或删除。
> **配套**：改法见 `03_rewrite_playbook.md`；语言特征见 `01_language_fingerprints.md`；检测原理见 `07_detector_logic.md`。
> **纪律**：模板词不是「见到就无脑删」——C 组（语境敏感）该留则留，但**同一稿内不得连用**。
> 词表规模：**中文 62 条 + 英文 40 条**。

---

## 0. 三条总原则

1. **改写只动「怎么说」，不动「说什么」。** 数据、年份、百分比、PMID、DOI、作者、机构、检索式、图表编号、结论方向——一律不动。
2. **判断句换数据陈述，模板句换限定陈述。** 拿掉大判断，补上数或限定语（「从检索结果看 / 就本稿数据而言 / 截至检索日 / 在本稿口径下」）。
3. **句法层面制造差异：拆句、换主语、变句长。** 这是对抗困惑度 / 突发性检测的**唯一有效层**——同义词替换无效（见 `07` §4）。

---

## 1. 中文模板词 / 套话词表（62 条）

### A 组｜收束 / 引导类：直接删或改写（26 条）

`综上所述`；`总而言之`；`总的来说`；`总体而言`；`值得注意的是`；`值得一提`；`需要指出的是`；`不可忽视（的是）`；`不容忽视`；`毋庸置疑`；`众所周知`；`诚然`；`换言之`；`简而言之`；`概而言之`；`如上所述`；`由此可见`；`由此可以看出`；`基于以上分析`；`综上`；`总之`；`一方面…另一方面…`；`不仅…而且…`；`既…又…`；`为…提供参考`；`具有重要价值 / 重要意义`。

### B 组｜万能判断 / 宏大词：换具体值（20 条）

`这一空白正是（高回报前沿）`；`高回报前沿`；`填补空白`；`本研究具有重要价值`；`提供了新视角`；`具有指导意义`；`意义重大`；`至关重要`；`核心特征`；`（本领域的）发展趋势`；`研究热点`（泛用）；`赋能`；`抓手`；`闭环`；`范式`；`路径`（泛用）；`维度`（泛用）；`层面`（泛用）；`生态`（泛用）。

### C 组｜程度 / 频率 / 连接虚词：语境敏感（16 条）

`进一步`；`显著`（无统计支撑时禁用）；`极大地`；`大幅`；`一定程度上`；`或多或少`；`在某种程度上`；`较为`；`相对而言`；`与此同时`；`此外`（连用时）；`首先 / 其次 / 最后`（机械排序）；`再者`。

> **C 组纪律**：
> - `显著` 在**没有统计量 / p 值**时禁用——「显著高于」必须给 p 或区间；
> - `首先 / 其次 / 最后` 整组换成因果、转折、递进、对比的自然连接；
> - 「存在一定的局限」这类**方法学限制句可以保留**（真人 32/63 篇都写），但不要变成空泛的「仍需进一步研究」。

### 与语料实测的对照（T1，观察）

| 词 | 真人 63 篇频次 | 处置 |
|---|---|---|
| 然而 | 78 | ✅ 中文转折首选 |
| 但是 | 14 | ⚠️ 尽量换「然而」 |
| 此外 / 同时 / 因此 | 136 / 151 / 126 | ⚠️ 每段 ≤1 个 |
| 综上 / 综上所述 | 43 + 30 | ✅ 收束可用 |
| 总而言之 | **0** | ❌ 不用 |
| 值得注意的是 | 15 | ⚠️ 全文合计才 15 次，别每段一次 |

---

## 2. 英文模板词 / formulaic phrases 词表（40 条）

### A 组｜禁用 / 慎用（16 条）

"it is worth noting that"；"in conclusion"；"moreover"；"furthermore"（连用）；"in addition"（连用）；"plays a crucial role"；"provides a foundation for"；"sheds light on"；"in the realm of"；"a growing body of literature"；"This field is growing rapidly"；"remains a clear gap"；"are recommended"；"has attracted increasing attention"；"with the rapid development of"；"it can be seen that"。

### B 组｜弱化 / 替换候选（24 条，按需）

"significantly"（无统计支撑时）；"to some extent"；"to a certain degree"；"it is important to"；"it should be noted that"；"needless to say"；"as we all know"；"in recent years"（→ 给具体年份）；"a large number of"（→ many，或给数）；"due to the fact that"（→ because）；"in order to"（→ to）；"at the present time"（→ currently）；"has the ability to"（→ can）；"with regard to"（→ regarding）；"in spite of the fact that"（→ despite）；"conduct an investigation of"（→ investigate）；"the vast majority of"（→ 给数）；"results show that"（过度泛用时）；"taken together"；"overall"；"in summary"；"the present study"（泛用）；"novel"（无对照时）；"comprehensive"（泛用）。

> 英文结论收尾：用 **"These findings suggest…"**，不要用 "In conclusion,"（20 篇语料里 0 次）。

### 英文 Wordy → Concise 速查（通用学术英文公认项）

| Wordy | Concise |
|---|---|
| in order to | to |
| due to the fact that | because |
| a large number of | many / 给数 |
| at the present time | currently / now |
| it is important to note that | notably |
| in the event that | if |
| has the ability to | can |
| with regard to | regarding / about |
| in spite of the fact that | despite / although |
| conduct an investigation of | investigate |

---

## 3. ⚠️ 口径分歧：中文摘要要不要「结构化标签」

转录自 T3 规则手册，**转规则前必须裁断**，别单方面执行：

- **语料观察**：中文语料 **81%（51/63）** 用「目的 / 方法 / 结果 / 结论」结构化摘要；学报网站版为「目的 探讨…」（标签后**不加冒号、仅空格**）。
- **本厂老板偏好**：明确要求「**不要逐项标签化，不要写成"目的：方法：结果：结论："的模板**；可以改成半结构式或连贯段落」。
- **裁断**：两者并非完全对立——学报用「目的 探讨…」（无冒号），老板反对的是**冒号式填空模板**与**逐项割裂**。
- **落地原则**：**以目标期刊《投稿须知》为准**。投《广西医科大学学报》类中文刊 → 随刊用结构化（不加冒号）；本厂自有稿件 / 非强制结构化的刊 → 走**非标签、半结构式**。
- ⇒ **不要把「强制结构化标签」写成硬规则**，写成「按目标期刊体裁二选一」，并保留老板的非标签偏好。

---

## 4. 交稿前自检（可脚本化）

1. **模板词零残留**：对 §1 A/B 组 + §2 A 组做全文 grep，命中数应为 0（C 组按语境人工判）。
2. **判断句扫描**：查「仍是空白 / 属高热度前沿 / 具有重要意义 / 提供了新视角」，命中即改数据陈述。
3. **标签扫描**：查「（本文数据支持的推断）/（纯文献推演）/ 待检验假说 / 不宣称 / 须特别声明」，命中即删（老板原话："不要标注这些乱七八糟的东西，正常表述"）。
4. **句式扫描**：查「首先…其次…最后」「不仅…而且」「一方面…另一方面」是否连用 / 堆叠。
5. **数据保全**：逐项对照原文数字 / 年份 / 百分比 / PMID / DOI，标出不一致处。
6. **引用格式**：统计全文 `（pmid：` 次数，逐条确认红色 `C00000`、句号在括号外（见 `09_citation_integrity.md`）。
7. **重复检测**：规范化后查完全重复段 + 前缀包含对（专抓「追加」型残留）。

> 自检脚本报「通过」不可信——必须索取**扫描范围 + 命中明细**。
