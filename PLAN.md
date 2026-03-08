# Voice Assistant for Windows — Implementation Plan

## 概覽

一個常駐背景的 Windows 語音助理：
- 持續監聽 **喚醒詞**（可自訂名字，例如 `小助手`、`電腦`、`JARVIS`）
- 聽到名字後進入「指令聆聽」模式
- 支援中英文「開啟 XXX 程式」指令
- 系統匣圖示常駐，方便設定與退出
- **完全離線本地運作**，不需要 API key 或網路

---

## 技術選型（中文離線版）

| 元件 | 選擇 | 理由 |
|---|---|---|
| 語言 | Python 3.11+ | 生態完整、Windows 支援佳 |
| 語音活動偵測 (VAD) | `silero-vad` | 1MB 超輕量，偵測有人說話才觸發 STT，省 CPU |
| 喚醒詞偵測 | `faster-whisper tiny` + 關鍵字比對 | 支援中文，完全離線，無需訓練 |
| 指令語音識別 (STT) | `faster-whisper small` | 中文高準確率，~244MB，CPU 可跑 |
| 音訊擷取 | `pyaudio` | 低延遲串流 |
| 文字轉語音 (TTS) | `pyttsx3` | 完全離線，Windows SAPI5，支援中文 |
| 系統匣 | `pystray` + `Pillow` | Windows 系統匣標準方案 |
| 設定 UI | `tkinter` (stdlib) | 零額外依賴 |
| 設定檔 | TOML (`tomllib` stdlib) | 人類可讀，Python 3.11 內建 |
| 程式探索 | `winreg` + `pywin32` + `rapidfuzz` | 登錄檔 + 捷徑 + 模糊比對 |
| 程式啟動 | `subprocess` (stdlib) | 安全，`shell=False` |
| 打包 | `PyInstaller` | 打包成 .exe |

### 為什麼不用 openwakeword 做喚醒詞？

`openwakeword` 主要以英文語料訓練，對中文名字（小助手、電腦、小明）效果差。
本計畫改用：

```
[VAD] → 偵測到說話 → [faster-whisper tiny 多語言] → 比對是否含喚醒詞
```

這樣任何語言的名字都能作為喚醒詞，完全不需要訓練。

### 模型對比

| 模型 | 大小 | 推理速度 | 支援語言 | 用途 |
|---|---|---|---|---|
| `faster-whisper tiny` | 72MB | ~100ms | 多語言含中文 | **喚醒詞偵測**（2s 短窗口）|
| `faster-whisper small` | 244MB | ~400ms | 多語言含中文 | **指令識別**（5s 全精度）|

> 注意：不要用 `tiny.en`、`base.en` 等 `.en` 後綴模型，那些是英文專用。

---

## 架構設計

```
[MainApplication]
       │
       ├── [AudioCapture]          PyAudio 16kHz mono 串流
       │         │ PCM chunks
       ├── [VAD]                   silero-vad，只在偵測到語音時傳遞 chunk
       │         │ speech chunks
       ├── [WakeWordEngine]        faster-whisper tiny，2s 視窗 + 關鍵字比對
       │         │ WakeEvent
       ├── [CommandListener]       喚醒後錄音 5 秒
       │         │ PCM buffer
       ├── [Transcriber]           faster-whisper small，高精度中文識別
       │         │ transcript text
       ├── [CommandDispatcher]     解析意圖 → 啟動程式
       │         │
       ├── [ProgramIndex]          程式庫（登錄檔+捷徑+PATH）
       └── [TrayController]        系統匣 + 設定視窗
```

### 核心流程

