# -*- coding: utf-8 -*-
"""
calibrate.py —— 检测器阳性/阴性对照实验（中英双语）
================================================================================
目的：证明检测器**没坏**、并量化它对不同风格文本的灵敏度边界。

逻辑（保留原 AIGC模型校准.py 的思路并扩展到双语 + 指纹）：
  * 阳性对照（AI 风格文本）—— 期望 P(AI) 高 / 指纹风险分高
  * 阴性对照（人工写作文本）—— 期望 P(AI) 低 / 指纹风险分低
  对照组里若出现「漏检」，如实标注（这正是报告可信度的一部分：
  说明检测器对含蓄 AI 文本偏保守，因此稿件得低分是一个**真实但有限**的正面信号）。

对每组分别跑：
  1) 规则指纹风险分（零依赖，必定可跑）
  2) 开源模型 P(AI)（若权重存在；缺权重时跳过并提示下载命令）

用法：
  python calibrate.py                      # 中英双语对照
  python calibrate.py --lang zh            # 只跑中文
  python calibrate.py --sample <稿件>      # 额外对真实稿件抽样（可选）
  python calibrate.py --json               # 结构化输出
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import safe_mean, load_text, strip_markdown, split_paragraphs, pretty_banner  # noqa: E402
from fingerprint import analyze_paragraph, risk_score  # noqa: E402

# ==========================================================================
# 对照组文本
# ==========================================================================
POS_ZH = [  # 典型 AI 生成风格（模板化、句式规整、连接词密集）
    "随着人工智能技术的快速发展，其在医学领域的应用日益广泛。值得注意的是，人工智能不仅可以提高诊断的准确性，而且能够显著提升医疗服务的效率。综上所述，人工智能为现代医学带来了前所未有的机遇与挑战。",
    "地中海贫血是一种严重的遗传性血液疾病，给患者及其家庭带来了沉重的负担。近年来，越来越多的研究表明，铁过载在该病的发生发展中起着至关重要的作用。因此，深入探讨其机制具有重要的临床意义。",
    "本文旨在系统梳理地中海贫血与铁代谢之间的关联。首先，我们介绍了地中海贫血的基本概念；其次，分析了铁过载的病理机制；最后，探讨了潜在的干预策略。总而言之，本研究为进一步的临床实践提供了有力支撑。",
]
NEG_ZH = [  # 人工写作风格（口语化、不等长、具体、不规整）
    "我们科去年收了 17 个地贫患儿，最大 14 岁，最小才 3 岁出头。家长最常问的一句话是「还要输多久」。说实话，这个问题很难答。有个孩子从 4 岁开始输，现在上初中了，肝功能一直不太好，铁蛋白常年 3000 以上。",
    "第一次看到那组数据时我有点意外：地贫合并铁死亡的文献只有 20 篇。本来以为会多一些。后来想想也合理——大家还是盯着输血和去铁，真正去做机制的团队本来就少，做地贫的更少。",
    "广西这边地贫携带率很高，大概每五个人里就有一个。所以临床上见得特别多。但真正让人头疼的不是贫血本身，是那些四十岁以后的病人，心脏、内分泌、骨头，一个接一个出问题。",
]

POS_EN = [  # typical AI-generated academic English
    "It is worth noting that artificial intelligence plays an important role in modern medicine. Moreover, it significantly improves diagnostic accuracy and enhances healthcare efficiency. In conclusion, artificial intelligence brings unprecedented opportunities and challenges to clinical practice.",
    "Thalassemia is a severe inherited blood disorder that imposes a substantial burden on patients. In recent years, a growing body of research has demonstrated that iron overload plays a crucial role in its pathogenesis. Therefore, delving into the underlying mechanisms is of great significance.",
    "This study aims to comprehensively analyze the association between thalassemia and iron metabolism. Firstly, we introduce the basic concepts; secondly, we analyze the pathological mechanisms; finally, we discuss potential interventions. Overall, this research provides strong support for future clinical practice.",
]
NEG_EN = [  # human academic / narrative English (uneven, concrete)
    "We followed 17 thalassemia children in our ward last year. The youngest was barely three; the oldest had just turned fourteen. Parents kept asking the same question: how much longer do we have to keep transfusing? Honestly, I never had a good answer.",
    "I was a bit surprised when the first count came back: only 20 papers on thalassemia with ferroptosis. I had expected more. On reflection it makes sense. Most groups still focus on transfusion and chelation, and the few doing real mechanistic work rarely pick thalassemia.",
    "Carrier rates run high in Guangxi, roughly one in five people. So we see a lot of it clinically. What actually wears you down is not the anemia itself but what happens after forty: the heart, the endocrine glands, the bones, one problem after another.",
]

CONTROLS = {"zh": (POS_ZH, NEG_ZH), "en": (POS_EN, NEG_EN)}


# --------------------------------------------------------------------------
def fp_score(text: str, lang: str) -> float | None:
    """规则指纹风险分（单段）。"""
    m = analyze_paragraph(text, lang)
    if not m:
        return None
    s, _ = risk_score(m, lang)
    return round(s, 1)


_DETECTOR_CACHE: dict = {}


def _get_scorer(lang: str):
    """加载并缓存语种对应的打分函数；缺权重返回 (None, 提示)。"""
    if lang in _DETECTOR_CACHE:
        return _DETECTOR_CACHE[lang]
    try:
        from model_common import load_detector, resolve_model_dir, _score_chunks
        md = resolve_model_dir(lang, None)
        tok, model, id2label, ai_idx = load_detector(lang, md)

        def scorer(texts):
            return [round(_score_chunks(tok, model, ai_idx, t) * 100, 2) for t in texts]

        _DETECTOR_CACHE[lang] = (scorer, None)
    except FileNotFoundError as e:
        _DETECTOR_CACHE[lang] = (None, str(e))
    except Exception as e:  # 环境缺 torch 等
        _DETECTOR_CACHE[lang] = (None, f"模型通路不可用：{e}")
    return _DETECTOR_CACHE[lang]


def model_scores(texts: list[str], lang: str):
    """用（缓存的）模型逐条打分；缺权重返回 (None, 提示)。"""
    scorer, err = _get_scorer(lang)
    if scorer is None:
        return None, err
    return scorer(texts), None


def run_lang(lang: str, use_model: bool = True) -> dict:
    pos, neg = CONTROLS[lang]
    print(pretty_banner(f"阳性 / 阴性对照 —— {lang.upper()} 通路"))
    out = {"lang": lang, "pos": [], "neg": [], "model_available": False}

    # 指纹
    print("\n[1] 规则指纹风险分（0–100，越高越像 AI）")
    for tag, group in (("正", pos), ("负", neg)):
        for i, t in enumerate(group, 1):
            s = fp_score(t, lang)
            print(f"  {tag}{i:02d}  指纹风险={('%.1f' % s) if s is not None else '  n/a'}   {t[:36]}…")
            out["pos" if tag == "正" else "neg"].append({"fp": s})

    # 模型
    mpos = mneg = None
    if use_model:
        print("\n[2] 开源模型 P(AI)（百分比，越高越像 AI）")
        mpos, err = model_scores(pos, lang)
        if mpos is None:
            print("  " + (err or "").replace("\n", "\n  "))
        else:
            out["model_available"] = True
            mneg, _ = model_scores(neg, lang)
            for i, s in enumerate(mpos, 1):
                print(f"  正{i:02d}  P(AI)={s:6.2f}%   {pos[i - 1][:36]}…")
            print("  ---")
            for i, s in enumerate(mneg, 1):
                print(f"  负{i:02d}  P(AI)={s:6.2f}%   {neg[i - 1][:36]}…")

    # 汇总
    fp_pos = [x["fp"] for x in out["pos"]]
    fp_neg = [x["fp"] for x in out["neg"]]
    print("\n[汇总]")
    print(f"  指纹  阳性均值 {safe_mean(fp_pos):.1f}  vs  阴性均值 {safe_mean(fp_neg):.1f}")
    out["fp_pos_mean"] = round(safe_mean(fp_pos), 1)
    out["fp_neg_mean"] = round(safe_mean(fp_neg), 1)
    if mpos is not None:
        print(f"  模型  阳性均值 {safe_mean(mpos):.2f}%  vs  阴性均值 {safe_mean(mneg):.2f}%")
        out["model_pos_mean"] = round(safe_mean(mpos), 2)
        out["model_neg_mean"] = round(safe_mean(mneg), 2)
        for i, s in enumerate(mpos, 1):
            out["pos"][i - 1]["model"] = s
        for i, s in enumerate(mneg, 1):
            out["neg"][i - 1]["model"] = s
    return out


def sample_manuscript(path: str, lang: str | None = None, use_model: bool = True) -> dict:
    """对真实稿件抽样（默认取指纹风险最高的若干段）。"""
    from utils import detect_lang
    text = load_text(path)
    if lang in (None, "auto"):
        lang = detect_lang(text)
    clean = strip_markdown(text)
    paras = split_paragraphs(clean, lang)
    print(pretty_banner(f"真实稿件抽样 —— {Path(path).name}（{lang}）"))
    scored = []
    for p in paras:
        s = fp_score(p, lang)
        if s is not None:
            scored.append((s, p))
    scored.sort(key=lambda z: -z[0])
    print(f"  段落 {len(scored)} 段，指纹均值 {safe_mean([s for s, _ in scored]):.1f}")
    if use_model and scored:
        ms, err = model_scores([p for _, p in scored[:8]], lang)
        if ms is None:
            print("  " + (err or "").replace("\n", "\n  "))
        else:
            for (s, p), m in zip(scored[:8], ms):
                print(f"  指纹={s:5.1f}  P(AI)={m:6.2f}%   {p[:40]}…")
    return {"n": len(scored), "fp_mean": round(safe_mean([s for s, _ in scored]), 1)}


def build_argparser():
    ap = argparse.ArgumentParser(
        description="检测器阳性/阴性对照（中英双语），证明检测器未失效并量化其灵敏度边界。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--lang", choices=["zh", "en", "all"], default="all", help="对照语种（默认 all）")
    ap.add_argument("--no-model", action="store_true", help="只跑指纹，不加载模型")
    ap.add_argument("--sample", default=None, help="额外对真实稿件抽样")
    ap.add_argument("--json", action="store_true", help="结构化输出")
    return ap


def main(argv=None):
    args = build_argparser().parse_args(argv)
    langs = ["zh", "en"] if args.lang == "all" else [args.lang]
    report = {"controls": []}
    for lg in langs:
        report["controls"].append(run_lang(lg, use_model=not args.no_model))
    if args.sample:
        s = sample_manuscript(args.sample, lang=None, use_model=not args.no_model)
        report["sample"] = s
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
