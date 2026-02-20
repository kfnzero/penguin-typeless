# Voice Assistant for Windows — Implementation Plan

## 概覽

一個常駐背景的 Windows 語音助理：
- 持續監聽 **喚醒詞**（可自訂名字，例如 `JARVIS`、`GEMINI`、`SIRI`）
- 聽到名字後進入「指令聆聽」模式
- 支援「開啟 XXX 程式」指令
- 系統匣圖示常駐，方便設定與退出
- **完全離線**，不需要 API key 或網路

---

## 技術選型

| 元件 | 選擇 | 理由 |
|---|---|---|
| 語言 | Python 3.11+ | 生態完整、Windows 支援佳 |
| 喚醒詞偵測 | `openwakeword` | 完全離線、開源免費、支援任意喚醒詞（零樣本） |
| 音訊擷取 | `pyaudio` | 低延遲串流，openwakeword 和 Whisper 都需要 |
| 語音識別 (STT) | `faster-whisper` (tiny.en) | 完全離線，~300ms 推理，39MB 模型 |
| 文字轉語音 (TTS) | `pyttsx3` | 完全離線，Windows SAPI5 |
| 系統匣 | `pystray` + `Pillow` | Windows 系統匣標準方案 |
| 設定 UI | `tkinter` (stdlib) | 零額外依賴，夠用 |
| 設定檔 | TOML (`tomllib` stdlib) | 人類可讀，Python 3.11 內建 |
| 程式探索 | `winreg` + `pywin32` + `rapidfuzz` | 登錄檔 + 捷徑 + 模糊比對 |
| 程式啟動 | `subprocess` (stdlib) | 安全，`shell=False` |
| 打包 | `PyInstaller` | 打包成 .exe，使用者不需裝 Python |

### 為什麼選完全離線方案？

- **無需 API key**，不需要 Google/OpenAI/Picovoice 帳號
- **無網路延遲**，`tiny.en` 指令識別約 300ms
- **隱私保護**，麥克風音訊不離開本機
- **openwakeword 零樣本**：任意名字都可作為喚醒詞，無需重新訓練模型

---

## 架構設計

```
[MainApplication]
       │
       ├── [AudioCapture]          PyAudio 16kHz mono 串流
       │         │ PCM chunks (queue)
       ├── [WakeWordEngine]        openwakeword 偵測喚醒詞
       │         │ WakeEvent (queue)
       ├── [CommandListener]       喚醒後錄音 5 秒
       │         │ PCM buffer
       ├── [Transcriber]           faster-whisper STT
       │         │ transcript text (queue)
       ├── [CommandDispatcher]     解析意圖 → 啟動程式
       │         │ 查詢
       ├── [ProgramIndex]          程式庫（登錄檔+捷徑+PATH）
       └── [TrayController]        系統匣 + 設定視窗
```

### 核心流程

```
[啟動] → 系統匣常駐
    │
    ▼
[背景聆聽] AudioCapture → WakeWordEngine (持續)
    │
    ├─ 未聽到喚醒詞 → 繼續
    └─ 聽到喚醒詞 ─────────────────────────┐
                                           ▼
                                   播放提示音 ♪
                                   圖示變色（listening）
                                           │
                                   [錄音 5 秒]
                                           │
                                   [Whisper STT]
                                           │
                                   [解析指令]
                                           │
                              ┌────────────┴─────────────┐
                              ▼                           ▼
                         "開啟 XXX"               聽不懂/無指令
                              │                           │
                         [ProgramIndex.find]        TTS: "請再說一次"
                              │
                    ┌─────────┴──────────┐
                    ▼                    ▼
               找到程式             找不到
                    │                    │
               subprocess.Popen    TTS: "找不到 XXX"
                    │
               TTS: "好的，開啟 XXX"
                    │
            [回到背景聆聽]
```

---

## 檔案結構

