#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""srt_to_text — 把 SRT 抽成純文字（去序號/時間軸，合併文字行）。

speech-to-prose Step 2 的確定性步驟。輸出每個字幕區塊一行純文字到 stdout。
"""
from __future__ import annotations

import argparse
import re
import sys

_TIMECODE = "-->"


def srt_to_text(content: str) -> str:
    """從 SRT 內容抽出純文字，每個區塊一行（去序號與時間軸）。"""
    blocks = re.split(r"\n\s*\n+", content.strip())
    out: list[str] = []
    for block in blocks:
        lines = [ln for ln in block.splitlines() if ln.strip() != ""]
        # 找時間軸那一行；其後才是字幕文字。容忍時間軸前有/無序號行。
        tc_idx = next((i for i, ln in enumerate(lines) if _TIMECODE in ln), None)
        if tc_idx is None:
            continue
        text = "".join(lines[tc_idx + 1:]).strip()
        if text:
            out.append(text)
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Extract plain text from an SRT file.")
    ap.add_argument("srt", help="path to .srt file")
    args = ap.parse_args(argv)
    try:
        content = open(args.srt, encoding="utf-8").read()
    except FileNotFoundError:
        print(f"ERROR: file not found: {args.srt}", file=sys.stderr)
        return 1
    sys.stdout.write(srt_to_text(content) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
