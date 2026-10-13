# -*- coding: utf-8 -*-
"""
model_common.py —— 开源 AI 文本检测模型的共用封装
================================================================================
被 model_zh.py / model_en.py 复用，集中处理：
  * 模型目录的**位置无关**解析（CLI --model-dir > 环境变量 > 默认 …/models/<name>）
  * 缺权重时给出清晰提示，并指向 download_models.py
  * 长段落分块推理（≤510 token 滑窗取最大风险块，避免 512 截断丢掉后半段）
  * 全文疑似率（按字数加权）、逐段排序、JSON 产物、可读报告

模型（均取自 hf-mirror 可达的开源仓库）：
  zh : Hello-SimpleAI/chatgpt-detector-roberta-chinese   (RoBERTa-base 中文, {0:Human,1:ChatGPT})
  en : Hello-SimpleAI/chatgpt-detector-roberta           (RoBERTa-base 英文, {0:Human,1:ChatGPT})

★ 诚实声明：这是开源社区的中文/英文 AI 文本检测器，可作为维普 AIGC 检测的**近似参照**；
  两者模型不同、语料不同，**数值不可等同**，仅用于定位高风险段落与评估改写效果。
"""
from __future__ import annotations

import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import (  # noqa: E402
    DEFAULT_MODEL_ROOT, load_text, strip_markdown, detect_lang,
    split_paragraphs, count_units, cjk_count, pretty_banner, safe_mean,
)

# 语种 → (HF 仓库名, 默认本地目录名, 环境变量名)
MODEL_SPEC = {
    "zh": ("Hello-SimpleAI/chatgpt-detector-roberta-chinese",
           "chatgpt-detector-roberta-chinese", "AIGC_MODEL_ZH_DIR"),
    "en": ("Hello-SimpleAI/chatgpt-detector-roberta",
           "chatgpt-detector-roberta", "AIGC_MODEL_EN_DIR"),
}

# 判定为「AI 类」标签的关键词（大小写不敏感）
_AI_LABEL_HINTS = ("chatgpt", "gpt", "ai", "machine", "fake", "generated")


def resolve_model_dir(lang: str, cli_dir: str | None = None) -> Path:
    """位置无关地解析模型目录。

    优先级：CLI --model-dir > 环境变量 AIGC_MODEL_{ZH,EN}_DIR > 默认 …/models/<name>
    """
    if cli_dir:
        return Path(cli_dir).expanduser().resolve()
    repo, default_name, env_name = MODEL_SPEC[lang]
    env_val = os.environ.get(env_name)
    if env_val:
        return Path(env_val).expanduser().resolve()
    return (DEFAULT_MODEL_ROOT / default_name).resolve()


def _missing_hint(lang: str, model_dir: Path) -> str:
    repo = MODEL_SPEC[lang][0]
    return (
        f"[缺少模型权重] 未找到 {lang} 检测模型目录：\n    {model_dir}\n"
        f"请先下载（位置无关，会自动落到本包的 models/ 下）：\n"
        f"    python {Path(__file__).resolve().parent / 'download_models.py'} --lang {lang}\n"
        f"或手动指定：--model-dir <目录>  /  设环境变量 {MODEL_SPEC[lang][2]}\n"
        f"（HF 仓库：{repo}，经 https://hf-mirror.com 获取）"
    )


def load_detector(lang: str, model_dir: Path):
    """加载 tokenizer 与分类模型；缺权重时报清晰错误。"""
    if not model_dir.exists() or not any(model_dir.glob("*.bin")) and not any(model_dir.glob("*.safetensors")):
        raise FileNotFoundError(_missing_hint(lang, model_dir))

    # 本地目录 = 离线优先；但仍允许 HF_ENDPOINT 指向镜像
    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_OFFLINE"] = "1"

    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification

    tok = AutoTokenizer.from_pretrained(str(model_dir))
    model = AutoModelForSequenceClassification.from_pretrained(str(model_dir))
    model.eval()

    id2label = {int(k): str(v) for k, v in getattr(model.config, "id2label", {}).items()}
    ai_idx = None
    for idx, name in id2label.items():
        if any(h in name.lower() for h in _AI_LABEL_HINTS):
            ai_idx = idx
            break
    if ai_idx is None:
        # 兜底：二分类里假定 label 1 = AI
        ai_idx = 1 if len(id2label) >= 2 else 0
    return tok, model, id2label, ai_idx


