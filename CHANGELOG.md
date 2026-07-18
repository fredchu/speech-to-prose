# Changelog

All notable changes to `speech-to-prose` are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versions track the `SKILL.md` frontmatter.

## 0.7.0 - 2026-07-18

### Features
- **Deterministic punctuation normalization (`scripts/punct_normalize.py` + mandatory
  Step 3.9).** Chinese prose gets fullwidth punctuation throughout; `--mode bilingual`
  normalizes only Chinese translation lines and leaves English source lines halfwidth.
  Only halfwidth punctuation adjacent to CJK characters is converted, so timestamps
  (`[00:12:34]`), URLs and pure-English sentences are naturally untouched; idempotent,
  skips code fences / blockquotes / YAML front matter. Motivated by a 4-segment
  subagent run where two segments drifted to halfwidth commas while two stayed
  fullwidth — a prompt contract alone does not hold, so the pipeline now backstops it
  with a script. The punctuation contract is also stated explicitly in the Step 3
  integration rules.

### Docs
- **Workspace hygiene: keep `prose/` media out of git.** The work directory
  accumulates source audio (~50–200 MB per item); if `${DATA_DIR}` lives inside a
  git repo, move the physical `prose/` directory outside the repo and symlink it
  back (skill paths unchanged), with a `.gitignore` entry as backstop.

### Docs (first real-world e2e of the bilingual English branch — 3 videos, 20 min ×2 + 1.5 h)
- **Chinese branch: `.wav` input is now explicitly forbidden.** `subtitle.sh` converts
  its input to a *same-named* 16 kHz wav, so a `.wav` input makes ffmpeg overwrite its
  own source in place and fail — and a wrapper script without `set -e` will still
  report success. Documented the m4a workaround and the "verify the .srt artifact
  exists" rule.
- **English-branch coverage gate documented.** `prose_coverage.py` counts Han
  characters only, so it is blind on the English branch; the interim gate is
  source-line English word count ÷ ASR word count with the same 0.6–1.3 thresholds
  (measured 0.94–1.00 across three videos). `--lang en` implementation pending.
- **Long-content segmented dispatch playbook.** Chapter-heading times must come from
  a deterministic word-offset → srt cumulative-word mapping, not text matching
  (after noun fixes the prose no longer matches the srt's mishearings; matching
  both misses and false-positives). Also: subagent note format pinned to fullwidth
  colon, and a mandatory tautological-note cleanup pass after applying noun fixes.

## 0.6.1 - 2026-07-14

### Fixes
- **Blank pages in Apple Books reading flow.** Books' page-turn view forces every
  linear spine document to start on a recto (right-hand) page, inserting blank
  versos — with pandoc's default front matter (title page + HTML TOC) the book
  opened onto consecutive blanks. Field-mapped page-by-page in Books, then
  verified via NotebookLM research (20 sources): the recto rule is reader-side
  and cannot be disabled from content for reflowable EPUBs, `linear="no"` has
  reports of being ignored by Books, and a `hidden` nav still renders as a blank
  page. Fix: `--epub-title-page=false` (title is on the cover and in metadata)
  and remove the nav itemref from the spine entirely — EPUB 3.3 requires nav in
  the manifest, not the spine, and Books builds its native TOC from the manifest.
  Reading flow is now cover → chapter 1 with a single unavoidable blank verso
  after the cover, same as a print book.

### Tests
- New assertions: no title_page in the archive; nav present in manifest with
  `properties="nav"` but absent from spine. The `.navtmp` rewrite honors the
  same artifact-safety contract (cleanup on all failure paths) — caught by the
  existing injected-failure matrix.

## 0.6.0 - 2026-07-14

### Features
- **EPUB output is now on by default.** Step 4.6 runs unless `--no-epub` (or the user
  explicitly asks for md only); chapter headings (`## [HH:MM:SS] 主題`) are upgraded
  from recommended to required so the default EPUB always gets a real TOC.
- **Cover image support (`--cover <img>`) in `scripts/prose_to_epub.py`.** The skill
  workflow fetches the YouTube thumbnail for video sources (`yt-dlp --write-thumbnail
  --convert-thumbnails jpg`) or the show/episode artwork for podcasts. Fixes the
  Apple Books first-open symptom: without a cover, the first spine item is pandoc's
  near-empty title page, which renders as a blank-looking first page; with a cover,
  Books opens on the cover image. Validation is fail-closed end to end:
  - jpg/png allowlist (reader-compatibility policy — WebP is a legal EPUB 3.3 core
    media type but conservative readers reject it) + magic-byte signature check;
  - post-build relationship-chain validation inside the archive: `container.xml` →
    OPF → the unique `properties="cover-image"` manifest item → first spine itemref →
    wrapper XHTML parsed as XML and its image URI resolved and compared exactly
    (no literal-path assumptions about pandoc internals);
  - the EPUB is built to a `mkstemp` sibling temp and atomically `os.replace`d only
    after validation passes — pandoc failures, validator exceptions, and replace
    failures all clean the temp and never clobber an existing output.
