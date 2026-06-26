# speech-to-prose

> Turn a recording/video/YouTube into a **faithful Traditional-Chinese prose write-up** (not subtitles, no timecodes). A [Claude Code](https://claude.com/claude-code) skill.
> 把錄音／影片／YouTube 轉成**忠於原話的繁體中文整理短文**（不是字幕、沒有時間軸）。一個 [Claude Code](https://claude.com/claude-code) skill。

**[English](#english) · [繁體中文](#繁體中文)**

---

## English

### What it does

Sibling skill to [`srt`](https://github.com/fredchu/srt-skill). Where `srt` produces timecoded SRT subtitles through a heavy correction pipeline, `speech-to-prose` produces **flowing prose** that stays faithful to the speaker's original wording and paragraphs — light cleanup only (punctuation, ASR typo/English fixes, paragraphing, filler removal). No summarizing, no rewriting.

Pipeline: dual-ASR (Breeze + VibeVoice, cross-referenced for terms/English) → LLM prose integration (faithful fidelity) → prose coverage gate → `.md`.

### Why a separate skill

Prose has fewer mechanical invariants than SRT, so omission and over-editing are harder to detect. It needs its own quality gate (`scripts/prose_coverage.py`) and a pinned **fidelity mode** (default: faithful, not summary) so the LLM doesn't silently normalize away the original voice. It reuses `srt`'s ASR via a documented adapter contract instead of duplicating it.

### Requirements

- The [`srt`](https://github.com/fredchu/srt-skill) skill (provides the ASR backends: Breeze via `subtitle.sh`, VibeVoice). MLX / Apple Silicon for local ASR.
- Python 3, `ffmpeg`. See `srt`'s README for the ASR stack.

### Install

```bash
git clone <repo-url> ~/dev/speech-to-prose
ln -sfn ~/dev/speech-to-prose ~/.claude/skills/speech-to-prose   # Claude Code
ln -sfn ~/dev/speech-to-prose ~/.codex/skills/speech-to-prose    # Codex CLI
```

Invoke with phrases like 「整理成短文」「把錄音整理成文章」「不要做字幕」「最接近原話」.

### Tests

```bash
pytest test/
```

### License

MIT.

---

## 繁體中文

### 這是什麼

[`srt`](https://github.com/fredchu/srt-skill) 的姊妹技能。`srt` 產出帶時間軸的 SRT 字幕、走重型校正管線；`speech-to-prose` 產出**流暢散文**，忠於講者原始用詞與段落——只做輕度清理（補標點、修 ASR 錯字/英文、分段、刪語助詞），不摘要、不改寫。

流程：雙路 ASR（Breeze + VibeVoice，交叉比對術語/英文）→ LLM 散文整理（faithful 模式）→ 散文品質 gate → `.md`。

### 為什麼獨立成技能

散文沒有 SRT 的機械不變量，漏聽與過度潤稿更難偵測，所以需要自己的品質 gate（`scripts/prose_coverage.py`）與釘死的 **fidelity mode**（預設 faithful、非 summary），避免 LLM 默默正規化掉原始語感。ASR 透過文件化的 adapter contract 重用 `srt`，不複製程式碼。

### 需求

- [`srt`](https://github.com/fredchu/srt-skill) 技能（提供 ASR 後端：Breeze `subtitle.sh`、VibeVoice）。本地 ASR 需 MLX / Apple Silicon。
- Python 3、`ffmpeg`。ASR 技術棧見 `srt` 的 README。

### 安裝

```bash
git clone <repo-url> ~/dev/speech-to-prose
ln -sfn ~/dev/speech-to-prose ~/.claude/skills/speech-to-prose   # Claude Code
ln -sfn ~/dev/speech-to-prose ~/.codex/skills/speech-to-prose    # Codex CLI
```

觸發詞：「整理成短文」「把錄音整理成文章」「不要做字幕」「最接近原話」。

### 測試

```bash
pytest test/
```

### 授權

MIT。
