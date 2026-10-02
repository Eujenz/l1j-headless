"""
ui/player_window.py - L1J Headless Player Desktop Game Window (MVP-07)

Layout:
  ┌────────────────────────────────────────────────────────────────┐
  │  標題列  L1J HEADLESS 1.82                      Lv.3 騎士     │
  ├──────────────────────────────────┬─────────────────────────────┤
  │  世界視窗 (Canvas 2D 地圖)         │  玩家狀態面板 (HUD)          │
  │                                  │  HP / MP / EXP / Adena      │
  │   · · · ○ · · ·                  │  目前目標                    │
  │   · ● · · · · ·                  │  目前狀態                    │
  │   · · · ○ · · ·                  │  輔助模組開關                │
  ├──────────────────────────────────┤                             │
  │  快速操作列                        │  背包                       │
  │  [暫停輔助] [攻擊] [喝水] [回城]   │                             │
  │  方向鍵  WASD / ↑↓←→              │                             │
  ├──────────────────────────────────┴─────────────────────────────┤
  │  活動訊息 (繁體中文遊戲事件)                                      │
  └────────────────────────────────────────────────────────────────┘

Performance:
  - World Canvas updates at ~12 FPS (every 80ms).
  - Player HUD updates at ~7 FPS (every 150ms).
  - Activity log: append-only, max 200 lines, never full-redraw.
  - Monster list: diff-only update (compare UIDs before redrawing).
  - All Tkinter widget mutations happen exclusively in main thread.
  - NO direct gameplay mutations from UI handlers.

Tkinter Thread Safety:
  - Background worker: HeadlessPlayerRuntime (separate thread).
  - Main thread only: all .config(), .insert(), canvas.create_*, root.after().
  - Data transfer: PlayerRuntimeSnapshot (immutable projection, copied under lock).
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog
from typing import Optional, List, Any

from native_engine.player_runtime import HeadlessPlayerRuntime, PlayerRuntimeSnapshot
from native_engine.bot.config import AVAILABLE_DESTINATIONS
from .player_view_model import PlayerViewModel
from .config_panel import ConfigPanel
from .world_canvas import WorldCanvas, CANVAS_W, CANVAS_H
from .game_events import (
    BOT_STATE_ZH, ITEM_NAME_ZH, MODULE_ZH, DESTINATION_ZH,
    zh_item, zh_state, zh_dest, zh_class, GameEventFormatter,
)


# ─────────────────────────── Label helpers ──────────────────────────────────

def _zh_dest(dest_name: str) -> str:
    return DESTINATION_ZH.get(dest_name, dest_name)

def _zh_module(key: str) -> str:
    return MODULE_ZH.get(key, key)

def _zh_item(name: str) -> str:
    return ITEM_NAME_ZH.get(name, name)

def _zh_weapon(name: str) -> str:
    return ITEM_NAME_ZH.get(name, name)


# ─────────────────────────────── Main Window ────────────────────────────────

class PlayerWindow:
    """
    Main L1J Headless game window.
    Composition:
      - Left:   WorldCanvas 2D tile view
      - Right:  Player HUD + helper modules + inventory
      - Bottom: Action bar + activity log
    """

    _POLL_CANVAS_MS = 80     # ~12 FPS for world view
    _POLL_HUD_MS    = 150    # ~7 FPS for HP/MP/state
    _POLL_LOG_MS    = 200    # ~5 FPS for activity log
    _LOG_MAX_LINES  = 200    # max lines in activity log before trimming

    def __init__(self, root: tk.Tk, runtime: HeadlessPlayerRuntime):
        self.root = root
        self.runtime = runtime
        self.vm = PlayerViewModel(runtime)

        # State for incremental log updates
        self._last_log_event_count = 0
        self._last_monster_uids: List[int] = []

        # Cached map grid for canvas rendering
        self._map_grid_cache: dict = {}

        # Setup window
        self.root.title("L1J Headless 1.82 — Headless L1J Player")
        self.root.geometry("1100x700")
        self.root.minsize(900, 620)
        self.root.configure(bg="#0f0f1a")

        self._build_styles()
        self._build_ui()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.bind("<KeyPress>", self._on_key_press)

        # Start background simulation
        self.runtime.start_background()

        # Stagger the polling loops to avoid all updating at same frame
        self._canvas_active = True
        self._hud_active = True
        self._log_active = True
        self.root.after(100, self._poll_canvas)
        self.root.after(150, self._poll_hud)
        self.root.after(200, self._poll_log)

    # ─────────────────────────── Styles ─────────────────────────────────────

    def _build_styles(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        # Main title
        style.configure("Title.TLabel",
                        font=("Helvetica", 13, "bold"), foreground="#ccccff", background="#0f0f1a")
        style.configure("Section.TLabel",
                        font=("Helvetica", 9, "bold"), foreground="#aaaadd", background="#15152a")
        style.configure("Value.TLabel",
                        font=("Consolas", 10), foreground="#e0e0ff", background="#15152a")
        style.configure("StatusActive.TLabel",
                        font=("Helvetica", 10, "bold"), foreground="#00dd66", background="#15152a")
        style.configure("StatusPaused.TLabel",
                        font=("Helvetica", 10, "bold"), foreground="#ff9900", background="#15152a")
        style.configure("Danger.TLabel",
                        font=("Helvetica", 10, "bold"), foreground="#ff4444", background="#15152a")
        style.configure("Action.TButton",
                        font=("Helvetica", 9, "bold"))
        style.configure("Pause.TButton",
                        font=("Helvetica", 10, "bold"))
        # Panel frames
        style.configure("Panel.TFrame", background="#15152a")
        style.configure("Dark.TFrame", background="#0f0f1a")
        style.configure("Panel.TLabelframe", background="#15152a")
        style.configure("Panel.TLabelframe.Label", background="#15152a", foreground="#aaaadd",
                        font=("Helvetica", 9, "bold"))

    # ─────────────────────────── UI Build ────────────────────────────────────

    def _build_ui(self) -> None:
        # Main container
        main = ttk.Frame(self.root, style="Dark.TFrame", padding=4)
        main.pack(fill=tk.BOTH, expand=True)

        # ── Title bar ────────────────────────────────────────────────────────
        title_bar = ttk.Frame(main, style="Dark.TFrame")
        title_bar.pack(fill=tk.X, pady=(0, 4))

        ttk.Label(title_bar, text="⚔  L1J HEADLESS 1.82",
                  style="Title.TLabel").pack(side=tk.LEFT, padx=4)

        # Speed selector
        ttk.Label(title_bar, text="節奏：", foreground="#888888",
                  background="#0f0f1a", font=("Helvetica", 9)).pack(side=tk.RIGHT, padx=(0, 2))
        self.speed_var = tk.StringVar(value="1.0x")
        speed_cb = ttk.Combobox(title_bar, textvariable=self.speed_var,
                                values=["0.5x", "1.0x", "2.0x", "5.0x", "10.0x", "極速"],
                                state="readonly", width=9)
        speed_cb.pack(side=tk.RIGHT, padx=4)
        speed_cb.bind("<<ComboboxSelected>>", self._on_speed_changed)

        # Char info (top right)
        self.title_char_lbl = ttk.Label(title_bar, text="Lv 1 騎士",
                                        font=("Helvetica", 10, "bold"),
                                        foreground="#ccccff", background="#0f0f1a")
        self.title_char_lbl.pack(side=tk.RIGHT, padx=12)

        # ── Middle area: Canvas + Right Panel ────────────────────────────────
        mid = ttk.Frame(main, style="Dark.TFrame")
        mid.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        # Left: 2D World Canvas
        left = ttk.Frame(mid, style="Panel.TFrame", padding=2)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.world_canvas = WorldCanvas(left)
        self.world_canvas.pack(fill=tk.BOTH, expand=True)

        # Right panel
        right = ttk.Frame(mid, style="Panel.TFrame", width=280, padding=6)
        right.pack(side=tk.RIGHT, fill=tk.Y)
        right.pack_propagate(False)

        self._build_right_panel(right)

        # ── Bottom: Action bar + Log ─────────────────────────────────────────
        bottom = ttk.Frame(main, style="Dark.TFrame")
        bottom.pack(fill=tk.X)

        self._build_action_bar(bottom)
        self._build_activity_log(bottom)

    def _build_right_panel(self, parent) -> None:
        """Build the right status panel: HP/MP, target, state, helper, inventory."""

        # ─ Character HUD ─────────────────────────────────────────────────────
        hud = ttk.LabelFrame(parent, text="玩家", style="Panel.TLabelframe", padding=6)
        hud.pack(fill=tk.X, pady=(0, 6))

        # HP
        hp_row = ttk.Frame(hud, style="Panel.TFrame")
        hp_row.pack(fill=tk.X, pady=2)
        ttk.Label(hp_row, text="HP", width=4, style="Section.TLabel").pack(side=tk.LEFT)
        self.hp_canvas = tk.Canvas(hp_row, height=14, bg="#220000", highlightthickness=0)
        self.hp_canvas.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.hp_text_lbl = ttk.Label(hp_row, text="100/100", width=9, style="Value.TLabel")
        self.hp_text_lbl.pack(side=tk.LEFT)

        # MP
        mp_row = ttk.Frame(hud, style="Panel.TFrame")
        mp_row.pack(fill=tk.X, pady=2)
        ttk.Label(mp_row, text="MP", width=4, style="Section.TLabel").pack(side=tk.LEFT)
        self.mp_canvas = tk.Canvas(mp_row, height=10, bg="#002222", highlightthickness=0)
        self.mp_canvas.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.mp_text_lbl = ttk.Label(mp_row, text="10/10", width=9, style="Value.TLabel")
        self.mp_text_lbl.pack(side=tk.LEFT)

        # EXP
        exp_row = ttk.Frame(hud, style="Panel.TFrame")
        exp_row.pack(fill=tk.X, pady=2)
        ttk.Label(exp_row, text="EXP", width=4, style="Section.TLabel").pack(side=tk.LEFT)
        self.exp_lbl = ttk.Label(exp_row, text="0", style="Value.TLabel")
        self.exp_lbl.pack(side=tk.LEFT, padx=4)
        self.adena_lbl = ttk.Label(exp_row, text="金幣: 0", style="Value.TLabel", foreground="#ffd700")
        self.adena_lbl.pack(side=tk.RIGHT)

        # Location
        self.loc_lbl = ttk.Label(hud, text="話島村莊", style="Value.TLabel", foreground="#aaaaaa")
        self.loc_lbl.pack(anchor=tk.W)

        # Weapon
        self.weapon_lbl = ttk.Label(hud, text="武器：長劍", style="Value.TLabel")
        self.weapon_lbl.pack(anchor=tk.W)

        # ─ Current Target ────────────────────────────────────────────────────
        tgt = ttk.LabelFrame(parent, text="目前目標", style="Panel.TLabelframe", padding=6)
        tgt.pack(fill=tk.X, pady=(0, 6))
        self.target_name_lbl = ttk.Label(tgt, text="無", style="Value.TLabel")
        self.target_name_lbl.pack(anchor=tk.W)
        self.target_hp_canvas = tk.Canvas(tgt, height=10, bg="#330000", highlightthickness=0)
        self.target_hp_canvas.pack(fill=tk.X, pady=2)
        self.target_hp_text = ttk.Label(tgt, text="", style="Value.TLabel", foreground="#ff6666")
        self.target_hp_text.pack(anchor=tk.W)

        # ─ Bot State ─────────────────────────────────────────────────────────
        state_frame = ttk.LabelFrame(parent, text="狀態", style="Panel.TLabelframe", padding=6)
        state_frame.pack(fill=tk.X, pady=(0, 6))
        self.state_lbl = ttk.Label(state_frame, text="搜尋目標中", style="StatusActive.TLabel")
        self.state_lbl.pack(anchor=tk.W)
        self.dest_lbl = ttk.Label(state_frame, text="獵場：話島地監 1F",
                                  style="Value.TLabel", foreground="#aaaacc")
        self.dest_lbl.pack(anchor=tk.W)

        # Destination change button
        ttk.Button(state_frame, text="更換獵場", command=self._on_change_destination,
                   style="Action.TButton").pack(anchor=tk.W, pady=(4, 0))

        # ─ Helper Modules ────────────────────────────────────────────────────
        helper_frame = ttk.LabelFrame(parent, text="輔助", style="Panel.TLabelframe", padding=6)
        helper_frame.pack(fill=tk.X, pady=(0, 6))

        self.helper_status_lbl = ttk.Label(helper_frame, text="● 輔助運行中",
                                           style="StatusActive.TLabel")
        self.helper_status_lbl.pack(anchor=tk.W, pady=(0, 4))

        # Module dots
        self._module_labels: dict = {}
        modules_display = [
            ("auto_target", "自動選怪"),
            ("auto_attack", "自動攻擊"),
            ("auto_move", "自動移動"),
            ("auto_potion", "自動喝水"),
            ("auto_loot", "自動撿物"),
            ("auto_return", "自動回城"),
        ]
        for key, label in modules_display:
            row = ttk.Frame(helper_frame, style="Panel.TFrame")
            row.pack(fill=tk.X)
            dot = ttk.Label(row, text="● ", foreground="#00cc44",
                            background="#15152a", font=("Helvetica", 9))
            dot.pack(side=tk.LEFT)
            ttk.Label(row, text=label, style="Value.TLabel",
                      font=("Helvetica", 9)).pack(side=tk.LEFT)
            self._module_labels[key] = dot

        # ─ Inventory ─────────────────────────────────────────────────────────
        inv_frame = ttk.LabelFrame(parent, text="背包", style="Panel.TLabelframe", padding=4)
        inv_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        self.inv_listbox = tk.Listbox(
            inv_frame, height=6,
            font=("Consolas", 9),
            bg="#0d0d1e", fg="#ccccee",
            selectbackground="#334466",
            selectforeground="#ffffff",
            activestyle="none",
        )
        self.inv_listbox.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        inv_scroll = ttk.Scrollbar(inv_frame, orient=tk.VERTICAL,
                                   command=self.inv_listbox.yview)
        inv_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.inv_listbox.config(yscrollcommand=inv_scroll.set)
        self.inv_listbox.bind("<Double-Button-1>", self._on_inv_double_click)

    def _build_action_bar(self, parent) -> None:
        """Build the action bar with Pause, attack, potion, return town, D-pad."""
        bar = ttk.Frame(parent, style="Panel.TFrame", padding=6)
        bar.pack(fill=tk.X, pady=(0, 4))

        # Pause / Resume Helper (large prominent button)
        self.pause_btn = tk.Button(
            bar, text="⏸ 暫停輔助",
            command=self._on_toggle_pause,
            bg="#3a2200", fg="#ffaa00",
            activebackground="#554400", activeforeground="#ffffff",
            font=("Helvetica", 10, "bold"),
            relief=tk.FLAT, padx=8, pady=4,
        )
        self.pause_btn.pack(side=tk.LEFT, padx=4)

        ttk.Separator(bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)

        # Quick action buttons
        btn_cfg = [
            ("⚔ 攻擊", self._on_manual_attack),
            ("🧪 喝藥水", self._on_drink_potion),
            ("🏠 回城", self._on_return_town),
        ]
        for text, cmd in btn_cfg:
            ttk.Button(bar, text=text, command=cmd, style="Action.TButton",
                       width=9).pack(side=tk.LEFT, padx=3)

        ttk.Separator(bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)

        # D-Pad (compact)
        dpad = ttk.Frame(bar, style="Panel.TFrame")
        dpad.pack(side=tk.LEFT)

        # Compact 3x3 grid
        pad_cfg = [
            ("↖", 7, 0, 0), ("↑", 0, 0, 1), ("↗", 1, 0, 2),
            ("←", 6, 1, 0), ("·", -1, 1, 1), ("→", 2, 1, 2),
            ("↙", 5, 2, 0), ("↓", 4, 2, 1), ("↘", 3, 2, 2),
        ]
        for txt, heading, row, col in pad_cfg:
            if heading == -1:
                ttk.Label(dpad, text="●", foreground="#00cc44",
                          background="#15152a", font=("Helvetica", 10)).grid(
                    row=row, column=col, padx=1, pady=1)
            else:
                h = heading  # capture for lambda
                tk.Button(dpad, text=txt, width=3,
                          command=lambda hd=h: self.vm.manual_move(hd),
                          bg="#1a1a2e", fg="#ccccff",
                          activebackground="#333355",
                          font=("Helvetica", 9), relief=tk.FLAT,
                          padx=2, pady=1).grid(row=row, column=col, padx=1, pady=1)

        ttk.Separator(bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)

        # Config button
        ttk.Button(bar, text="⚙ 設定", command=self.open_config_dialog,
                   style="Action.TButton").pack(side=tk.LEFT, padx=4)

        # Nearby monsters (compact listbox on right side of action bar)
        mon_box = ttk.LabelFrame(bar, text="附近怪物", style="Panel.TLabelframe", padding=2)
        mon_box.pack(side=tk.RIGHT, padx=6)
        self.monster_listbox = tk.Listbox(
            mon_box, height=4, width=28,
            font=("Consolas", 8),
            bg="#0d0d1e", fg="#ff8888",
            selectbackground="#441111",
            selectforeground="#ffffff",
            activestyle="none",
        )
        self.monster_listbox.pack(side=tk.LEFT, fill=tk.BOTH)
        self.monster_listbox.bind("<Double-Button-1>", self._on_monster_double_click)
        self.monster_listbox.bind("<<ListboxSelect>>", self._on_monster_select)

    def _build_activity_log(self, parent) -> None:
        """Build the Chinese game activity log (bounded, append-only)."""
        log_frame = ttk.LabelFrame(parent, text="活動訊息", style="Panel.TLabelframe", padding=4)
        log_frame.pack(fill=tk.X)

        self.log_text = tk.Text(
            log_frame,
            height=5,
            font=("Consolas", 9),
            bg="#0a0a1a", fg="#cccccc",
            wrap=tk.WORD,
            state=tk.DISABLED,  # Read-only
        )
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL,
                                   command=self.log_text.yview)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=log_scroll.set)

        # Tag colors for different event types
        self.log_text.tag_configure("damage", foreground="#ff8888")
        self.log_text.tag_configure("death", foreground="#ff4444")
        self.log_text.tag_configure("heal", foreground="#44ff88")
        self.log_text.tag_configure("loot", foreground="#ffd700")
        self.log_text.tag_configure("levelup", foreground="#ffff00", font=("Consolas", 9, "bold"))
        self.log_text.tag_configure("map", foreground="#88aaff")
        self.log_text.tag_configure("shop", foreground="#aaddff")
        self.log_text.tag_configure("return", foreground="#ffaa66")
        self.log_text.tag_configure("default", foreground="#cccccc")

    # ─────────────────────────── Polling Loops ───────────────────────────────

    def _poll_canvas(self) -> None:
        """Update 2D world canvas at ~12 FPS."""
        if not self._canvas_active:
            return
        try:
            snap = self.vm.get_cached_snapshot()
            if snap is not None:
                grid = self._get_map_grid(snap.map_id)
                self.world_canvas.update_view(snap, grid)
        except Exception as e:
            pass  # Canvas errors must never freeze the game
        self.root.after(self._POLL_CANVAS_MS, self._poll_canvas)

    def _poll_hud(self) -> None:
        """Update player HUD, target, state, helper, inventory at ~7 FPS."""
        if not self._hud_active:
            return
        try:
            snap = self.vm.refresh_snapshot()
            self._update_hud(snap)
        except Exception as e:
            pass
        self.root.after(self._POLL_HUD_MS, self._poll_hud)

    def _poll_log(self) -> None:
        """Update activity log at ~5 FPS (append-only)."""
        if not self._log_active:
            return
        try:
            snap = self.vm.get_cached_snapshot()
            if snap is not None and hasattr(snap, "game_events"):
                self._append_new_events(snap.game_events)
        except Exception as e:
            pass
        self.root.after(self._POLL_LOG_MS, self._poll_log)

    def _get_map_grid(self, map_id: int):
        """Get cached WorldMapGrid for a given map_id."""
        if map_id not in self._map_grid_cache:
            try:
                self._map_grid_cache[map_id] = self.runtime.session.world.maps.get(map_id)
            except Exception:
                self._map_grid_cache[map_id] = None
        return self._map_grid_cache[map_id]

    # ─────────────────────────── HUD Update ──────────────────────────────────

    def _update_hud(self, snap: PlayerRuntimeSnapshot) -> None:
        """Update all HUD widgets from snapshot (called in main thread)."""
        # Title char info
        class_zh = {1: "騎士", 2: "魔法師", 3: "精靈"}.get(snap.class_type, "冒險者")
        self.title_char_lbl.config(text=f"Lv {snap.level} {class_zh}")

        # HP bar (Canvas-based for color control)
        hp_ratio = max(0.0, min(1.0, snap.hp / max(1, snap.max_hp)))
        hp_color = "#00cc44" if hp_ratio > 0.5 else ("#ffaa00" if hp_ratio > 0.25 else "#ff2222")
        self._draw_bar(self.hp_canvas, hp_ratio, hp_color)
        self.hp_text_lbl.config(text=f"{snap.hp}/{snap.max_hp}")

        # MP bar
        mp_ratio = max(0.0, min(1.0, snap.mp / max(1, snap.max_mp)))
        self._draw_bar(self.mp_canvas, mp_ratio, "#2244cc")
        self.mp_text_lbl.config(text=f"{snap.mp}/{snap.max_mp}")

        # EXP / Adena
        self.exp_lbl.config(text=f"EXP: {snap.exp:,}")
        self.adena_lbl.config(text=f"金幣: {snap.adena:,}")

        # Location
        self.loc_lbl.config(text=f"{snap.map_name} ({snap.x}, {snap.y})")

        # Weapon
        self.weapon_lbl.config(text=f"武器：{_zh_weapon(snap.equipped_weapon_name)}")

        # Target
        if snap.active_target:
            t = snap.active_target
            self.target_name_lbl.config(text=t["name"], foreground="#ff8888")
            t_ratio = max(0.0, min(1.0, t["hp"] / max(1, t["max_hp"])))
            self._draw_bar(self.target_hp_canvas, t_ratio, "#cc2222")
            self.target_hp_text.config(text=f"HP {t['hp']} / {t['max_hp']}")
        else:
            self.target_name_lbl.config(text="無", foreground="#666688")
            self._draw_bar(self.target_hp_canvas, 0.0, "#440000")
            self.target_hp_text.config(text="")

        # Bot state (Chinese)
        state_zh = BOT_STATE_ZH.get(snap.bot_state, snap.bot_state)
        if snap.is_dead:
            self.state_lbl.config(text="💀 死亡", style="Danger.TLabel")
        elif snap.helper_paused:
            self.state_lbl.config(text="⏸ 輔助已暫停 (手動模式)", style="StatusPaused.TLabel")
        else:
            self.state_lbl.config(text=f"▶ {state_zh}", style="StatusActive.TLabel")

        # Destination
        dest_zh = _zh_dest(snap.hunting_destination_name)
        self.dest_lbl.config(text=f"獵場：{dest_zh}")

        # Helper pause button
        if snap.helper_paused:
            self.pause_btn.config(text="▶ 恢復輔助",
                                  bg="#002222", fg="#00cc88")
            self.helper_status_lbl.config(text="○ 輔助已暫停", style="StatusPaused.TLabel")
        else:
            self.pause_btn.config(text="⏸ 暫停輔助",
                                  bg="#3a2200", fg="#ffaa00")
            self.helper_status_lbl.config(text="● 輔助運行中", style="StatusActive.TLabel")

        # Helper module dots
        modules = snap.helper_modules
        for key, dot_lbl in self._module_labels.items():
            on = modules.get(key, True)
            dot_lbl.config(text="● ", foreground="#00cc44" if on else "#666666")

        # Inventory (diff-update only when changed)
        self._update_inventory(snap.inventory)

        # Monster list (diff-update)
        self._update_monsters(snap.nearby_monsters, snap.active_target)

    def _draw_bar(self, canvas: tk.Canvas, ratio: float, color: str) -> None:
        """Draw a simple progress bar on a Canvas widget."""
        canvas.update_idletasks()
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w <= 1:
            return
        canvas.delete("all")
        fill_w = int(w * ratio)
        if fill_w > 0:
            canvas.create_rectangle(0, 0, fill_w, h, fill=color, outline="")

    def _update_inventory(self, inventory: list) -> None:
        """Diff-update inventory listbox."""
        # Simple strategy: rebuild if item count or any name changed
        current_items = [
            (i["item_id"], i["count"]) for i in inventory
        ]
        if hasattr(self, "_last_inv_items") and self._last_inv_items == current_items:
            return
        self._last_inv_items = current_items
        self.inv_listbox.delete(0, tk.END)
        for item in inventory:
            eq_str = "◆ " if item.get("is_equipped") else "   "
            name_zh = _zh_item(item["name"])
            self.inv_listbox.insert(tk.END, f"{eq_str}{name_zh:<12} x{item['count']}")

    def _update_monsters(self, monsters: list, active_target) -> None:
        """Diff-update monster listbox if UIDs changed."""
        new_uids = [m.get("uid", 0) for m in monsters[:20]]
        if new_uids == self._last_monster_uids:
            # Still diff-update HP values (they change frequently)
            pass
        self._last_monster_uids = new_uids
        target_uid = active_target["uid"] if active_target else None
        self.monster_listbox.delete(0, tk.END)
        for m in monsters[:20]:
            marker = "★ " if m.get("uid") == target_uid else "   "
            hp_pct = int(m["hp"] / max(1, m["max_hp"]) * 100)
            line = f"{marker}{m['name']:<10} HP:{hp_pct:>3}% (d={m['dist']})"
            self.monster_listbox.insert(tk.END, line)

    def _append_new_events(self, game_events: list) -> None:
        """Append-only log update. Only adds events we haven't shown yet."""
        total = len(game_events)
        if total <= self._last_log_event_count:
            return
        new_events = game_events[self._last_log_event_count:]
        self._last_log_event_count = total

        self.log_text.config(state=tk.NORMAL)
        for evt in new_events:
            ts = GameEventFormatter.format_time(evt.timestamp_ms)
            line = f"[{ts}] {evt.text}\n"

            tag = self._event_tag(evt.type)
            self.log_text.insert(tk.END, line, tag)

        # Trim top if over max lines
        line_count = int(self.log_text.index("end-1c").split(".")[0])
        if line_count > self._LOG_MAX_LINES:
            excess = line_count - self._LOG_MAX_LINES
            self.log_text.delete("1.0", f"{excess + 1}.0")

        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _event_tag(self, event_type: str) -> str:
        return {
            "COMBAT_DAMAGE": "damage",
            "MONSTER_DEATH": "death",
            "COMBAT_HEAL": "heal",
            "ITEM_USED": "heal",
            "LOOT_PICKED": "loot",
            "LEVEL_UP": "levelup",
            "MAP_TRANSITION": "map",
            "SHOP_PURCHASE": "shop",
            "RETURN_STARTED": "return",
            "PLAYER_DEATH": "damage",
            "RESPAWN": "heal",
        }.get(event_type, "default")

    # ─────────────────────────── Button Handlers ─────────────────────────────

    def _on_toggle_pause(self) -> None:
        self.vm.toggle_helper_pause()

    def _on_manual_attack(self) -> None:
        self.vm.manual_attack()

    def _on_drink_potion(self) -> None:
        self.vm.manual_use_item(104)  # Red Potion

    def _on_return_town(self) -> None:
        self.vm.manual_return_town()

    def _on_monster_select(self, event=None) -> None:
        """Select monster as target on single click."""
        sel = self.monster_listbox.curselection()
        if sel:
            snap = self.vm.snapshot
            idx = sel[0]
            if idx < len(snap.nearby_monsters):
                uid = snap.nearby_monsters[idx].get("uid")
                if uid is not None:
                    self.vm.manual_select_target(uid)

    def _on_monster_double_click(self, event=None) -> None:
        """Attack selected monster on double click."""
        self._on_monster_select()
        self.vm.manual_attack()

    def _on_inv_double_click(self, event=None) -> None:
        """Use item on double click."""
        sel = self.inv_listbox.curselection()
        if sel:
            snap = self.vm.snapshot
            idx = sel[0]
            if idx < len(snap.inventory):
                item = snap.inventory[idx]
                self.vm.manual_use_item(item["item_id"])

    def _on_change_destination(self) -> None:
        """Open destination selection dialog."""
        dest_options = {
            "話島地監 1F": "ti_dungeon_1f",
            "話島野外": "ti_surface_field",
        }
        choices = list(dest_options.keys())
        # Simple selection dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("選擇獵場")
        dialog.geometry("260x160")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="選擇狩獵目的地：",
                  font=("Helvetica", 10, "bold")).pack(pady=(16, 8))

        var = tk.StringVar(value=choices[0])
        cb = ttk.Combobox(dialog, textvariable=var, values=choices,
                          state="readonly", width=24)
        cb.pack(pady=4)

        def confirm():
            key = dest_options.get(var.get(), "ti_dungeon_1f")
            self.vm.set_destination(key)
            dialog.destroy()

        ttk.Button(dialog, text="確認切換", command=confirm).pack(pady=12)
        dialog.bind("<Return>", lambda e: confirm())

    def _on_speed_changed(self, event=None) -> None:
        val = self.speed_var.get()
        speed_map = {
            "0.5x": 0.5, "1.0x": 1.0, "2.0x": 2.0,
            "5.0x": 5.0, "10.0x": 10.0, "極速": 100.0,
        }
        speed = speed_map.get(val, 1.0)
        self.vm.set_speed(speed)

    def _on_key_press(self, event) -> None:
        """WASD keyboard movement."""
        key_heading = {"w": 0, "a": 6, "s": 4, "d": 2,
                       "W": 0, "A": 6, "S": 4, "D": 2}
        heading = key_heading.get(event.char)
        if heading is not None:
            self.vm.manual_move(heading)

    def open_config_dialog(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("輔助設定")
        dialog.geometry("680x560")
        dialog.minsize(600, 480)
        dialog.transient(self.root)

        panel = ConfigPanel(dialog, view_model=self.vm)
        panel.pack(fill=tk.BOTH, expand=True)

    def on_close(self) -> None:
        self._canvas_active = False
        self._hud_active = False
        self._log_active = False
        self.runtime.stop_background()
        self.root.destroy()


# ─────────────────────────────────── main() ──────────────────────────────────

def main(
    config_path: str = "configs/autonomous_default.json",
    contract_path: Optional[str] = None,
    seed: Optional[int] = 777777,
    speed: float = 1.0,
    dest_key: Optional[str] = None,
    legacy_root: Optional[str] = None,
    show_startup: bool = True,
) -> None:
    """
    Launch the interactive Headless Player game window.
    
    If show_startup=True (default), shows the startup dialog first so the
    player can choose destination and helper profile before the world starts.
    """
    if show_startup:
        from .startup_dialog import StartupDialog
        dlg = StartupDialog(
            configs_dir="configs",
            default_config=config_path,
            default_dest_key=dest_key or "ti_dungeon_1f",
        )
        result = dlg.show()
        if result is None:
            return  # User cancelled

        config_path = result["config_path"]
        speed = result["speed"]
        chosen_dest_key = result["dest_key"]
    else:
        chosen_dest_key = dest_key or "ti_dungeon_1f"

    # Create runtime AFTER user confirms (so world doesn't start during selection)
    runtime = HeadlessPlayerRuntime(
        config_path=config_path,
        contract_path=contract_path,
        seed=seed,
        speed=speed,
        legacy_root=legacy_root,
    )

    # Apply chosen destination
    if chosen_dest_key and chosen_dest_key in AVAILABLE_DESTINATIONS:
        runtime.set_destination(chosen_dest_key)

    # Launch game window
    root = tk.Tk()
    app = PlayerWindow(root, runtime=runtime)
    root.mainloop()


if __name__ == "__main__":
    main()
