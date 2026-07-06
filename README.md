# speech-to-prose

> Turn a recording/video/YouTube into a **faithful Traditional-Chinese prose write-up** — not SRT subtitles, but with a per-paragraph approximate timestamp, optional timestamped EPUB, and automatic **bilingual (source + Chinese) output for non-Chinese audio**. A [Claude Code](https://claude.com/claude-code) skill.
> 把錄音／影片／YouTube 轉成**忠於原話的繁體中文整理短文**——不是 SRT 字幕，但每段開頭帶大概時間戳、可選輸出帶時間戳的 EPUB，英文（非中文）影音則**自動產中英對照版**。一個 [Claude Code](https://claude.com/claude-code) skill。

**[English](#english) · [繁體中文](#繁體中文)**

---

## English

### What it does

Sibling skill to [`srt`](https://github.com/fredchu/srt-skill). Where `srt` produces per-cue timecoded SRT subtitles through a heavy correction pipeline, `speech-to-prose` produces **flowing prose** that stays faithful to the speaker's original wording and paragraphs — light cleanup only (punctuation, ASR typo/English fixes, paragraphing, filler removal). No summarizing, no rewriting.

Pipeline (Chinese audio): dual-ASR (Breeze + VibeVoice, cross-referenced for terms/English) → LLM prose integration (faithful fidelity) → noun verification pass → prose coverage gate → per-paragraph timestamp alignment → `.md` (optional EPUB).

**Per-paragraph timestamps** (default on): each paragraph is prefixed with an approximate `[HH:MM:SS]` aligned to the ASR timeline via monotonic n-gram anchoring + interpolation (`scripts/prose_timestamp.py`), so you can jump back to the video. Fail-closed when alignment coverage is too low.

**Noun verification pass** (Step 3.5): proper nouns that contradict their context (companies, tickers, people, jargon) are collected during integration, then verified through four evidence layers — whole-transcript phonetic cross-reference first (`scripts/noun_xref.py`: same entity is usually mentioned more than once and mis-recognized differently each time), local sources, then neutral web search with the model's guess barred from queries (hypothesis-driven search confirms itself). Unresolved nouns stay marked `〔註：…〕` rather than guessed. Confirmed fixes are applied per-occurrence and fed back into the speaker glossary.

**Optional EPUB** (`--epub`): a timestamped-paragraph e-book via pandoc (`scripts/prose_to_epub.py`).

**Bilingual for non-Chinese audio** (default): English (or other non-Chinese) audio is transcribed with Whisper large-v3 (mandatory anti-hallucination flags) and rendered as a **source-on-top / Traditional-Chinese-below** bilingual document, timestamped per paragraph (`prose_timestamp.py --bilingual`). This is for personal study; don't redistribute copyrighted material.

### Why a separate skill

Prose has fewer mechanical invariants than SRT, so omission and over-editing are harder to detect. It needs its own quality gate (`scripts/prose_coverage.py`) and a pinned **fidelity mode** (default: faithful, not summary) so the LLM doesn't silently normalize away the original voice. It reuses `srt`'s ASR via a documented adapter contract instead of duplicating it.

### Requirements

- The [`srt`](https://github.com/fredchu/srt-skill) skill (provides the ASR backends: Breeze via `subtitle.sh`, VibeVoice). MLX / Apple Silicon for local ASR.
- Python 3, `ffmpeg`. See `srt`'s README for the ASR stack.
- `mlx-whisper` (Whisper large-v3) for the English/bilingual branch.
- `pandoc` — optional, only for `--epub`.

### Install

```bash
git clone <repo-url> ~/dev/speech-to-prose
ln -sfn ~/dev/speech-to-prose ~/.claude/skills/speech-to-prose   # Claude Code
ln -sfn ~/dev/speech-to-prose ~/.codex/skills/speech-to-prose    # Codex CLI
```

Invoke with phrases like 「整理成短文」「把錄音整理成文章」「不要做字幕」「最接近原話」.

### Tests

```bash
pytest test/                              # prose pipeline tests
python3 scripts/tests/test_noun_xref.py   # noun cross-reference scanner (stdlib, no pytest)
```

### License

MIT.

---

## 繁體中文

### 這是什麼

[`srt`](https://github.com/fredchu/srt-skill) 的姊妹技能。`srt` 產出帶逐句時間軸的 SRT 字幕、走重型校正管線；`speech-to-prose` 產出**流暢散文**，忠於講者原始用詞與段落——只做輕度清理（補標點、修 ASR 錯字/英文、分段、刪語助詞），不摘要、不改寫。

流程（中文影音）：雙路 ASR（Breeze + VibeVoice，交叉比對術語/英文）→ LLM 散文整理（faithful 模式）→ 名詞查證 pass → 散文品質 gate → 段落時間戳對齊 → `.md`（可選 EPUB）。

**段落時間戳**（預設開）：每段開頭加對齊 ASR 時間軸的大概 `[HH:MM:SS]`，用單調 n-gram 叢集錨定 + 內插（`scripts/prose_timestamp.py`）方便跳回影片；覆蓋率過低時 fail-closed 不寫。

**名詞查證 pass**（Step 3.5）：整理時收集「與上下文矛盾的專有名詞」（公司、ticker、人名、術語），走四層查證——全文音近變體交叉比對優先（`scripts/noun_xref.py`：同一實體通常被提到多次、每次錯法不同）、本地資源、再來才是中性網路搜尋（**禁止把猜測放進 query**，帶假設搜尋只會自我證實）。查不動的保留〔註：…〕不硬改；確認的修正逐處套用並回寫講者術語表。

**可選 EPUB**（`--epub`）：由帶時間戳的散文經 pandoc 產電子書（`scripts/prose_to_epub.py`）。

**英文（非中文）影音預設產中英對照版**：用 Whisper large-v3（**反幻覺旗標必帶**）辨識，排成**來源語在上、繁中翻譯在下**、每段帶時間戳的對照文件（`prose_timestamp.py --bilingual`）。屬個人研讀用途，勿散布受著作權保護內容。

### 為什麼獨立成技能

散文沒有 SRT 的機械不變量，漏聽與過度潤稿更難偵測，所以需要自己的品質 gate（`scripts/prose_coverage.py`）與釘死的 **fidelity mode**（預設 faithful、非 summary），避免 LLM 默默正規化掉原始語感。ASR 透過文件化的 adapter contract 重用 `srt`，不複製程式碼。

### 需求

- [`srt`](https://github.com/fredchu/srt-skill) 技能（提供 ASR 後端：Breeze `subtitle.sh`、VibeVoice）。本地 ASR 需 MLX / Apple Silicon。
- Python 3、`ffmpeg`。ASR 技術棧見 `srt` 的 README。
- `mlx-whisper`（Whisper large-v3）：英文／中英對照分支需要。
- `pandoc`：可選，只有 `--epub` 才需要。

### 安裝

```bash
git clone <repo-url> ~/dev/speech-to-prose
ln -sfn ~/dev/speech-to-prose ~/.claude/skills/speech-to-prose   # Claude Code
ln -sfn ~/dev/speech-to-prose ~/.codex/skills/speech-to-prose    # Codex CLI
```

觸發詞：「整理成短文」「把錄音整理成文章」「不要做字幕」「最接近原話」。

### 測試

```bash
pytest test/                              # 散文管線測試
python3 scripts/tests/test_noun_xref.py   # 名詞交叉比對掃描器（純標準庫，不需 pytest）
```

### 授權

MIT。
