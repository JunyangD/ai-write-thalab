# -*- coding: utf-8 -*-
"""
download_models.py —— 从 hf-mirror 一键下载中/英文 AI 检测模型权重
================================================================================
为什么不用 huggingface_hub？
  本机用 huggingface_hub.snapshot_download 拉大权重会被 sandbox 的 safe-delete 拦截
  （报 SHFileOperationW 0x2）。因此改为**直接 HTTP 直取** hf-mirror 的 resolve 链接：
      https://hf-mirror.com/<repo>/resolve/main/<file>
  下载到本地后不经过 hf_hub 的临时文件/软链逻辑，规避该问题。

下载目标（位置无关）：
  默认 <包根>/models/<目录名>/   可用 --dest 覆盖。

模型：
  zh : Hello-SimpleAI/chatgpt-detector-roberta-chinese   → models/chatgpt-detector-roberta-chinese
  en : Hello-SimpleAI/chatgpt-detector-roberta           → models/chatgpt-detector-roberta

用法：
  python download_models.py                 # 下载中英两个模型
  python download_models.py --lang zh       # 只下中文
  python download_models.py --lang en       # 只下英文
  python download_models.py --dest <目标目录>                          # 指定目录
  python download_models.py --repo other/repo --dest <目标目录>        # 自定义仓库（如备选检测器）
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import DEFAULT_MODEL_ROOT  # noqa: E402

HF_ENDPOINT = os.environ.get("HF_ENDPOINT", "https://hf-mirror.com")

# 语种 → (HF 仓库名, 默认目录名)
REPOS = {
    "zh": ("Hello-SimpleAI/chatgpt-detector-roberta-chinese", "chatgpt-detector-roberta-chinese"),
    "en": ("Hello-SimpleAI/chatgpt-detector-roberta", "chatgpt-detector-roberta"),
}

# 兜底文件清单（当 API 取不到 siblings 时使用）
KNOWN_FILES = {
    "zh": ["config.json", "pytorch_model.bin", "tokenizer.json",
           "tokenizer_config.json", "special_tokens_map.json", "vocab.txt"],
    "en": ["config.json", "pytorch_model.bin", "vocab.json", "merges.txt",
           "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json"],
}


def _api_file_list(repo: str) -> list[str] | None:
    """通过 hf-mirror 的 models API 取仓库文件清单（更稳，不依赖硬编码）。"""
    url = f"{HF_ENDPOINT}/api/models/{repo}"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
        files = [s["rfilename"] for s in data.get("siblings", [])]
        # 只要权重/分词所需文件
        keep = [f for f in files
                if not f.startswith(".")
                and not f.lower().endswith((".md", ".gitattributes", ".onnx", ".h5", ".msgpack", ".tflite"))
                and (f.endswith((".json", ".bin", ".safetensors", ".txt")) or f.endswith("merges.txt"))]
        return keep or None
    except Exception:
        return None


def _remote_size(url: str) -> int:
    """HEAD 请求取远端文件大小（跟随重定向）；失败返回 0。"""
    try:
        req = urllib.request.Request(url, method="HEAD",
                                     headers={"User-Agent": "aigc-detector-downloader/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return int(r.headers.get("Content-Length", 0) or 0)
    except Exception:
        return 0


def _curl() -> str | None:
    return shutil.which("curl")


def _download_curl(url: str, dest: Path, retries: int = 6) -> bool:
    """优先用 curl：支持断点续传（-C -）与自动重试，应对大文件镜像较慢/断流。"""
    curl = _curl()
    if not curl:
        return False
    cmd = [curl, "-L", "-C", "-", "-f", "--connect-timeout", "30",
           "--retry", str(retries), "--retry-delay", "3", "--retry-all-errors",
           "-o", str(dest), url]
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"    [curl 退出码 {e.returncode}] {dest.name}")
        return False


def _download_urllib(url: str, dest: Path, retries: int = 4) -> bool:
    """urllib 回退：按现有字节数做 Range 续传，断流后重试。"""
    for attempt in range(1, retries + 1):
        have = dest.stat().st_size if dest.exists() else 0
        headers = {"User-Agent": "aigc-detector-downloader/1.0"}
        if have:
            headers["Range"] = f"bytes={have}-"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                mode = "ab" if (have and r.status == 206) else "wb"
                if mode == "wb":
                    have = 0
                with open(dest, mode) as f:
                    while True:
                        chunk = r.read(1024 * 256)
                        if not chunk:
                            break
                        f.write(chunk)
                        have += len(chunk)
            return True
        except Exception as e:
            print(f"    [urllib 第 {attempt}/{retries} 次中断：{e}]")
            time.sleep(2 * attempt)
    return False


def _download(url: str, dest: Path) -> bool:
    """下载单文件：优先 curl 续传，回退 urllib 续传；完成后校验大小。"""
    expected = _remote_size(url)
    if dest.exists() and expected and dest.stat().st_size == expected:
        print(f"  [跳过] {dest.name} 已存在（{expected:,} B）")
        return True

    print(f"  下载 {dest.name} ...（约 {expected / 1e6:.0f} MB）" if expected
          else f"  下载 {dest.name} ...")
    ok = _download_curl(url, dest)
    if not ok or (expected and dest.exists() and dest.stat().st_size != expected):
        # curl 不可用或未完成 → urllib 续传
        ok = _download_urllib(url, dest)

    if ok and dest.exists():
        got = dest.stat().st_size
        if expected and got != expected:
            print(f"  [警告] {dest.name} 大小不符：{got:,} != {expected:,}")
            return False
        print(f"  [完成] {dest.name}  ({got:,} B)")
        return True
    print(f"  [失败] {dest.name}")
    return False


def download_repo(repo: str, dest_dir: Path, lang: str | None = None) -> int:
    dest_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n=== 下载 {repo}  →  {dest_dir} ===")
    files = _api_file_list(repo) or (KNOWN_FILES.get(lang) if lang else None)
    if not files:
        print("  [错误] 无法获取仓库文件清单（API 不可达且无兜底清单）")
        return 1
    print(f"  文件清单（{len(files)}）：{', '.join(files)}")
    ok = 0
    for fn in files:
        url = f"{HF_ENDPOINT}/{repo}/resolve/main/{fn}"
        if _download(url, dest_dir / fn):
            ok += 1
    print(f"  完成 {ok}/{len(files)} 个文件。")
    return 0 if ok else 1


def build_argparser():
    ap = argparse.ArgumentParser(
        description="从 hf-mirror 直取下载中/英文 AI 检测模型权重（规避 hf_hub 的 safe-delete 问题）。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--lang", choices=["zh", "en", "all"], default="all", help="下载哪个模型（默认 all）")
    ap.add_argument("--dest", default=None, help="目标根目录（默认 …/models）")
    ap.add_argument("--repo", default=None, help="自定义 HF 仓库名（配合 --dest 使用）")
    return ap


def main(argv=None):
    args = build_argparser().parse_args(argv)
    root = Path(args.dest).expanduser().resolve() if args.dest else DEFAULT_MODEL_ROOT

    if args.repo:
        return download_repo(args.repo, root / args.repo.split("/")[-1], lang=None)

    rc = 0
    langs = ["zh", "en"] if args.lang == "all" else [args.lang]
    for lg in langs:
        repo, name = REPOS[lg]
        rc |= download_repo(repo, root / name, lang=lg)
    print("\n全部完成。模型已就位于:", root)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
