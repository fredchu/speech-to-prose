---
name: speech-to-prose
version: 0.7.0
description: |
  把音檔/影片/YouTube 轉成「忠於原話的繁體中文整理短文」（不是 SRT 字幕；
  每段開頭帶對齊 ASR 的大概時間戳，預設同時輸出段落帶時間戳的 epub 電子書）。
  中文影音跑雙路 ASR（Breeze + VibeVoice）整理成繁中散文；**英文（非中文）影音預設產「中英對照版」**
  （英文在上、繁中翻譯在下，段落帶時間戳）。輸出 .md，保留原始字句與段落、輕度清理。
  當用戶說「整理成短文」「整理成文字稿」「把錄音整理成文章」「逐字整理」「不要做字幕」「最接近原話」
  「把這段語音整理成文章」「中英對照」「英文影片做對照」，或給一個錄音/演講音檔、
  影片、YouTube 連結並表明要「可讀文字稿而非字幕」時使用。
  觸發詞範例：`整理成短文`、`整理成文字稿`、`把錄音整理成文章`、`不要做字幕`、`最接近原話`、`中英對照`。
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

把講者的錄音整理成一篇**保留原始字句與段落**的繁體中文短文。與 `srt` 的根本差異：srt 產出帶逐句時間軸的 SRT 字幕並走重型字幕校正管線；本技能產出**流暢散文（非 SRT 結構）**，核心是把雙路 ASR 融成忠於原話的可讀文章——每段開頭附**段落級大概時間戳**方便對照影片（非逐句字幕時間軸）。

## Contract（保證）

- 輸出一份 `.md` 短文，**忠於講者原始用詞與語感**，只做輕度清理（補標點、修 ASR 錯字、修英文/術語、分段、刪純贅詞），**不摘要、不改寫語意、不正規化口語**。
- 中文影音用**雙路 ASR 交叉比對**（Breeze 主 + VibeVoice 輔）提高術語與英文正確率。
- **英文（非中文）影音預設產「中英對照版」**：英文（來源語）在上、繁中忠實翻譯在下，每段帶時間戳（見 Step 0.5 / 英文分支）。用戶明確只要純中文可覆寫。
- 通過**散文品質 gate**（coverage 不足會警示）才算完成。
- **不確定的專有名詞經「內部交叉比對＋有界查證」後才修正**（Step 3.5）：查證未收斂者保留〔註：…〕標記，絕不憑單一外部搜尋結果自信改詞。
- **每段開頭帶對齊 ASR 時間軸的 `[HH:MM:SS]` 大概時間戳（預設開）**；**預設另輸出「段落帶時間戳」的 epub 電子書**（`--no-epub` 或用戶明說只要 md 才關）。
- 不產生 SRT 字幕、不嵌字幕。時間戳是**段落級大概值**（非逐句時間軸、非字幕）。

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

> ⚠️ 工作目錄會累積原音檔等大型媒體檔。若 `${DATA_DIR}` 位於 git repo 內，建議把 `prose/` 實體目錄放到 repo 外、原位置以 symlink 連回（skill 路徑不變、媒體不進 git），並在 repo 的 `.gitignore` 加上該路徑作為 backstop。若你的環境已這樣設置，不要把 symlink「修正」回真目錄。

### Step 0.5：語言偵測 → 決定分支

- **YouTube**：`yt-dlp --skip-download --print "%(language)s" "<url>"`。
- **本地檔**：無法從 metadata 判斷時，跑 mlx_whisper 前 30 秒自動偵測，或直接聽/看內容判斷。
- **語言為 `zh*` → 中文分支**（Step 1 雙路 ASR，原流程，產繁中散文）。
- **語言為非中文（en 等）→ 英文/對照分支**（走下方「英文分支」，**預設產中英對照版**）。用戶明確只要純中文散文才不做對照。

### Step 1：雙路 ASR（中文分支，重用 srt）

