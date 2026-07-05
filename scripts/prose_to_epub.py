#!/usr/bin/env python3
"""prose_to_epub.py — 由（通常已加時間戳的）speech-to-prose 散文 md 產生 epub。

包 pandoc；時間戳前綴是段落內文，pandoc 原樣保留，故 epub 每段開頭即帶時間戳
（結構與參考的 Allen 3Q2026 epub 一致：單章、<p> 段落）。

用法:
    prose_to_epub.py <md> [-o <out.epub>] [--title T] [--author A]

fail-closed: pandoc 不在 → exit 3；產出不良構 → exit 2。不 fallback、不靜默產壞檔。
"""
import os
import re
import sys
import shutil
import argparse
import subprocess


def first_title(md_path):
    for line in open(md_path, encoding="utf-8"):
        m = re.match(r"^#\s+(.+?)\s*$", line)
        if m:
            return m.group(1)
    return os.path.splitext(os.path.basename(md_path))[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("md")
    ap.add_argument("-o", "--output")
    ap.add_argument("--title")
    ap.add_argument("--author", default="speech-to-prose")
    args = ap.parse_args()

    if not os.path.isfile(args.md):
        print(f"ERROR: md 不存在: {args.md}", file=sys.stderr)
        return 2
    if shutil.which("pandoc") is None:
        print("ERROR: 找不到 pandoc，無法產生 epub。請 `brew install pandoc`。",
              file=sys.stderr)
        return 3

    out = args.output or os.path.splitext(args.md)[0] + ".epub"
    if not out.lower().endswith(".epub"):
        print(f"ERROR: 輸出路徑須以 .epub 結尾（避免覆寫其他檔）: {out}",
              file=sys.stderr)
        return 2
    title = args.title or first_title(args.md)

    cmd = [
        "pandoc", args.md, "-o", out,
        "--metadata", f"title={title}",
        "--metadata", f"author={args.author}",
        "--metadata", "lang=zh-TW",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"ERROR: pandoc 失敗 (rc={proc.returncode})\n{proc.stderr}",
              file=sys.stderr)
        return 2
    if not os.path.isfile(out):
        print("ERROR: pandoc 宣稱成功但無輸出檔", file=sys.stderr)
        return 2

    # 驗 epub 內 xhtml 良構
    try:
        import zipfile
        import xml.dom.minidom as minidom
        with zipfile.ZipFile(out) as z:
            xhtmls = [n for n in z.namelist() if n.endswith((".xhtml", ".html"))]
            if not xhtmls:
                print("ERROR: epub 內無 xhtml 內容檔", file=sys.stderr)
                return 2
            for n in xhtmls:
                minidom.parseString(z.read(n))
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: epub 內 xhtml 不良構: {e}", file=sys.stderr)
        return 2

    print(f"epub={out} title={title} xhtml_files={len(xhtmls)} OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
