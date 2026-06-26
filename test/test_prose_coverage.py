# -*- coding: utf-8 -*-
import importlib.util
import pathlib

_SPEC = importlib.util.spec_from_file_location(
    "prose_coverage",
    pathlib.Path(__file__).resolve().parent.parent / "scripts" / "prose_coverage.py",
)
pc = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(pc)


def test_han_count_ignores_punct_and_english():
    assert pc.han_count("你好，world！測試") == 4  # 你好測試


def test_ok_range():
    asr = "一" * 100
    prose = "一" * 90
    r = pc.assess(asr, prose)
    assert r["verdict"] == "ok"
    assert r["warning"] is None
    assert 0.6 <= r["ratio"] <= 1.3


def test_omission_warn():
    asr = "一" * 100
    prose = "一" * 50  # ratio 0.5 < 0.6
    r = pc.assess(asr, prose)
    assert r["verdict"] == "warn_omission"
    assert r["warning"]


def test_overedit_warn():
    asr = "一" * 100
    prose = "一" * 140  # ratio 1.4 > 1.3
    r = pc.assess(asr, prose)
    assert r["verdict"] == "warn_overedit"


def test_inconclusive_when_no_asr_han():
    r = pc.assess("...123 english only...", "一" * 10)
    assert r["verdict"] == "inconclusive"
    assert r["ratio"] == 0.0


def test_boundary_low_inclusive():
    # ratio exactly 0.6 should be OK (not < low)
    asr = "一" * 100
    prose = "一" * 60
    assert pc.assess(asr, prose)["verdict"] == "ok"


def test_custom_thresholds():
    asr = "一" * 100
    prose = "一" * 80
    r = pc.assess(asr, prose, low=0.85, high=1.3)
    assert r["verdict"] == "warn_omission"
