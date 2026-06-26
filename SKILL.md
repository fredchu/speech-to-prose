---
name: speech-to-prose
version: 0.1.0
description: |
  把音檔/影片/YouTube 轉成「忠於原話的繁體中文整理短文」（不是字幕、沒有時間軸）。
  跑雙路 ASR（Breeze + VibeVoice）交叉比對修正術語與英文，再整理成保留原始字句與段落、
  輕度清理的可讀短文，輸出 .md。當用戶說「整理成短文」「整理成文字稿」「把錄音整理成文章」
  「逐字整理」「不要做字幕」「最接近原話」「把這段語音整理成文章」，或給一個錄音/演講音檔、
  影片、YouTube 連結並表明要「可讀文字稿而非字幕」時使用。
  觸發詞範例：`整理成短文`、`整理成文字稿`、`把錄音整理成文章`、`不要做字幕`、`最接近原話`。
  不要用於：要帶時間軸的 SRT 字幕（用 srt）、要摘要重點（用 podcast-digest 或 polish）、
  已有文字只想潤稿（用 polish）、翻譯（用 translator 類）。
allowed-tools:
  - Bash
  - Read
  - Write
  - Agent
mutating: true
---

# speech-to-prose — 語音 → 忠於原話的整理短文

把講者的錄音整理成一篇**保留原始字句與段落**的繁體中文短文。與 `srt` 的根本差異：srt 產出帶時間軸的 SRT 字幕並走重型字幕校正管線；本技能產出**流暢散文（無時間軸、無 SRT 結構）**，核心是把雙路 ASR 融成忠於原話的可讀文章。

## Contract（保證）

- 輸出一份 `.md` 短文，**忠於講者原始用詞與語感**，只做輕度清理（補標點、修 ASR 錯字、修英文/術語、分段、刪純贅詞），**不摘要、不改寫語意、不正規化口語**。
- 用**雙路 ASR 交叉比對**（Breeze 主 + VibeVoice 輔）提高術語與英文正確率。
- 通過**散文品質 gate**（coverage 不足會警示）才算完成。
- 不產生字幕、不嵌字幕、不輸出時間軸。

## Fidelity Mode（必先確定，預設 faithful）

散文整理混了三種產品，務必先釘死模式（否則 LLM 會默默正規化、丟掉原話）：

| mode | 做什麼 | 何時 |
|------|--------|------|
| **faithful（預設）** | 保留原始字句與段落，只補標點/修錯字/修英文術語/分段/刪純語助詞 | 用戶說「最接近原話」「整理成短文」 |
| verbatim | 幾乎逐字，連語助詞都留 | 用戶要逐字記錄 |
| summary | 抓重點改寫 | 用戶明確要摘要（多半改用 podcast-digest） |

預設 faithful。除非用戶明說，不要往 summary 漂。

## ASR Adapter Contract（重用 srt 的 ASR，不複製）

本技能不自己實作 ASR，重用 `srt` 技能的腳本。依賴點（srt 變動時這裡要同步）：

```bash
SRT_SKILL_DIR="${SRT_SKILL_DIR:-$HOME/.claude/skills/srt}"
SUBTITLE_DIR="${SRT_SKILL_DIR}/scripts"
VV_SCRIPT="${SRT_VV_SCRIPT:-$HOME/dev/vibevoice-poc/vibevoice_asr.py}"
TERMS="${SRT_TERMS:-$HOME/Documents/For_Claude/scripts/subtitle/srt_correct/terms_austin_v2.txt}"
DATA_DIR="${SRT_DATA_DIR:-$HOME/Documents/For_Claude/scripts/subtitle}"
```

消費契約：Breeze 產 `<檔名>.srt`、VibeVoice 產 `<檔名>_vibevoice.srt`（+ `_vibevoice.json`）。本技能只取其純文字，不依賴時間軸。
> 中期目標：第二個 consumer 穩定後，把 ASR 抽成 srt/speech-to-prose 共用模組。現階段呼叫 + 契約即可。

## 執行步驟

### Step 0：解析輸入 + 工作目錄

判斷輸入：YouTube 連結 / 本地影片 / 本地音檔。建工作目錄（成品與中間檔不散落）：

```bash
WORK="${DATA_DIR}/prose/<簡短名稱>"   # 與 srt 的 media/ 分開
mkdir -p "$WORK"
# 本地檔 cp 進 WORK（不動原檔）；YouTube 用 srt 的 yt-dlp 慣例下載到 WORK
```

### Step 1：雙路 ASR（重用 srt）

