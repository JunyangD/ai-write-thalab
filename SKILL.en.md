# Reduce-AI-Rate Writing Skill — English Standalone Guide

> Read this file alone and you can run the whole pipeline: from detecting a draft, to driving its
> AIGC suspicion rate below 5%, to a pre-submission self-review. Chinese writers should read
> `SKILL.zh.md` (the other standalone guide). Entry point: `SKILL.md`.

---

## 0. What this skill is for

You have a manuscript (`.md` / `.txt` / `.docx`) and you are worried an AI-content detector will flag
it. This skill helps you:

1. **Measure** the "AI-ness" of the whole document and of each paragraph;
2. **Locate** the highest-risk paragraphs and read *why* they score high (uniform sentence length,
   formulaic phrases, connective stacking, long sentences, repeated sentence openings, comma runs);
3. **Rewrite** those paragraphs with structure-level techniques;
4. **Re-measure** and compare before/after;
5. **Iterate** until the document's AIGC suspicion rate falls below **5%**.

After rewriting, your data, citations, and conclusions are untouched.

**What it cannot do:** sanitize copied text. If the body came from unlabelled third-party text,
that is a plagiarism/integrity problem — no rewriting changes its nature.

---

## 1. One-line workflow

> **Detect → locate the highest-risk paragraphs → rewrite them by technique → re-check → loop until AIGC < 5%.**

This is a **loop**, not a single action.

| Step | Action | Tool |
|---|---|---|
| 1 Detect | Get whole-document and per-paragraph risk | `detox_pipeline.py`, `fingerprint.py`, `model_en.py` |
| 2 Locate | Read each high-risk paragraph's **main risk source** | `detox_pipeline.py` → `paragraphs[].instructions` |
| 3 Rewrite | Apply targeted edits | `references/03_rewrite_playbook.md` + `references/02_template_wordlist.md` |
| 4 Re-check | Re-run and compare before/after numbers | `detox_pipeline.py <new draft>` |
| 5 Iterate | Repeat 2–4 while below threshold | agent loop or manual |

---

## 2. Setup (once)

Run everything from the skill root directory (the folder that contains this file).

```bash
PY=<your python>

# 2.1 Download the detector (English model ~500MB, via hf-mirror)
$PY scripts/download_models.py --lang en

# 2.2 Positive/negative controls — DO NOT SKIP
$PY scripts/calibrate.py --lang en --sample examples/sample_ai_en.md
```

**Why controls matter:** if the detector is broken (scoring everything low), you would get a false
"pass". The positive control (a known AI template text) must score high; the negative control (human
text) must score low. Only when both behave correctly is a low score on your draft trustworthy.

---

## 3. Detect: get the risk ranking

### 3.1 Main pipeline (recommended)

```bash
$PY scripts/detox_pipeline.py <draft.md|txt|docx> --top 12
```

The report shows: language, paragraph count, **document fingerprint risk (0–100)**,
**document AIGC suspicion rate (model, weighted by word count)**, the highest single-paragraph P(AI),
the number of paragraphs to rewrite, the **pass/fail (<5%)** verdict, a per-paragraph risk ranking,
and targeted rewrite instructions for each flagged paragraph.

### 3.2 Machine-readable interface (for looping)

```bash
$PY scripts/detox_pipeline.py <draft> --json --no-report
```
`stdout` is pure JSON. Key fields:

| Field | Meaning |
|---|---|
| `passed` | Whether the draft passes (<5%). `null` if the model is unavailable (**never falsely reports a pass**) |
| `doc_suspected_rate` | Document AIGC suspicion rate (model path, 0–1) |
| `doc_fingerprint_score` | Document fingerprint risk (0–100) |
| `rewrite_targets` | Indices of paragraphs to rewrite |
| `paragraphs[].instructions` | Actionable rewrite instructions per paragraph |
| `paragraphs[].fp_sources` | Each paragraph's main risk sources |
| `need_rewrite` | Whether more rewriting is needed |

### 3.3 Single-path runs

```bash
$PY scripts/fingerprint.py <draft> --lang auto --top 12     # rule-based fingerprint (zero-dependency, seconds)
$PY scripts/model_en.py   <draft> --top 15                  # English model (needs weights)
```