短音檔（≤ 55 分鐘）：
```bash
cd "${SUBTITLE_DIR}" && ./subtitle.sh "$WORK/<檔名>" --breeze        # Breeze 主
cd "$WORK" && python3 "$VV_SCRIPT" "$WORK/<檔名>" --terms "$TERMS" --terms-max 50 --json \
    --output "$WORK/<檔名>_vibevoice.srt"                            # VibeVoice 輔（平行）
```
兩者可平行（Breeze + VV 是 srt 標準平行組合）。

⚠️ **輸入檔不可以是 .wav**：subtitle.sh 會把輸入轉成**同名** 16kHz wav，.wav 輸入等於 ffmpeg 原地覆寫自己、直接失敗（2026-07-16 實測，且失敗後外層腳本沒 set -e 會假裝成功——確認產物 srt 存在才算數）。來源是 wav 先轉 m4a（`ffmpeg -i in.wav -c:a aac in.m4a`），YouTube 下載直接用 `-x --audio-format m4a`。

**長音檔（> 55 分鐘）必須走切段**（mlx_audio 硬限 59 分，超過靜默 trim）：
```bash
python3 "${SUBTITLE_DIR}/vv_longaudio.py" "$WORK/<檔名>" --terms "$TERMS" --terms-max 50 \
    --output-json "$WORK/<檔名>_vibevoice.json" --output-srt "$WORK/<檔名>_vibevoice.srt"
```

### Step 1（英文分支）：英文 ASR（單路 Whisper，反幻覺旗標必帶）

英文用 mlx_whisper large-v3（**不跑 Breeze/VV，那是中文雙路**）。**反幻覺旗標必帶**——實測預設會在尾段/靜音處進入重複幻覺迴圈、吃掉大段內容：

```bash
export PATH="$HOME/.local/bin:$PATH"
mlx_whisper "$WORK/<檔名>.wav" --model mlx-community/whisper-large-v3-mlx --language en \
    --condition-on-previous-text False --hallucination-silence-threshold 2 \
    --output-format srt --output-dir "$WORK" --output-name "<檔名>_en"
```
- 產 `<檔名>_en.srt`（英文、含時間軸）。跑完**掃尾段**確認沒有重複句迴圈（幻覺徵兆：均勻 0.5s 分段 + 同句重複）；若有 → 幻覺沒壓下，調高 `--hallucination-silence-threshold` 或加 `--compression-ratio-threshold 2.4` 重跑。
- 抽純文字：`python3 "$SP_DIR/scripts/srt_to_text.py" "$WORK/<檔名>_en.srt" > "$WORK/_en.txt"`。

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
- **標點契約**：中文散文一律**全形標點**（，。：；？！）；英文句內（前後都是拉丁字元）維持半形。分段 subagent 常各自漂移，Step 3.9 有 deterministic 正規化兜底，但 prompt 仍應明示此契約。
- 講者明顯離題的插話（如旁白）可獨立成段保留，不刪。
- 多人對話：**不做 speaker diarization**；只有當 ASR 文字本身明顯有輪流（你問我答）才用分段呈現，否則輸出連續散文。
- 不確定的人名/作品/時事用語不要改（講者可能引用你不知道的東西）；ASR 嚴重聽不清處用〔註：…〕標記，不硬填。
- **可疑名詞收集（供 Step 3.5 查證）**：整理時發現「名詞與上下文矛盾、但不確定正解」（公司名/ticker/人名/術語聽起來就不對勁）→ 記入 sidecar（見下），照常先照 ASR 原樣輸出＋標〔註〕。**sidecar 內容絕不寫進 prose.md**。

