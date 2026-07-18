#!/usr/bin/env python3
"""標點正規化：中文散文全形標點；中英對照只動中文（譯文）行。

規則（保守、冪等）：
- 只轉換「與 CJK 相鄰」的半形標點（, : ; ? !），句點 . 需前一字元為 CJK 才轉 。
  → 時間戳 [00:12:34]、URL、英文句內標點（前後都是拉丁字元）天然不受影響。
- 轉換後若緊接一個空格且其後是 CJK，順手移除該空格（"argue, 跟" → "argue，跟"）。
- 跳過：code fence 區塊、`>` blockquote（meta 行含 URL）、YAML front matter。
- --mode zh（預設）：處理所有內文行。
- --mode bilingual：只處理 CJK 佔比 > 0.3 的行（譯文行），來源語行原樣保留。

用法：
    python3 punct_normalize.py <file.md> [--mode zh|bilingual] [--dry-run]
"""
import argparse
import re
import sys
from pathlib import Path

PUNCT_MAP = {",": "，", ":": "：", ";": "；", "?": "？", "!": "！"}
CJK = re.compile(r"[㐀-鿿豈-﫿]")


def is_cjk(ch: str) -> bool:
    return bool(ch) and bool(CJK.match(ch))


def cjk_ratio(line: str) -> float:
    chars = [c for c in line if not c.isspace()]
    if not chars:
        return 0.0
    return sum(1 for c in chars if is_cjk(c)) / len(chars)


def normalize_line(line: str) -> tuple[str, int]:
    out = []
    n = 0
    i = 0
    while i < len(line):
        ch = line[i]
        prev = out[-1] if out else ""
        nxt = line[i + 1] if i + 1 < len(line) else ""
        if ch in PUNCT_MAP and (is_cjk(prev) or is_cjk(nxt)):
            out.append(PUNCT_MAP[ch])
            n += 1
            # 全形標點後面的半形空格若接 CJK，一併移除
            if nxt == " " and i + 2 < len(line) and is_cjk(line[i + 2]):
                i += 1
        elif ch == "." and is_cjk(prev) and (not nxt or nxt in " \t" or is_cjk(nxt)):
            out.append("。")
            n += 1
            if nxt == " " and i + 2 < len(line) and is_cjk(line[i + 2]):
                i += 1
        else:
            out.append(ch)
        i += 1
    return "".join(out), n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--mode", choices=["zh", "bilingual"], default="zh")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    path = Path(args.file)
    lines = path.read_text(encoding="utf-8").splitlines()
    in_fence = False
    in_frontmatter = False
    total = 0
    out_lines = []
    for idx, line in enumerate(lines):
        if idx == 0 and line.strip() == "---":
            in_frontmatter = True
            out_lines.append(line)
            continue
        if in_frontmatter:
            if line.strip() == "---":
                in_frontmatter = False
            out_lines.append(line)
            continue
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out_lines.append(line)
            continue
        if in_fence or line.lstrip().startswith(">"):
            out_lines.append(line)
            continue
        if args.mode == "bilingual" and cjk_ratio(line) <= 0.3:
            out_lines.append(line)
            continue
        new, n = normalize_line(line)
        total += n
        out_lines.append(new)

    text = "\n".join(out_lines) + "\n"
    if args.dry_run:
        print(f"would convert {total} chars in {path}")
    else:
        path.write_text(text, encoding="utf-8")
        print(f"converted {total} chars in {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