> `--no-model` runs the fingerprint only (fast, but **cannot** give a <5% verdict; `passed=null`).

---

## 4. Locate: read the risk sources

Each "main risk source" maps to one disease and one cure:

| Risk source | The problem | Technique (`03`) |
|---|---|---|
| Sentence-length uniformity | Every sentence is the same length | 6 vary sentence length; 1 split sentences |
| Long-sentence ratio | Nested clauses, long modifiers | 1 split sentences |
| Template-phrase density | Formulaic openings/closings | 4 delete template phrases |
| Connective density | "Moreover / furthermore / therefore" stacked | 4 delete template phrases |
| Sentence-opening repetition | Every sentence follows one mould | 2 rotate subjects |
| Comma ratio | One comma run to the end | 1 split; use periods/semicolons |
| Lexical richness | Mechanical word repetition | 8 make precise; use concrete nouns |

**Per-paragraph trigger:** model P(AI) ≥ 50% **or** combined risk ≥ 40
(combined = 0.5 × fingerprint + 0.5 × model × 100).

---

## 5. Rewrite by technique

Full playbook: `references/03_rewrite_playbook.md`. The ten techniques, in brief:

1. **Split sentences** — one idea per sentence;
2. **Rotate subjects** — at least two subjects per paragraph;
3. **Add scope** — give each claim a checkable boundary ("as of the search date", "under this manuscript's criteria");
4. **Delete template phrases** — see `references/02_template_wordlist.md`;
5. **Cut grand claims** — reduce rhetorical assertions to checkable statements;
6. **Vary sentence length** — break the uniform plateau;
7. **Remove self-labelling** — do not tag every inference ("inference supported by our data"); state it plainly;
8. **Be precise** — replace hedges ("most", "possibly") with numbers or ranges;
9. **Remove repetition and tautology**;
10. **De-duplicate headings** — turn them into question- or mechanism-chain forms.

### English template phrases to delete (full list of 40 in `02` §2)

- **Ban / avoid:** "it is worth noting that", "in conclusion", "moreover", "furthermore" (stacked),
  "in addition" (stacked), "plays a crucial role", "provides a foundation for", "sheds light on",
  "in the realm of", "a growing body of literature", "This field is growing rapidly",
  "remains a clear gap", "has attracted increasing attention", "with the rapid development of",
  "it can be seen that".
- **Weaken / replace:** "significantly" (without statistics), "to some extent", "it is important to",
  "it should be noted that", "needless to say", "as we all know", "in recent years" (→ give the year),
  "a large number of" (→ many / give a number), "due to the fact that" (→ because),
  "in order to" (→ to), "has the ability to" (→ can), "with regard to" (→ regarding),
  "in spite of the fact that" (→ despite), "the vast majority of" (→ give a number),
  "taken together", "overall", "in summary".

> **From the corpus (20 thalassemia papers):** "In conclusion," appears **0 times**; conclusions end
> with **"These findings suggest…"**. Transition density is low (However ×2, Furthermore ×2, In addition ×2).

### Before → after (English)

| ❌ Formulaic | ✅ Idiomatic |
|---|---|
| This field is growing rapidly, and it is worth noting that ferro-aging remains a clear gap. | Ferro-aging is a recent label: within the 2015–2026 window, only 39–40 co-word-linked papers appear, and none fall in the TDT–ferroaging intersection. |
| In conclusion, more studies are recommended, and international collaboration should be strengthened. | Priority should go to mechanistic work on iron overload–lipid peroxidation–cellular senescence and to validation in aging TDT cohorts in high-prevalence regions. |
| It is worth noting that ferroptosis plays a crucial role in the pathophysiology of thalassemia. | Non-transferrin-bound iron and the labile iron pool drive redox-active iron deposition in transfusion-dependent thalassemia. |

### Idiomatic English rules

1. **Do not translate the Chinese abstract sentence by sentence.** Restructure into an English flow:
   problem → evidence → interpretation → close.
2. **Vary sentence length.** Avoid the 25–35-word plateau.
3. **Avoid formulaic phrases** (above).
4. **Make the ending specific** — name the concrete priority, cohort, or mechanism.
5. **Voice:** passive for Methods, active for findings. Follow evidence-hierarchy conventions for medicine/health.
6. **Add no new citations, data, or conclusions**; numbers and conclusions must match the source draft.

