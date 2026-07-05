# -*- coding: utf-8 -*-
from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from xml.dom import minidom

import pytest

from scripts import prose_to_epub as pe


def _run_main(monkeypatch, *argv: str) -> int:
    monkeypatch.setattr(sys, "argv", ["prose_to_epub.py", *argv])
    return pe.main()


def test_first_title_uses_first_markdown_h1(tmp_path):
    md = tmp_path / "episode.md"
    md.write_text("intro\n# Main Title\n\nbody\n", encoding="utf-8")

    assert pe.first_title(md) == "Main Title"


def test_first_title_falls_back_to_filename_stem(tmp_path):
    md = tmp_path / "episode-name.md"
    md.write_text("intro\n## Not an h1\n", encoding="utf-8")

    assert pe.first_title(md) == "episode-name"


def test_missing_md_returns_two(tmp_path, monkeypatch):
    assert _run_main(monkeypatch, str(tmp_path / "missing.md")) == 2


def test_missing_pandoc_returns_three(tmp_path, monkeypatch):
    md = tmp_path / "in.md"
    md.write_text("# Title\n\nBody\n", encoding="utf-8")
    monkeypatch.setattr(pe.shutil, "which", lambda name: None)

    assert _run_main(monkeypatch, str(md)) == 3


def test_output_extension_guard_returns_two_without_subprocess(tmp_path, monkeypatch):
    md = tmp_path / "in.md"
    md.write_text("# Title\n\nBody\n", encoding="utf-8")
    monkeypatch.setattr(pe.shutil, "which", lambda name: "/usr/local/bin/pandoc")
    monkeypatch.setattr(
        pe.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("subprocess called")),
    )

    assert _run_main(monkeypatch, str(md), "-o", str(tmp_path / "out.md")) == 2


@pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc 未安裝")
def test_real_pandoc_generates_valid_epub_with_body_text(tmp_path, monkeypatch):
    md = tmp_path / "in.md"
    out = tmp_path / "out.epub"
    md.write_text("# Test Title\n\nParagraph body text.\n", encoding="utf-8")

    assert _run_main(monkeypatch, str(md), "-o", str(out)) == 0
    assert out.is_file()

    with zipfile.ZipFile(out) as zf:
        xhtml_names = [name for name in zf.namelist() if name.endswith((".xhtml", ".html"))]
        assert xhtml_names
        docs = [minidom.parseString(zf.read(name)) for name in xhtml_names]
        text = "\n".join(node.toxml() for doc in docs for node in doc.getElementsByTagName("p"))

    assert "Paragraph body text." in text
