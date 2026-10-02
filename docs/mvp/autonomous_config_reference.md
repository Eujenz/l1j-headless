# Autonomous Configuration Reference

This document describes the schema and options available for configuring the `HeadlessBot` autonomous gameplay policy. Configuration files are stored as standard JSON documents under `configs/`.

---

## 1. Top-Level Schema (`AutonomousConfig`)

```json
{
  "version": "1.0.0",
  "name": "default_knight_ti",
  "potion_rules": [ ... ],
  "emergency_rules": [ ... ],
  "return_to_town": { ... },
  "resupply": { ... },
  "hunting": { ... }
}
```

### Fields

| Field | Type | Description |
| :--- | :--- | :--- |
| `version` | string | Configuration format version. |
| `name` | string | Profile name or character archetype description. |
| `potion_rules` | list[`PotionRule`] | Ordered list of rules governing consumable healing usage. |
| `emergency_rules` | list[`EmergencyActionRule`] | Ordered list of critical escape rules evaluated before combat. |
| `return_to_town` | `ReturnToTownPolicy` | Rules and triggers dictating when to leave the hunting ground. |
| `resupply` | `ResupplyProfile` | Rules dictating target inventory quantities and NPC merchant to visit. |
| `hunting` | `HuntingPolicy` | Hunting ground selection, combat range, and target acquisition rules. |

---

## 2. Component Specifications

### 2.1 PotionRule

Defines when and how the bot automatically consumes restorative items.

```json
{
  "name": "red_potion_heal",
  "item_id": 102,
  "condition": "HP_PERCENT_BELOW",
  "threshold_percent": 75.0,
  "cooldown_ms": 200,
  "priority": 10
}
```

- `name` (string): Human-readable identifier.
- `item_id` (int): L1J 1.82 item ID (`102` = Red Potion, `103` = Orange Potion, `104` = Clear Potion).
- `condition` (string): `HP_PERCENT_BELOW` or `HP_ABSOLUTE_BELOW`.
- `threshold_percent` (float, optional): Trigger threshold when using percentage condition.
- `threshold_absolute` (int, optional): Trigger threshold when using absolute HP condition.
- `cooldown_ms` (int): Minimum interval between item consumptions (canonical legacy value: 200ms).
- `priority` (int): Higher evaluated first when multiple rules qualify.

### 2.2 EmergencyActionRule

Defines critical life-saving actions triggered under imminent threat of death.

```json
{
  "name": "emergency_escape",
  "condition": "HP_PERCENT_BELOW",
  "threshold_percent": 25.0,
  "action_type": "USE_ESCAPE_ITEM",
  "escape_item_id": 139,
  "priority": 1
}
```

- `name` (string): Rule identifier.
- `condition` (string): Trigger condition (e.g. `HP_PERCENT_BELOW`).
- `threshold_percent` (float): HP threshold below which emergency escape fires immediately.
- `action_type` (string): `USE_ESCAPE_ITEM` (Escape Scroll item 139) or `WALK_TO_TOWN`.
- `escape_item_id` (int): Canonical Escape Scroll item ID (`139`).
- `priority` (int): Lower numbers evaluated first (Priority 1 = highest).

### 2.3 ReturnToTownPolicy

Defines non-emergency operational return triggers (e.g., supply depletion).

```json
{
  "enabled": true,
  "trigger_conditions": ["LOW_POTION", "BAG_WEIGHT_EXCEEDED"],
  "min_potions_threshold": 3,
  "max_weight_percent": 82.0,
  "return_method": "USE_ESCAPE_ITEM",
  "escape_item_id": 139
}
```

- `enabled` (bool): Enable or disable automated town return.
- `trigger_conditions` (list[string]): Supported triggers:
  - `LOW_POTION`: When designated potion count drops $\le \text{min\_potions\_threshold}$.
  - `BAG_WEIGHT_EXCEEDED`: When player weight exceeds percentage.
  - `LOW_HP`: Return to town if HP is critical and no potions remain.
- `min_potions_threshold` (int): Minimum potion count before initiating return.
- `return_method` (string): `USE_ESCAPE_ITEM` or `WALK_TO_TOWN`.

### 2.4 ResupplyProfile

Configures NPC merchant restocking operations upon reaching town.

```json
{
  "enabled": true,
  "shop_npc_id": 3,
  "shop_npc_name": "Pandora",
  "items": [
    {
      "item_id": 102,
      "name": "Red Potion",
      "target_quantity": 30,
      "max_price": 37,
      "priority": 1
    },
    {
      "item_id": 139,
      "name": "Escape Scroll",
      "target_quantity": 5,
      "max_price": 120,
      "priority": 2
    }
  ]
}
```

- `enabled` (bool): Enable automated restocking at NPC store.
- `shop_npc_id` (int): Canonical NPC ID (`3` = Pandora on Talking Island).
- `items` (list[`ResupplyItem`]): Items to purchase up to `target_quantity`. The bot calculates shortage and purchases according to priority and available Adena.

### 2.5 HuntingPolicy

Defines target destination and combat tactics.

```json
{
  "destination": {
    "name": "ti_dungeon_1f",
    "map_id": 1,
    "center_x": 32671,
    "center_y": 32804,
    "patrol_radius": 20
  },
  "preferred_targets": [],
  "avoid_targets": [],
  "max_hunt_duration_ms": 0
}
```

- `destination.map_id` (int): Target map (`1` = Talking Island Dungeon 1F).
- `destination.center_x / center_y`: Anchor coordinates for hunting patrol.
- `destination.patrol_radius`: Bounding radius around center point.
- `avoid_targets` (list[string]): Monster names to skip or flee from.

---

## 3. CLI Usage

To run the autonomous bot with custom configurations:

```bash
# Run with default configuration for 30 minutes in instant virtual time
python autonomous.py --config configs/autonomous_default.json --duration 1800000 --instant

# Run with simulated speed multiplier (e.g. 5x real-time) with verbose state logging
python autonomous.py --config configs/autonomous_default.json --speed 5.0 --verbose

# Run Scenario 008 certified test harness
python scenario_008_configurable_autonomous_hunting.py --duration 1800000
```
