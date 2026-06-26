#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, cast

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import prose_coverage


DEFAULT_MODEL = "gemma4:26b"
OLLAMA_TAGS_URL = "http://localhost:11434/api/tags"
OLLAMA_PS_URL = "http://localhost:11434/api/ps"

# ponytail: warning-only charset catches common Simplified output; upgrade to OpenCC
# if this becomes a blocking validation gate.
SIMPLIFIED_CHARS = set(
    "这们说为对会个国过时来样发经学体开关现见实长"
    "简转语话请让读写听后里"
)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local Ollama prose runner for speech-to-prose.")
    parser.add_argument("--breeze", required=True, help="Breeze ASR plain text path")
    parser.add_argument("--vv", required=True, help="VibeVoice ASR plain text path")
    parser.add_argument("--system", required=True, help="System prompt path")
    parser.add_argument("--out", required=True, help="Output .md path")
    parser.add_argument(
        "--model",
        default=os.environ.get("SPEECH_TO_PROSE_LOCAL_MODEL", DEFAULT_MODEL),
        help="Ollama model name",
    )
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--max-asr-lines", type=int, default=300)
    parser.add_argument(
        "--max-asr-han", type=int, default=6000,
        help="長音檔兜底：Breeze 漢字數超過此值也判長音檔（防單段無換行逃過 line gate）",
    )
    parser.add_argument("--json", action="store_true", help="Reserved for future use")
    return parser.parse_args(argv)


def http_get_json(url: str, timeout: int = 5) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _model_matches(wanted: str, found: str) -> bool:
    return wanted == found or wanted.removesuffix(":latest") == found.removesuffix(":latest")


def _model_names(tags: dict) -> list[str]:
    return [m.get("name", "") for m in tags.get("models", []) if isinstance(m, dict)]


def preflight(model: str, stderr=sys.stderr) -> int:
    try:
        tags = http_get_json(OLLAMA_TAGS_URL, timeout=5)
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        print(f"OLLAMA_DOWN: {exc}", file=stderr)
        return 3

    names = _model_names(tags)
    if not any(_model_matches(model, name) for name in names):
        print(f"MODEL_MISSING: {model}", file=stderr)
        return 3

    try:
        ps = http_get_json(OLLAMA_PS_URL, timeout=5)
        loaded = ", ".join(_model_names(ps)) or "-"
        print(f"OLLAMA_PS: {loaded}", file=stderr)
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        print(f"OLLAMA_PS: unavailable ({exc})", file=stderr)
    return 0


class WrapperLoadError(Exception):
    """srt ollama_llm.py wrapper 缺檔 / 無法 import / 形狀不對 → 映射到 exit 3。"""


def load_ollama_chat() -> Callable[..., dict]:
    skill_dir = Path(os.environ.get("SRT_SKILL_DIR", "~/.claude/skills/srt")).expanduser()
    wrapper = skill_dir / "scripts" / "srt_correct" / "ollama_llm.py"
    if not wrapper.exists():
        raise WrapperLoadError(f"wrapper not found: {wrapper}")
    spec = importlib.util.spec_from_file_location("srt_ollama_llm", wrapper)
    if spec is None or spec.loader is None:
        raise WrapperLoadError(f"cannot create import spec: {wrapper}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - 任何 import-time 失敗都當 load error
        raise WrapperLoadError(f"wrapper import failed: {exc}") from exc
    fn = getattr(module, "ollama_chat", None)
    if not callable(fn):
        raise WrapperLoadError("wrapper missing callable ollama_chat()")
    return cast("Callable[..., dict]", fn)


def ollama_chat(**kwargs) -> dict:
    return load_ollama_chat()(**kwargs)


def build_user_input(breeze: str, vv: str) -> str:
    return (
        "【第一版 ASR — Breeze（逐句較細，當骨幹）】\n"
        f"{breeze}\n\n"
        "【第二版 ASR — VibeVoice（標點較完整，當交叉參考）】\n"
        f"{vv}\n\n"
        "請依系統指示，把上面同一段語音的兩版 ASR 整理成一篇忠於原話的繁體中文短文。"
    )


def simplified_chars(text: str) -> str:
    return "".join(sorted(set(text) & SIMPLIFIED_CHARS))


def strip_code_fences(text: str) -> str:
    """只在『整篇被 ``` 完整包裹』時剝除首尾 fence；部分 fence（內文含 code block）原樣保留。"""
    t = text.strip()
    lines = t.split("\n")
    if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return text


def write_output(path: str, text: str) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")


def run(args: argparse.Namespace, stderr=sys.stderr) -> int:
    # 本次重新產生此音檔成品：最先清既有 out，任何後續失敗（含 input/long-audio/preflight）
    # 都不留 stale 成品 → exit code 為唯一真相源。成功路徑最後重寫 out。
    Path(args.out).unlink(missing_ok=True)
    try:
        breeze = Path(args.breeze).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"INPUT_ERROR: {exc}", file=stderr)
        return 2

    line_count = len(breeze.splitlines())
    han_count = sum(1 for c in breeze if 0x4E00 <= ord(c) <= 0x9FFF)
    if line_count > args.max_asr_lines or han_count > args.max_asr_han:
        print(
            f"LONG_AUDIO: {line_count} lines / {han_count} han > limit, local v1 unsupported",
            file=stderr,
        )
        return 4

    try:
        vv = Path(args.vv).read_text(encoding="utf-8")
        system = Path(args.system).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"INPUT_ERROR: {exc}", file=stderr)
        return 2

    code = preflight(args.model, stderr=stderr)
    if code:
        return code

    try:
        result = ollama_chat(
            system=system,
            user=build_user_input(breeze, vv),
            model=args.model,
            max_tokens=args.max_tokens,
            temperature=0.1,
        )
    except WrapperLoadError as exc:
        print(f"WRAPPER_LOAD_FAIL: {exc}", file=stderr)
        return 3
    except Exception as exc:  # noqa: BLE001 - 推論期任何崩潰（HTTP 非 JSON 等）→ fallback code
        print(f"INFER_EXCEPTION: {exc}", file=stderr)
        return 2

    if result.get("error"):
        print(f"INFER_ERROR: {result['error']}", file=stderr)
        return 2

    text = strip_code_fences(result.get("text", "")).strip()
    if not text:
        print("EMPTY_OUTPUT", file=stderr)
        return 2

    eval_count = int(result.get("eval_count") or 0)
    if eval_count >= args.max_tokens:
        print(f"TRUNCATED: eval_count={eval_count} >= max_tokens={args.max_tokens}", file=stderr)
        return 2

    coverage = prose_coverage.assess(breeze, text)
    ratio = coverage["ratio"]
    if ratio < 0.6 or ratio > 1.3:
        rejected = f"{args.out}.rejected"
        write_output(rejected, text)
        print(f"COVERAGE_FAIL: ratio={ratio} (rejected draft saved to {rejected})", file=stderr)
        return 2

    # 簡體偵測為粗字表，warning-only（不 block）：誤判風險高、且 gemma4 對拍實測簡體 0。
    # 要升成硬性 gate 需換 OpenCC s2t 純字級偵測（留 v2）。
    chars = simplified_chars(text)
    if chars:
        print(f"SIMPLIFIED_WARN: {chars}", file=stderr)

    write_output(args.out, text)
    print(
        f"OK: chars={len(text)} ratio={ratio} wall={result.get('wall_s', 0)}s "
        f"tps={result.get('eval_tps', 0)} model={args.model}",
        file=stderr,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    return run(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
