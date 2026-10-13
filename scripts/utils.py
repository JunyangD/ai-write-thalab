# -*- coding: utf-8 -*-
"""
utils.py —— 检测管线共用工具（文本抽取 / 分句 / 语言判定 / 统计）
=================================================================
职责：
  * load_text()         读取 .md / .txt / .docx（docx 用 zipfile 直读，位置无关）
  * strip_markdown()    去掉标题行、参考文献条目、表格/图注、分隔线
  * detect_lang()       粗判文档语种（zh / en），用于自动选择检测通路
  * split_sentences()   中英文分句
  * count_units()       中文按汉字计、英文按词计（供密度指标使用）
  * cv() / band()       统计小工具（变异系数 / 线性映射）

设计原则：
  1) **位置无关** —— 所有资源路径一律相对本文件（Path(__file__).resolve().parent）定位，
     绝不出现任何本机绝对路径（如 Windows 盘符路径）。
  2) **零重依赖** —— 本模块只依赖标准库；docx 读取用 zipfile + xml.etree，
     不经 python-docx / lxml（lxml itertext 会把同一段文本重复取到）。
  3) **双语** —— 中文与英文两套分句 / 计数规则。

诚实声明：维普 AIGC 模型闭源，本套工具复刻的是**检测维度**、输出**相对风险分**，
不等于维普数值，最终仍以维普官方检测为准。
"""
from __future__ import annotations

import os
import re
import sys
import zipfile
import statistics as st
import xml.etree.ElementTree as ET
from pathlib import Path

# --------------------------------------------------------------------------
# 路径定位（位置无关的核心）
# --------------------------------------------------------------------------
# 本文件所在目录 …/<包根>/scripts/
SCRIPTS_DIR = Path(__file__).resolve().parent
# 包根目录 <包根>（本文件的上上级目录）
PKG_ROOT = SCRIPTS_DIR.parent
# 默认模型目录 <包根>/models/
DEFAULT_MODEL_ROOT = PKG_ROOT / "models"

# 中文句末标点；英文句末标点单独处理
ZH_SENT_END = "。！？；!?"
# 中文标点集合（用于标点单一度）
ZH_PUNCT_RE = re.compile(r"[，。、；：！？“”‘’（）「」《》—…\.,;:!?\"'()\[\]<>]")

_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
_WORD_RE = re.compile(r"[A-Za-z]+(?:['\-][A-Za-z]+)*")


# --------------------------------------------------------------------------
# 文本读取
# --------------------------------------------------------------------------
def _docx_text(path: str | os.PathLike) -> str:
    """直读 .docx：解压 word/document.xml，按 <w:p> 段落收集 <w:t> 文本。

    注意：**只**遍历每个 <w:p> 下的 <w:t>，不要对整棵 XML 树用 itertext()，
    否则页眉/批注/域代码里的文本会被重复计入（原脚本踩过的坑）。
    """
    W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(path) as z:
        xml_bytes = z.read("word/document.xml")
    root = ET.fromstring(xml_bytes)
    paras = []
    for p in root.iter(W + "p"):
        # 段内文本片段：<w:t> 的文本 + <w:tab>/<w:br> 的空格占位
        buf = []
        for node in p.iter():
            tag = node.tag
            if tag == W + "t":
                buf.append(node.text or "")
            elif tag in (W + "tab", W + "br", W + "cr"):
                buf.append(" ")
        paras.append("".join(buf))
    return "\n".join(paras)


def load_text(path: str | os.PathLike) -> str:
    """读取稿件为纯文本。支持 .docx / .md / .txt（其余按 UTF-8 纯文本尝试）。"""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"找不到文件：{p}")
    if p.suffix.lower() == ".docx":
        return _docx_text(p)
    # 尝试常见编码
    for enc in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return p.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return p.read_text(encoding="utf-8", errors="replace")


# --------------------------------------------------------------------------
# Markdown / 结构化噪声清理
# --------------------------------------------------------------------------
def strip_markdown(text: str) -> str:
    """去掉标题、参考文献条目、表格 / 引用 / 图注、分隔线、<sup> 标签。"""
    text = re.sub(r"^#+\s.*$", "", text, flags=re.M)        # 标题
    text = re.sub(r"^\s*\[\d+\].*$", "", text, flags=re.M)  # 参考文献 [1]...
    text = re.sub(r"^\s*[|>].*$", "", text, flags=re.M)     # 表格 / 引用 / 图注
    text = re.sub(r"^\s*-{3,}\s*$", "", text, flags=re.M)   # 分隔线
    text = re.sub(r"^\s*\d+[\.、]\s", "", text, flags=re.M)  # 编号行前缀
    text = re.sub(r"<sup>.*?</sup>", "", text, flags=re.S)  # 上标标签
    text = re.sub(r"</?[a-zA-Z][^>]*>", "", text)           # 残留 HTML 标签
    return text