**Sidecar 契約**（單一 JSON envelope，非陣列非 JSONL）：
```json
{"seg": 1, "overflow": false,
 "items": [{"term": "KISS", "para_head": "有位S9008129想詢問KI",
            "context": "想詢問KISS在2027年CPO這裡的看法", "guess": "KEYS"}]}
```
（`para_head` = 該段落前 10 字，定位輔助；srt 技能的 sidecar 用 `ts` 時間戳，本技能 Step 3 時散文尚未加戳，故用 `para_head`。實際定位以 `context` 子串為準。）
- `guess` 可選——**只准在查證收斂後拿來比對，禁止用於任何搜尋 query 或候選生成**（防確認偏誤）。
- `items` 每段上限 10 條，超過取矛盾最明顯前 10、envelope 標 `"overflow": true`。
- 短音檔（主 session 整理）：寫 `$WORK/_uncertain_terms.json`。
- 長音檔分段 subagent：各段寫 `$WORK/_uncertain_seg_N.json`，**回傳文字維持純散文**；envelope 多帶 `"prose_sha256"`（該段回傳散文文字的 SHA-256），主 session 聚合時對實收文字重算比對，不符即棄（防 stale/斷點殘留）。

**分派**：
- 短音檔（單段 ≤ ~300 行純文字）→ 主 session 直接整理。
- 長音檔 → 分段派 Sonnet subagent（每段帶前一段尾段做銜接），最後接起來；分段/銜接規則固定，不靠單次主 session 硬吞。

輸出寫到 `$WORK/<簡短名稱>_prose.md`（含標題行 + 來源/日期 meta）。

**章節標題（供 epub 目錄，必做——epub 預設會產）**：在明顯主題轉折處插入 `## [HH:MM:SS] 主題` 標題（時間戳取該段），讓 epub 切出章節目錄（`prose_to_epub.py` 已設 `--split-level=2`）。`##` 標題行不會被 Step 4.5 加段落時間戳（跳過 `#` 行）。約每 1-3 分鐘或每個主題一節；只有一個 `#` 標題、零 `##` 的 md 會產出「沒有章節的單章 epub」。

> 以上是**雲端模式（預設）**。要本地整理見 Step 3b。

### Step 3（英文分支）：中英對照整理（latent）

英文影音預設走這裡。用 `_en.txt` 產「中英對照」草稿：

- **英文段落（faithful，輕度清理）**：合併 ASR 破碎斷句成通順段落、修明顯 ASR 錯字（人名/產品名/專有名詞先查再改，不確定用〔註：…〕）、正確標點大小寫；不摘要、不改寫。
- **繁中翻譯（faithful，台灣用語）**：忠實翻譯該段，不摘要不加料；技術術語保留英文原文，其餘自然中文；語氣貼近講者。
- **版面**：每個段落單元 = 一行英文（來源語）在上、一行繁中翻譯在下，單元間空行分隔。**英文與中文各自只佔一行**（段落內文不換行，用標點連貫）——這是 `prose_timestamp.py --bilingual` 的結構契約。
- **分派**：短內容主 session 直接做；長內容（>~300 行）派 Sonnet subagent 產草稿（EN 段 + ZH 段，同上格式），主 session 校術語。
- **長內容分段實務**（2026-07-16 以 1.5h 訪談實證）：(1) 句子邊界＋等字數切段，**記下各段字數偏移**；(2) 章節標題時間用「字數偏移 → srt 累計字數」映射取得（deterministic、天然單調）——**不要用文字匹配**：名詞修正後散文與 srt 的原始誤聽對不上，匹配會漏也會假中；(3) subagent 的〔註〕規定用全形冒號統一格式；(4) 名詞修正套用後必再跑一輪冗餘註清理（「X〔註：或為 X〕」型套套邏輯）。
- **著作權**：對公開演講/影片做**個人研讀用**的轉錄+翻譯（存私人 inbox、不公開散布）屬合理個人使用；成品加註「個人研讀用，勿轉散布」。

輸出寫到 `$WORK/<簡短名稱>_prose.md`（標題 + meta + 對照段落，先不加時間戳，交給 Step 4.5 `--bilingual`）。同中文分支：在主題轉折處插 `## [HH:MM:SS] 主題` 章節標題供 epub 目錄。

### Step 3b：本地模式（`--local`，opt-in，fail-closed 不打雲端）