短音檔（≤ 55 分鐘）：
```bash
cd "${SUBTITLE_DIR}" && ./subtitle.sh "$WORK/<檔名>" --breeze        # Breeze 主
cd "$WORK" && python3 "$VV_SCRIPT" "$WORK/<檔名>" --terms "$TERMS" --terms-max 50 --json \
    --output "$WORK/<檔名>_vibevoice.srt"                            # VibeVoice 輔（平行）
```
兩者可平行（Breeze + VV 是 srt 標準平行組合）。

**長音檔（> 55 分鐘）必須走切段**（mlx_audio 硬限 59 分，超過靜默 trim）：
```bash
python3 "${SUBTITLE_DIR}/vv_longaudio.py" "$WORK/<檔名>" --terms "$TERMS" --terms-max 50 \
    --output-json "$WORK/<檔名>_vibevoice.json" --output-srt "$WORK/<檔名>_vibevoice.srt"
```

### Step 2：抽純文字（deterministic）

```bash
SP_DIR="${SPEECH_TO_PROSE_DIR:-$HOME/.claude/skills/speech-to-prose}"
python3 "$SP_DIR/scripts/srt_to_text.py" "$WORK/<檔名>.srt"            > "$WORK/_breeze.txt"
python3 "$SP_DIR/scripts/srt_to_text.py" "$WORK/<檔名>_vibevoice.srt"  > "$WORK/_vv.txt"
```

### Step 3：LLM 散文整理（latent — 判斷，不是腳本）

把兩版純文字交給 LLM 整理成 faithful 短文。**規則**：
- 以 Breeze 版為骨幹（逐句較細），用 VV 版交叉比對**英文名詞、財經術語、同音字**（VV 標點較完整可參考）。
- **保留原始字句**：補標點、修 ASR 錯字、修英文拼寫、分段、刪純語助詞；不摘要、不改語意、不換句型。
- 講者明顯離題的插話（如旁白）可獨立成段保留，不刪。
- 多人對話：**不做 speaker diarization**；只有當 ASR 文字本身明顯有輪流（你問我答）才用分段呈現，否則輸出連續散文。
- 不確定的人名/作品/時事用語不要改（講者可能引用你不知道的東西）；ASR 嚴重聽不清處用〔註：…〕標記，不硬填。

**分派**：
- 短音檔（單段 ≤ ~300 行純文字）→ 主 session 直接整理。
- 長音檔 → 分段派 Sonnet subagent（每段帶前一段尾段做銜接），最後接起來；分段/銜接規則固定，不靠單次主 session 硬吞。

輸出寫到 `$WORK/<簡短名稱>_prose.md`（含標題行 + 來源/日期 meta）。

### Step 4：散文品質 gate（散文沒有 SRT 的機械不變量，需自己驗）

```bash
python3 "$SP_DIR/scripts/prose_coverage.py" --asr "$WORK/_breeze.txt" --prose "$WORK/<...>_prose.md" --json
```
檢查中文字數 coverage ratio（散文 / ASR）：
- ratio < 0.6 → WARN「可能漏聽或過度摘要」，回 Step 3 補。
- ratio > 1.3 → WARN「可能加料/過度潤稿」，回 Step 3 收。
- 0.6–1.3 → 通過（faithful 整理通常比 ASR 略短：刪語助詞）。
gate 只警示不阻斷，但 WARN 必須處理或向用戶說明。

### Step 5：交付 + 清理

- 把成品 `.md` 交付（預設複製到 `inbox/`，或用戶指定位置）。
- 清理中間檔（`_breeze.txt`/`_vv.txt`/ASR 暫存），保留原音檔與成品 .md。

## 完成後回報
- 成品 .md 路徑
- 輸入時長、ASR 引擎（Breeze + VV 是否都成功）、長音檔是否走切段
- coverage ratio + 任何 WARN
- fidelity mode

## Output（持久化位置宣告）

- 成品短文 `.md`：`${SRT_DATA_DIR}/prose/<簡短名稱>/<簡短名稱>_prose.md`，並複製一份到 `inbox/`（或用戶指定路徑）。
- 中間 ASR 產物：工作目錄內，Step 5 清理。

## 邊界與限制
- 純音檔跳過任何畫面/投影片處理（本技能本來就不做 caption）。
- 不做 speaker diarization（多人只在 ASR 明顯輪流時分段）。
- 極短音檔（< ~30 秒）避免過度分段與過度潤稿。
- 重用 srt ASR；srt 的 ASR 腳本/路徑變動時，依 Adapter Contract 同步。
- 是「忠於原話的整理」，不是逐字法律級 transcript、也不是摘要。
