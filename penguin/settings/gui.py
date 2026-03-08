"""Settings window built with tkinter (no extra dependencies)."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from penguin.settings.schema import AssistantConfig

logger = logging.getLogger(__name__)


class SettingsWindow:
    """Opens a modal settings dialog.

    Args:
        cfg: Current configuration (will be modified in-place on save).
        on_save: Called with the updated config when the user clicks Save.
    """

    def __init__(
        self,
        cfg: AssistantConfig,
        on_save: Callable[[AssistantConfig], None] | None = None,
    ) -> None:
        self._cfg = cfg
        self._on_save = on_save

    def show(self) -> None:
        root = tk.Tk()
        root.title("Penguin 語音助理 — 設定")
        root.resizable(False, False)
        self._build(root)
        root.mainloop()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build(self, root: tk.Tk) -> None:
        pad = {"padx": 10, "pady": 6}

        frame = ttk.Frame(root, padding=16)
        frame.grid(sticky="nsew")

        # --- Wake word ---
        ttk.Label(frame, text="喚醒詞名字：").grid(row=0, column=0, sticky="w", **pad)
        name_var = tk.StringVar(value=self._cfg.name)
        ttk.Entry(frame, textvariable=name_var, width=20).grid(row=0, column=1, sticky="w", **pad)

        # --- Language ---
        ttk.Label(frame, text="語言：").grid(row=1, column=0, sticky="w", **pad)
        lang_var = tk.StringVar(value=self._cfg.language)
        lang_combo = ttk.Combobox(
            frame, textvariable=lang_var, width=10,
            values=["zh", "en", "auto"], state="readonly"
        )
        lang_combo.grid(row=1, column=1, sticky="w", **pad)

        # --- Wake model ---
        ttk.Label(frame, text="喚醒詞模型：").grid(row=2, column=0, sticky="w", **pad)
        wake_model_var = tk.StringVar(value=self._cfg.wake_model)
        ttk.Combobox(
            frame, textvariable=wake_model_var, width=10,
            values=["tiny", "base"], state="readonly"
        ).grid(row=2, column=1, sticky="w", **pad)

        # --- Command model ---
        ttk.Label(frame, text="指令識別模型：").grid(row=3, column=0, sticky="w", **pad)
        cmd_model_var = tk.StringVar(value=self._cfg.command_model)
        ttk.Combobox(
            frame, textvariable=cmd_model_var, width=10,
            values=["base", "small", "medium"], state="readonly"
        ).grid(row=3, column=1, sticky="w", **pad)

        # --- Wake threshold ---
        ttk.Label(frame, text="喚醒靈敏度：").grid(row=4, column=0, sticky="w", **pad)
        threshold_var = tk.DoubleVar(value=self._cfg.wake_threshold)
        threshold_scale = ttk.Scale(frame, from_=0.5, to=1.0, variable=threshold_var,
                                    orient="horizontal", length=120)
        threshold_scale.grid(row=4, column=1, sticky="w", **pad)
        threshold_lbl = ttk.Label(frame, text=f"{self._cfg.wake_threshold:.2f}", width=5)
        threshold_lbl.grid(row=4, column=2, sticky="w")
        threshold_var.trace_add("write", lambda *_: threshold_lbl.config(
            text=f"{threshold_var.get():.2f}"
        ))

        # --- Command capture seconds ---
        ttk.Label(frame, text="指令聆聽秒數：").grid(row=5, column=0, sticky="w", **pad)
        capture_var = tk.DoubleVar(value=self._cfg.command_capture_seconds)
        ttk.Spinbox(frame, from_=2.0, to=10.0, increment=0.5,
                    textvariable=capture_var, width=6).grid(row=5, column=1, sticky="w", **pad)

        # --- Startup ---
        startup_var = tk.BooleanVar(value=self._cfg.launch_on_startup)
        ttk.Checkbutton(frame, text="開機時自動啟動", variable=startup_var).grid(
            row=6, column=0, columnspan=2, sticky="w", **pad
        )

        ttk.Separator(frame, orient="horizontal").grid(
            row=7, column=0, columnspan=3, sticky="ew", pady=8
        )

        # --- Buttons ---
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=8, column=0, columnspan=3, sticky="e")
        ttk.Button(btn_frame, text="取消", command=root.destroy).pack(side="right", padx=4)
        ttk.Button(
            btn_frame, text="儲存",
            command=lambda: self._save(
                root, name_var, lang_var, wake_model_var, cmd_model_var,
                threshold_var, capture_var, startup_var
            )
        ).pack(side="right", padx=4)

        root = frame.winfo_toplevel()

    def _save(self, root, name_var, lang_var, wake_model_var,
              cmd_model_var, threshold_var, capture_var, startup_var) -> None:
        name = name_var.get().strip()
        if not name:
            messagebox.showerror("錯誤", "喚醒詞不能為空")
            return

        self._cfg.name = name
        self._cfg.language = lang_var.get()
        self._cfg.wake_model = wake_model_var.get()
        self._cfg.command_model = cmd_model_var.get()
        self._cfg.wake_threshold = round(threshold_var.get(), 2)
        self._cfg.command_capture_seconds = capture_var.get()
        self._cfg.launch_on_startup = startup_var.get()

        if self._on_save:
            self._on_save(self._cfg)

        messagebox.showinfo("已儲存", "設定已儲存，重新啟動後生效。")
        root.destroy()