# --------------------------------------------------------------------------
# 语言判定
# --------------------------------------------------------------------------
def cjk_count(s: str) -> int:
    """统计汉字数量。"""
    return len(_CJK_RE.findall(s))


def word_count(s: str) -> int:
    """统计英文词数（连续字母串，含连字符/撇号）。"""
    return len(_WORD_RE.findall(s))


def count_units(s: str, lang: str) -> int:
    """按语种计数：中文=汉字数，英文=词数。用于密度指标的分母。"""
    return cjk_count(s) if lang == "zh" else word_count(s)


def detect_lang(text: str) -> str:
    """粗判语种：CJK 字符占「CJK+字母」总量的比例 ≥0.20 判为中文，否则英文。"""
    cjk = cjk_count(text)
    latin = len(re.findall(r"[A-Za-z]", text))
    total = cjk + latin
    if total == 0:
        return "zh"
    return "zh" if (cjk / total) >= 0.20 else "en"


# --------------------------------------------------------------------------
# 分句 / 分段
# --------------------------------------------------------------------------
def split_sentences(text: str, lang: str = "zh") -> list[str]:
    """分句。

    中文：按句末标点 。！？；!? 切分（保留标点）。
    英文：按 . ! ? ; 后跟空白切分，避免把小数 / 缩写切碎（对常见缩写做保护）。
    """
    if lang == "zh":
        sents, cur = [], ""
        for ch in text:
            cur += ch
            if ch in ZH_SENT_END:
                s = cur.strip()
                if s:
                    sents.append(s)
                cur = ""
        if cur.strip():
            sents.append(cur.strip())
        return sents

    # 英文：先保护常见缩写与小数（把句点临时换成占位符 █，避免被误切）
    sentinel = "\u2588"
    protected = text
    for abbr in ("e.g.", "i.e.", "et al.", "vs.", "Fig.", "No.", "Dr.", "Mr.", "Ms.", "etc."):
        protected = protected.replace(abbr, abbr.replace(".", sentinel))
    # 小数：1.5 → 1█5
    protected = re.sub(r"(\d)\.(\d)", lambda m: m.group(1) + sentinel + m.group(2), protected)
    parts = re.split(r"(?<=[.!?;])\s+", protected)
    out = []
    for p in parts:
        p = p.replace("\u2588", ".").strip()
        if p:
            out.append(p)
    return out


def split_paragraphs(text: str, lang: str = "zh", min_units: int | None = None) -> list[str]:
    """按空行/换行切段，并按最小计数阈值过滤（过短的标题/残句不计入）。

    min_units 默认：中文 40 汉字、英文 25 词。
    """
    if min_units is None:
        min_units = 40 if lang == "zh" else 25
    raw = re.split(r"\n\s*\n|\n", text)
    paras = []
    for p in raw:
        p = p.strip()
        if not p:
            continue
        if count_units(p, lang) >= min_units:
            paras.append(p)
    return paras


# --------------------------------------------------------------------------
# 统计小工具
# --------------------------------------------------------------------------
def cv(xs) -> float:
    """变异系数 = 总体标准差 / 均值。句长越均匀（CV 越低）越像 AI。"""
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return 0.0
    m = st.mean(xs)
    return (st.pstdev(xs) / m) if m else 0.0


def band(v: float, lo: float, hi: float) -> float:
    """把 v 从 lo(安全线) 到 hi(高危线) 线性映射到 0~1 并裁剪。"""
    if hi == lo:
        return 0.0
    return max(0.0, min(1.0, (v - lo) / (hi - lo)))


def safe_mean(xs) -> float:
    xs = [x for x in xs if x is not None]
    return st.mean(xs) if xs else 0.0


def pretty_banner(title: str, width: int = 78) -> str:
    return "=" * width + "\n" + title + "\n" + "=" * width


if __name__ == "__main__":
    # 自检：解析常驻路径
    print("SCRIPTS_DIR      =", SCRIPTS_DIR)
    print("PKG_ROOT         =", PKG_ROOT)
    print("DEFAULT_MODEL_ROOT =", DEFAULT_MODEL_ROOT)
    print("用法：本模块供 fingerprint.py / model_*.py / detox_pipeline.py 导入。")