```
penguin-typeless/
│
├── penguin/                     # 主套件
│   ├── __init__.py
│   ├── __main__.py              # python -m penguin 進入點
│   ├── app.py                   # MainApplication：執行緒協調
│   │
│   ├── audio/
│   │   ├── capture.py           # AudioCapture：PyAudio 串流執行緒
│   │   └── player.py            # play_sound()：播放 .wav 提示音
│   │
│   ├── wake/
│   │   └── engine.py            # WakeWordEngine：openwakeword 封裝
│   │
│   ├── stt/
│   │   └── transcriber.py       # Transcriber：faster-whisper 封裝
│   │
│   ├── commands/
│   │   ├── listener.py          # CommandListener：喚醒後錄音邏輯
│   │   ├── dispatcher.py        # CommandDispatcher：意圖解析 + 啟動
│   │   └── intent.py            # parse_intent()：regex 解析指令
│   │
│   ├── programs/
│   │   └── index.py             # ProgramIndex：程式探索 + 模糊比對
│   │
│   ├── tray/
│   │   ├── controller.py        # TrayController：pystray 封裝
│   │   └── icons/               # idle.png / listening.png / processing.png
│   │
│   ├── settings/
│   │   ├── manager.py           # SettingsManager：TOML 讀寫
│   │   ├── schema.py            # AssistantConfig dataclass
│   │   └── gui.py               # tkinter 設定視窗
│   │
│   └── utils/
│       ├── events.py            # 事件 dataclass（WakeEvent、TranscriptEvent）
│       └── logging_config.py   # logging 設定
│
├── assets/
│   ├── sounds/
│   │   ├── wake_ack.wav         # 聽到喚醒詞時播放
│   │   └── command_done.wav     # 指令執行後播放
│   └── models/                  # 首次執行時自動下載（.gitignore）
│
├── tests/
│   ├── test_intent.py
│   ├── test_program_index.py
│   └── test_settings.py
│
├── scripts/
│   ├── download_models.py       # 下載 openwakeword + whisper 模型
│   └── build_exe.py             # PyInstaller 打包腳本
│
├── pyproject.toml
├── requirements.txt
└── requirements-dev.txt
```

---

## 相依套件

```txt
# requirements.txt
pyaudio==0.2.14
openwakeword==0.6.0
numpy==1.26.4
tflite-runtime==2.14.0       # openwakeword 後端（輕量，非完整 TensorFlow）
faster-whisper==1.0.3
ctranslate2==4.3.1
pyttsx3>=2.90
pystray==0.19.5
Pillow==10.3.0
pywin32==306
tomli-w==1.0.0
rapidfuzz==3.9.0             # 程式名稱模糊比對（比 fuzzywuzzy 快 100x）
```

```txt
# requirements-dev.txt
pytest==8.2.2
pytest-mock==3.14.0
pyinstaller==6.6.0
```

---

## 程式探索策略（ProgramIndex）

Windows 沒有單一的「已安裝程式」API，需要多來源整合：

| 優先順序 | 來源 | 說明 |
|---|---|---|
| 1 | `config.toml` 自訂對應 | 最高優先，使用者手動指定 |
| 2 | **Windows 登錄檔** | `HKLM\...\Uninstall\*` 讀取 DisplayName + 路徑 |
| 3 | **Start Menu 捷徑** | `%APPDATA%` + `%ProgramData%` 下的 `.lnk` 檔案 |
| 4 | **PATH 環境變數** | 收集 PATH 中的 `.exe` 檔案 |
| 5 | **rapidfuzz 模糊比對** | `WRatio` scorer，score_cutoff=70 |

> **為什麼需要 Start Menu 捷徑？**
> UWP / MSIX 應用程式（Edge、Windows Calculator）不寫登錄檔，只有 Start Menu 捷徑。

程式名稱正規化：小寫 + 去掉版本號碼 + 去掉常見後綴（"application"、"for windows"）

