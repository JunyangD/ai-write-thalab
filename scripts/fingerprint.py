# -*- coding: utf-8 -*-
"""
fingerprint.py —— 规则型「AI 指纹」自检器（原理复刻版 · 中英双语 · 位置无关）
================================================================================
用途：投稿前定位「AI 味」偏重的段落，输出可解释的**相对风险分**并给出改写方向。

原理依据（据公开资料归纳的维普 AIGC 检测维度）：
  1) 句长分布过于规整（burstiness 偏低）
  2) 长句比例偏高（AI 中文/英文都倾向长而工整的复句）
  3) 模板化套话密度
  4) 过渡连接词密度
  5) 句首结构重复度
  6) 标点单一度（「一逗到底」）
  7) 词汇丰富度（type-token ratio，越低越像 AI）

★ 诚实声明：维普的模型闭源（私有语料 + 训练权重），**无法复制其数值**。
  本工具复刻的是其**检测维度**，输出「相对风险分（0–100）」，用于自查与改写，
  不能替代维普官方检测结果。

中英自适应：中文按**汉字**计、英文按**词**计；两套模板词/连接词表与阈值。

用法：
  python fingerprint.py <稿件.md|txt|docx> [--lang zh|en|auto] [--top N] [--json]
  python fingerprint.py --help

输出：
  默认打印可读报告；附加 --json 时，把结构化结果以 JSON 打到 stdout，
  便于上层 agent 循环调用。
产物：与稿件同目录的 <稿件>.aigc.json（可用 --out 指定）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# 允许「直接运行本文件」与「作为包导入」两种方式
sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import (  # noqa: E402
    cv, band, safe_mean, load_text, strip_markdown, detect_lang,
    split_sentences, split_paragraphs, count_units, cjk_count, word_count,
    ZH_PUNCT_RE, pretty_banner,
)

# ==========================================================================
# 词表：中文
# ==========================================================================
TEMPLATE_ZH = [
    "值得注意的是", "综上所述", "总而言之", "总的来说", "总之",
    "首先", "其次", "再次", "最后",
    "此外", "与此同时", "不仅", "而且", "不仅仅", "更进一步",
    "换句话说", "换言之", "也就是说", "简而言之",
    "随着", "在当今", "在…的背景下", "近年来", "当前",
    "起着重要作用", "起到了重要作用", "具有重要意义", "意义重大",
    "日益受到关注", "广泛关注", "引起广泛关注", "备受关注",
    "本文旨在", "本研究旨在", "旨在", "有利于",
    "不可忽视", "至关重要", "尤为关键",
    "众所周知", "显而易见", "不言而喻",
    "一方面", "另一方面", "既可以", "也可以",
    "研究表明", "大量研究表明", "越来越多的研究", "多项研究表明",
    "为……提供了", "为…提供", "奠定了坚实基础", "提供有力支撑",
    "深入探讨", "系统梳理", "全面分析", "多维度",
    "呈现出", "体现出", "折射出", "彰显",
    "在某种程度上", "从某种意义上说", "毫无疑问",
]
CONNECTIVE_ZH = [
    "因此", "然而", "但是", "而且", "并且", "此外", "同时",
    "从而", "进而", "由此", "据此", "鉴于", "基于此", "在此基础上",
    "综上所述", "总而言之", "总的来说", "可见", "由此可见",
    "首先", "其次", "最后", "第一", "第二", "第三",
]

# ==========================================================================
# 词表：英文（学术写作里的高频 AI 痕迹）
# ==========================================================================
TEMPLATE_EN = [
    "it is worth noting", "it is important to note", "it should be noted",
    "in conclusion", "in summary", "to sum up", "overall", "in recent years",
    "with the rapid development", "with the development of", "in today's",
    "plays an important role", "plays a crucial role", "plays a vital role",
    "significant", "significantly", "crucial", "vital", "essential",
    "has attracted increasing attention", "has drawn considerable attention",
    "this study aims to", "this paper aims to", "the present study aims to",
    "delve into", "delves into", "shed light on", "paves the way",
    "comprehensive analysis", "multifaceted", "underscores", "highlights",
    "provides strong support", "lays a solid foundation", "broad prospects",
    "firstly", "secondly", "thirdly", "last but not least",
    "on the one hand", "on the other hand", "as we all know", "it is well known",
    "naturally", "undoubtedly", "without a doubt", "to some extent",
    "in other words", "that is to say", "in light of", "against this backdrop",
    "a growing body of", "an increasing number of", "a variety of",
    "notably", "importantly", "more importantly",
]
CONNECTIVE_EN = [
    "therefore", "however", "moreover", "furthermore", "in addition",
    "additionally", "thus", "hence", "consequently", "as a result",
    "meanwhile", "nevertheless", "nonetheless", "in contrast",
    "on the contrary", "for instance", "for example", "in particular",
    "first", "second", "third", "finally", "in conclusion", "overall",
]

# ==========================================================================
# 阈值与权重（中英各一套；权重为经验值，权重之和 = 1.00）
# ==========================================================================
# 每项：(高风险方向? , 安全线 lo , 高危线 hi , 权重)
#   sent_cv / ttr 为「越低越像 AI」，用反向映射。
WEIGHTS = {
    "sent_cv":      0.22,   # 句长均匀度（CV 低 = 像 AI）
    "long_ratio":   0.16,   # 长句比例
    "tpl_density":  0.20,   # 模板词密度
    "con_density":  0.14,   # 连接词密度
    "start_rep":    0.10,   # 句首重复
    "comma_ratio":  0.10,   # 逗号占比
    "ttr":          0.08,   # 词汇丰富度（反向）
}

# 阈值（lo=安全线，hi=高危线）。中文句长以「字」、英文以「词」为单位。
THRESH = {
    "zh": {
        "sent_cv":     (0.55, 0.22),   # 安全 0.55 → 高危 0.22（越大越安全，反向）
        "long_ratio":  (0.15, 0.48),   # ≥45 字/句
        "tpl_density": (3.0, 15.0),    # 每千汉字
        "con_density": (5.0, 20.0),    # 每千汉字
        "start_rep":   (0.05, 0.40),   # 句首 4 汉字重复率
        "comma_ratio": (0.48, 0.78),
        "ttr":         (0.50, 0.25),   # 越大越安全，反向
        "long_len":    45,             # 长句定义（字）
    },
    "en": {
        "sent_cv":     (0.55, 0.25),
        "long_ratio":  (0.15, 0.45),   # ≥30 词/句
        "tpl_density": (2.0, 12.0),    # 每千词
        "con_density": (8.0, 25.0),    # 每千词
        "start_rep":   (0.05, 0.40),   # 句首 2 词重复率
        "comma_ratio": (0.35, 0.65),
        "ttr":         (0.70, 0.45),
        "long_len":    30,             # 长句定义（词）
    },
}

# 中文易混淆子串：避免把「首先」在「首先…其次」之外过度计数的问题——此处保持原样，
# 与旧脚本一致（保守，不做额外去重）。


# --------------------------------------------------------------------------
# 单段分析
# --------------------------------------------------------------------------
def analyze_paragraph(p: str, lang: str) -> dict | None:
    """返回单段的原始指标字典；句数 <2 时返回 None（无法算句长波动）。"""
    th = THRESH[lang]
    sents = split_sentences(p, lang)
    if len(sents) < 2:
        return None

    lens = [count_units(s, lang) for s in sents]
    lens = [x for x in lens if x > 0] or [1]

    n = max(count_units(p, lang), 1)

    # 1) 句长突发性：CV 低 = 句子太均匀 = 像 AI
    sent_cv = cv(lens)
    # 2) 长句占比
    long_ratio = sum(1 for x in lens if x >= th["long_len"]) / len(lens)
    # 3) 模板词密度（每千单位）
    table = TEMPLATE_ZH if lang == "zh" else TEMPLATE_EN
    low = p.lower() if lang == "en" else p
    tpl = sum(low.count(w.lower() if lang == "en" else w) for w in table)
    tpl_density = tpl / n * 1000
    # 4) 连接词密度
    ctable = CONNECTIVE_ZH if lang == "zh" else CONNECTIVE_EN
    con = sum(low.count(w.lower() if lang == "en" else w) for w in ctable)
    con_density = con / n * 1000
    # 5) 句首重复度
    if lang == "zh":
        starts = [re_sub_cjk(s)[:4] for s in sents]
        starts = [s for s in starts if len(s) >= 4]
    else:
        starts = [" ".join(s.split()[:2]).lower() for s in sents]
        starts = [s for s in starts if s]
    start_rep = 1 - (len(set(starts)) / len(starts)) if starts else 0.0
    # 6) 词汇丰富度：中文=字符级 TTR，英文=词级 TTR
    if lang == "zh":
        units = re_sub_cjk(p)
    else:
        from utils import _WORD_RE  # 复用英文词切分
        units = [w.lower() for w in _WORD_RE.findall(p)]
    ttr = (len(set(units)) / len(units)) if units else 0.0
    # 7) 标点单一度：逗号占比
    puncts = ZH_PUNCT_RE.findall(p)
    comma_ratio = (p.count("，") if lang == "zh" else p.count(",")) / len(puncts) if puncts else 0.0
    # 8) 平均句长
    mean_len = safe_mean(lens)

    return {
        "sents": len(sents),
        "units": n,
        "sent_cv": sent_cv,
        "long_ratio": long_ratio,
        "tpl_density": tpl_density,
        "con_density": con_density,
        "start_rep": start_rep,
        "ttr": ttr,
        "comma_ratio": comma_ratio,
        "mean_len": mean_len,
        "n_template": tpl,
        "n_connective": con,
    }


def re_sub_cjk(s: str) -> str:
    """只保留汉字（用于句首比较与字符级 TTR）。"""
    import re
    return re.sub(r"[^\u4e00-\u9fff\u3400-\u4dbf]", "", s)


def risk_score(m: dict, lang: str) -> tuple[float, dict]:
    """把指标归一为 0~100 风险分，并返回各维度贡献明细（0~100）。"""
    th = THRESH[lang]

    def inv(v, lo, hi):
        # 值越大越安全：把 lo(安全) 到 hi(高危) 反向映射
        return 1 - band(v, hi, lo)

    parts = {
        "句长均匀度": (1 - band(m["sent_cv"], th["sent_cv"][1], th["sent_cv"][0]), WEIGHTS["sent_cv"]),
        "长句比例":   (band(m["long_ratio"], th["long_ratio"][0], th["long_ratio"][1]), WEIGHTS["long_ratio"]),
        "模板词密度": (band(m["tpl_density"], th["tpl_density"][0], th["tpl_density"][1]), WEIGHTS["tpl_density"]),
        "连接词密度": (band(m["con_density"], th["con_density"][0], th["con_density"][1]), WEIGHTS["con_density"]),
        "句首重复":   (band(m["start_rep"], th["start_rep"][0], th["start_rep"][1]), WEIGHTS["start_rep"]),
        "逗号占比":   (band(m["comma_ratio"], th["comma_ratio"][0], th["comma_ratio"][1]), WEIGHTS["comma_ratio"]),
        "词汇丰富度": (1 - band(m["ttr"], th["ttr"][1], th["ttr"][0]), WEIGHTS["ttr"]),
    }
    score = sum(v * w for v, w in parts.values()) * 100
    detail = {k: round(v * 100, 1) for k, (v, w) in parts.items()}
    return score, detail


# --------------------------------------------------------------------------
# 定向改写指令生成（每段主要风险来源 → 可执行建议）
# --------------------------------------------------------------------------
REWRITE_HINTS = {
    "句长均匀度": "拆句/并句：把部分长复句拆成短句，并在短句间插入一个明显更长或更短的句子，制造句长波动（提高 burstiness）。",
    "长句比例":   "拆分长句：把 ≥{long} 单位的长复句按逻辑拆成 2–3 句，补主语，避免层层套叠的定语从句。",
    "模板词密度": "删除模板套话：去掉「值得注意的是 / 综上所述 / 首先其次最后 / it is worth noting / plays an important role」等，改为直陈事实。",
    "连接词密度": "减少过渡词：删掉可省的「因此/此外/然而/moreover/furthermore」，让逻辑靠语义衔接而非连接词堆叠。",
    "句首重复":   "更换句首：避免多句以相同词/结构开头，改用不同主语、时间状语或直接切入。",
    "逗号占比":   "打断「一逗到底」：把超长逗号链断开，改用句号分号，控制单句逗号数。",
    "词汇丰富度": "增加用词变化：避免高频重复用字/词，用具体名词替换泛指词，减少同义词的机械循环。",
}


def rewrite_instructions(detail: dict, lang: str, top_k: int = 3) -> list[str]:
    th = THRESH[lang]
    ordered = sorted(detail.items(), key=lambda x: -x[1])
    out = []
    for k, v in ordered[:top_k]:
        if v <= 0:
            continue
        hint = REWRITE_HINTS[k].format(long=th["long_len"])
        out.append(f"[{k} {v:.0f}/100] {hint}")
    return out


# --------------------------------------------------------------------------
# 全文分析
# --------------------------------------------------------------------------
def analyze_text(text: str, lang: str | None = None) -> dict:
    """对全文做指纹分析，返回结构化结果字典（供 CLI / 机读接口共用）。"""
    if lang in (None, "auto"):
        lang = detect_lang(text)
    clean = strip_markdown(text)
    paras = split_paragraphs(clean, lang)

    rows = []
    for p in paras:
        m = analyze_paragraph(p, lang)
        if not m:
            continue
        s, detail = risk_score(m, lang)
        rows.append({
            "score": round(s, 2),
            "detail": detail,
            "metrics": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in m.items()},
            "sources": [k for k, _ in sorted(detail.items(), key=lambda x: -x[1]) if _ > 0][:3],
            "instructions": rewrite_instructions(detail, lang),
            "text": p,
        })

    result = {
        "tool": "fingerprint",
        "lang": lang,
        "n_paragraphs": len(rows),
        "doc_score": 0.0,
        "grade": "",
        "mean_metrics": {},
        "paras": [],
    }
    if not rows:
        return result

    allm = {}
    for k in rows[0]["metrics"]:
        vals = [r["metrics"][k] for r in rows]
        allm[k] = round(safe_mean(vals), 4)
    doc_score = safe_mean([r["score"] for r in rows])

    result["doc_score"] = round(doc_score, 2)
    result["grade"] = "低" if doc_score < 30 else ("中" if doc_score < 50 else "高")
    result["mean_metrics"] = allm
    rows.sort(key=lambda r: -r["score"])
    # 记录原文段序，便于上游定位
    result["paras"] = rows
    return result


def render_report(result: dict, path: str, topn: int = 12) -> str:
    lang = result["lang"]
    lines = []
    lines.append(pretty_banner("AIGC 指纹自检报告（原理复刻版 · 非维普官方）"))
    lines.append(f"文件：{os.path.basename(path)}   语种：{lang}")
    lines.append(f"分析段落：{result['n_paragraphs']} 段")
    lines.append(f"全文 AI 味风险分：{result['doc_score']:.1f} / 100（{result['grade']}）")
    if result["n_paragraphs"] == 0:
        lines.append("没有可分析的段落（可能语种判定或最小长度阈值不合适）。")
        return "\n".join(lines)

    lines.append("\n【全文指纹均值】")
    for k, v in result["mean_metrics"].items():
        lines.append(f"  {k:<12} {v}")

    lines.append(f"\n【风险最高的 {min(topn, len(result['paras']))} 段】")
    for i, r in enumerate(result["paras"][:topn], 1):
        lines.append("-" * 78)
        src = "、".join(f"{k} {r['detail'][k]:.0f}" for k in r["sources"])
        lines.append(f"  #{i}  风险分 {r['score']:.1f}   【主要来源】{src}")
        mm = r["metrics"]
        lines.append(
            f"  句数 {mm['sents']}｜平均句长 {mm['mean_len']:.1f}｜句长CV {mm['sent_cv']:.2f}"
            f"｜模板词/千 {mm['tpl_density']:.1f}｜连接词/千 {mm['con_density']:.1f}"
        )
        for ins in r["instructions"]:
            lines.append("    → " + ins)
        preview = r["text"].replace("\n", " ")
        lines.append("  原文：" + preview[:170] + ("…" if len(preview) > 170 else ""))
    return "\n".join(lines)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def build_argparser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="规则型 AI 指纹自检器（中英双语，位置无关）。输出相对风险分，非维普数值。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("path", nargs="?", help="稿件路径（.md / .txt / .docx）")
    ap.add_argument("--lang", choices=["zh", "en", "auto"], default="auto",
                    help="语种；默认 auto 自动判定")
    ap.add_argument("--top", type=int, default=12, help="报告里展示的风险最高段落数（默认 12）")
    ap.add_argument("--json", action="store_true", help="把结构化结果以 JSON 打到 stdout（机读接口）")
    ap.add_argument("--out", default=None, help="JSON 明细输出路径（默认 <稿件>.aigc.json）")
    ap.add_argument("--quiet", action="store_true", help="不打印可读报告（配合 --json）")
    return ap


def main(argv=None):
    ap = build_argparser()
    args = ap.parse_args(argv)
    if not args.path:
        ap.print_help()
        return 0

    try:
        text = load_text(args.path)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 2
    result = analyze_text(text, args.lang)
    result["source_file"] = os.path.basename(args.path)

    # 写 JSON 明细
    out = args.out or (str(args.path) + ".aigc.json")
    try:
        Path(out).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        out = None

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    if not args.quiet and not args.json:
        print(render_report(result, args.path, args.top))
        if out:
            print("\n明细已写入：" + out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
