# -*- coding: utf-8 -*-
"""E2E smoke：完整確定性鏈 SRT → 純文字 → coverage gate。

不打外部 ASR（那是 srt 技能的整合測試範疇）；本測試驗證 speech-to-prose 自己擁有的
兩個確定性步驟串起來能跑、且 coverage gate 對「忠實 vs 過度壓縮」給出正確判定。
"""
import importlib.util
import pathlib

_ROOT = pathlib.Path(__file__).resolve().parent.parent / "scripts"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _ROOT / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


srt_to_text = _load("srt_to_text")
prose_coverage = _load("prose_coverage")

_SRT = """1
00:00:01,000 --> 00:00:03,000
我們先理一下選擇權的邏輯順序

2
00:00:03,000 --> 00:00:05,000
散戶沒有現貨不能裸賣買權

3
00:00:05,000 --> 00:00:07,000
所以造市商在買權端通常是買方
"""


def test_e2e_pipeline_faithful_passes_gate():
    # Step 2: SRT → 純文字
    asr_text = srt_to_text.srt_to_text(_SRT)
    assert "造市商" in asr_text and "\n" in asr_text
    # Step 3 (模擬 faithful 整理：保留原話、只補標點分段)
    faithful = (
        "我們先理一下選擇權的邏輯順序。散戶沒有現貨，不能裸賣買權，"
        "所以造市商在買權端通常是買方。"
    )
    # Step 4: coverage gate → faithful 應在 ok 區間
    r = prose_coverage.assess(asr_text, faithful)
    assert r["verdict"] == "ok", r


def test_e2e_pipeline_oversummarized_warns():
    asr_text = srt_to_text.srt_to_text(_SRT)
    summary = "講選擇權邏輯。"  # 過度壓縮
    r = prose_coverage.assess(asr_text, summary)
    assert r["verdict"] == "warn_omission"