> **Routing**：`--local` 在本技能只代表「Step 3 散文整理改用本地 LLM」，**不是 SRT 字幕本地化**。若用戶要的是帶逐句時間軸的 SRT 字幕（即使說了 `--local`），仍 route 到 `srt`；只有要「非 SRT 字幕的散文」（即使帶段落時間戳）才留在本技能。

**觸發**：用戶說 `--local` /「用本地」/「離線」。預設仍走 Step 3 雲端（潤飾較精）；本地模式省雲端額度、可離線，忠實度足夠但潤飾略淺（gemma4:26b 對拍實測 coverage 0.91、ASR 諧音/英文術語修正達標、繁中乾淨、~43s/短段）。

**範圍**：v1 **只支援短音檔**（Breeze ≤ ~300 行純文字）。長音檔 runner 直接回 exit 4——**不要硬切**，告知用戶本地模式 v1 不支援長音檔、請改雲端（長音檔分段 local 待 v2，需先拿 2-3 長樣本對拍）。

**執行**（deterministic runner，重用 srt 的 ollama_llm.py，模型可換）：
```bash
SP_DIR="${SPEECH_TO_PROSE_DIR:-$HOME/.claude/skills/speech-to-prose}"
python3 "$SP_DIR/scripts/prose_local.py" \
    --breeze "$WORK/_breeze.txt" --vv "$WORK/_vv.txt" \
    --system "$SP_DIR/scripts/prose_system_prompt.txt" \
    --out "$WORK/<簡短名稱>_prose.md"
# 模型預設 gemma4:26b，可用 SPEECH_TO_PROSE_LOCAL_MODEL 覆寫
```

**fail-closed（離線契約，不偷上雲）**：依 exit code 處理，**任何非 0 都不自動打雲端**：
- `0`：成功（runner 內已含 coverage gate + 簡體掃描 + 去 code fence），直接進 Step 5，**不必再跑 Step 4**。
- `2`：推論/驗證失敗（空輸出 / 截斷 / coverage 出界 / HTTP 非 JSON 等推論崩潰）。失敗稿落 `<out>.rejected` 不污染成品路徑。問用戶要不要 `--cloud-fallback`（退回 Step 3 雲端整理）；用戶要離線就停在這裡回報，不要自作主張上雲。
- `3`：環境不可用（Ollama 沒開 / 模型不在 / srt wrapper 載入失敗）。提示 `ollama serve` +（必要時）`ollama pull <model>`。
- `4`：長音檔（行數或漢字數超限），本地 v1 不支援（見上）。

> 簡體偵測是 warning-only（粗字表、不 block；gemma4 對拍實測簡體 0）。要硬性 gate 需換 OpenCC，留 v2。

### Step 3.5：名詞查證（latent＋工具混合，主 session；在 coverage/時間戳之前）

聚合 sidecar（長音檔先過 `prose_sha256` 比對，不符即棄並警示）→ 去重（normalized term 為 key）→ 對每個獨特可疑名詞走**四層查證**，證據不足寧可標〔註〕不硬修：

- **L0 全文內部交叉比對（最優先，零成本）**：同一實體講者通常提多次、ASR 錯法不一致（實例：KISS 在他處被聽對成「keys」）。跑變體叢集掃描，再由 LLM 判讀候選段落的語境是否指向同一實體：
```bash
python3 "$SP_DIR/scripts/noun_xref.py" --term "<詞1>" --term "<詞2>" \
    "$WORK/<檔名>.srt" "$WORK/_breeze.txt" "$WORK/_vv.txt" --json
```
- **L1 本地資源**：講者 terms 檔（`srt_correct/terms_<講者>.txt`）、投影片 OCR terms（srt 場景）、wiki。
- **L2 中性 WebSearch**：**query 只准用上下文關鍵詞**（如「CPO 光通訊 測試設備 股票」），**禁止把猜測答案放進 query**（帶假設搜尋=確認偏誤，2026-07-06 K&S 事故）。搜尋得候選清單後才驗音近。
- **L3 未收斂**：保留〔註〕，可帶候選寫「〔註：或為 X〕」。

