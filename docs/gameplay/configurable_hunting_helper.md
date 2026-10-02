# Configurable Hunting Helper

## 1. Concept & Scope

The **Configurable Hunting Helper** is **Layer 4** of the L1J Headless runtime.
It represents the automation rules that a real human player would set up in a Lineage helper tool.

It is **NOT**:
- A generic AI agent or neural network planner.
- An economic profit optimizer or EXP maximizer.
- A dynamic strategy optimizer.

It is **STRICTLY**:
- A deterministic rule evaluator that maps world perception to standard **Layer 3 Player Operations** based on user-configured thresholds.

---

## 2. Configuration Schema (`AutonomousConfig`)

The automation rules are configured via JSON files (e.g. `configs/autonomous_default.json`):

```json
{
  "name": "default_knight_ti",
  "character": {
    "class_type": "KNIGHT",
    "intended_role": "MELEE_ATTACKER"
  },
  "targeting": {
    "target_priority": "NEAREST",
    "search_radius": 15,
    "lock_current_target": true
  },
  "movement": {
    "use_haste_potion": true,
    "use_brave_potion": false,
    "roam_radius": 8
  },
  "loot": {
    "pickup_all_items": true,
    "priority_items": ["Adena", "Armor Scroll", "Weapon Scroll"]
  },
  "potion_rules": [
    {
      "trigger_type": "HP_PERCENT_BELOW",
      "threshold": 70,
      "item_id": 104,
      "item_name": "Red Potion",
      "cooldown_ms": 1000
    }
  ],
  "emergency_rules": [
    {
      "trigger_type": "HP_PERCENT_BELOW",
      "threshold": 25,
      "action": "RETURN_TOWN"
    }
  ],
  "return_to_town": {
    "return_method": "USE_ESCAPE_ITEM",
    "triggers": [
      { "trigger_type": "LOW_POTIONS", "item_name": "Red Potion", "threshold": 5 },
      { "trigger_type": "LOW_MP", "threshold": 0 }
    ]
  },
  "resupply": {
    "vendor_name": "Pandora",
    "items": [
      { "item_id": 104, "item_name": "Red Potion", "target_count": 35, "price": 40 },
      { "item_id": 139, "item_name": "Escape Scroll", "target_count": 3, "price": 120 }
    ]
  },
  "hunting": {
    "destination": {
      "name": "ti_dungeon_1f",
      "map_id": 1,
      "target_x": 32671,
      "target_y": 32804
    }
  }
}
```

---

## 3. Rule Evaluation Precedence

The Policy Evaluator iterates through rules in strict order of player survival and priority:

1. **Survival & Emergency Triggers**:
   - Check HP against emergency thresholds (e.g. HP < 25%).
   - If triggered, immediately emit `PlayerOperation(RETURN_TOWN)` using Escape Scroll.
2. **Consumable & Potion Rules**:
   - Check HP against potion thresholds (e.g. HP < 70%).
   - If red potions are available and off-cooldown, emit `PlayerOperation(USE_ITEM, item_id=104)`.
3. **Buff & Status Rules**:
   - Maintain active Haste (Item 108) or Bravery (Item 110) if configured and elapsed.
4. **Town Resupply Cycle**:
   - If potions fall below minimum supply threshold (`LOW_POTIONS`), trigger return to town.
   - While in town, navigate to Pandora NPC and execute `PlayerOperation(BUY_SUPPLY)`.
   - When restocked, path to dungeon entrance and execute `PlayerOperation(TRANSITION_MAP)`.
5. **Combat & Targeting**:
   - If monster in range and no current target, emit `PlayerOperation(SELECT_TARGET)`.
   - If target acquired and in melee reach (dist <= 1), emit `PlayerOperation(ATTACK)`.
   - If target acquired but out of reach, emit `PlayerOperation(MOVE_STEP)` approaching target.
6. **Loot Pickup**:
   - If ground items are within perception range, emit `PlayerOperation(LOOT)`.
7. **Exploration / Roam**:
   - If no monsters or loot in sight, emit `PlayerOperation(ROAM)` around hunting anchor.

---

## 4. Automation Profiles

Three distinct profiles are provided to demonstrate configurable behavioral variance:

| Profile | Target HP Potion % | Emergency HP % | Resupply Restock | Playstyle Behavior |
| :--- | :--- | :--- | :--- | :--- |
| **`autonomous_default.json`** | 70% | 25% | 35 Red Potions | Balanced, steady hunting uptime with standard recovery buffers. |
| **`conservative_hunt.json`** | 80% | 40% | 45 Red Potions | High safety margin, early potion drinking, returns to town promptly upon threat. |
| **`aggressive_hunt.json`** | 50% | 15% | 20 Red Potions | Lean inventory, stays in combat longer at lower HP, lower potion consumption. |
