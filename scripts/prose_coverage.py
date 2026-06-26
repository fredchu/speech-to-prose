#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""prose_coverage — 散文品質 gate。

散文輸出沒有 SRT 的條數/時間軸機械不變量，最大風險是「漏聽（omission）」與
「過度潤稿/加料（over-editing）」。這支腳本用中文字數 coverage ratio 當粗略護欄：

    ratio = prose 中文字數 / asr 中文字數

- ratio < LOW (0.6)  → WARN: 可能漏聽或過度摘要
- ratio > HIGH (1.3) → WARN: 可能加料或過度潤稿
- 否則              → OK（faithful 整理通常略低於 ASR，因刪語助詞）

只警示不阻斷，回傳 verdict 供呼叫端決定。
"""
from __future__ import annotations

import argparse
import json
import re
import sys

LOW = 0.6
HIGH = 1.3

# CJK 統一表意文字（不含標點/英數），用來算「實質字數」避免標點/英文干擾比值。
_HAN = re.compile(r"[一-鿿]")


def han_count(text: str) -> int:
    return len(_HAN.findall(text))


def assess(asr_text: str, prose_text: str, low: float = LOW, high: float = HIGH) -> dict:
    asr_n = han_count(asr_text)
    prose_n = han_count(prose_text)
    ratio = (prose_n / asr_n) if asr_n > 0 else 0.0
    if asr_n == 0:
        verdict, warn = "inconclusive", "ASR 文字無中文字，無法評估 coverage"
    elif ratio < low:
        verdict, warn = "warn_omission", f"ratio {ratio:.2f} < {low}：可能漏聽或過度摘要"
    elif ratio > high:
        verdict, warn = "warn_overedit", f"ratio {ratio:.2f} > {high}：可能加料或過度潤稿"
    else:
        verdict, warn = "ok", None
    return {
        "asr_han": asr_n,
        "prose_han": prose_n,
        "ratio": round(ratio, 4),
        "low": low,
        "high": high,
        "verdict": verdict,
        "warning": warn,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Prose coverage quality gate vs ASR text.")
    ap.add_argument("--asr", required=True, help="ASR 純文字檔（如 _breeze.txt）")
    ap.add_argument("--prose", required=True, help="整理後散文 .md")
    ap.add_argument("--low", type=float, default=LOW)
    ap.add_argument("--high", type=float, default=HIGH)
    ap.add_argument("--json", action="store_true", help="輸出 JSON")
    args = ap.parse_args(argv)

    try:
        asr = open(args.asr, encoding="utf-8").read()
        prose = open(args.prose, encoding="utf-8").read()
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    result = assess(asr, prose, args.low, args.high)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"ASR 中文字={result['asr_han']}  散文中文字={result['prose_han']}  "
              f"ratio={result['ratio']}  → {result['verdict']}")
        if result["warning"]:
            print(f"WARN: {result['warning']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
