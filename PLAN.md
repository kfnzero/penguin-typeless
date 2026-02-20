# Voice Assistant for Windows — Implementation Plan

## 概覽

一個常駐背景的 Windows 語音助理：
- 持續監聽 **喚醒詞**（可自訂名字，例如 `JARVIS`、`GEMINI`）
- 聽到名字後進入「指令聆聽」模式
- 支援「開啟 XXX 程式」指令
- 系統匣圖示常駐，方便設定與退出

---

## 技術選型

| 元件 | 選擇 | 理由 |
|---|---|---|
| 語言 | Python 3.10+ | 生態完整、Windows 支援佳 |
| 語音識別 | `SpeechRecognition` + Google STT | 簡單可靠，中英文皆支援 |
| 離線備援 STT | `Vosk` | 無網路時可用 |
| 喚醒詞偵測 | 連續 STT + 關鍵字比對 | 不需額外 API key，輕量 |
| 文字轉語音 (TTS) | `pyttsx3` | 完全離線，Windows SAPI5 |
| 系統匣 | `pystray` + `Pillow` | 跨平台 tray 標準方案 |
| 程式探索 | `winreg` + 路徑掃描 + `fuzzywuzzy` | 精準找到已安裝程式 |
| 設定檔 | `YAML` (pyyaml) | 易讀易改 |
| 打包成 exe | `PyInstaller` | 使用者不需裝 Python |

---

## 架構設計

```
voice_assistant/
│
├── main.py              # 程式進入點，啟動 tray + listener
├── config.py            # 讀寫 config.yaml
├── listener.py          # 主要聆聽迴圈（喚醒詞 → 指令）
├── recognizer.py        # STT 封裝（Google / Vosk 切換）
├── command_parser.py    # 解析指令（"open chrome" → action)
├── launcher.py          # 在 Windows 找到並啟動程式
├── tts.py               # 語音回應封裝
├── tray.py              # 系統匣圖示與選單
│
├── config.yaml          # 使用者設定（名字、自訂程式路徑）
├── assets/
│   └── icon.ico         # 系統匣圖示
└── requirements.txt
```

---

## config.yaml 範例

```yaml
assistant:
  name: "JARVIS"          # 喚醒詞（不分大小寫）
  language: "zh-TW"       # 語音識別語言
  voice_enabled: true     # TTS 回應開關
  offline_mode: false     # 強制使用 Vosk 離線模式

# 自訂程式對應（找不到時的 fallback）
custom_apps:
  記事本: "notepad.exe"
  小畫家: "mspaint.exe"
  瀏覽器: "C:/Program Files/Google/Chrome/Application/chrome.exe"
```

---

## 核心流程

```
[啟動]
   │
   ▼
[系統匣常駐] ──────────────────────────────────────┐
   │                                               │ 右鍵選單
   ▼                                               │ Settings / Exit
[背景聆聽迴圈]                                      │
   │                                               │
   ├─ 收音 → STT                                   │
   │                                               │
   ├─ 是否包含喚醒詞？                               │
   │   ├─ 否 → 繼續聆聽                             │
   │   └─ 是 → 播放提示音 ♪                         │
   │              │                                │
   │              ▼                                │
   │         [指令聆聽模式]（5 秒 timeout）          │
   │              │                                │
   │              ▼                                │
   │         [解析指令]                             │
   │              │                                │
   │         ┌────┴──────────────┐                 │
   │         ↓                   ↓                 │
   │    "開啟 XXX"          其他/聽不懂              │
   │         │                   │                 │
   │         ▼                   ▼                 │
   │    [找到程式]          TTS: "請再說一次"        │
   │         │                                     │
   │         ▼                                     │
   │    [subprocess 啟動]                           │
   │         │                                     │
   │    TTS: "好的，開啟 XXX"                       │
   │         │                                     │
   └─────────┘（回到背景聆聽）
```

---

## 程式探索策略（launcher.py）

Windows 上找已安裝程式的優先順序：

1. **config.yaml 自訂對應** — 最高優先
2. **Windows 登錄檔**
   - `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths`
3. **Start Menu 捷徑掃描**
   - `%APPDATA%\Microsoft\Windows\Start Menu\Programs`
   - `%ProgramData%\Microsoft\Windows\Start Menu\Programs`
4. **常見路徑掃描**
   - `C:\Program Files`, `C:\Program Files (x86)`
5. **PATH 環境變數中的可執行檔**
6. **模糊比對**（`fuzzywuzzy`）—  找最接近的名稱

---

## 實作階段

### Phase 1 — 骨架 (Skeleton)
- [ ] 專案結構初始化
- [ ] `config.yaml` 讀寫
- [ ] `main.py` 進入點
- [ ] `pystray` 系統匣（圖示 + 退出）

### Phase 2 — 語音識別
- [ ] `recognizer.py`：麥克風收音 + Google STT
- [ ] `listener.py`：喚醒詞偵測迴圈
- [ ] 聽到喚醒詞 → 提示音 → 指令聆聽

### Phase 3 — 指令解析 + 程式啟動
- [ ] `command_parser.py`：解析 "打開/開啟/open + 程式名"
- [ ] `launcher.py`：Registry + Start Menu + 模糊比對
- [ ] `subprocess.Popen` 啟動程式

### Phase 4 — TTS 回應
- [ ] `tts.py`：pyttsx3 封裝
- [ ] 成功/失敗語音回應

### Phase 5 — 設定 UI
- [ ] 系統匣右鍵「Settings」→ 簡易 tkinter 視窗
- [ ] 修改喚醒詞、新增自訂程式

### Phase 6 — 打包
- [ ] `PyInstaller` 打包成單一 `.exe`
- [ ] 開機自動啟動（選用）

---

## 相依套件

```txt
SpeechRecognition>=3.10.0
PyAudio>=0.2.13
pyttsx3>=2.90
pystray>=0.19.5
Pillow>=10.0.0
pyyaml>=6.0
fuzzywuzzy>=0.18.0
python-Levenshtein>=0.12.2
pywin32>=306
vosk>=0.3.45          # 離線模式用（選用）
pyinstaller>=6.0      # 打包用
```

---

## 關鍵技術決策

### 喚醒詞偵測方式
選擇「**連續 STT 關鍵字比對**」而非 Picovoice Porcupine：
- Porcupine 需要帳號與 API key
- 連續 STT 對短語（只有名字）延遲可接受（~1-2 秒）
- 未來可升級成 `openwakeword`（本機推理，更省資源）

### 中文支援
`language: "zh-TW"` 傳給 Google STT 即可支援中文指令，
例如：「JARVIS，**幫我開啟** Chrome」

### 音訊架構
喚醒詞聆聽使用較短的 `phrase_time_limit=3`，
指令聆聽使用 `phrase_time_limit=5`，避免長時間佔用 CPU。

---

## 執行方式（未來）

```bash
# 直接執行
python main.py

# 或執行打包後的 exe
voice_assistant.exe
```

---

## 後續擴充方向

- 更多指令類型：「關閉 XXX」、「搜尋 XXX」、「調音量」
- 接入 Claude API 處理複雜自然語言指令
- 多語言喚醒詞（同時監聽多個名字）
- 本機喚醒詞模型（openwakeword）降低 CPU 使用
- GUI 設定介面（PyQt6）
