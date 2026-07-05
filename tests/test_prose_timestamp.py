# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import sys
from pathlib import Path

from scripts import prose_timestamp as pt


SRT_TEXT = """1
00:00:10,000 --> 00:00:15,000
Alpha beta gamma delta epsilon zeta eta theta.

2
00:00:20,000 --> 00:00:25,000
Iota kappa lambda mu nu xi omicron pi rho sigma.

3
00:00:30,000 --> 00:00:35,000
Tau upsilon phi chi psi omega final segment.
"""

PARA1 = "Alpha beta gamma delta epsilon zeta eta theta."
PARA2 = "Iota kappa lambda mu nu xi omicron pi rho sigma."
PARA3 = "Tau upsilon phi chi psi omega final segment."


def _write_srt(tmp_path: Path, text: str = SRT_TEXT) -> Path:
    path = tmp_path / "audio.srt"
    path.write_text(text, encoding="utf-8")
    return path


def _run_main(monkeypatch, srt: Path, md: Path, *extra: str) -> int:
    monkeypatch.setattr(sys, "argv", ["prose_timestamp.py", str(srt), str(md), *extra])
    return pt.main()


def _prefix_seconds(line: str) -> int:
    h, m, s = map(int, re.match(r"^\[(\d{2}):(\d{2}):(\d{2})\]", line).groups())
    return h * 3600 + m * 60 + s


def test_parse_srt_returns_start_seconds_and_joined_text(tmp_path):
    srt = tmp_path / "sample.srt"
    srt.write_text(
        """1
00:01:02,345 --> 00:01:04,000
Hello,
世界!
""",
        encoding="utf-8",
    )

    assert pt.parse_srt(srt) == [(62.345, "Hello,世界!")]


def test_norm_keeps_only_cjk_latin_and_digits():
    assert pt.norm("Hello, 世界! 123") == "Hello世界123"


def test_is_cjk_dominant():
    assert pt.is_cjk_dominant("中文內容abc") is True
    assert pt.is_cjk_dominant("Mostly English 中文") is False


def test_fmt_time_hms_and_ms():
    assert pt.fmt_time(65, "hms") == "00:01:05"
    assert pt.fmt_time(65, "ms") == "01:05"
    assert pt.fmt_time(6000, "ms") == "100:00"


def test_ts_prefix_re_strips_supported_prefixes_only():
    assert pt.TS_PREFIX_RE.sub("", "[00:01:02]　Text  ") == "Text  "
    assert pt.TS_PREFIX_RE.sub("", "[1:02]　Text  ") == "Text  "
    assert pt.TS_PREFIX_RE.sub("", "[100:00]　Text  ") == "Text  "
    assert pt.TS_PREFIX_RE.sub("", "No timestamp") == "No timestamp"


def test_collect_blocks_skips_non_body_regions():
    lines = [
        "---",
        "title: Hidden",
        "---",
        "# Heading",
        "",
        "first body line",
        "second body line",
        "",
        "> quote",
        "```",
        "code line",
        "```",
        "third body line",
    ]

    assert pt.collect_blocks(lines) == [[5, 6], [12]]


def test_main_adds_hms_prefixes_monotonically(tmp_path, monkeypatch):
    srt = _write_srt(tmp_path)
    md = tmp_path / "out.md"
    md.write_text(f"# Title\n\n{PARA1}\n\n{PARA2}\n\n{PARA3}\n", encoding="utf-8")

    assert _run_main(monkeypatch, srt, md) == 0

    stamped = md.read_text(encoding="utf-8").splitlines()
    body = [line for line in stamped if line.startswith("[")]
    assert body == [
        f"[00:00:10]　{PARA1}",
        f"[00:00:20]　{PARA2}",
        f"[00:00:30]　{PARA3}",
    ]
    assert [_prefix_seconds(line) for line in body] == sorted(_prefix_seconds(line) for line in body)


def test_main_is_idempotent_without_double_prefixes(tmp_path, monkeypatch):
    srt = _write_srt(tmp_path)
    md = tmp_path / "out.md"
    md.write_text(f"{PARA1}\n\n{PARA2}\n", encoding="utf-8")

    assert _run_main(monkeypatch, srt, md) == 0
    once = md.read_text(encoding="utf-8")
    assert _run_main(monkeypatch, srt, md) == 0

    assert md.read_text(encoding="utf-8") == once
    assert once.count("[00:00:10]") == 1


def test_main_fail_closed_does_not_write_when_unaligned(tmp_path, monkeypatch):
    srt = _write_srt(tmp_path)
    md = tmp_path / "out.md"
    original = "Completely unrelated body text with no shared anchor grams.\n"
    md.write_text(original, encoding="utf-8")

    assert _run_main(monkeypatch, srt, md) == 2

    assert md.read_text(encoding="utf-8") == original
    assert "[" not in md.read_text(encoding="utf-8")


def test_main_force_writes_even_when_unaligned(tmp_path, monkeypatch):
    srt = _write_srt(tmp_path)
    md = tmp_path / "out.md"
    md.write_text("Completely unrelated body text with no shared anchor grams.\n", encoding="utf-8")

    assert _run_main(monkeypatch, srt, md, "--force") == 0

    assert md.read_text(encoding="utf-8").startswith("[00:00:00]　")


def test_main_ms_format(tmp_path, monkeypatch):
    srt = _write_srt(tmp_path)
    md = tmp_path / "out.md"
    md.write_text(f"{PARA1}\n", encoding="utf-8")

    assert _run_main(monkeypatch, srt, md, "--fmt", "ms") == 0

    assert md.read_text(encoding="utf-8").startswith("[00:10]　")


def test_main_bilingual_stamps_only_source_line_and_adds_hard_break(tmp_path, monkeypatch):
    srt = _write_srt(tmp_path)
    md = tmp_path / "out.md"
    md.write_text(f"{PARA1}\n這是第一段翻譯。\n\n{PARA2}\n這是第二段翻譯。\n", encoding="utf-8")

    assert _run_main(monkeypatch, srt, md, "--bilingual") == 0

    lines = md.read_text(encoding="utf-8").splitlines()
    assert lines[0] == f"[00:00:10]　{PARA1}  "
    assert lines[1] == "這是第一段翻譯。"
    assert lines[3] == f"[00:00:20]　{PARA2}  "
    assert lines[4] == "這是第二段翻譯。"


def test_main_bilingual_skips_cjk_dominant_head(tmp_path, monkeypatch, capsys):
    srt = _write_srt(tmp_path)
    md = tmp_path / "out.md"
    md.write_text("中文為主的首行會被跳過\nEnglish translation line\n", encoding="utf-8")

    code = _run_main(monkeypatch, srt, md, "--bilingual")
    captured = capsys.readouterr()

    assert code == 2
    assert "WARN" in captured.err
    assert md.read_text(encoding="utf-8") == "中文為主的首行會被跳過\nEnglish translation line\n"


def test_main_skips_headings_blockquotes_and_code_fences(tmp_path, monkeypatch):
    srt = _write_srt(tmp_path)
    md = tmp_path / "out.md"
    md.write_text(
        f"# {PARA1}\n\n> {PARA2}\n\n```\n{PARA3}\n```\n\n{PARA1}\n",
        encoding="utf-8",
    )

    assert _run_main(monkeypatch, srt, md) == 0

    lines = md.read_text(encoding="utf-8").splitlines()
    assert lines[0] == f"# {PARA1}"
    assert lines[2] == f"> {PARA2}"
    assert lines[5] == PARA3
    assert lines[8] == f"[00:00:10]　{PARA1}"
