<p align="center">
  <img src="assets/banner.png" alt="Hermes Agent" width="100%">
</p>

# Hermes Agent ☤

<p align="center">
  <a href="https://hermes-agent.nousresearch.com/docs/"><img src="https://img.shields.io/badge/Docs-hermes--agent.nousresearch.com-FFD700?style=for-the-badge" alt="Documentation"></a>
  <a href="https://discord.gg/NousResearch"><img src="https://img.shields.io/badge/Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Discord"></a>
  <a href="https://github.com/NousResearch/hermes-agent/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License: MIT"></a>
  <a href="https://nousresearch.com"><img src="https://img.shields.io/badge/Built%20by-Nous%20Research-blueviolet?style=for-the-badge" alt="Built by Nous Research"></a>
  <a href="README.md"><img src="https://img.shields.io/badge/Lang-English-lightgrey?style=for-the-badge" alt="English"></a>
  <a href="README.ur-pk.md"><img src="https://img.shields.io/badge/Lang-اردو-green?style=for-the-badge" alt="اردو"></a>
</p>

**由 [Nous Research](https://nousresearch.com) 構建的自進化 AI 代理。** 它是唯一內置學習閉環的智能代理——從經驗中創建技能，在使用中改進技能，主動持久化知識，搜索過往對話，並在跨會話中逐步構建對你的深度理解。可以在 $5 的 VPS 上運行，也可以在 GPU 集群上運行，或者使用幾乎零成本的 Serverless 基礎設施。它不綁定你的筆記本——你可以在 Telegram 上與它對話，而它在雲端 VM 上工作。

支持任意模型——[Nous Portal](https://portal.nousresearch.com)、[OpenRouter](https://openrouter.ai)（200+ 模型）、[NVIDIA NIM](https://build.nvidia.com)（Nemotron）、[小米 MiMo](https://platform.xiaomimimo.com)、[z.ai/GLM](https://z.ai)、[Kimi/Moonshot](https://platform.moonshot.ai)、[MiniMax](https://www.minimax.io)、[Hugging Face](https://huggingface.co)、OpenAI，或自定義端點。使用 `hermes model` 即可切換——無需改代碼，無鎖定。

<table>
<tr><td><b>真正的終端界面</b></td><td>完整的 TUI，支持多行編輯、斜槓命令自動補全、對話歷史、中斷重定向和流式工具輸出。</td></tr>
<tr><td><b>隨你所在</b></td><td>Telegram、Discord、Slack、WhatsApp、Signal 和 CLI——全部從單個網關進程運行。語音備忘錄轉寫、跨平臺對話連續性。</td></tr>
<tr><td><b>閉環學習</b></td><td>代理管理記憶並定期自我提醒。複雜任務後自動創建技能。技能在使用中自我改進。FTS5 會話搜索配合 LLM 摘要實現跨會話回溯。<a href="https://github.com/plastic-labs/honcho">Honcho</a> 辯證式用戶建模。兼容 <a href="https://agentskills.io">agentskills.io</a> 開放標準。</td></tr>
<tr><td><b>定時自動化</b></td><td>內置 cron 調度器，支持向任何平臺投遞。日報、夜間備份、周審計——全部用自然語言描述，無人值守運行。</td></tr>
<tr><td><b>委派與並行</b></td><td>生成隔離子代理處理並行工作流。編寫 Python 腳本通過 RPC 調用工具，將多步管道壓縮為零上下文開銷的輪次。</td></tr>
<tr><td><b>隨處運行</b></td><td>六種終端後端——本地、Docker、SSH、Daytona、Singularity 和 Modal。Daytona 和 Modal 提供 Serverless 持久化——代理環境空閒時休眠、按需喚醒，空閒期間幾乎零成本。$5 VPS 或 GPU 集群都能跑。</td></tr>
<tr><td><b>研究就緒</b></td><td>批量軌跡生成、軌跡壓縮——用於訓練下一代工具調用模型。</td></tr>
</table>

---

## 快速安裝

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
```

支持 Linux、macOS、WSL2 和 Android (Termux)。安裝程序會自動處理平臺特定的配置。

> **Android / Termux：** 已測試的手動安裝路徑請參考 [Termux 指南](https://hermes-agent.nousresearch.com/docs/getting-started/termux)。在 Termux 上，Hermes 會安裝精選的 `.[termux]` 擴展，因為完整的 `.[all]` 擴展會拉取 Android 不兼容的語音依賴。
>
> **Windows：** 原生 Windows 不受支持。請安裝 [WSL2](https://learn.microsoft.com/zh-cn/windows/wsl/install) 並運行上述命令。

安裝後：

```bash
source ~/.bashrc    # 重新加載 shell（或: source ~/.zshrc）
hermes              # 開始對話！
```

---

## 快速入門

```bash
hermes              # 交互式 CLI — 開始對話
hermes model        # 選擇 LLM 提供商和模型
hermes tools        # 配置啟用的工具
hermes config set   # 設置單個配置項
hermes gateway      # 啟動消息網關（Telegram、Discord 等）
hermes setup        # 運行完整設置嚮導（一次性配置所有內容）
hermes claw migrate # 從 OpenClaw 遷移（如果來自 OpenClaw）
hermes update       # 更新到最新版本
hermes doctor       # 診斷問題
```

📖 **[完整文檔 →](https://hermes-agent.nousresearch.com/docs/)**

---

## 省去到處收集 API Key — Nous Portal

Hermes 始終允許你使用任意服務商，這點不會改變。但如果你不想為模型、網頁搜索、圖像生成、TTS、雲瀏覽器分別去申請五個不同的 API Key，**[Nous Portal](https://portal.nousresearch.com)** 用一個訂閱就能覆蓋全部：

- **300+ 模型** — 用 `/model <name>` 隨時切換
- **Tool Gateway** — 網頁搜索（Firecrawl）、圖像生成（FAL）、文本轉語音（OpenAI）、雲瀏覽器（Browser Use），全部通過訂閱託管。無需額外註冊任何賬戶。

全新安裝時一條命令即可：

```bash
hermes setup --portal
```

它會通過 OAuth 登錄、把 Nous 設為推理服務商，並啟用 Tool Gateway。隨時用 `hermes portal info` 查看路由狀態。完整說明見 [Tool Gateway 文檔](https://hermes-agent.nousresearch.com/docs/user-guide/features/tool-gateway)。

你隨時可以按工具單獨切回自己的 API Key — Gateway 是按工具粒度生效的，不是一刀切。

---

## CLI 與消息平臺 快速對照

Hermes 有兩種入口：用 `hermes` 啟動終端 UI，或運行網關從 Telegram、Discord、Slack、WhatsApp、Signal 或 Email 與之對話。進入對話後，許多斜槓命令在兩種界面中通用。

| 操作 | CLI | 消息平臺 |
|------|-----|----------|
| 開始對話 | `hermes` | 運行 `hermes gateway setup` + `hermes gateway start`，然後給機器人發消息 |
| 開始新對話 | `/new` 或 `/reset` | `/new` 或 `/reset` |
| 更換模型 | `/model [provider:model]` | `/model [provider:model]` |
| 設置人格 | `/personality [name]` | `/personality [name]` |
| 重試或撤銷上一輪 | `/retry`、`/undo` | `/retry`、`/undo` |
| 壓縮上下文 / 查看用量 | `/compress`、`/usage`、`/insights [--days N]` | `/compress`、`/usage`、`/insights [days]` |
| 瀏覽技能 | `/skills` 或 `/<skill-name>` | `/skills` 或 `/<skill-name>` |
| 中斷當前工作 | `Ctrl+C` 或發送新消息 | `/stop` 或發送新消息 |
| 平臺特定狀態 | `/platforms` | `/status`、`/sethome` |

完整命令列表請參閱 [CLI 指南](https://hermes-agent.nousresearch.com/docs/user-guide/cli) 和 [消息網關指南](https://hermes-agent.nousresearch.com/docs/user-guide/messaging)。

---

## 文檔

所有文檔位於 **[hermes-agent.nousresearch.com/docs](https://hermes-agent.nousresearch.com/docs/)**：

| 章節 | 內容 |
|------|------|
| [快速開始](https://hermes-agent.nousresearch.com/docs/getting-started/quickstart) | 安裝 → 設置 → 2 分鐘內開始首次對話 |
| [CLI 使用](https://hermes-agent.nousresearch.com/docs/user-guide/cli) | 命令、快捷鍵、人格、會話 |
| [配置](https://hermes-agent.nousresearch.com/docs/user-guide/configuration) | 配置文件、提供商、模型、所有選項 |
| [消息網關](https://hermes-agent.nousresearch.com/docs/user-guide/messaging) | Telegram、Discord、Slack、WhatsApp、Signal、Home Assistant |
| [安全](https://hermes-agent.nousresearch.com/docs/user-guide/security) | 命令審批、DM 配對、容器隔離 |
| [工具與工具集](https://hermes-agent.nousresearch.com/docs/user-guide/features/tools) | 40+ 工具、工具集系統、終端後端 |
| [技能系統](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills) | 過程記憶、技能中心、創建技能 |
| [記憶](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory) | 持久記憶、用戶畫像、最佳實踐 |
| [MCP 集成](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp) | 連接任意 MCP 服務器擴展能力 |
| [定時調度](https://hermes-agent.nousresearch.com/docs/user-guide/features/cron) | 定時任務與平臺投遞 |
| [上下文文件](https://hermes-agent.nousresearch.com/docs/user-guide/features/context-files) | 影響每次對話的項目上下文 |
| [架構](https://hermes-agent.nousresearch.com/docs/developer-guide/architecture) | 項目結構、代理循環、關鍵類 |
| [貢獻](https://hermes-agent.nousresearch.com/docs/developer-guide/contributing) | 開發設置、PR 流程、代碼風格 |
| [CLI 參考](https://hermes-agent.nousresearch.com/docs/reference/cli-commands) | 所有命令和標誌 |
| [環境變量](https://hermes-agent.nousresearch.com/docs/reference/environment-variables) | 完整環境變量參考 |

---

## 從 OpenClaw 遷移

如果你來自 OpenClaw，Hermes 可以自動導入你的設置、記憶、技能和 API 密鑰。

**首次安裝時：** 安裝嚮導（`hermes setup`）會自動檢測 `~/.openclaw` 並在配置開始前提供遷移選項。

**安裝後任意時間：**

```bash
hermes claw migrate              # 交互式遷移（完整預設）
hermes claw migrate --dry-run    # 預覽將要遷移的內容
hermes claw migrate --preset user-data   # 僅遷移用戶數據，不含密鑰
hermes claw migrate --overwrite  # 覆蓋已有衝突
```

導入內容：
- **SOUL.md** — 人格文件
- **記憶** — MEMORY.md 和 USER.md 條目
- **技能** — 用戶創建的技能 → `~/.hermes/skills/openclaw-imports/`
- **命令白名單** — 審批模式
- **消息設置** — 平臺配置、允許用戶、工作目錄
- **API 密鑰** — 白名單中的密鑰（Telegram、OpenRouter、OpenAI、Anthropic、ElevenLabs）
- **TTS 資產** — 工作區音頻文件
- **工作區指令** — AGENTS.md（使用 `--workspace-target`）

使用 `hermes claw migrate --help` 查看所有選項，或使用 `openclaw-migration` 技能進行交互式代理引導遷移（含幹運行預覽）。

---

## 貢獻

歡迎貢獻！請參閱 [貢獻指南](https://hermes-agent.nousresearch.com/docs/developer-guide/contributing) 瞭解開發設置、代碼風格和 PR 流程。

貢獻者快速開始——使用標準安裝器，然後在它創建的完整 git checkout 中開發：
`$HERMES_HOME/hermes-agent`（通常是 `~/.hermes/hermes-agent`）。這會匹配
`hermes update`、託管 venv、lazy dependencies、gateway 和 docs tooling 使用的佈局。

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
cd "${HERMES_HOME:-$HOME/.hermes}/hermes-agent"
uv pip install -e ".[all,dev]"
scripts/run_tests.sh
```

手動克隆備用路徑（用於一次性 clone / CI，或你明確不想使用 managed install layout 時）：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv venv --python 3.11
source venv/bin/activate
uv pip install -e ".[all,dev]"
python -m pytest tests/ -q
```

---

## 社區

- 💬 [Discord](https://discord.gg/NousResearch)
- 📚 [技能中心](https://agentskills.io)
- 🐛 [問題反饋](https://github.com/NousResearch/hermes-agent/issues)
- 💡 [討論區](https://github.com/NousResearch/hermes-agent/discussions)
- 🔌 [HermesClaw](https://github.com/AaronWong1999/hermesclaw) — 社區微信橋接：在同一微信賬號上運行 Hermes Agent 和 OpenClaw。

---

## 許可證

MIT — 詳見 [LICENSE](LICENSE)。

由 [Nous Research](https://nousresearch.com) 構建。
