# -*- coding: utf-8 -*-
import importlib.util
import pathlib

_SPEC = importlib.util.spec_from_file_location(
    "srt_to_text",
    pathlib.Path(__file__).resolve().parent.parent / "scripts" / "srt_to_text.py",
)
srt_to_text = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(srt_to_text)
fn = srt_to_text.srt_to_text


def test_basic_block():
    srt = "1\n00:00:01,000 --> 00:00:02,000\n你好世界\n"
    assert fn(srt) == "你好世界"


def test_multiple_blocks_one_line_each():
    srt = (
        "1\n00:00:01,000 --> 00:00:02,000\n第一句\n\n"
        "2\n00:00:02,000 --> 00:00:03,000\n第二句\n"
    )
    assert fn(srt) == "第一句\n第二句"


def test_multiline_text_joined():
    srt = "1\n00:00:01,000 --> 00:00:02,000\n上行\n下行\n"
    assert fn(srt) == "上行下行"


def test_block_without_leading_index():
    # 容忍沒有序號行（時間軸在第一行）
    srt = "00:00:01,000 --> 00:00:02,000\n沒有序號\n"
    assert fn(srt) == "沒有序號"


def test_block_with_no_timecode_skipped():
    srt = "這是雜訊沒有時間軸\n\n1\n00:00:01,000 --> 00:00:02,000\n有效\n"
    assert fn(srt) == "有效"


def test_empty_text_block_dropped():
    srt = "1\n00:00:01,000 --> 00:00:02,000\n\n\n2\n00:00:02,000 --> 00:00:03,000\n有字\n"
    assert fn(srt) == "有字"


def test_empty_input():
    assert fn("") == ""


def test_extra_blank_lines_between_blocks():
    srt = "1\n00:00:01,000 --> 00:00:02,000\nA\n\n\n\n2\n00:00:02,000 --> 00:00:03,000\nB\n"
    assert fn(srt) == "A\nB"
