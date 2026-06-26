# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import pytest

from scripts import prose_local


def _files(tmp_path: Path) -> dict[str, Path]:
    paths = {
        "breeze": tmp_path / "breeze.txt",
        "vv": tmp_path / "vv.txt",
        "system": tmp_path / "system.txt",
        "out": tmp_path / "out.md",
    }
    paths["breeze"].write_text("一" * 100, encoding="utf-8")
    paths["vv"].write_text("一" * 100, encoding="utf-8")
    paths["system"].write_text("faithful", encoding="utf-8")
    return paths


def _argv(paths: dict[str, Path], *extra: str) -> list[str]:
    return [
        "--breeze", str(paths["breeze"]),
        "--vv", str(paths["vv"]),
        "--system", str(paths["system"]),
        "--out", str(paths["out"]),
        *extra,
    ]


def _patch_preflight_http(monkeypatch):
    def fake_get(url, timeout=5):
        if url == prose_local.OLLAMA_TAGS_URL:
            return {"models": [{"name": "gemma4:26b"}]}
        if url == prose_local.OLLAMA_PS_URL:
            return {"models": [{"name": "gemma4:26b"}]}
        raise AssertionError(url)

    monkeypatch.setattr(prose_local, "http_get_json", fake_get)


def _patch_chat(monkeypatch, result):
    monkeypatch.setattr(prose_local, "ollama_chat", lambda **kwargs: result)


def test_normal_text_writes_output_and_exits_zero(tmp_path, monkeypatch):
    paths = _files(tmp_path)
    _patch_preflight_http(monkeypatch)
    _patch_chat(monkeypatch, {"text": "一" * 90, "eval_count": 20, "eval_tps": 3.2, "wall_s": 1.5, "error": None})

    code = prose_local.main(_argv(paths))

    assert code == 0
    assert paths["out"].read_text(encoding="utf-8") == "一" * 90


def test_infer_error_exits_two(tmp_path, monkeypatch):
    paths = _files(tmp_path)
    _patch_preflight_http(monkeypatch)
    _patch_chat(monkeypatch, {"text": "", "eval_count": 0, "eval_tps": 0, "wall_s": 0, "error": "boom"})

    assert prose_local.main(_argv(paths)) == 2


def test_empty_text_exits_two(tmp_path, monkeypatch):
    paths = _files(tmp_path)
    _patch_preflight_http(monkeypatch)
    _patch_chat(monkeypatch, {"text": "  \n", "eval_count": 1, "eval_tps": 1, "wall_s": 1, "error": None})

    assert prose_local.main(_argv(paths)) == 2


def test_eval_count_at_max_tokens_exits_two(tmp_path, monkeypatch):
    paths = _files(tmp_path)
    _patch_preflight_http(monkeypatch)
    _patch_chat(monkeypatch, {"text": "一" * 90, "eval_count": 10, "eval_tps": 1, "wall_s": 1, "error": None})

    assert prose_local.main(_argv(paths, "--max-tokens", "10")) == 2


def test_long_breeze_exits_four_before_preflight(tmp_path, monkeypatch):
    paths = _files(tmp_path)
    paths["breeze"].write_text("一\n二\n三\n", encoding="utf-8")
    monkeypatch.setattr(prose_local, "http_get_json", lambda url, timeout=5: (_ for _ in ()).throw(AssertionError("http called")))

    assert prose_local.main(_argv(paths, "--max-asr-lines", "2")) == 4


def test_low_coverage_writes_rejected_not_final(tmp_path, monkeypatch):
    paths = _files(tmp_path)
    paths["out"].write_text("STALE 上次成品", encoding="utf-8")  # 預置 stale，才有鑑別力
    _patch_preflight_http(monkeypatch)
    _patch_chat(monkeypatch, {"text": "一" * 20, "eval_count": 5, "eval_tps": 1, "wall_s": 1, "error": None})

    code = prose_local.main(_argv(paths))

    assert code == 2
    # 失敗稿不得污染最終 out 路徑（stale 已被清），只落 .rejected debug 檔
    assert not paths["out"].exists()
    assert Path(str(paths["out"]) + ".rejected").read_text(encoding="utf-8") == "一" * 20