- Success line now reports `cover=yes/no`; top-level `OSError` converges to exit 2.

### Tests
- 6 → 17 tests: jpg/png relationship-chain assertions against real pandoc output,
  input-failure matrix (missing / webp / mislabeled / empty cover), injected pandoc
  failure, malformed-EPUB validator path, injected validator exception, injected
  `os.replace` failure — each asserting byte-for-byte preservation of pre-existing
  output and zero temp residue — plus idempotent double-build.

## 0.5.0 - 2026-07-06

### Features
- **Noun verification pass (Step 3.5).** Proper nouns that contradict their context
  (companies, tickers, people, jargon) are collected into a sidecar during prose
  integration, then verified through four evidence layers before any fix is applied:
  L0 whole-transcript phonetic cross-reference first (the same entity is usually
  mentioned more than once and mis-recognized differently each time), L1 local sources
  (speaker glossary / slide OCR terms), L2 neutral web search — **the model's guess is
  barred from queries** (hypothesis-driven search only confirms itself), L3 keep the
  `〔註：…〕` mark rather than guess. Confirmed fixes are applied per-occurrence
  (context-substring locating, never whole-file substitution) and written back to the
  speaker glossary with provenance comment lines.
- `scripts/noun_xref.py`: L0 phonetic-variant scanner. Latin-token fuzzy matching with
  Mandarin-accent confusion folding (v/w→b, catches VIAVI→"BIAB"), merged windows of
  fragmented tokens (catches "vr a vr"), weak Chinese char-overlap fallback. Recall over
  precision — output feeds an LLM judgment step. Stdlib only; tests in `scripts/tests/`.
- Sidecar contract: single JSON envelope per segment; long-audio segment subagents bind
  the sidecar to their returned prose text with SHA-256 (stale sidecars from retries are
  detected and dropped); sidecar content never enters `prose.md`, and Step 3.5 completes
  before the coverage gate and timestamping.

### Docs
- README (EN/zh): pipeline line + noun-verification section + test instructions.
- Field-validated on a 7-hour finance livestream: 138 unique flagged nouns, ~100
  applied fixes incl. KISS→KEYS, "one room"→萬潤, asyna→Synaptics; design converged
  through 5 adversarial review rounds + 2 implementation verify rounds (codex).

## 0.4.1 - 2026-07-05

### Fixes
- EPUB chapters: `prose_to_epub.py` now passes `--toc --split-level=2`, so `## ` section
  headings in the prose become navigable chapters with a table of contents. Prose with only
  a single `#` title and no `##` headings produced a chapterless single-file EPUB.
- SKILL.md: Step 3 now instructs inserting `## [HH:MM:SS] topic` section headings at topic
  boundaries for chapter navigation. Removed a duplicated Chinese dual-ASR block that had been
  left under the English branch.

## 0.4.0 - 2026-07-05

### Features
- **Bilingual output for non-Chinese audio (default).** English (or other non-Chinese)
  audio is transcribed with Whisper large-v3 and rendered as a source-on-top /
  Traditional-Chinese-below bilingual document, timestamped per paragraph.
- `prose_timestamp.py --bilingual`: aligns and timestamps only the source-language line
  of each block, leaves the translation line untouched, and adds a Markdown hard break so
  the pairing renders source-over-translation (incl. EPUB). CJK-dominant first line is
  treated as malformed structure and skipped (fail-safe).
- English ASR path documented with **mandatory anti-hallucination flags**
  (`--condition-on-previous-text False --hallucination-silence-threshold 2`) — the default
  Whisper decode can loop-hallucinate on trailing/silent audio and silently drop content.

### Docs
- SKILL.md: language-detection step, English branch, bilingual assembly, boundaries.
  README updated (English + 繁體中文).

## 0.3.0 - 2026-07-04

### Features
- **Per-paragraph timestamps (default on).** `scripts/prose_timestamp.py` aligns each
  paragraph to the ASR timeline via non-poisoning n-gram cluster anchoring + monotonic
  backbone + interpolation, prepending an approximate `[HH:MM:SS]`. Idempotent; fail-closed
  when anchor coverage is too low (`--min-coverage`, `--force`); `--fmt ms` for short clips.
- **Optional EPUB** (`scripts/prose_to_epub.py`, `--epub`): timestamped-paragraph e-book
  via pandoc, fail-closed when pandoc is missing or output is malformed.
- Skip code fences and YAML front matter when timestamping.

## 0.2.0

### Features
- `--local` prose mode: offline LLM integration (default gemma4:26b) with a deterministic,
  fail-closed runner that never silently falls back to the cloud.

## 0.1.0

### Features
- Initial release: recording/video/YouTube → faithful Traditional-Chinese prose, dual-ASR
  (Breeze + VibeVoice) cross-referencing, fidelity modes, and a prose coverage gate.
