"""
ui/config_panel.py - Player-Configurable Hunting Helper Settings Panel

Allows real-time inspection, editing, and live application of:
  - Hunting Destination (Talking Island Dungeon 1F, Talking Island Surface Field)
  - Helper Automation Modules (auto-target, auto-attack, auto-move, auto-potion, auto-buff, auto-loot, auto-return, auto-resupply)
  - Potion Rules (HP threshold & item choice)
  - Emergency Escape (HP threshold & action)
  - Return to Town Conditions (potion count threshold, HP threshold, escape method)
  - Town Resupply Target Quantities (Red Potion, Green Potion, Escape Scroll at Pandora)
  - Profile Management (Save, Load, Save As JSON)
"""
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Optional, Callable

from native_engine.bot import (
    AutonomousConfig,
    AVAILABLE_DESTINATIONS,
    PotionRule,
    PotionThresholdMode,
    EmergencyCondition,
    EmergencyConditionType,
    EmergencyOperator,
    EmergencyAction,
    EmergencyActionRule,
    ReturnTrigger,
    ReturnTriggerType,
    ReturnMethod,
    ReturnToTownPolicy,
    ResupplyItem,
    ResupplyProfile,
    HelperModulesConfig,
)
from .player_view_model import PlayerViewModel


class ConfigPanel(ttk.Frame):
    """
    Configuration panel widget providing interactive configuration of helper rules.
    """

    def __init__(self, parent: tk.Widget, view_model: PlayerViewModel, on_applied: Optional[Callable[[], None]] = None):
        super().__init__(parent)
        self.vm = view_model
        self.on_applied = on_applied
        self._build_ui()
        self.load_from_config(self.vm.runtime.config)

    def _build_ui(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Tab 1: Profile & Destination & Helper Switches
        general_frame = ttk.Frame(notebook, padding=10)
        notebook.add(general_frame, text="一般與獵場 (General & Destination)")
        self._build_general_tab(general_frame)

        # Tab 2: Potion & Emergency Survival Rules
        potion_frame = ttk.Frame(notebook, padding=10)
        notebook.add(potion_frame, text="喝水與逃脫 (Potions & Emergency)")
        self._build_potion_tab(potion_frame)

        # Tab 3: Town Return & Pandora Resupply
        resupply_frame = ttk.Frame(notebook, padding=10)
        notebook.add(resupply_frame, text="回城與補給 (Return & Resupply)")
        self._build_resupply_tab(resupply_frame)

        # Bottom Button Bar
        btn_bar = ttk.Frame(self, padding=8)
        btn_bar.pack(fill=tk.X, side=tk.BOTTOM)

        apply_btn = ttk.Button(btn_bar, text="✓ 套用至遊戲 (Apply to Game)", command=self.apply_to_game)
        apply_btn.pack(side=tk.RIGHT, padx=5)

        save_btn = ttk.Button(btn_bar, text="儲存設定檔 (Save Profile)", command=self.save_profile_dialog)
        save_btn.pack(side=tk.RIGHT, padx=5)

        load_btn = ttk.Button(btn_bar, text="載入設定檔 (Load Profile)", command=self.load_profile_dialog)
        load_btn.pack(side=tk.RIGHT, padx=5)

        self.status_lbl = ttk.Label(btn_bar, text="準備就緒", foreground="gray")
        self.status_lbl.pack(side=tk.LEFT, padx=5)

    def _build_general_tab(self, parent: ttk.Frame) -> None:
        # Profile Info
        p_group = ttk.LabelFrame(parent, text="設定檔 (Profile)", padding=8)
        p_group.pack(fill=tk.X, pady=5)

        ttk.Label(p_group, text="名稱 (Name):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=3)
        self.profile_name_var = tk.StringVar(value="default_knight_ti")
        ttk.Entry(p_group, textvariable=self.profile_name_var, width=30).grid(row=0, column=1, sticky=tk.W, padx=5)

        # Destination Selection
        d_group = ttk.LabelFrame(parent, text="狩獵區域選擇 (Hunting Destination)", padding=8)
        d_group.pack(fill=tk.X, pady=5)

        ttk.Label(d_group, text="獵場目標 (Destination):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.dest_var = tk.StringVar(value="ti_dungeon_1f")
        dest_choices = [
            ("ti_dungeon_1f", "話島地監 1F (TI Dungeon 1F - Map 1)"),
            ("ti_surface_field", "話島野外 (TI Surface Field - Map 0)"),
        ]
        self.dest_combo = ttk.Combobox(
            d_group,
            textvariable=self.dest_var,
            values=[c[0] for c in dest_choices],
            state="readonly",
            width=35,
        )
        self.dest_combo.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)

        # Helper Module Switches
        m_group = ttk.LabelFrame(parent, text="輔助模組開關 (Helper Automation Modules)", padding=8)
        m_group.pack(fill=tk.X, pady=5)

        self.mod_vars = {
            "auto_target": tk.BooleanVar(value=True),
            "auto_attack": tk.BooleanVar(value=True),
            "auto_move": tk.BooleanVar(value=True),
            "auto_potion": tk.BooleanVar(value=True),
            "auto_buff": tk.BooleanVar(value=True),
            "auto_loot": tk.BooleanVar(value=True),
            "auto_return": tk.BooleanVar(value=True),
            "auto_resupply": tk.BooleanVar(value=True),
        }

        labels = {
            "auto_target": "自動選怪 (Auto-Target)",
            "auto_attack": "自動攻擊 (Auto-Attack)",
            "auto_move": "自動移動 (Auto-Move)",
            "auto_potion": "自動喝水 (Auto-Potion)",
            "auto_buff": "自動使用綠水 Buff (Auto-Buff)",
            "auto_loot": "自動拾取 (Auto-Loot)",
            "auto_return": "自動回城 (Auto-Return to Town)",
            "auto_resupply": "自動潘朵拉補給 (Auto-Resupply)",
        }

        r, c = 0, 0
        for k, var in self.mod_vars.items():
            ttk.Checkbutton(m_group, text=labels[k], variable=var).grid(row=r, column=c, sticky=tk.W, padx=8, pady=4)
            c += 1
            if c >= 2:
                c = 0
                r += 1

    def _build_potion_tab(self, parent: ttk.Frame) -> None:
        # Potion Rule 1
        p1_group = ttk.LabelFrame(parent, text="喝水規則 1 (Primary Potion Rule)", padding=8)
        p1_group.pack(fill=tk.X, pady=5)

        self.p1_enable_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(p1_group, text="啟用 (Enable)", variable=self.p1_enable_var).grid(row=0, column=0, sticky=tk.W)

        ttk.Label(p1_group, text="HP 低於:").grid(row=0, column=1, padx=5)
        self.p1_thresh_var = tk.DoubleVar(value=70.0)
        p1_spin = ttk.Spinbox(p1_group, from_=5.0, to=95.0, increment=5.0, textvariable=self.p1_thresh_var, width=6)
        p1_spin.grid(row=0, column=2, padx=2)
        ttk.Label(p1_group, text="% 使用:").grid(row=0, column=3, padx=2)

        self.p1_item_var = tk.StringVar(value="Red Potion")
        p1_items = ttk.Combobox(p1_group, textvariable=self.p1_item_var, values=["Red Potion", "Orange Potion", "Clear Potion"], state="readonly", width=14)
        p1_items.grid(row=0, column=4, padx=5)

        # Potion Rule 2
        p2_group = ttk.LabelFrame(parent, text="喝水規則 2 (Secondary Potion Rule)", padding=8)
        p2_group.pack(fill=tk.X, pady=5)

        self.p2_enable_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(p2_group, text="啟用 (Enable)", variable=self.p2_enable_var).grid(row=0, column=0, sticky=tk.W)

        ttk.Label(p2_group, text="HP 低於:").grid(row=0, column=1, padx=5)
        self.p2_thresh_var = tk.DoubleVar(value=35.0)
        p2_spin = ttk.Spinbox(p2_group, from_=5.0, to=95.0, increment=5.0, textvariable=self.p2_thresh_var, width=6)
        p2_spin.grid(row=0, column=2, padx=2)
        ttk.Label(p2_group, text="% 使用:").grid(row=0, column=3, padx=2)

        self.p2_item_var = tk.StringVar(value="Orange Potion")
        p2_items = ttk.Combobox(p2_group, textvariable=self.p2_item_var, values=["Orange Potion", "Red Potion", "Clear Potion"], state="readonly", width=14)
        p2_items.grid(row=0, column=4, padx=5)

        # Emergency Escape
        em_group = ttk.LabelFrame(parent, text="緊急危機處理 (Emergency Escape)", padding=8)
        em_group.pack(fill=tk.X, pady=5)

        self.em_enable_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(em_group, text="啟用緊急逃脫", variable=self.em_enable_var).grid(row=0, column=0, sticky=tk.W)

        ttk.Label(em_group, text="HP 低於等於:").grid(row=0, column=1, padx=5)
        self.em_thresh_var = tk.DoubleVar(value=20.0)
        em_spin = ttk.Spinbox(em_group, from_=5.0, to=50.0, increment=5.0, textvariable=self.em_thresh_var, width=6)
        em_spin.grid(row=0, column=2, padx=2)
        ttk.Label(em_group, text="% 時動作:").grid(row=0, column=3, padx=2)

        self.em_action_var = tk.StringVar(value="Escape Scroll")
        em_actions = ttk.Combobox(em_group, textvariable=self.em_action_var, values=["Escape Scroll"], state="readonly", width=14)
        em_actions.grid(row=0, column=4, padx=5)

    def _build_resupply_tab(self, parent: ttk.Frame) -> None:
        # Return to Town Triggers
        ret_group = ttk.LabelFrame(parent, text="回城條件 (Return to Town Triggers)", padding=8)
        ret_group.pack(fill=tk.X, pady=5)

        self.ret_enable_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(ret_group, text="啟用自動回城", variable=self.ret_enable_var).grid(row=0, column=0, sticky=tk.W, columnspan=2)

        self.ret_low_pot_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(ret_group, text="紅色藥水低於:", variable=self.ret_low_pot_var).grid(row=1, column=0, sticky=tk.W, padx=5, pady=3)
        self.ret_pot_thresh_var = tk.IntVar(value=10)
        ttk.Spinbox(ret_group, from_=0, to=100, increment=5, textvariable=self.ret_pot_thresh_var, width=6).grid(row=1, column=1, sticky=tk.W)

        self.ret_low_hp_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(ret_group, text="無藥水且 HP 低於 20%", variable=self.ret_low_hp_var).grid(row=2, column=0, sticky=tk.W, padx=5, pady=3)

        ttk.Label(ret_group, text="回城方式:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=3)
        self.ret_method_var = tk.StringVar(value="USE_ESCAPE_ITEM")
        ttk.Radiobutton(ret_group, text="使用回城卷軸 (Escape Scroll)", variable=self.ret_method_var, value="USE_ESCAPE_ITEM").grid(row=3, column=1, sticky=tk.W)
        ttk.Radiobutton(ret_group, text="步行回城 (Walk via Portal)", variable=self.ret_method_var, value="WALK").grid(row=4, column=1, sticky=tk.W)

        # Pandora Shop Resupply Targets
        resup_group = ttk.LabelFrame(parent, text="潘朵拉商店補給目標數量 (Pandora Shop Resupply)", padding=8)
        resup_group.pack(fill=tk.X, pady=5)

        ttk.Label(resup_group, text="商店 NPC: 潘朵拉 (Pandora - NPC ID 3)").grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=3)

        ttk.Label(resup_group, text="紅色藥水 (Red Potion) 目標:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=3)
        self.resup_red_var = tk.IntVar(value=50)
        ttk.Spinbox(resup_group, from_=0, to=200, increment=10, textvariable=self.resup_red_var, width=8).grid(row=1, column=1, sticky=tk.W)

        ttk.Label(resup_group, text="綠色藥水 (Green Potion) 目標:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=3)
        self.resup_green_var = tk.IntVar(value=10)
        ttk.Spinbox(resup_group, from_=0, to=50, increment=5, textvariable=self.resup_green_var, width=8).grid(row=2, column=1, sticky=tk.W)

        ttk.Label(resup_group, text="回城卷軸 (Escape Scroll) 目標:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=3)
        self.resup_scroll_var = tk.IntVar(value=5)
        ttk.Spinbox(resup_group, from_=0, to=20, increment=1, textvariable=self.resup_scroll_var, width=8).grid(row=3, column=1, sticky=tk.W)

    # ---------------------------------------------------------------------------
    # Data Mapping (Config -> UI & UI -> Config)
    # ---------------------------------------------------------------------------

    def load_from_config(self, config: AutonomousConfig) -> None:
        """Populates UI widgets from an AutonomousConfig instance."""
        self.profile_name_var.set(config.name)
        if config.hunting.destination.name in AVAILABLE_DESTINATIONS:
            self.dest_var.set(config.hunting.destination.name)
        else:
            self.dest_var.set("ti_dungeon_1f")

        # Modules
        mods = config.helper_modules
        for k, var in self.mod_vars.items():
            var.set(getattr(mods, k, True))

        # Potion rules
        if len(config.potion_rules) > 0:
            r1 = config.potion_rules[0]
            self.p1_enable_var.set(r1.enabled)
            self.p1_thresh_var.set(r1.threshold)
            self.p1_item_var.set(r1.item)
        if len(config.potion_rules) > 1:
            r2 = config.potion_rules[1]
            self.p2_enable_var.set(r2.enabled)
            self.p2_thresh_var.set(r2.threshold)
            self.p2_item_var.set(r2.item)

        # Emergency
        if config.emergency_rules:
            er = config.emergency_rules[0]
            self.em_enable_var.set(er.enabled)
            self.em_thresh_var.set(er.condition.value)
            self.em_action_var.set(er.action.item)

        # Return to town
        ret = config.return_to_town
        self.ret_enable_var.set(ret.enabled)
        self.ret_method_var.set(ret.return_method.value if hasattr(ret.return_method, "value") else str(ret.return_method))
        for t in ret.triggers:
            if t.type == ReturnTriggerType.LOW_POTION:
                self.ret_low_pot_var.set(True)
                self.ret_pot_thresh_var.set(t.threshold)
            elif t.type == ReturnTriggerType.LOW_HP:
                self.ret_low_hp_var.set(True)

        # Resupply
        for item in config.resupply.items:
            if item.item_id == 104 or "Red" in item.item:
                self.resup_red_var.set(item.target_quantity)
            elif item.item_id == 108 or "Green" in item.item:
                self.resup_green_var.set(item.target_quantity)
            elif item.item_id in (139, 454) or "Escape" in item.item:
                self.resup_scroll_var.set(item.target_quantity)

        self.status_lbl.config(text=f"已載入設定: {config.name}")

    def build_config(self) -> AutonomousConfig:
        """Constructs an AutonomousConfig from current UI widget values."""
        cfg = AutonomousConfig()
        cfg.name = self.profile_name_var.get().strip() or "custom_profile"

        # Hunting Destination
        dest_key = self.dest_var.get()
        if dest_key in AVAILABLE_DESTINATIONS:
            cfg.hunting.destination = AVAILABLE_DESTINATIONS[dest_key]

        # Helper Modules
        cfg.helper_modules = HelperModulesConfig(
            auto_target=self.mod_vars["auto_target"].get(),
            auto_attack=self.mod_vars["auto_attack"].get(),
            auto_move=self.mod_vars["auto_move"].get(),
            auto_potion=self.mod_vars["auto_potion"].get(),
            auto_buff=self.mod_vars["auto_buff"].get(),
            auto_loot=self.mod_vars["auto_loot"].get(),
            auto_return=self.mod_vars["auto_return"].get(),
            auto_resupply=self.mod_vars["auto_resupply"].get(),
        )

        # Potion Rules
        potion_rules = []
        p_item_ids = {"Red Potion": 104, "Orange Potion": 103, "Clear Potion": 106}
        if self.p1_enable_var.get():
            item_name = self.p1_item_var.get()
            potion_rules.append(PotionRule(
                enabled=True,
                threshold_mode=PotionThresholdMode.HP_PERCENT,
                threshold=self.p1_thresh_var.get(),
                item=item_name,
                item_id=p_item_ids.get(item_name, 104),
                priority=100,
            ))
        if self.p2_enable_var.get():
            item_name = self.p2_item_var.get()
            potion_rules.append(PotionRule(
                enabled=True,
                threshold_mode=PotionThresholdMode.HP_PERCENT,
                threshold=self.p2_thresh_var.get(),
                item=item_name,
                item_id=p_item_ids.get(item_name, 103),
                priority=200,
            ))
        cfg.potion_rules = potion_rules

        # Emergency
        if self.em_enable_var.get():
            cfg.emergency_rules = [
                EmergencyActionRule(
                    enabled=True,
                    condition=EmergencyCondition(
                        type=EmergencyConditionType.HP_PERCENT,
                        operator=EmergencyOperator.LE,
                        value=self.em_thresh_var.get(),
                    ),
                    action=EmergencyAction(type="USE_ITEM", item="Escape Scroll", item_id=139),
                    priority=100,
                )
            ]
        else:
            cfg.emergency_rules = []

        # Return to Town
        ret_triggers = []
        if self.ret_low_pot_var.get():
            ret_triggers.append(ReturnTrigger(
                type=ReturnTriggerType.LOW_POTION,
                item="Red Potion",
                item_id=104,
                threshold=self.ret_pot_thresh_var.get(),
            ))
        if self.ret_low_hp_var.get():
            ret_triggers.append(ReturnTrigger(
                type=ReturnTriggerType.LOW_HP,
                threshold=20,
            ))

        method_str = self.ret_method_var.get()
        method_enum = ReturnMethod.USE_ESCAPE_ITEM if method_str == "USE_ESCAPE_ITEM" else ReturnMethod.WALK
        cfg.return_to_town = ReturnToTownPolicy(
            enabled=self.ret_enable_var.get(),
            triggers=ret_triggers,
            return_method=method_enum,
            escape_item="Escape Scroll",
            escape_item_id=139,
        )

        # Resupply
        cfg.resupply = ResupplyProfile(
            enabled=True,
            shop_npc_id=3,
            items=[
                ResupplyItem(enabled=True, item="Red Potion", item_id=104, target_quantity=self.resup_red_var.get(), priority=100),
                ResupplyItem(enabled=True, item="Green Potion", item_id=108, target_quantity=self.resup_green_var.get(), priority=80),
                ResupplyItem(enabled=True, item="Escape Scroll", item_id=139, target_quantity=self.resup_scroll_var.get(), priority=60),
            ]
        )

        return cfg

    # ---------------------------------------------------------------------------
    # Button Actions
    # ---------------------------------------------------------------------------

    def apply_to_game(self) -> None:
        """Applies configuration directly to the active HeadlessPlayerRuntime."""
        new_config = self.build_config()
        self.vm.update_config(new_config)
        self.status_lbl.config(text="✓ 設定已成功套用至運行中的遊戲！", foreground="darkgreen")
        if self.on_applied:
            self.on_applied()

    def save_profile_dialog(self) -> None:
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json")],
            initialdir="configs",
            initialfile=f"{self.profile_name_var.get()}.json",
        )
        if filepath:
            config = self.build_config()
            config.save_json(filepath)
            self.status_lbl.config(text=f"設定已儲存: {os.path.basename(filepath)}", foreground="blue")

    def load_profile_dialog(self) -> None:
        filepath = filedialog.askopenfilename(
            filetypes=[("JSON Files", "*.json")],
            initialdir="configs",
        )
        if filepath and os.path.exists(filepath):
            loaded = AutonomousConfig.load_json(filepath)
            self.load_from_config(loaded)
            self.vm.update_config(loaded)
            self.status_lbl.config(text=f"已載入並套用: {os.path.basename(filepath)}", foreground="blue")