def test_long_audio_clears_stale_out(tmp_path, monkeypatch):
    paths = _files(tmp_path)
    paths["breeze"].write_text("一\n二\n三\n", encoding="utf-8")
    paths["out"].write_text("STALE 上次成品", encoding="utf-8")  # early-failure 也該清
    monkeypatch.setattr(
        prose_local, "http_get_json",
        lambda url, timeout=5: (_ for _ in ()).throw(AssertionError("http called")),
    )

    assert prose_local.main(_argv(paths, "--max-asr-lines", "2")) == 4
    assert not paths["out"].exists()


def test_preflight_ollama_down_exits_three(tmp_path, monkeypatch):
    paths = _files(tmp_path)

    def boom(url, timeout=5):
        raise OSError("connection refused")

    monkeypatch.setattr(prose_local, "http_get_json", boom)
    assert prose_local.main(_argv(paths)) == 3


def test_preflight_model_missing_exits_three(tmp_path, monkeypatch):
    paths = _files(tmp_path)
    monkeypatch.setattr(prose_local, "http_get_json", lambda url, timeout=5: {"models": [{"name": "other-model"}]})
    assert prose_local.main(_argv(paths)) == 3


def test_wrapper_load_failure_exits_three(tmp_path, monkeypatch):
    paths = _files(tmp_path)
    _patch_preflight_http(monkeypatch)

    def boom(**kwargs):
        raise prose_local.WrapperLoadError("wrapper not found")

    monkeypatch.setattr(prose_local, "ollama_chat", boom)
    assert prose_local.main(_argv(paths)) == 3


def test_infer_exception_maps_to_exit_two(tmp_path, monkeypatch):
    paths = _files(tmp_path)
    _patch_preflight_http(monkeypatch)

    def boom(**kwargs):
        raise ValueError("non-JSON body from ollama")

    monkeypatch.setattr(prose_local, "ollama_chat", boom)
    assert prose_local.main(_argv(paths)) == 2


def test_code_fence_stripped_and_exits_zero(tmp_path, monkeypatch):
    paths = _files(tmp_path)
    _patch_preflight_http(monkeypatch)
    fenced = "```markdown\n" + "一" * 90 + "\n```"
    _patch_chat(monkeypatch, {"text": fenced, "eval_count": 20, "eval_tps": 1, "wall_s": 1, "error": None})

    code = prose_local.main(_argv(paths))

    assert code == 0
    assert paths["out"].read_text(encoding="utf-8") == "一" * 90


def test_long_breeze_by_han_exits_four(tmp_path, monkeypatch):
    paths = _files(tmp_path)
    paths["breeze"].write_text("一" * 100, encoding="utf-8")  # 單行但 100 漢字
    monkeypatch.setattr(
        prose_local, "http_get_json",
        lambda url, timeout=5: (_ for _ in ()).throw(AssertionError("http called")),
    )
    assert prose_local.main(_argv(paths, "--max-asr-han", "50")) == 4


def test_partial_fence_not_corrupted(tmp_path, monkeypatch):
    paths = _files(tmp_path)
    _patch_preflight_http(monkeypatch)
    # 以 code block 開頭但非整篇包裹 → strip_code_fences 不得破壞
    body = "```python\nx=1\n```\n後面是正文" + "一" * 90
    _patch_chat(monkeypatch, {"text": body, "eval_count": 20, "eval_tps": 1, "wall_s": 1, "error": None})

    code = prose_local.main(_argv(paths))

    assert code == 0
    assert paths["out"].read_text(encoding="utf-8") == body


def test_load_ollama_chat_missing_wrapper_raises(tmp_path, monkeypatch):
    # SRT_SKILL_DIR 指向空目錄 → wrapper 不存在 → 真實 load 失敗拋 WrapperLoadError
    monkeypatch.setenv("SRT_SKILL_DIR", str(tmp_path))
    with pytest.raises(prose_local.WrapperLoadError):
        prose_local.load_ollama_chat()
