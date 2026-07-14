# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import posixpath
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET
from xml.dom import minidom

import pytest

from scripts import prose_to_epub as pe


JPEG_1PX = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP//////////////////////////////////////"
    "////////////////////////////////////////////2wBDAf//////////////////////"
    "////////////////////////////////////////////////////////////wAARCAABAAED"
    "ASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAX/xAAUEAEAAAAAAAAAAAAAAAAA"
    "AAAA/9oADAMBAAIQAxAAAAF//8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABBQJ/"
    "/8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAgBAwEBPwF//8QAFBEBAAAAAAAAAAAAAAAA"
    "AAAAAP/aAAgBAgEBPwF//8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQAGPwJ//8QA"
    "FBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPyF//9oADAMBAAIAAwAAABAf/8QAFBEB"
    "AAAAAAAAAAAAAAAAAAAAAP/aAAgBAwEBPxB//8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/a"
    "AAgBAgEBPxB//8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxB//9k="
)
PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8A"
    "AQUBAScY42YAAAAASUVORK5CYII="
)


def _run_main(monkeypatch, *argv: str) -> int:
    monkeypatch.setattr(sys, "argv", ["prose_to_epub.py", *argv])
    return pe.main()


def _prepare_failure(tmp_path: Path) -> tuple[Path, Path, set[str]]:
    md = tmp_path / "in.md"
    out = tmp_path / "out.epub"
    md.write_text("# Title\n\nBody\n", encoding="utf-8")
    out.write_bytes(b"old epub bytes")
    return md, out, {path.name for path in tmp_path.iterdir()}


def _assert_output_preserved(out: Path, initial_entries: set[str]) -> None:
    assert out.read_bytes() == b"old epub bytes"
    assert {path.name for path in out.parent.iterdir()} == initial_entries


def _cover_relationship(zf: zipfile.ZipFile) -> tuple[str, str]:
    members = set(zf.namelist())
    container = ET.fromstring(zf.read("META-INF/container.xml"))
    rootfile = next(node for node in container.iter() if node.tag.rsplit("}", 1)[-1] == "rootfile")
    opf_member = posixpath.normpath(rootfile.attrib["full-path"])
    opf = ET.fromstring(zf.read(opf_member))
    items = [node for node in opf.iter() if node.tag.rsplit("}", 1)[-1] == "item"]
    covers = [item for item in items if "cover-image" in item.attrib.get("properties", "").split()]
    assert len(covers) == 1
    cover_member = posixpath.normpath(
        posixpath.join(posixpath.dirname(opf_member), covers[0].attrib["href"])
    )
    assert cover_member in members

    item_by_id = {item.attrib["id"]: item for item in items}
    spine = next(node for node in opf.iter() if node.tag.rsplit("}", 1)[-1] == "spine")
    first_itemref = next(node for node in spine if node.tag.rsplit("}", 1)[-1] == "itemref")
    wrapper_item = item_by_id[first_itemref.attrib["idref"]]
    wrapper_member = posixpath.normpath(
        posixpath.join(posixpath.dirname(opf_member), wrapper_item.attrib["href"])
    )
    wrapper = ET.fromstring(zf.read(wrapper_member))
    image_uris = []
    for node in wrapper.iter():
        local_name = node.tag.rsplit("}", 1)[-1]
        if local_name == "img" and node.attrib.get("src"):
            image_uris.append(node.attrib["src"])
        elif local_name == "image":
            href = node.attrib.get("{http://www.w3.org/1999/xlink}href") or node.attrib.get("href")
            if href:
                image_uris.append(href)
    resolved = {
        posixpath.normpath(posixpath.join(posixpath.dirname(wrapper_member), uri))
        for uri in image_uris
    }
    assert cover_member in resolved
    return cover_member, wrapper_member


def test_first_title_uses_first_markdown_h1(tmp_path):
    md = tmp_path / "episode.md"
    md.write_text("intro\n# Main Title\n\nbody\n", encoding="utf-8")

    assert pe.first_title(md) == "Main Title"


def test_first_title_falls_back_to_filename_stem(tmp_path):
    md = tmp_path / "episode-name.md"
    md.write_text("intro\n## Not an h1\n", encoding="utf-8")

    assert pe.first_title(md) == "episode-name"


def test_missing_md_returns_two(tmp_path, monkeypatch):
    out = tmp_path / "out.epub"
    out.write_bytes(b"old epub bytes")
    initial_entries = {path.name for path in tmp_path.iterdir()}

    assert _run_main(
        monkeypatch, str(tmp_path / "missing.md"), "-o", str(out)
    ) == 2
    _assert_output_preserved(out, initial_entries)


def test_missing_pandoc_returns_three(tmp_path, monkeypatch):
    md, out, initial_entries = _prepare_failure(tmp_path)
    monkeypatch.setattr(pe.shutil, "which", lambda name: None)

    assert _run_main(monkeypatch, str(md), "-o", str(out)) == 3
    _assert_output_preserved(out, initial_entries)


def test_output_extension_guard_returns_two_without_subprocess(tmp_path, monkeypatch):
    md = tmp_path / "in.md"
    out = tmp_path / "out.md"
    md.write_text("# Title\n\nBody\n", encoding="utf-8")
    out.write_bytes(b"old epub bytes")
    initial_entries = {path.name for path in tmp_path.iterdir()}
    monkeypatch.setattr(pe.shutil, "which", lambda name: "/usr/local/bin/pandoc")
    monkeypatch.setattr(
        pe.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("subprocess called")),
    )

    assert _run_main(monkeypatch, str(md), "-o", str(out)) == 2
    _assert_output_preserved(out, initial_entries)


@pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc 未安裝")
def test_real_pandoc_generates_valid_epub_with_body_text(tmp_path, monkeypatch, capsys):
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
    with zipfile.ZipFile(out) as zf:
        opf_name = next(name for name in zf.namelist() if name.endswith("content.opf"))
        opf = ET.fromstring(zf.read(opf_name))
        assert not [
            node for node in opf.iter()
            if "cover-image" in node.attrib.get("properties", "").split()
        ]
    assert "cover=no" in capsys.readouterr().out


@pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc 未安裝")
@pytest.mark.parametrize(("name", "image"), [("cover.jpg", JPEG_1PX), ("cover.png", PNG_1PX)])
def test_real_pandoc_cover_relationship_chain(tmp_path, monkeypatch, capsys, name, image):
    md = tmp_path / "in.md"
    cover = tmp_path / name
    out = tmp_path / "out.epub"
    md.write_text("# Test Title\n\nParagraph body text.\n", encoding="utf-8")
    cover.write_bytes(image)
    monkeypatch.chdir(tmp_path)

    assert _run_main(monkeypatch, str(md), "-o", str(out), "--cover", cover.name) == 0
    with zipfile.ZipFile(out) as zf:
        cover_member, wrapper_member = _cover_relationship(zf)
        assert zf.read(cover_member) == image
        assert wrapper_member != cover_member
    assert "cover=yes" in capsys.readouterr().out


@pytest.mark.parametrize("case", ["missing", "webp", "mislabeled", "empty"])
def test_cover_input_failures_preserve_existing_output(tmp_path, monkeypatch, case):
    md, out, _ = _prepare_failure(tmp_path)
    cover = tmp_path / ("missing.jpg" if case == "missing" else "cover.webp")
    if case == "webp":
        cover.write_bytes(b"RIFF\x00\x00\x00\x00WEBP")
    elif case == "mislabeled":
        cover = tmp_path / "cover.jpg"
        cover.write_bytes(b"not a jpeg")
    elif case == "empty":
        cover = tmp_path / "cover.png"
        cover.write_bytes(b"")
    initial_entries = {path.name for path in tmp_path.iterdir()}
    monkeypatch.setattr(pe.shutil, "which", lambda name: "/usr/local/bin/pandoc")

    assert _run_main(
        monkeypatch, str(md), "-o", str(out), "--cover", str(cover)
    ) == 2
    _assert_output_preserved(out, initial_entries)


def test_pandoc_failure_preserves_existing_output(tmp_path, monkeypatch):
    md, out, initial_entries = _prepare_failure(tmp_path)
    monkeypatch.setattr(pe.shutil, "which", lambda name: "/usr/local/bin/pandoc")
    monkeypatch.setattr(
        pe.subprocess,
        "run",
        lambda cmd, **kwargs: subprocess.CompletedProcess(cmd, 9, "", "injected failure"),
    )

    assert _run_main(monkeypatch, str(md), "-o", str(out)) == 2
    _assert_output_preserved(out, initial_entries)


def test_malformed_epub_preserves_existing_output(tmp_path, monkeypatch):
    md, out, initial_entries = _prepare_failure(tmp_path)
    monkeypatch.setattr(pe.shutil, "which", lambda name: "/usr/local/bin/pandoc")

    def write_bad_epub(cmd, **kwargs):
        temp_out = Path(cmd[cmd.index("-o") + 1])
        with zipfile.ZipFile(temp_out, "w") as zf:
            zf.writestr("text/chapter.xhtml", b"<html><p>broken")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(pe.subprocess, "run", write_bad_epub)

    assert _run_main(monkeypatch, str(md), "-o", str(out)) == 2
    _assert_output_preserved(out, initial_entries)


def test_validator_exception_preserves_existing_output(tmp_path, monkeypatch):
    md, out, initial_entries = _prepare_failure(tmp_path)
    monkeypatch.setattr(pe.shutil, "which", lambda name: "/usr/local/bin/pandoc")

    def write_output(cmd, **kwargs):
        Path(cmd[cmd.index("-o") + 1]).write_bytes(b"candidate")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(pe.subprocess, "run", write_output)
    monkeypatch.setattr(
        pe,
        "_validate_epub",
        lambda *args: (_ for _ in ()).throw(RuntimeError("injected validator error")),
    )

    assert _run_main(monkeypatch, str(md), "-o", str(out)) == 2
    _assert_output_preserved(out, initial_entries)


@pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc 未安裝")
def test_replace_failure_preserves_existing_output(tmp_path, monkeypatch):
    md, out, initial_entries = _prepare_failure(tmp_path)
    monkeypatch.setattr(
        pe.os,
        "replace",
        lambda *args: (_ for _ in ()).throw(OSError("injected replace error")),
    )

    assert _run_main(monkeypatch, str(md), "-o", str(out)) == 2
    _assert_output_preserved(out, initial_entries)


@pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc 未安裝")
def test_cover_build_is_idempotent(tmp_path, monkeypatch):
    md = tmp_path / "in.md"
    cover = tmp_path / "cover.jpg"
    out = tmp_path / "out.epub"
    md.write_text("# Test Title\n\nParagraph body text.\n", encoding="utf-8")
    cover.write_bytes(JPEG_1PX)
    argv = (str(md), "-o", str(out), "--cover", str(cover))

    assert _run_main(monkeypatch, *argv) == 0
    assert _run_main(monkeypatch, *argv) == 0
    with zipfile.ZipFile(out) as zf:
        _cover_relationship(zf)
    assert {path.name for path in tmp_path.iterdir()} == {"in.md", "cover.jpg", "out.epub"}