**套用門檻**（滿足其一才改詞，且候選必須是不靠 guess 發現的）：
1. L0 內部證據：他處音近變體＋該處上下文獨立支持同一實體
2. L1 權威對應：terms 檔已有／slide OCR 命中／官方名稱與音**完全**相同（全同音，非僅音近）
3. L2 雙重收斂：中性搜尋候選中**恰一個**同時音近一致＋領域吻合；若換一組上下文關鍵詞結果就變，視為未收斂

**量上限**：聚合後最多 30 個獨特名詞進查證（按出現段數×語境重要性排序，其餘直接 L3）；WebSearch 短音檔 ≤10 次、長音檔 ≤20 次；溢出必須回報統計、不得靜默截斷。
**修正套用**：以 `context` 子串定位段落、段內精確 match `term` 逐處 Edit；找不到→報告人工確認；絕不全檔字串替換。雙語對照版只改來源語行。
**查證報告**：逐 mapping 一行 `原詞 → 新詞 @ 位置（證據層級）`＋「考慮過的候選＋淘汰理由」（負面證據）＋溢出統計。
**回寫**：確認 mapping 寫回講者 terms 檔——provenance 獨立註解行在前、mapping 行保持純 `wrong→correct`（行內加 `#` 會被 srt parser 吃進 term，禁止）。
**不可驗證類**：會員 ID、暱稱、私人人名→永不搜尋，直接標註。
**收尾**：刪 `$WORK/_uncertain*.json`（保證 Step 4/4.5 輸入乾淨）。

### Step 3.9：標點正規化（deterministic，必跑）

LLM 整理（尤其分段 subagent）常在全形/半形標點間漂移，靠 prompt 不可靠，一律用腳本兜底：

```bash
# 中文散文：CJK 相鄰的半形 , : ; ? ! .（句點需前字元為 CJK）→ 全形
python3 "$SP_DIR/scripts/punct_normalize.py" "$WORK/<簡短名稱>_prose.md"
# 中英對照版：只動 CJK 佔比 > 0.3 的譯文行，來源語（英文）行原樣保留
python3 "$SP_DIR/scripts/punct_normalize.py" "$WORK/<簡短名稱>_prose.md" --mode bilingual
```

- 冪等；只轉換與 CJK 相鄰的半形標點——時間戳 `[00:12:34]`、URL、純英文句（`A, B` 兩側都是拉丁字元）天然不動。
- 跳過 code fence、`>` blockquote（meta 行）、YAML front matter。
- 在 Step 4 coverage 之前跑（時間戳前後跑都安全，但慣例放這裡）。

### Step 4：散文品質 gate（散文沒有 SRT 的機械不變量，需自己驗）

```bash
python3 "$SP_DIR/scripts/prose_coverage.py" --asr "$WORK/_breeze.txt" --prose "$WORK/<...>_prose.md" --json
```
檢查中文字數 coverage ratio（散文 / ASR）：
- ratio < 0.6 → WARN「可能漏聽或過度摘要」，回 Step 3 補。
- ratio > 1.3 → WARN「可能加料/過度潤稿」，回 Step 3 收。
- 0.6–1.3 → 通過（faithful 整理通常比 ASR 略短：刪語助詞）。
gate 只警示不阻斷，但 WARN 必須處理或向用戶說明。

**英文/對照分支的 coverage**：`prose_coverage.py` 只算中文字數，英文分支不適用。改用英文字數比對：prose 各區塊首行（來源語行）總字數 ÷ ASR 純文字總字數，門檻同 0.6–1.3（2026-07-16 三部英文片實測 0.94–1.00）。待固化為 `prose_coverage.py --lang en`。

### Step 4.5：段落時間戳（deterministic，預設開）

把 ASR 時間軸對齊到散文，每段開頭就地加 `[HH:MM:SS]　` 前綴。**用 Breeze srt**（時間軸細、錨點密）：

