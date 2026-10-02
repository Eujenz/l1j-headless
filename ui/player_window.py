"""
ui/player_window.py - Main Interactive Window for L1J Headless Player

Features:
  - Real-time Player HUD (HP/MP progress bars, EXP, Level, Adena, Position, Weapon)
  - Helper Automation Status Badge (Active / Paused) & Real-time Speed Scaler
  - Manual Directional Movement Pad (NW, N, NE, W, E, SW, S, SE)
  - Manual Action Buttons (Select Target, Attack, Drink Potion, Return Town)
  - Nearby Monsters Listbox with direct targeting & engagement
  - Inventory Listbox with item usage
  - Live Activity Log & Trace Monitor
  - Embedded Config Settings Dialog
  - Thread-safe periodic polling via root.after()
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from typing import Optional

from native_engine.player_runtime import HeadlessPlayerRuntime, PlayerRuntimeSnapshot
from .player_view_model import PlayerViewModel
from .config_panel import ConfigPanel


class PlayerWindow:
    """
    Main desktop window for the L1J Headless Player.
    """

    def __init__(self, root: tk.Tk, runtime: Optional[HeadlessPlayerRuntime] = None):
        self.root = root
        self.root.title("L1J Headless 1.82 - Interactive Player Client")
        self.root.geometry("1060x780")
        self.root.minsize(960, 680)

        # 1. Initialize Runtime & ViewModel
        self.runtime = runtime or HeadlessPlayerRuntime(speed=1.0)
        self.vm = PlayerViewModel(self.runtime)

        # 2. Build UI Layout
        self._build_styles()
        self._build_ui()

        # 3. Setup Window Close Protocol
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # 4. Start Background Simulation & Polling Loop
        self.runtime.start_background()
        self._polling_active = True
        self.root.after(100, self._poll_tick)

    def _build_styles(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Header.TLabel", font=("Helvetica", 14, "bold"))
        style.configure("SubHeader.TLabel", font=("Helvetica", 10, "bold"))
        style.configure("StatusActive.TLabel", font=("Helvetica", 11, "bold"), foreground="green")
        style.configure("StatusPaused.TLabel", font=("Helvetica", 11, "bold"), foreground="darkorange")
        style.configure("Action.TButton", font=("Helvetica", 9, "bold"))

    def _build_ui(self) -> None:
        main_frame = ttk.Frame(self.root, padding=8)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # -----------------------------------------------------------------------
        # TOP: Player Status & Control HUD
        # -----------------------------------------------------------------------
        top_hud = ttk.LabelFrame(main_frame, text="角色狀態 (Player HUD)", padding=8)
        top_hud.pack(fill=tk.X, pady=(0, 6))

        # Row 0: Character details
        info_frame = ttk.Frame(top_hud)
        info_frame.pack(fill=tk.X)

        self.char_name_lbl = ttk.Label(info_frame, text="Arthur (Knight)", style="Header.TLabel")
        self.char_name_lbl.pack(side=tk.LEFT, padx=5)

        self.level_lbl = ttk.Label(info_frame, text="Lv 1 (0 EXP)", font=("Helvetica", 10, "bold"))
        self.level_lbl.pack(side=tk.LEFT, padx=10)

        self.location_lbl = ttk.Label(info_frame, text="話島村莊 (32477, 32875)", font=("Helvetica", 10))
        self.location_lbl.pack(side=tk.LEFT, padx=10)

        self.adena_lbl = ttk.Label(info_frame, text="1,000 Adena", font=("Helvetica", 10, "bold"), foreground="goldenrod")
        self.adena_lbl.pack(side=tk.LEFT, padx=10)

        self.weapon_lbl = ttk.Label(info_frame, text="武器: Long Sword", font=("Helvetica", 10))
        self.weapon_lbl.pack(side=tk.LEFT, padx=10)

        # Right side: Speed and Config button
        ctrl_frame = ttk.Frame(info_frame)
        ctrl_frame.pack(side=tk.RIGHT)

        ttk.Label(ctrl_frame, text="節奏速度:").pack(side=tk.LEFT, padx=2)
        self.speed_var = tk.StringVar(value="1.0x")
        self.speed_combo = ttk.Combobox(
            ctrl_frame,
            textvariable=self.speed_var,
            values=["0.5x", "1.0x", "2.0x", "5.0x", "10.0x", "極速 Instant"],
            state="readonly",
            width=12,
        )
        self.speed_combo.pack(side=tk.LEFT, padx=4)
        self.speed_combo.bind("<<ComboboxSelected>>", self._on_speed_changed)

        cfg_btn = ttk.Button(ctrl_frame, text="⚙ Helper 設定", command=self.open_config_dialog)
        cfg_btn.pack(side=tk.LEFT, padx=4)

        # Row 1: HP & MP Bars & Helper Status Badge
        bars_frame = ttk.Frame(top_hud, padding=(0, 4, 0, 0))
        bars_frame.pack(fill=tk.X)

        # HP Bar
        ttk.Label(bars_frame, text="HP:", font=("Helvetica", 9, "bold")).pack(side=tk.LEFT, padx=(5, 2))
        self.hp_bar = ttk.Progressbar(bars_frame, length=180, maximum=100)
        self.hp_bar.pack(side=tk.LEFT, padx=(0, 5))
        self.hp_text_lbl = ttk.Label(bars_frame, text="100 / 100", width=12)
        self.hp_text_lbl.pack(side=tk.LEFT)

        # MP Bar
        ttk.Label(bars_frame, text="MP:", font=("Helvetica", 9, "bold")).pack(side=tk.LEFT, padx=(10, 2))
        self.mp_bar = ttk.Progressbar(bars_frame, length=120, maximum=100)
        self.mp_bar.pack(side=tk.LEFT, padx=(0, 5))
        self.mp_text_lbl = ttk.Label(bars_frame, text="10 / 10", width=10)
        self.mp_text_lbl.pack(side=tk.LEFT)

        # Helper Status Badge
        self.helper_badge_lbl = ttk.Label(bars_frame, text="● HELPER ACTIVE", style="StatusActive.TLabel")
        self.helper_badge_lbl.pack(side=tk.RIGHT, padx=10)

        # -----------------------------------------------------------------------
        # MIDDLE: Paned Window (Left: Monsters/Inventory, Center: D-Pad, Right: Logs)
        # -----------------------------------------------------------------------
        paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, pady=4)

        # --- LEFT PANEL: Nearby Monsters & Inventory ---
        left_panel = ttk.Frame(paned, width=320, padding=4)
        paned.add(left_panel, weight=1)

        # Nearby Monsters
        mon_group = ttk.LabelFrame(left_panel, text="感知範圍怪物 (Nearby Monsters)", padding=6)
        mon_group.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        self.monster_listbox = tk.Listbox(mon_group, height=7, font=("Consolas", 9), selectmode=tk.SINGLE)
        self.monster_listbox.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        mon_scroll = ttk.Scrollbar(mon_group, orient=tk.VERTICAL, command=self.monster_listbox.yview)
        mon_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.monster_listbox.config(yscrollcommand=mon_scroll.set)

        mon_btn_bar = ttk.Frame(left_panel)
        mon_btn_bar.pack(fill=tk.X, pady=(0, 6))
        self.select_tgt_btn = ttk.Button(mon_btn_bar, text="選為目標 (Select)", command=self._on_select_target)
        self.select_tgt_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        self.attack_tgt_btn = ttk.Button(mon_btn_bar, text="手動攻擊 (Attack)", command=self._on_manual_attack)
        self.attack_tgt_btn.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=2)

        # Inventory
        inv_group = ttk.LabelFrame(left_panel, text="角色背包 (Inventory)", padding=6)
        inv_group.pack(fill=tk.BOTH, expand=True)

        self.inv_listbox = tk.Listbox(inv_group, height=6, font=("Consolas", 9), selectmode=tk.SINGLE)
        self.inv_listbox.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        inv_scroll = ttk.Scrollbar(inv_group, orient=tk.VERTICAL, command=self.inv_listbox.yview)
        inv_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.inv_listbox.config(yscrollcommand=inv_scroll.set)

        inv_btn_bar = ttk.Frame(left_panel)
        inv_btn_bar.pack(fill=tk.X, pady=(4, 0))
        self.use_item_btn = ttk.Button(inv_btn_bar, text="手動使用物品 (Use Item)", command=self._on_use_item)
        self.use_item_btn.pack(fill=tk.X, padx=2)

        # --- CENTER PANEL: Manual Controls & D-Pad ---
        center_panel = ttk.Frame(paned, width=280, padding=6)
        paned.add(center_panel, weight=0)

        # Pause / Resume Helper Button
        self.pause_btn = ttk.Button(
            center_panel,
            text="❚❚ 暫停 Helper (手動介入)",
            command=self._on_toggle_pause,
            style="Action.TButton",
        )
        self.pause_btn.pack(fill=tk.X, pady=6)

        # Directional D-Pad
        dpad_group = ttk.LabelFrame(center_panel, text="手動方向移動 (Manual Movement)", padding=8)
        dpad_group.pack(fill=tk.X, pady=6)

        # 3x3 Grid for headings:
        # 7(NW)  0(N)   1(NE)
        # 6(W)   Stop   2(E)
        # 5(SW)  4(S)   3(SE)
        btn_nw = ttk.Button(dpad_group, text="↖ NW", width=6, command=lambda: self.vm.manual_move(7))
        btn_nw.grid(row=0, column=0, padx=3, pady=3)
        btn_n = ttk.Button(dpad_group, text="↑ N", width=6, command=lambda: self.vm.manual_move(0))
        btn_n.grid(row=0, column=1, padx=3, pady=3)
        btn_ne = ttk.Button(dpad_group, text="↗ NE", width=6, command=lambda: self.vm.manual_move(1))
        btn_ne.grid(row=0, column=2, padx=3, pady=3)

        btn_w = ttk.Button(dpad_group, text="← W", width=6, command=lambda: self.vm.manual_move(6))
        btn_w.grid(row=1, column=0, padx=3, pady=3)
        btn_center = ttk.Label(dpad_group, text="●", width=6, anchor=tk.CENTER)
        btn_center.grid(row=1, column=1, padx=3, pady=3)
        btn_e = ttk.Button(dpad_group, text="→ E", width=6, command=lambda: self.vm.manual_move(2))
        btn_e.grid(row=1, column=2, padx=3, pady=3)

        btn_sw = ttk.Button(dpad_group, text="↙ SW", width=6, command=lambda: self.vm.manual_move(5))
        btn_sw.grid(row=2, column=0, padx=3, pady=3)
        btn_s = ttk.Button(dpad_group, text="↓ S", width=6, command=lambda: self.vm.manual_move(4))
        btn_s.grid(row=2, column=1, padx=3, pady=3)
        btn_se = ttk.Button(dpad_group, text="↘ SE", width=6, command=lambda: self.vm.manual_move(3))
        btn_se.grid(row=2, column=2, padx=3, pady=3)

        # Quick Action Buttons
        act_group = ttk.LabelFrame(center_panel, text="即時指令 (Quick Operations)", padding=8)
        act_group.pack(fill=tk.X, pady=6)

        ttk.Button(act_group, text="⚔ 攻擊當前目標 (Attack)", command=self._on_manual_attack).pack(fill=tk.X, pady=3)
        ttk.Button(act_group, text="🍷 喝紅色藥水 (Red Potion)", command=self._on_drink_potion).pack(fill=tk.X, pady=3)
        ttk.Button(act_group, text="🏠 回城卷軸 (Return Town)", command=self._on_return_town).pack(fill=tk.X, pady=3)

        # Destination indicator
        dest_box = ttk.LabelFrame(center_panel, text="當前獵場目標", padding=6)
        dest_box.pack(fill=tk.X, pady=6)
        self.dest_lbl = ttk.Label(dest_box, text="話島地監 1F", font=("Helvetica", 9, "bold"))
        self.dest_lbl.pack()

        # --- RIGHT PANEL: Activity Log & Trace Monitor ---
        right_panel = ttk.Frame(paned, padding=4)
        paned.add(right_panel, weight=3)

        log_group = ttk.LabelFrame(right_panel, text="即時操作紀錄 (Activity Log / Trace Monitor)", padding=6)
        log_group.pack(fill=tk.BOTH, expand=True)

        self.log_text = scrolledtext.ScrolledText(log_group, wrap=tk.WORD, font=("Consolas", 9), bg="#1e1e1e", fg="#d4d4d4")
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # -----------------------------------------------------------------------
        # BOTTOM: Operations Count & Status Bar
        # -----------------------------------------------------------------------
        bot_bar = ttk.Frame(main_frame, padding=4)
        bot_bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.status_bar_lbl = ttk.Label(
            bot_bar,
            text="MOVE: 0 | ATTACK: 0 | LOOT: 0 | USE_ITEM: 0 | RETURN_TOWN: 0",
            font=("Consolas", 9),
            foreground="darkblue",
        )
        self.status_bar_lbl.pack(side=tk.LEFT)

        self.virtual_time_lbl = ttk.Label(bot_bar, text="T=000000 ms", font=("Consolas", 9))
        self.virtual_time_lbl.pack(side=tk.RIGHT)

    # ---------------------------------------------------------------------------
    # UI Refresh & Polling Tick
    # ---------------------------------------------------------------------------

    def _poll_tick(self) -> None:
        """Periodic UI update loop invoked every 100ms."""
        if not self._polling_active:
            return

        try:
            self.update_ui()
        except Exception as e:
            print(f"[UI ERROR] Failed to update UI: {e}")

        self.root.after(100, self._poll_tick)

    def update_ui(self) -> None:
        """Pulls latest snapshot from runtime and updates all widgets."""
        snap = self.vm.refresh_snapshot()

        # Update Player info
        self.char_name_lbl.config(text=f"{snap.player_name} (Knight)")
        self.level_lbl.config(text=self.vm.level_str)
        self.location_lbl.config(text=self.vm.location_str)
        self.adena_lbl.config(text=self.vm.adena_str)
        self.weapon_lbl.config(text=f"武器: {self.vm.weapon_str}")

        # Update HP & MP
        self.hp_bar["value"] = self.vm.hp_ratio * 100
        self.hp_text_lbl.config(text=self.vm.hp_str)
        self.mp_bar["value"] = self.vm.mp_ratio * 100
        self.mp_text_lbl.config(text=self.vm.mp_str)

        # Update Helper Status Badge & Pause Button
        if snap.helper_paused:
            self.helper_badge_lbl.config(text="❚❚ HELPER PAUSED (手動模式)", style="StatusPaused.TLabel")
            self.pause_btn.config(text="▶ 恢復 Helper (自動狩獵)")
        else:
            self.helper_badge_lbl.config(text=f"● HELPER ACTIVE ({snap.bot_state})", style="StatusActive.TLabel")
            self.pause_btn.config(text="❚❚ 暫停 Helper (手動介入)")

        # Update Destination
        self.dest_lbl.config(text=snap.hunting_destination_name)

        # Update Nearby Monsters Listbox
        self._update_monsters_list(snap.nearby_monsters, snap.active_target)

        # Update Inventory Listbox
        self._update_inventory_list(snap.inventory)

        # Update Logs
        self._update_logs(snap.recent_logs)

        # Update Bottom Status Bar
        ops = snap.operations_count
        ops_str = f"MOVE: {ops.get('MOVE_STEP', 0)} | ATTACK: {ops.get('ATTACK', 0)} | LOOT: {ops.get('LOOT', 0)} | USE_ITEM: {ops.get('USE_ITEM', 0)} | RET_TOWN: {ops.get('RETURN_TOWN', 0)}"
        self.status_bar_lbl.config(text=ops_str)
        self.virtual_time_lbl.config(text=f"T={snap.virtual_time_ms:06d} ms")

    def _update_monsters_list(self, monsters: list, active_target: Optional[dict]) -> None:
        self.monster_listbox.delete(0, tk.END)
        for m in monsters:
            marker = "★ " if active_target and active_target.get("uid") == m["uid"] else "  "
            item_text = f"{marker}{m['name']:<12} Lv{m['level']:<2} HP:{m['hp']:>2}/{m['max_hp']:<2} (dist={m['dist']})"
            self.monster_listbox.insert(tk.END, item_text)

    def _update_inventory_list(self, inventory: list) -> None:
        self.inv_listbox.delete(0, tk.END)
        for item in inventory:
            eq_str = "[E] " if item["is_equipped"] else "    "
            self.inv_listbox.insert(tk.END, f"{eq_str}{item['name']:<18} x{item['count']}")

    def _update_logs(self, recent_logs: list) -> None:
        current_lines = int(self.log_text.index("end-1c").split(".")[0])
        if len(recent_logs) > 0 and len(recent_logs) != current_lines:
            self.log_text.delete("1.0", tk.END)
            for line in recent_logs:
                self.log_text.insert(tk.END, line + "\n")
            self.log_text.see(tk.END)

    # ---------------------------------------------------------------------------
    # Button Handlers
    # ---------------------------------------------------------------------------

    def _on_toggle_pause(self) -> None:
        self.vm.toggle_helper_pause()
        self.update_ui()

    def _on_select_target(self) -> None:
        sel = self.monster_listbox.curselection()
        if sel:
            idx = sel[0]
            snap = self.vm.snapshot
            if idx < len(snap.nearby_monsters):
                target_m = snap.nearby_monsters[idx]
                self.vm.manual_select_target(target_m["uid"])
                self.update_ui()

    def _on_manual_attack(self) -> None:
        self.vm.manual_attack()
        self.update_ui()

    def _on_use_item(self) -> None:
        sel = self.inv_listbox.curselection()
        if sel:
            idx = sel[0]
            snap = self.vm.snapshot
            if idx < len(snap.inventory):
                item = snap.inventory[idx]
                self.vm.manual_use_item(item["item_id"])
                self.update_ui()

    def _on_drink_potion(self) -> None:
        self.vm.manual_use_item(104)  # Red Potion
        self.update_ui()

    def _on_return_town(self) -> None:
        self.vm.manual_return_town()
        self.update_ui()

    def _on_speed_changed(self, event=None) -> None:
        val = self.speed_var.get()
        speed_map = {
            "0.5x": 0.5,
            "1.0x": 1.0,
            "2.0x": 2.0,
            "5.0x": 5.0,
            "10.0x": 10.0,
            "極速 Instant": 100.0,
        }
        speed = speed_map.get(val, 1.0)
        self.vm.set_speed(speed)

    def open_config_dialog(self) -> None:
        """Opens interactive configuration panel window."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Helper 自動狩獵與規則設定 (Helper Configuration)")
        dialog.geometry("680x560")
        dialog.minsize(600, 480)
        dialog.transient(self.root)

        def on_applied():
            self.update_ui()

        panel = ConfigPanel(dialog, view_model=self.vm, on_applied=on_applied)
        panel.pack(fill=tk.BOTH, expand=True)

    def on_close(self) -> None:
        """Clean shutdown handler."""
        self._polling_active = False
        self.runtime.stop_background()
        self.root.destroy()


def main(
    config_path: str = "configs/autonomous_default.json",
    contract_path: Optional[str] = None,
    seed: Optional[int] = 777777,
    speed: float = 1.0,
    legacy_root: Optional[str] = None,
) -> None:
    root = tk.Tk()
    runtime = HeadlessPlayerRuntime(
        config_path=config_path,
        contract_path=contract_path,
        seed=seed,
        speed=speed,
        legacy_root=legacy_root,
    )
    app = PlayerWindow(root, runtime=runtime)
    root.mainloop()


if __name__ == "__main__":
    main()
