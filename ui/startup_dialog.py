"""
ui/startup_dialog.py - L1J Headless Player Launch Screen

Shows a startup dialog for player to select hunting area, helper profile,
and speed before starting the game session. The HeadlessPlayerRuntime is
created AFTER the player confirms, ensuring intentional start and no
background simulation running during selection.

Flow:
  python mvp.py
    → StartupDialog opens (modal)
    → Player selects destination + profile
    → [開始遊戲] clicked
    → HeadlessPlayerRuntime created with chosen config
    → PlayerWindow opens with running game
"""
import os
import glob
import tkinter as tk
from tkinter import ttk
from typing import Optional, Dict

from native_engine.bot.config import AVAILABLE_DESTINATIONS
from ui.game_events import DESTINATION_ZH


# Destination display names (Chinese → key mapping)
DEST_OPTIONS = {
    "話島地監 1F": "ti_dungeon_1f",
    "話島野外": "ti_surface_field",
}

SPEED_OPTIONS = {
    "真實節奏 (1.0x)": 1.0,
    "快速 (2.0x)": 2.0,
    "超快 (5.0x)": 5.0,
    "極速": 100.0,
}


class StartupDialog:
    """
    Launch screen dialog. Blocks until user clicks [開始遊戲] or closes the window.
    After confirm(), call .result to get the chosen options dict.
    """

    def __init__(
        self,
        configs_dir: str = "configs",
        default_config: str = "configs/autonomous_default.json",
        default_dest_key: str = "ti_dungeon_1f",
    ):
        self.configs_dir = configs_dir
        self.default_config = default_config
        self.result: Optional[Dict] = None   # Set when user confirms

        self.root = tk.Tk()
        self.root.title("L1J Headless 1.82 — 啟動遊戲")
        self.root.resizable(False, False)

        # Center on screen
        w, h = 480, 340
        self.root.geometry(f"{w}x{h}")
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

        self._build_ui(default_config, default_dest_key)
        self.root.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _find_configs(self) -> list:
        """Scan configs/ directory for all .json profiles."""
        if not os.path.isdir(self.configs_dir):
            return [self.default_config]
        configs = sorted(glob.glob(os.path.join(self.configs_dir, "*.json")))
        return configs if configs else [self.default_config]

    def _build_ui(self, default_config: str, default_dest_key: str) -> None:
        main = ttk.Frame(self.root, padding=24)
        main.pack(fill=tk.BOTH, expand=True)

        # Title
        ttk.Label(main, text="L1J HEADLESS 1.82", font=("Helvetica", 16, "bold")).pack(pady=(0, 4))
        ttk.Label(main, text="Lineage I 放置遊戲入口", font=("Helvetica", 10), foreground="gray").pack(pady=(0, 16))

        # Separator
        ttk.Separator(main, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 16))

        form = ttk.Frame(main)
        form.pack(fill=tk.X)

        # Hunting Destination
        ttk.Label(form, text="獵場選擇：", font=("Helvetica", 10, "bold")).grid(
            row=0, column=0, sticky=tk.W, padx=(0, 12), pady=6)
        self.dest_var = tk.StringVar()
        dest_labels = list(DEST_OPTIONS.keys())
        # Set default
        default_zh = next((k for k, v in DEST_OPTIONS.items() if v == default_dest_key), dest_labels[0])
        self.dest_var.set(default_zh)
        dest_combo = ttk.Combobox(
            form, textvariable=self.dest_var,
            values=dest_labels,
            state="readonly", width=22
        )
        dest_combo.grid(row=0, column=1, sticky=tk.W, pady=6)

        # Helper Profile
        ttk.Label(form, text="輔助設定檔：", font=("Helvetica", 10, "bold")).grid(
            row=1, column=0, sticky=tk.W, padx=(0, 12), pady=6)
        self.config_var = tk.StringVar()
        available_configs = self._find_configs()
        config_names = [os.path.basename(c) for c in available_configs]
        # Match default
        default_name = os.path.basename(default_config)
        self.config_var.set(default_name if default_name in config_names else (config_names[0] if config_names else ""))
        config_combo = ttk.Combobox(
            form, textvariable=self.config_var,
            values=config_names,
            state="readonly", width=30
        )
        config_combo.grid(row=1, column=1, sticky=tk.W, pady=6)
        self._config_files = {os.path.basename(c): c for c in available_configs}

        # Speed
        ttk.Label(form, text="遊戲節奏：", font=("Helvetica", 10, "bold")).grid(
            row=2, column=0, sticky=tk.W, padx=(0, 12), pady=6)
        self.speed_var = tk.StringVar(value="真實節奏 (1.0x)")
        speed_combo = ttk.Combobox(
            form, textvariable=self.speed_var,
            values=list(SPEED_OPTIONS.keys()),
            state="readonly", width=22
        )
        speed_combo.grid(row=2, column=1, sticky=tk.W, pady=6)

        # Info text
        ttk.Separator(main, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(16, 12))
        info_lbl = ttk.Label(
            main,
            text="角色從話島村莊出發，輔助系統會自動前往選定獵場。\n"
                 "你可以隨時暫停輔助，手動控制角色。",
            foreground="gray", font=("Helvetica", 9), justify=tk.CENTER
        )
        info_lbl.pack(pady=(0, 12))

        # Buttons
        btn_frame = ttk.Frame(main)
        btn_frame.pack()

        start_btn = ttk.Button(
            btn_frame, text="  開始遊戲  ",
            command=self._on_start, style="Accent.TButton"
        )
        start_btn.pack(side=tk.LEFT, padx=8, ipadx=8, ipady=4)

        cancel_btn = ttk.Button(btn_frame, text="離開", command=self._on_cancel)
        cancel_btn.pack(side=tk.LEFT, padx=8)

        # Bind Enter key to start
        self.root.bind("<Return>", lambda e: self._on_start())

    def _on_start(self) -> None:
        dest_zh = self.dest_var.get()
        dest_key = DEST_OPTIONS.get(dest_zh, "ti_dungeon_1f")
        config_name = self.config_var.get()
        config_path = self._config_files.get(config_name, self.default_config)
        speed_label = self.speed_var.get()
        speed = SPEED_OPTIONS.get(speed_label, 1.0)

        self.result = {
            "dest_key": dest_key,
            "config_path": config_path,
            "speed": speed,
        }
        self.root.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self.root.destroy()

    def show(self) -> Optional[Dict]:
        """Show modal dialog and return result dict, or None if cancelled."""
        self.root.mainloop()
        return self.result