```bash
# 中文散文：對齊 Breeze srt
python3 "$SP_DIR/scripts/prose_timestamp.py" "$WORK/<檔名>.srt" "$WORK/<簡短名稱>_prose.md"
# 短片想用 [MM:SS]：加 --fmt ms

# 英文中英對照版：對齊英文 srt + --bilingual（只戳英文行、中文譯文行原樣，尾端補硬換行讓英上中下）
python3 "$SP_DIR/scripts/prose_timestamp.py" "$WORK/<檔名>_en.srt" "$WORK/<簡短名稱>_prose.md" --bilingual
```

- 演算法：8-gram 叢集錨定（非中毒游標）→ 單調骨架 → 相鄰錨點間按段落序內插 → 單調 clamp。**冪等**（已加戳可安全 re-run）。
- **`--bilingual`**：每空行分隔區塊只取**首行（來源語）**對齊加戳 + 尾端補 markdown 硬換行；其餘行（譯文）原樣保留。防呆：首行若中文為主 → 判結構畸形、跳過並 WARN（來源語應在上）。
- **fail-closed**：錨定覆蓋率 < 0.5（或零錨點）→ exit 2 **不寫**（多半是 srt 與 md 不對應）。確認無誤要硬寫用 `--force`。
- 輸出摘要 `段數/錨點/覆蓋率/首尾時間/非單調`；**覆蓋率應 > 0.6、非單調應為 0**，否則查。
- 標題（`#`）、前言（`>` blockquote / YAML front matter）、code fence 區塊不加戳。時間戳是大概值，**內容近乎重複的相鄰段可能共用時間戳**（對齊本質限制，不影響單調）。

### Step 4.6：epub（預設做；`--no-epub` 或用戶明說只要 md 才跳過）

由**已加戳的** md 產「段落帶時間戳的 epub 電子書」（包 pandoc）。**預設帶封面**（Books 首開第一頁即封面；無封面時 pandoc title page 在 Books 首開近乎空白、像壞掉）：

```bash
# 1) 取封面（YT 影片 → 縮圖；podcast → 節目/單集封面。yt-dlp 支援的平台同一招）
yt-dlp --skip-download --write-thumbnail --convert-thumbnails jpg -o "$WORK/cover" "<url>"
# YT 縮圖原生常是 webp，--convert-thumbnails jpg 需 ffmpeg（srt 環境已有）
# 純 RSS podcast：抓 episode/show artwork URL 下載存成 $WORK/cover.jpg
# 本地檔來源沒有封面 → 跳過，不帶 --cover

# 2) 產 epub
python3 "$SP_DIR/scripts/prose_to_epub.py" "$WORK/<簡短名稱>_prose.md" --cover "$WORK/cover.jpg"
# 預設輸出同目錄同名 .epub；title 取 md 第一個 # 標題；成功行含 cover=yes/no
```

- `--cover` 只收 jpg/png（Apple Books 相容性策略；webp 是合法 EPUB media type 但先轉檔）；驗 magic bytes、關係鏈（OPF cover-image ↔ spine 首項 wrapper）、temp+atomic replace，全 fail-closed exit 2。
- **前置頁已精簡**（0.6.1）：不產題名頁（`--epub-title-page=false`）、目錄 nav 移出 spine（Books 用自己的目錄 UI）。Books 翻頁模式封面後仍有**一頁**空白——閱讀器強制每章從右手頁開始（同實體書），內容層關不掉，屬正常。
- **拿不到封面不是錯**：不帶 `--cover` 照舊產無封面 epub，回報用戶即可（首開第一頁會是近空白 title page）。

- 時間戳前綴是段落內文，pandoc 原樣保留 → epub 每段 `<p>` 開頭即帶時間戳（結構同參考的 Allen 3Q2026 epub）。
- **章節目錄**：`--toc --split-level=2` 把 md 的 `## 標題` 切成獨立章節 + 產目錄。所以 Step 3 要在主題轉折插 `## [HH:MM:SS] 主題`，否則 epub 只有時間戳、沒有章節（2026-07-05 踩過：早期散文只有一個 `#` 標題 → 產出無章節單章 epub）。
- **fail-closed**：無 pandoc → exit 3（提示 `brew install pandoc`）；產出不良構 → exit 2。