```
[啟動] → 系統匣常駐
    │
    ▼
[背景聆聽] AudioCapture → VAD → WakeWordEngine（持續）
    │
    ├─ 靜音 → VAD 過濾，WakeWordEngine 不觸發，省 CPU
    │
    ├─ 偵測到語音 → tiny Whisper 轉文字（2秒視窗）
    │       │
    │       ├─ 不含喚醒詞 → 繼續
    │       └─ 含喚醒詞 ─────────────────────────┐
    │                                             ▼
    │                                     播放提示音 ♪
    │                                     圖示變色（listening）
    │                                             │
    │                                     [錄音 5 秒]
    │                                             │
    │                                     [small Whisper STT]
    │                                             │
    │                                     [解析指令]
    │                                             │
    │                                ┌────────────┴─────────────┐
    │                                ▼                           ▼
    │                           "開啟 XXX"               聽不懂/無指令
    │                                │                           │
    │                           [ProgramIndex]          TTS: "請再說一次"
    │                                │
    │                       ┌────────┴────────┐
    │                       ▼                  ▼
    │                   找到程式           找不到
    │                       │                  │
    │                 subprocess.Popen   TTS: "找不到 XXX"
    │                       │
    │                 TTS: "好的，開啟 XXX"
    │                       │
    └───────────────[回到背景聆聽]
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
│   │   ├── capture.py           # AudioCapture：PyAudio 串流（16kHz mono）
│   │   ├── vad.py               # VAD：silero-vad 語音活動偵測
│   │   └── player.py            # play_sound()：播放 .wav 提示音
│   │
│   ├── wake/
│   │   └── engine.py            # WakeWordEngine：tiny Whisper + 關鍵字比對
│   │
│   ├── stt/
│   │   └── transcriber.py       # Transcriber：small Whisper 高精度識別
│   │
│   ├── commands/
│   │   ├── listener.py          # CommandListener：喚醒後錄音邏輯
│   │   ├── dispatcher.py        # CommandDispatcher：意圖解析 + 啟動
│   │   └── intent.py            # parse_intent()：中英文指令解析
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
│       ├── whisper-tiny/
│       └── whisper-small/
│
├── tests/
│   ├── test_intent.py           # 中英文指令解析單元測試
│   ├── test_program_index.py    # ProgramIndex mock 測試
│   └── test_settings.py
│
├── scripts/
│   ├── download_models.py       # 下載 whisper tiny + small 模型
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

# VAD
silero-vad==5.1.2
torch==2.2.2+cpu              # silero-vad 需要，用 CPU-only 版本（~200MB）

# STT（喚醒詞 + 指令）
faster-whisper==1.0.3
ctranslate2==4.3.1

# TTS
pyttsx3>=2.90

# 系統匣
pystray==0.19.5
Pillow==10.3.0

# Windows 登錄檔 + 捷徑解析
pywin32==306

# 設定
tomli-w==1.0.0

# 程式名稱模糊比對
rapidfuzz==3.9.0
```

```txt
# requirements-dev.txt
pytest==8.2.2
pytest-mock==3.14.0
pyinstaller==6.6.0
```

### 下載大小估計

| 套件 | 大小 |
|---|---|
| torch (CPU-only) | ~200MB |
| whisper-tiny 模型 | 72MB |
| whisper-small 模型 | 244MB |
| ctranslate2 + faster-whisper | ~50MB |
| 其餘套件合計 | ~50MB |
| **總計** | **~620MB** |

---

## 設定檔（%APPDATA%\penguin-typeless\config.toml）

```toml
[assistant]
name = "小助手"                # 喚醒詞（支援中文、英文、任意名字）
wake_threshold = 0.7           # 喚醒詞比對相似度閾值（0.5~1.0）
command_capture_seconds = 5.0  # 喚醒後聆聽秒數
wake_model = "tiny"            # 喚醒詞用（多語言 tiny）
command_model = "small"        # 指令識別用（多語言 small）
language = "zh"                # Whisper 語言提示（zh / en / auto）
launch_on_startup = false

[custom_apps]                  # 自訂程式對應
"瀏覽器" = "C:/Program Files/Google/Chrome/Application/chrome.exe"
"記事本" = "notepad.exe"
"小畫家" = "mspaint.exe"
```

---

## 中文指令解析（intent.py）

支援常見中文說法：

```python
PATTERNS_ZH = [
    r"(?:幫我|請)?(?:開啟|打開|啟動|執行|開)\s*(.+)",
    r"(?:開啟|打開|啟動)\s*一下\s*(.+)",
    r"(?:我要|我想)\s*(?:開|用)\s*(.+)",
]

PATTERNS_EN = [
    r"(?:open|launch|start|run|execute)\s+(.+)",
    r"(?:can you |please )?(?:open|launch|start|run)\s+(.+?)(?:\s+for me)?$",
]
```