def _score_chunks(tok, model, ai_idx, text: str, max_len: int = 510, stride: int = 384) -> float:
    """对单段文本分块推理，返回风险最高的块 P(AI)。

    长段按 token 滑窗切块（窗口 max_len、步进 stride），取各块最大 P(AI)，
    避免原脚本 512 截断丢失段落后半段的 AI 特征。
    """
    import torch

    enc = tok(text, return_tensors="pt", truncation=True, max_length=max_len, add_special_tokens=True)
    ntok = int(enc["input_ids"].shape[1])
    if ntok <= max_len:
        with torch.no_grad():
            logits = model(**enc).logits
        prob = torch.softmax(logits, dim=-1)[0]
        return float(prob[ai_idx])

    # 分块：按字符近似切分再编码，取最大风险
    all_ids = tok(text, add_special_tokens=False)["input_ids"]
    best = 0.0
    start = 0
    while start < len(all_ids):
        chunk = all_ids[start:start + max_len - 2]
        if not chunk:
            break
        ids = tok.build_inputs_with_special_tokens(chunk)
        t = torch.tensor([ids])
        with torch.no_grad():
            logits = model(input_ids=t, attention_mask=torch.ones_like(t)).logits
        prob = torch.softmax(logits, dim=-1)[0]
        best = max(best, float(prob[ai_idx]))
        if start + max_len - 2 >= len(all_ids):
            break
        start += stride
    return best


def analyze_file(path: str, lang: str | None = None, model_dir: str | None = None,
                 min_units: int | None = None) -> dict:
    """对文件逐段推理，返回结构化结果。"""
    text = load_text(path)
    if lang in (None, "auto"):
        lang = detect_lang(text)
    clean = strip_markdown(text)
    paras = split_paragraphs(clean, lang, min_units=min_units)

    resolved = resolve_model_dir(lang, model_dir)
    tok, model, id2label, ai_idx = load_detector(lang, resolved)

    rows = []
    for p in paras:
        ai = _score_chunks(tok, model, ai_idx, p)
        rows.append({"ai": round(ai, 6), "units": count_units(p, lang), "text": p})

    if not rows:
        return {"tool": f"model_{lang}", "lang": lang, "model_dir": str(resolved),
                "id2label": id2label, "doc_ai_rate": 0.0, "n_paragraphs": 0, "paras": []}

    tot = sum(r["units"] for r in rows) or 1
    doc_ai = sum(r["ai"] * r["units"] for r in rows) / tot
    rows.sort(key=lambda r: -r["ai"])
    n_hi = sum(1 for r in rows if r["ai"] >= 0.5)
    return {
        "tool": f"model_{lang}",
        "lang": lang,
        "model": MODEL_SPEC[lang][0],
        "model_dir": str(resolved),
        "id2label": id2label,
        "ai_index": ai_idx,
        "doc_ai_rate": round(doc_ai, 6),
        "n_paragraphs": len(rows),
        "total_units": tot,
        "n_paras_ge_50pct": n_hi,
        "verdict": ("低于 5% ✓" if doc_ai < 0.05 else
                    ("5~25% 需关注" if doc_ai < 0.25 else "≥25% 高危")),
        "paras": rows,
    }


def render_report(result: dict, path: str, topn: int = 15) -> str:
    lines = [pretty_banner(f"AIGC 模型检测报告（{result.get('model', result['tool'])}）"),
             f"文件：{os.path.basename(path)}   语种：{result['lang']}"]
    lines.append(f"模型目录：{result.get('model_dir')}")
    lines.append(f"id2label：{result.get('id2label')}")
    if result["n_paragraphs"] == 0:
        lines.append("无有效段落。")
        return "\n".join(lines)
    lines.append(f"段落：{result['n_paragraphs']}｜计数单位合计：{result['total_units']}")
    lines.append("")
    lines.append("★ 全文 AIGC 疑似率（按字数加权）：%.2f%%" % (result["doc_ai_rate"] * 100))
    lines.append(f"  判定（参照维普阈值 ≥25%% 高危）：{result['verdict']}")
    lines.append(f"  P(AI) ≥50%% 的段落：{result['n_paras_ge_50pct']} 段")
    lines.append("")
    lines.append(f"【风险最高的 {min(topn, result['n_paragraphs'])} 段】")
    for i, r in enumerate(result["paras"][:topn], 1):
        lines.append("-" * 78)
        lines.append(f"  #{i}  P(AI)={r['ai'] * 100:.2f}%   {r['units']} 单位")
        prev = r["text"].replace("\n", " ")
        lines.append("  " + prev[:180] + ("…" if len(prev) > 180 else ""))
    return "\n".join(lines)