---

## 6. Re-check and iterate

```bash
# save the rewrite as a new file, then re-run
$PY scripts/detox_pipeline.py <new draft> --top 12
```

- **Pass:** `passed=true` (document suspicion rate < 5%) → go to §8 self-review.
- **Fail:** read the new `rewrite_targets` and `instructions`; return to §5.
- **Round cap:** set 3–4 rounds. If still failing at the cap, **report the un-met items honestly** — never claim a false pass.

### Optional autonomous loop

```bash
$PY scripts/detox_pipeline.py <draft> --iterate 3 --rewriter "<cmd template {in} {out}>"
```
The pipeline calls your rewriter after each detected round. **The tool does not ship a rewriter**
(rewriting is the upstream LLM's job); `--rewriter` must be supplied. Without it, each round hands control back to the caller.

---

## 7. Absolute prohibitions (red lines — re-check every round)

1. **Do not change facts:** data, years, percentages, PMIDs, DOIs, authors, institutions, search strings, figure/table numbers, or the direction of conclusions.
2. **Do not add content:** no new references, data, mechanisms, countries, institutions, or conclusions; no fabricated citations.
3. **Do not swap terminology** for non-technical words (thalassemia, iron overload, ferroptosis, ACSL4, GPX4, hepcidin, TDT, NTBI must stay intact).
4. **Citation format:** end a claim sentence with `（pmid：XXXXXXX）` inside **red font (RGB C00000)** with the **period outside the parentheses**; every PMID must be verified against NCBI esummary by reading the record back — **never fabricate** (see `references/09_citation_integrity.md`).
5. **Remove AI traces:** delete template phrases; **do not tag every sentence of a mechanism/inference passage with a label** — state it plainly.
6. **Not rewriting = not done:** the skill must actually perform edits, not just emit a risk report.

### Data-preservation check (do this after every rewrite)
Compare before/after item by item: numbers, years, percentages, PMIDs, DOIs, figure/table numbers,
technical terms. Any mismatch → roll back and re-edit.

---

## 8. Post-rewrite self-review (pre-submission)

A lower score does not mean a better paper. Work through `references/05_reviewer_simulation.md`. Confirm above all:

- every "assertion → data statement" edit **supplied a concrete number or scope**, not just deleted the assertion;
- logic between split sentences still holds;
- **no new defensive hedging** was introduced ("this study does not claim…");
- **methodological limitations are preserved** (only repetition and pre-emptive self-criticism were removed);
- the argument chain question → method → findings → implications is complete and traceable;
- the problem and the contribution both appear in the first five sentences of the abstract.

---

## 9. Honest boundaries (must know)

- **The AIGC models from VIP, CNKI, and Wanfang are closed-source.** This tool reproduces their
  **detection dimensions** and outputs a **relative risk score**; it **does not equal any vendor's official number**.
- **Open-source detectors are conservative on subtle AI text** (they miss some positives in the control set).
  A low score is a **real but limited** positive signal. For English, model readings can be much lower than
  intuition — in that case the fingerprint's per-dimension breakdown is more informative.
- **Run the target system's official detection before submission**; then re-edit any paragraph it flags.
- **Run `calibrate.py`** before submission and keep the positive/negative control results on file.

---

## 10. Contents and further reading

- `references/01_language_fingerprints.md` — ZH/EN language features (human vs AI, with real examples)
- `references/02_template_wordlist.md` — ZH/EN template word lists (62 ZH + 40 EN)
- `references/03_rewrite_playbook.md` — ten rewrite techniques (each with before→after)
- `references/04_anti_defensive_writing.md` — anti-defensive writing + .docx point edits
- `references/05_reviewer_simulation.md` — post-rewrite self-review checklist
- `references/06_academic_style.md` — academic style and knowledge isolation (against fabrication)
- `references/07_detector_logic.md` — plagiarism vs AIGC detection; why synonym swaps fail
- `references/08_corpus_notes.md` — corpus learning notes
- `references/09_citation_integrity.md` — citation verification and GB/T 7714
- `examples/` — runnable examples (ZH/EN before/after with measured numbers)