範例：
- 「小助手，**幫我開啟** Chrome」→ 找 Chrome
- 「小助手，**打開** 記事本」→ 找 notepad
- 「小助手，**open** Spotify」→ 找 Spotify

---

## 程式探索策略（ProgramIndex）

| 優先順序 | 來源 | 說明 |
|---|---|---|
| 1 | `config.toml` 自訂對應 | 最高優先 |
| 2 | Windows 登錄檔 | `HKLM\...\Uninstall\*`，DisplayName + 路徑 |
| 3 | Start Menu 捷徑 | `%APPDATA%` + `%ProgramData%` 下的 `.lnk` |
| 4 | PATH 環境變數 | 收集 PATH 中的 `.exe` |
| 5 | rapidfuzz 模糊比對 | `WRatio` scorer，score_cutoff=70 |

程式名稱正規化：去掉版本號、去掉常見後綴（"Application"、"for Windows"）

---

## 實作階段

### Phase 1 — 音訊管線 + VAD
- `audio/capture.py`：16kHz mono PyAudio 串流，80ms chunks
- `audio/vad.py`：silero-vad，靜音直接跳過（省 ~70% CPU）
- `utils/events.py`：事件 dataclass

### Phase 2 — 設定 + 系統匣
- `settings/schema.py`：`AssistantConfig` dataclass（含 `language`、`wake_model`、`command_model`）
- `settings/manager.py`：TOML 讀寫（`%APPDATA%`）
- `tray/controller.py`：三種狀態圖示（idle / listening / processing）
- `settings/gui.py`：tkinter 設定視窗，可改喚醒詞和語言

### Phase 3 — 喚醒詞引擎
- `wake/engine.py`：
  1. 從 VAD 拿到語音 chunk，累積 2 秒緩衝
  2. `faster-whisper tiny` 轉文字
  3. 比對：transcript 是否含 `config.name`（模糊比對 rapidfuzz，threshold 0.7）
  4. 2 秒 debounce

### Phase 4 — 指令識別
- `commands/listener.py`：喚醒後切換錄音模式，同一音訊串流，錄 5 秒
- `stt/transcriber.py`：`faster-whisper small`，啟動時預載

### Phase 5 — 程式探索 + 分派
- `programs/index.py`：三來源掃描 + rapidfuzz，每 30 分鐘重建
- `commands/intent.py`：中英文 regex 解析
- `commands/dispatcher.py`：`subprocess.Popen`，TTS 回應

### Phase 6 — 主應用程式
- `app.py`：執行緒協調，事件佇列，啟動/關閉順序

### Phase 7 — 打包
- `scripts/build_exe.py`：PyInstaller `--onedir`
- 打包模型（`assets/models/`）、音效、圖示

---

## 喚醒詞比對邏輯

因為 STT 轉錄不一定 100% 精確（例如說「小助手」可能轉成「小住手」），
使用模糊比對而非完全一致：

```python
from rapidfuzz import fuzz

def is_wake_word(transcript: str, wake_word: str, threshold: float = 0.7) -> bool:
    transcript = transcript.lower().strip()
    wake_word = wake_word.lower().strip()
    # 完全包含
    if wake_word in transcript:
        return True
    # 模糊比對（處理 STT 誤差）
    score = fuzz.partial_ratio(wake_word, transcript) / 100.0
    return score >= threshold
```

---

## CPU 使用估計（一般 Intel i5 筆電）

| 狀態 | CPU 使用率 |
|---|---|
| 靜音（VAD 過濾）| ~1-2% |
| 有人說話（tiny Whisper）| ~15-25%（2 秒推理一次）|
| 指令識別（small Whisper）| ~40-60%（約 0.5 秒尖峰）|
| 常駐系統匣（無聲音輸入）| ~1% |

VAD 是關鍵優化：靜音環境下幾乎不耗 CPU。

---

## 後續擴充方向

- 更多指令：「關閉 XXX」「搜尋 XXX」「調音量」
- 接入 Claude API 處理複雜自然語言（現有架構只需在 dispatcher 加一層）
- 支援多個喚醒詞（陣列）
- `medium` 模型選項（更高準確率，需要較好 CPU）
- GPU 加速（`device="cuda"` 傳給 faster-whisper）