### Step 5：交付 + 清理

- 把成品 `.md`（已加戳）＋ epub（預設有；跳過 Step 4.6 時無）交付（預設複製到 `inbox/`，或用戶指定位置）。
- 清理中間檔（`_breeze.txt`/`_vv.txt`/`_uncertain*.json`/ASR 暫存），**保留原音檔、srt（時間戳來源）、成品 .md / .epub**。

## 完成後回報
- 成品 .md 路徑（+ epub 路徑，若有）
- 輸入時長、ASR 引擎（Breeze + VV 是否都成功）、長音檔是否走切段
- coverage ratio + 任何 WARN
- 時間戳摘要（段數/錨點/覆蓋率/首尾時間）
- 名詞查證摘要（查證 N／修正 M／標註 K／溢出 O；有修正時附逐條 mapping＋證據層級）
- fidelity mode

## Output（持久化位置宣告）

- 成品短文 `.md`（已加段落時間戳）：`${SRT_DATA_DIR}/prose/<簡短名稱>/<簡短名稱>_prose.md`（`prose/` 可為指向 repo 外的 symlink，見 Step 0），並複製一份到 `inbox/`（或用戶指定路徑）。
- epub（預設）：同目錄 `<簡短名稱>_prose.epub`，一併交付（`--no-epub` 時不產）。
- 中間 ASR 產物：工作目錄內，Step 5 清理（srt 保留為時間戳來源）。

## 邊界與限制
- **段落時間戳是大概值**：錨定段誤差數秒、內插段可能微飄，但全程單調不亂序，供對照影片足夠，非逐句字幕精度。覆蓋率過低會 fail-closed（見 Step 4.5）。
- **英文分支**：單路 Whisper（無雙路交叉比對），**反幻覺旗標必帶**（見 Step 1 英文分支；預設會幻覺迴圈吃內容，跑完必掃尾段）。中英對照為**個人研讀用途**（公開內容的私用轉錄/翻譯），成品加註勿轉散布。
- **`--bilingual` 對齊只對每區塊首行（來源語）**，結構契約是「來源語一行在上、譯文一行在下」；譯文行不對齊不加戳，首行若中文為主會被判畸形跳過。
- **epub 需 pandoc**（`brew install pandoc`）；無 pandoc 時 epub fail-closed（回報並提示安裝），不影響 .md 產出。
- 純音檔跳過任何畫面/投影片處理（本技能本來就不做 caption）。
- 不做 speaker diarization（多人只在 ASR 明顯輪流時分段）。
- 極短音檔（< ~30 秒）避免過度分段與過度潤稿。
- 重用 srt ASR；srt 的 ASR 腳本/路徑變動時，依 Adapter Contract 同步。
- 本地模式（`--local`，Step 3b）v1 僅短音檔；fail-closed 不自動上雲；預設 gemma4:26b，可用 `SPEECH_TO_PROSE_LOCAL_MODEL` 覆寫。潤飾深度略遜雲端，要最精的整理用預設雲端模式。
- 需要**講者分離（diarization）/ 結構化摘要 / 高光 / 帶逐句時間軸的逐字稿** → 用 `podcast-digest`（本技能刻意不做 diarization、只給段落級大概時間戳而非逐句時間軸；本技能的「中英對照」是 faithful 逐段翻譯散文，非結構化摘要——兩者是協作不是替代）。
- **名詞查證（Step 3.5）是有界的**：上限內查不完的落〔註〕不硬修；帶假設搜尋（把猜測放進 query）被明文禁止——內部交叉比對（L0）優先於一切外部搜尋。
- 是「忠於原話的整理」，不是逐字法律級 transcript、也不是摘要。
