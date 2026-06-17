# Builder / Runner split for ZIT image generation

## Why this exists

這次任務把原本偏混合的 JSON-mode prompt 流程，正式拆成兩層：

- **Builder**：自然語言 → `prompt_json`
- **Runner**：`prompt` / `prompt_json` / `request_text` → workflow 執行

這個拆法比較穩，因為語意理解與實際生成責任被分開了。

## Recommended input contract

### 1. `request_text`
用在：
- 預留中的 Builder 入口
- 使用者只給自然語言需求
- 使用者說「用 JSON 生成」

目前實作狀態：
- Builder 只會辨識 JSON mode trigger，並移除該觸發語
- **LLM-backed expansion 尚未接線**
- 因此目前不會自動把自然語言需求補成完整 `prompt_json`
- 若 caller 真的走 `request_text` + JSON mode，現況應明確報錯，要求改由上游 LLM / agent 先填好固定模板，再傳 `prompt_json`

也就是說，`request_text` 現在是保留接口，不是已完成的自然語言自動轉 JSON 功能。

### 2. `prompt_json`
用在：
- 上游已經有結構化內容
- 你要精準控制欄位
- 不需要再做自然語言抽象

行為：
- 直接正規化 key 順序
- 直接序列化
- 交給 Runner 跑 workflow

### 3. `prompt`
用在：
- 明確要走舊式自由文字 prompt
- 不需要 Builder

行為：
- 不做 JSON expansion
- 直接送 Runner

## Practical rule

如果需求裡出現這類句子：
- `用 JSON 生成`
- `json生成`

那它們應該被視為**流程切換訊號**，不是最後 prompt 的內容。

## Implementation notes

這次實作後，成功結果可附帶：
- `built_prompt_json`

它的價值是：
- 可直接檢查 Builder 轉得對不對
- 可在 debug 時分辨問題是出在 Builder 還是 Runner
- 可作為未來更進一步模板化 Builder 的觀察點

## Current implementation reality

目前 `tools/zit_prompt_builder.py` 的 Builder 側只做三件事：
- 偵測 `用 JSON 生成` / `json生成` 這類流程切換 trigger
- 提供固定英文 key / 中文 value 的 JSON 模板
- 對已提供的 `prompt_json` 做 key 順序正規化與序列化

它**沒有**內建自然語言理解用的 `call_llm`，也沒有完成 heuristics-to-JSON 的自動擴寫流程。

因此目前正確分工是：
- **Agent / caller**：負責理解使用者需求、必要時自行擴寫，並填好 `prompt_json`
- **Builder module**：只負責 trigger 判斷、模板與序列化
- **Runner / `zit_image_generate`**：只負責 workflow 選擇、參數整理、Comfy Cloud 執行與結果交付

若未來真的要支援 `request_text` 直轉 `prompt_json`，應新增明確的 LLM-backed Builder 路徑，而不是讓 Runner 偷偷做 prompt parsing。

## Durable lesson

對這類工作流，**先拆 Builder / Runner，再慢慢迭代 Builder 的擴寫品質**，比把全部邏輯塞進單一 tool handler 更容易維護，也更不容易把執行器污染成半個 prompt parser。
