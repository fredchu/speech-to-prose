#!/usr/bin/env python3
"""prose_to_epub.py — 由（通常已加時間戳的）speech-to-prose 散文 md 產生 epub。

包 pandoc；時間戳前綴是段落內文，pandoc 原樣保留，故 epub 每段開頭即帶時間戳
（結構與參考的 Allen 3Q2026 epub 一致：單章、<p> 段落）。

用法:
    prose_to_epub.py <md> [-o <out.epub>] [--title T] [--author A] [--cover <image>]

fail-closed: pandoc 不在 → exit 3；輸入或產出不良構 → exit 2。不 fallback、不靜默產壞檔。
"""
import argparse
import os
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile


def first_title(md_path):
    for line in open(md_path, encoding="utf-8"):
        m = re.match(r"^#\s+(.+?)\s*$", line)
        if m:
            return m.group(1)
    return os.path.splitext(os.path.basename(md_path))[0]


def _validate_epub(epub_path, expect_cover):
    with zipfile.ZipFile(epub_path) as z:
        members = set(z.namelist())
        xhtmls = [n for n in members if n.endswith((".xhtml", ".html"))]
        if not xhtmls:
            raise ValueError("xhtml 良構驗證：epub 內無 xhtml 內容檔")
        for name in xhtmls:
            try:
                ET.fromstring(z.read(name))
            except ET.ParseError as e:
                raise ValueError(f"xhtml 良構驗證失敗 ({name}): {e}") from e

        if not expect_cover:
            return len(xhtmls)

        try:
            container = ET.fromstring(z.read("META-INF/container.xml"))
            rootfile = next(
                node for node in container.iter()
                if node.tag.rsplit("}", 1)[-1] == "rootfile"
            )
            opf_href = rootfile.attrib["full-path"]
            opf_member = posixpath.normpath(opf_href)
            if opf_member not in members:
                raise ValueError(f"OPF member 不存在: {opf_member}")
        except (KeyError, StopIteration, ET.ParseError, ValueError) as e:
            raise ValueError(f"container.xml -> OPF 驗證失敗: {e}") from e

        try:
            opf = ET.fromstring(z.read(opf_member))
            manifest_items = [
                node for node in opf.iter()
                if node.tag.rsplit("}", 1)[-1] == "item"
            ]
            cover_items = [
                item for item in manifest_items
                if "cover-image" in item.attrib.get("properties", "").split()
            ]
            if len(cover_items) != 1:
                raise ValueError(f"cover-image item 數量須為 1，實際為 {len(cover_items)}")
            cover_href = cover_items[0].attrib["href"]
            cover_member = posixpath.normpath(
                posixpath.join(posixpath.dirname(opf_member), cover_href)
            )
            if cover_member not in members:
                raise ValueError(f"cover member 不存在: {cover_member}")
        except (KeyError, ET.ParseError, ValueError) as e:
            raise ValueError(f"OPF manifest cover-image 驗證失敗: {e}") from e

        try:
            item_by_id = {item.attrib["id"]: item for item in manifest_items if "id" in item.attrib}
            spine = next(
                node for node in opf.iter()
                if node.tag.rsplit("}", 1)[-1] == "spine"
            )
            first_itemref = next(
                node for node in spine
                if node.tag.rsplit("}", 1)[-1] == "itemref"
            )
            wrapper_item = item_by_id[first_itemref.attrib["idref"]]
            wrapper_member = posixpath.normpath(
                posixpath.join(posixpath.dirname(opf_member), wrapper_item.attrib["href"])
            )
            if wrapper_member not in members:
                raise ValueError(f"spine 首項 wrapper 不存在: {wrapper_member}")
        except (KeyError, StopIteration, ValueError) as e:
            raise ValueError(f"spine 首項 -> manifest wrapper 驗證失敗: {e}") from e

        try:
            wrapper = ET.fromstring(z.read(wrapper_member))
            image_uris = []
            for node in wrapper.iter():
                local_name = node.tag.rsplit("}", 1)[-1]
                if local_name == "img" and node.attrib.get("src"):
                    image_uris.append(node.attrib["src"])
                elif local_name == "image":
                    href = node.attrib.get("{http://www.w3.org/1999/xlink}href")
                    href = href or node.attrib.get("href")
                    if href:
                        image_uris.append(href)
            resolved_images = {
                posixpath.normpath(posixpath.join(posixpath.dirname(wrapper_member), uri))
                for uri in image_uris
            }
            if not image_uris:
                raise ValueError("wrapper 內找不到 img/src 或 svg image href")
            if cover_member not in resolved_images:
                raise ValueError(
                    f"wrapper image 未指向 cover member: {sorted(resolved_images)} != {cover_member}"
                )
        except (ET.ParseError, ValueError) as e:
            raise ValueError(f"wrapper XHTML -> cover member 驗證失敗: {e}") from e

    return len(xhtmls)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("md")
    ap.add_argument("-o", "--output")
    ap.add_argument("--title")
    ap.add_argument("--author", default="speech-to-prose")
    ap.add_argument("--cover")
    args = ap.parse_args()

    try:
        if not os.path.isfile(args.md):
            print(f"ERROR: md 不存在: {args.md}", file=sys.stderr)
            return 2

        cover = os.path.abspath(args.cover) if args.cover else None
        if cover:
            if not os.path.isfile(cover):
                print(f"ERROR: cover 不存在: {cover}", file=sys.stderr)
                return 2
            if os.path.getsize(cover) == 0:
                print(f"ERROR: cover 是空檔: {cover}", file=sys.stderr)
                return 2
            extension = os.path.splitext(cover)[1].lower()
            if extension not in (".jpg", ".jpeg", ".png"):
                print(
                    "ERROR: 本工具僅接受 jpg/png（目標閱讀器相容性），webp 請先轉檔: "
                    f"{cover}",
                    file=sys.stderr,
                )
                return 2
            with open(cover, "rb") as image:
                signature = image.read(8)
            valid_signature = (
                extension in (".jpg", ".jpeg") and signature.startswith(b"\xff\xd8\xff")
            ) or (
                extension == ".png" and signature.startswith(b"\x89PNG")
            )
            if not valid_signature:
                print(
                    f"ERROR: cover 格式簽名與副檔名不符（僅檢查 magic bytes）: {cover}",
                    file=sys.stderr,
                )
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

        temp_path = None
        try:
            fd, temp_path = tempfile.mkstemp(
                prefix=f".{os.path.basename(out)}.",
                suffix=".epub",
                dir=os.path.dirname(os.path.abspath(out)),
            )
            os.close(fd)
            cmd = [
                "pandoc", args.md, "-o", temp_path,
                "--metadata", f"title={title}",
                "--metadata", f"author={args.author}",
                "--metadata", "lang=zh-TW",
                "--toc",                 # 產生目錄
                "--split-level=2",       # 以 ## 章節標題切分成獨立章節（無 ## 時優雅退化為單章）
            ]
            if cover:
                cmd.append(f"--epub-cover-image={cover}")
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                print(f"ERROR: pandoc 失敗 (rc={proc.returncode})\n{proc.stderr}",
                      file=sys.stderr)
                return 2
            if not os.path.isfile(temp_path) or os.path.getsize(temp_path) == 0:
                print("ERROR: pandoc 宣稱成功但無輸出檔", file=sys.stderr)
                return 2

            try:
                xhtml_count = _validate_epub(temp_path, cover is not None)
            except Exception as e:  # noqa: BLE001 - validator failure must preserve output
                print(f"ERROR: epub 驗證失敗: {e}", file=sys.stderr)
                return 2

            os.replace(temp_path, out)
            temp_path = None
        finally:
            if temp_path is not None and os.path.exists(temp_path):
                os.unlink(temp_path)

        print(
            f"epub={out} title={title} xhtml_files={xhtml_count} "
            f"cover={'yes' if cover else 'no'} OK"
        )
        return 0
    except OSError as e:
        print(f"ERROR: I/O 失敗: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
