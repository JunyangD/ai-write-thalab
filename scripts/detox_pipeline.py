# -*- coding: utf-8 -*-
"""
detox_pipeline.py —— 「降 AI 率」主控管线（检测 → 定位 → 定向改写指令 → 达标判定）
================================================================================
一条命令跑完双检测，并给出**逐段风险排序**与**每段的可执行改写指令**；
既可交互式被上游 agent 循环调用，也可（给定改写器）自主迭代。

双检测：
  ① 规则指纹（fingerprint.py，零依赖）—— 7 维相对风险分 0–100
  ② 开源模型（model_zh.py / model_en.py，需 torch+权重）—— 逐段 P(AI)
两者在**同一套段落**上逐段对齐，合成每段综合风险，供定位与改写。

达标判定：**全文 AIGC 疑似率 < --threshold（默认 5%）** 视为达标。
  * 全文疑似率 = 各段 P(AI) 按计数单位（中文汉字 / 英文词）加权的平均，取模型通路。
  * 若模型不可用，无法给出该口径的疑似率，pass 判定置为 null 并如实提示。

迭代模式：
  * 默认：跑一轮，输出「待改段 + 指令 + 判定」，由**调用方/上游 agent** 改写后
    再次调用本脚本复检（推荐：上游 agent 循环，见 --json 的机读接口）。
  * --iterate N：最多检测 N 轮。
  * --rewriter "CMD"：给出自动改写器（命令模板，占位符 {in} {out}），
    则每轮检测后自动调用它生成下一版，形成闭环（CMD 需自行提供，本工具不自带 LLM）。

★ 诚实声明：本工具复刻的是检测维度 + 开源检测器近似，**不等于维普**数值；
  最终须以维普官方检测为准。

用法：
  python detox_pipeline.py <稿件> [--lang auto|zh|en] [--no-model] [--model-dir DIR]
      [--threshold 0.05] [--top 12] [--json] [--out r.json] [--md r.md]
      [--iterate N] [--rewriter "CMD {in} {out}"] [--round-current R]

机读接口（供上层 agent 循环）：
  python detox_pipeline.py <稿件> --json --no-report   # 仅吐结构化 JSON
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import (  # noqa: E402
    load_text, strip_markdown, detect_lang, split_paragraphs, count_units,
    safe_mean, pretty_banner,
)
from fingerprint import analyze_paragraph, risk_score  # noqa: E402

# 综合风险里指纹与模型的权重（模型可用时）
BLEND = {"fp": 0.5, "model": 0.5}
# 「需要改写」的单段触发线
PARA_MODEL_HI = 0.50     # 单段 P(AI) ≥ 50%
PARA_COMBINED_HI = 40.0  # 或综合风险 ≥ 40


# --------------------------------------------------------------------------
def _model_score_paragraphs(paras: list[str], lang: str, model_dir: str | None):
    """尝试用模型对段落逐条打分；返回 (scores|None, err|None)。"""
    try:
        from model_common import load_detector, resolve_model_dir, _score_chunks
        md = resolve_model_dir(lang, model_dir)
        tok, model, id2label, ai_idx = load_detector(lang, md)
        scores = [round(_score_chunks(tok, model, ai_idx, p), 6) for p in paras]
        return scores, None, {"model_dir": str(md), "id2label": id2label}
    except FileNotFoundError as e:
        return None, str(e), None
    except Exception as e:
        return None, f"模型通路不可用：{e}", None


# --------------------------------------------------------------------------
def analyze(path: str, lang: str | None = None, use_model: bool = True,
            model_dir: str | None = None, threshold: float = 0.05,
            round_current: int = 1) -> dict:
    text = load_text(path)
    if lang in (None, "auto"):
        lang = detect_lang(text)
    clean = strip_markdown(text)
    # 统一段落（双检测对齐同一套段）
    min_units = 40 if lang == "zh" else 25
    paras = split_paragraphs(clean, lang, min_units=min_units)

    # ---- 指纹（逐段）----
    fp_rows = []
    for p in paras:
        m = analyze_paragraph(p, lang)
        if not m:
            fp_rows.append(None)
            continue
        s, detail = risk_score(m, lang)
        fp_rows.append({"fp_score": round(s, 2), "detail": detail,
                        "sources": [k for k, v in sorted(detail.items(), key=lambda x: -x[1])
                                    if v > 0][:3],
                        "metrics": {k: (round(v, 4) if isinstance(v, float) else v)
                                    for k, v in m.items()}})

    # ---- 模型（逐段，可选）----
    model_scores = None
    model_err = None
    model_meta = None
    if use_model and paras:
        model_scores, model_err, model_meta = _model_score_paragraphs(paras, lang, model_dir)
    elif not use_model:
        model_err = "已用 --no-model 跳过模型通路（无法给出 <5% 判定）"

    # ---- 逐段合成 ----
    from fingerprint import rewrite_instructions
    rows = []
    for i, p in enumerate(paras):
        fp = fp_rows[i]
        fp_score = fp["fp_score"] if fp else None
        detail = fp["detail"] if fp else {}
        mai = model_scores[i] if model_scores else None
        # 综合风险
        if fp_score is not None and mai is not None:
            combined = BLEND["fp"] * fp_score + BLEND["model"] * mai * 100
        elif fp_score is not None:
            combined = fp_score
        elif mai is not None:
            combined = mai * 100
        else:
            combined = None
        need = ((mai is not None and mai >= PARA_MODEL_HI) or
                (combined is not None and combined >= PARA_COMBINED_HI))
        rows.append({
            "index": i,
            "units": count_units(p, lang),
            "fp_score": fp_score,
            "fp_sources": (fp["sources"] if fp else []),
            "fp_detail": detail,
            "model_ai": mai,
            "combined_risk": (round(combined, 2) if combined is not None else None),
            "need_rewrite": bool(need),
            "instructions": rewrite_instructions(detail, lang) if detail else [],
            "text": p,
        })

    # ---- 全文指标 ----
    n = len(rows) or 1
    fp_doc = safe_mean([r["fp_score"] for r in rows])
    doc_rate = None
    if model_scores:
        tot = sum(r["units"] for r in rows) or 1
        doc_rate = sum(r["model_ai"] * r["units"] for r in rows) / tot
    passed = (doc_rate < threshold) if doc_rate is not None else None

    rows.sort(key=lambda r: -(r["combined_risk"] if r["combined_risk"] is not None else -1))
    targets = [r for r in rows if r["need_rewrite"]]

    return {
        "tool": "detox_pipeline",
        "lang": lang,
        "round": round_current,
        "threshold": threshold,
        "model_available": model_scores is not None,
        "model_error": model_err,
        "model_meta": model_meta,
        "n_paragraphs": len(rows),
        "doc_fingerprint_score": round(fp_doc, 2),
        "doc_suspected_rate": (round(doc_rate, 6) if doc_rate is not None else None),
        "max_para_ai": (round(max((r["model_ai"] for r in rows), default=0.0), 6)
                        if model_scores else None),
        "n_need_rewrite": len(targets),
        "passed": passed,
        "needs_rewrite": bool(targets),
        "rewrite_targets": [r["index"] for r in targets],
        "paragraphs": rows,
    }


# --------------------------------------------------------------------------
def render_md(result: dict, path: str, topn: int = 12) -> str:
    r = result
    L = []
    L.append(f"# 降 AI 率检测报告 —— {os.path.basename(path)}")
    L.append("")
    L.append(f"- 语种：**{r['lang']}**　轮次：第 {r['round']} 轮")
    L.append(f"- 模型通路：{'✅ 可用' if r['model_available'] else '❌ 不可用（' + str(r['model_error']).splitlines()[0] + '）'}")
    L.append(f"- 段落数：{r['n_paragraphs']}")
    L.append(f"- 全文指纹风险分：**{r['doc_fingerprint_score']} / 100**")
    if r["doc_suspected_rate"] is not None:
        L.append(f"- 全文 AIGC 疑似率（模型·按字数加权）：**{r['doc_suspected_rate'] * 100:.3f}%**")
        L.append(f"- 最高单段 P(AI)：**{(r['max_para_ai'] or 0) * 100:.2f}%**")
        L.append(f"- 达标判定（阈值 {r['threshold'] * 100:.0f}%）："
                 f"{'✅ 达标' if r['passed'] else '❌ 未达标'}")
    else:
        L.append("- 全文 AIGC 疑似率：**无法判定**（缺模型权重，先跑 download_models.py）")
    L.append(f"- 待改写段落：**{r['n_need_rewrite']} 段**")
    L.append("")
    L.append("## 逐段风险排序与定向改写指令")
    L.append("")
    L.append("| # | 综合风险 | 指纹分 | P(AI)% | 主要来源 | 预览 |")
    L.append("|---|---|---|---|---|---|")
    for k, p in enumerate(r["paragraphs"][:topn], 1):
        prev = p["text"].replace("\n", " ").replace("|", "/")[:46]
        mai = f"{p['model_ai'] * 100:.2f}" if p["model_ai"] is not None else "—"
        comb = f"{p['combined_risk']:.1f}" if p["combined_risk"] is not None else "—"
        L.append(f"| {k} | {comb} | {p['fp_score'] if p['fp_score'] is not None else '—'} "
                 f"| {mai} | {'、'.join(p['fp_sources']) or '—'} | {prev}… |")
    L.append("")
    L.append("## 重点段改写建议")
    L.append("")
    for k, p in enumerate([x for x in r["paragraphs"] if x["need_rewrite"]][:topn], 1):
        L.append(f"### 段 {p['index']}（综合风险 {p['combined_risk']}）")
        L.append("")
        L.append("> " + p["text"].replace("\n", " ")[:220] + "…")
        L.append("")
        for ins in p["instructions"]:
            L.append(f"- {ins}")
        if not p["instructions"]:
            L.append("- 该段无显著单一风险来源，建议整体口语化、增加具体细节与句长波动。")
        L.append("")
    L.append("---")
    L.append("")
    L.append("> ⚠️ 维普模型闭源，本报告复刻的是检测维度 + 开源检测器近似，**数值不等于维普**。")
    L.append("> 定稿后请务必以维普官方检测为准。")
    return "\n".join(L)


# --------------------------------------------------------------------------
def run_iteration(path: str, args) -> tuple[dict, str]:
    """跑一轮或多轮检测（含可选自动改写器）。返回 (最后一轮 result, 最终文件路径)。"""
    current = path
    last = None
    # --json 时进度信息走 stderr，保证 stdout 为**纯净 JSON**（便于上层 agent 直接解析）
    def log(*a, **k):
        print(*a, **k, file=(sys.stderr if getattr(args, "json", False) else sys.stdout))
    for rd in range(1, max(1, args.iterate) + 1):
        last = analyze(current, lang=args.lang, use_model=not args.no_model,
                       model_dir=args.model_dir, threshold=args.threshold, round_current=rd)
        log(pretty_banner(f"第 {rd} 轮检测 —— {os.path.basename(current)}"))
        rate_txt = ('%.3f%%' % (last['doc_suspected_rate'] * 100)) if last['doc_suspected_rate'] is not None else 'n/a'
        verdict = '达标' if last['passed'] else ('未达标' if last['passed'] is False else '无法判定(缺模型)')
        log(f"  语种={last['lang']}  段落={last['n_paragraphs']}  "
            f"指纹分={last['doc_fingerprint_score']}  "
            f"疑似率={rate_txt}  "
            f"待改={last['n_need_rewrite']} 段  判定={verdict}")
        if last["model_error"]:
            log("  [提示] " + last["model_error"].splitlines()[0])

        if last["passed"] or not last["needs_rewrite"]:
            break
        if not args.rewriter:
            # 无自动改写器：交回调用方
            log("  → 无 --rewriter，交回调用方/上游 agent 按指令改写后复检。")
            break
        # 调用自动改写器（命令模板）——用「哨兵占位→shlex.split→回填」，
        # 无论调用方写 {in} {out} 还是 "{in}" "{out}" 都能正确解析，且 shell=False 无转义问题。
        out_path = str(Path(current).with_name(
            Path(current).stem + f".r{rd + 1}" + Path(current).suffix))
        S_IN, S_OUT = "__AIGC_IN_PATH__", "__AIGC_OUT_PATH__"
        tmpl = args.rewriter.replace("{in}", S_IN).replace("{out}", S_OUT)
        try:
            argv = shlex.split(tmpl)
        except ValueError as e:
            log(f"  [改写器失败] 命令解析出错：{e}")
            break
        argv = [a.replace(S_IN, current).replace(S_OUT, out_path) for a in argv]
        log("  → 调用改写器：" + " ".join(shlex.quote(a) for a in argv))
        try:
            subprocess.run(argv, shell=False,
                           cwd=str(Path(__file__).resolve().parent), check=True)
        except (subprocess.CalledProcessError, OSError) as e:
            log(f"  [改写器失败] {e}")
            break
        current = out_path
    return last, current


def build_argparser():
    ap = argparse.ArgumentParser(
        description="降 AI 率主控：双检测 → 逐段风险排序 + 定向改写指令 + 达标判定（默认阈值 5%）。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("path", nargs="?", help="稿件路径（.md / .txt / .docx）")
    ap.add_argument("--lang", choices=["auto", "zh", "en"], default="auto", help="语种（默认 auto）")
    ap.add_argument("--no-model", action="store_true", help="只跑指纹（不加载模型）")
    ap.add_argument("--model-dir", default=None, help="模型目录（覆盖默认/环境变量）")
    ap.add_argument("--threshold", type=float, default=0.05, help="达标阈值（默认 0.05，即 5 个百分点）")
    ap.add_argument("--top", type=int, default=12, help="报告展示段数（默认 12）")
    ap.add_argument("--iterate", type=int, default=1, help="最多检测轮数（默认 1）")
    ap.add_argument("--rewriter", default=None,
                    help="自动改写命令模板，占位符 {in} {out}（加不加引号均可，shell=False 执行）；不给则交回调用方")
    ap.add_argument("--json", action="store_true", help="把结构化结果打到 stdout（机读接口）")
    ap.add_argument("--no-report", action="store_true", help="不打印可读摘要（配合 --json）")
    ap.add_argument("--out", default=None, help="JSON 输出路径（默认 <稿件>.detox.json）")
    ap.add_argument("--md", default=None, help="Markdown 报告输出路径（默认 <稿件>.detox.md）")
    return ap


def main(argv=None):
    args = build_argparser().parse_args(argv)
    if not args.path:
        build_argparser().print_help()
        return 0

    try:
        result, final_path = run_iteration(args.path, args)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 2
    result["final_file"] = os.path.basename(final_path)

    # 出口文件
    out = args.out or (str(args.path) + ".detox.json")
    try:
        Path(out).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        out = None
    md = args.md or (str(args.path) + ".detox.md")
    try:
        Path(md).write_text(render_md(result, args.path, args.top), encoding="utf-8")
    except OSError:
        md = None

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    elif not args.no_report:
        print(render_md(result, args.path, args.top))
    if not args.json:
        print("\nJSON 明细：" + (out or "（写入失败）"))
        print("Markdown 报告：" + (md or "（写入失败）"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
