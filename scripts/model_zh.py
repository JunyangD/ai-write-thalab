# -*- coding: utf-8 -*-
"""
model_zh.py —— 中文 AI 文本检测器（Hello-SimpleAI/chatgpt-detector-roberta-chinese）
================================================================================
用开源中文 RoBERTa 二分类模型对正文**逐段**打 P(AI)，全文疑似率按**字数加权**。

模型：Hello-SimpleAI/chatgpt-detector-roberta-chinese（RoBERTa-base 中文，{0:Human,1:ChatGPT}）
获取：经 https://hf-mirror.com；缺权重时先跑 download_models.py --lang zh。

位置无关：模型目录解析顺序 = --model-dir > 环境变量 AIGC_MODEL_ZH_DIR > 默认 …/models/chatgpt-detector-roberta-chinese

★ 诚实声明：该检测器 ≠ 维普，模型不同、语料不同，**数值不可等同**，
  仅用于定位高风险段落与评估改写效果；最终以维普官方检测为准。

用法：
  python model_zh.py <稿件.md|txt|docx> [--model-dir DIR] [--top N] [--json] [--lang zh]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from model_common import analyze_file, render_report, resolve_model_dir  # noqa: E402


def build_argparser():
    ap = argparse.ArgumentParser(
        description="中文 AI 文本检测器（逐段 P(AI)，字数加权全文疑似率）。输出相对参照，非维普数值。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("path", nargs="?", help="稿件路径（.md / .txt / .docx）")
    ap.add_argument("--model-dir", default=None,
                    help="模型目录；默认可由环境变量 AIGC_MODEL_ZH_DIR 指定，否则取 …/models/chatgpt-detector-roberta-chinese")
    ap.add_argument("--lang", choices=["zh", "auto"], default="zh", help="语种（本脚本固定中文通路）")
    ap.add_argument("--top", type=int, default=15, help="展示的风险最高段落数（默认 15）")
    ap.add_argument("--min-units", type=int, default=None, help="段落最小汉字数（默认 30）")
    ap.add_argument("--json", action="store_true", help="以 JSON 打到 stdout（机读接口）")
    ap.add_argument("--out", default=None, help="JSON 明细输出路径（默认 <稿件>.aigc_model.json）")
    ap.add_argument("--quiet", action="store_true", help="不打印可读报告（配合 --json）")
    return ap


def main(argv=None):
    args = build_argparser().parse_args(argv)
    if not args.path:
        build_argparser().print_help()
        return 0
    try:
        result = analyze_file(args.path, lang="zh", model_dir=args.model_dir,
                              min_units=args.min_units)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 2

    result["source_file"] = os.path.basename(args.path)
    out = args.out or (str(args.path) + ".aigc_model.json")
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