---

## 設定檔（%APPDATA%\penguin-typeless\config.toml）

```toml
[assistant]
name = "JARVIS"                # 喚醒詞（不分大小寫）
wake_threshold = 0.5           # 偵測靈敏度（0.1~0.9）
command_capture_seconds = 5.0  # 喚醒後聆聽秒數
whisper_model = "tiny.en"      # tiny.en / base.en / small.en
launch_on_startup = false      # 開機自動啟動

[custom_apps]                  # 自訂程式對應
"記事本" = "notepad.exe"
"小畫家" = "mspaint.exe"
```

---

## 實作階段

### Phase 1 — 音訊管線
- `AudioCapture`：16kHz mono PyAudio 串流，80ms chunks，`queue.Queue`
- `utils/events.py`：事件 dataclass
- `utils/logging_config.py`：`%APPDATA%\penguin-typeless\logs\app.log`

### Phase 2 — 設定 + 系統匣
- `settings/schema.py`：`AssistantConfig` dataclass
- `settings/manager.py`：TOML 讀寫（`%APPDATA%`）
- `tray/controller.py`：pystray，三種狀態圖示（idle/listening/processing）
- 開機自動啟動：寫入 `HKCU\...\Run`（無需 admin）

### Phase 3 — 喚醒詞引擎
- `wake/engine.py`：openwakeword 零樣本偵測
- 2 秒 debounce 防止重複觸發
- `scripts/download_models.py`：首次執行自動下載模型

### Phase 4 — 指令聆聽 + STT
- `commands/listener.py`：喚醒後切換錄音模式，同一音訊串流
- `stt/transcriber.py`：faster-whisper，啟動時預載模型避免首次延遲

### Phase 5 — 程式探索 + 指令分派
- `programs/index.py`：三來源掃描 + rapidfuzz 模糊比對，每 30 分鐘重建
- `commands/intent.py`：regex 解析「開啟/打開/open/launch/start + 程式名」
- `commands/dispatcher.py`：`subprocess.Popen` 啟動，TTS 回應

### Phase 6 — 主應用程式
- `app.py`：執行緒協調，啟動/關閉順序
- 關閉順序：CommandListener → WakeWordEngine → AudioCapture → TrayController

### Phase 7 — 打包
- `scripts/build_exe.py`：PyInstaller `--onedir`（比 `--onefile` 啟動快）
- 打包模型檔案、音效、圖示
- 產出可分發的資料夾（可壓縮成 zip）

---

## 關鍵技術決策

### 喚醒詞：零樣本 vs 預訓練模型
選擇 **openwakeword 零樣本**：直接傳入名字字串即可，無需訓練
- Picovoice Porcupine 需要帳號、自訂喚醒詞需付費
- openwakeword 完全開源（Apache 2.0），支援任意名字

### STT：離線 vs 線上
選擇 **faster-whisper（離線）**：
- 線上 STT（Google、Azure）有 200-800ms 網路延遲
- `tiny.en` 對「open Chrome」這類短指令準確率接近完美
- 啟動時預載模型，後續推理 ~300ms

### 單一音訊串流
喚醒詞偵測和指令錄音共用同一個 PyAudio 串流：
- Windows 有時只允許一個應用程式開啟麥克風
- 用 flag 切換路由（Wake queue / Recording buffer）

### 執行緒 vs asyncio
選擇 **threading**：
- PyAudio C 層回調與 asyncio event loop 相容性差
- queue 為基礎的訊息傳遞清晰易除錯

---

## 後續擴充方向

- 更多指令：「關閉 XXX」、「搜尋 XXX」、「調音量到 50%」
- 接入 Claude API 處理複雜自然語言
- 多語言支援（切換 `whisper_model = "small"` 支援中文）
- `openwakeword` 微調：用 100 個合成音訊樣本提升自訂名字準確率
- GUI 設定介面（PyQt6）
