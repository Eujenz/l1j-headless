# Layer 3: Player Operation Model

## 1. Product Context & Rationale

In canonical Lineage 1 (L1J 1.82), a player interacts with the world via discrete input commands transmitted over packets or local input events (cursor click, hotkey, drag-and-drop).
Prior engine prototypes mixed decision heuristics, automation policies, and world state modifications directly into the bot controller.

To ensure **100% equivalence between a human player and an automated helper**, MVP-05 establishes **Layer 3: Player Operation Model**.

```text
+--------------------------------------------------------------+
| Layer 4: Configurable Automation Helper (AutonomousConfig)    |
| (Evaluates rules, detects low HP, selects target candidate)  |
+--------------------------------------------------------------+
                                |
                   Emits PlayerOperation
                                |
                                v
+--------------------------------------------------------------+
| Layer 3: Player Operation Model (PlayerOperationType)        |
| - Unified action dispatcher: execute_player_operation()      |
| - Target lock gate, action delay cadence, item usage intents  |
+--------------------------------------------------------------+
                                |
                   Delegates World Resolution
                                |
                                v
+--------------------------------------------------------------+
| Layer 2: Native L1J World (Canonical Server Rules)           |
| - Combat math (Knight sword timing, AC/Hit, Damage)          |
| - Real map collision & cross-map portals                     |
| - Monster AI, Spawns, Drop & Inventory Tables                |
+--------------------------------------------------------------+
```

---

## 2. Discrete Player Operations

All player actions are enumerated in [`native_engine.player_operation.PlayerOperationType`](file:///c:/Users/p0282768/Documents/l1j-headless/native_engine/player_operation.py):

| Operation Type | Parameters / Payload | Description |
| :--- | :--- | :--- |
| `MOVE_STEP` | `target_pos: Position` | Moves one tile towards adjacent coordinates along 8-directional heading. Respects movement speed timing (600ms base / 400ms haste). |
| `SELECT_TARGET` | `target: Actor` | Targets an entity in perception range. Sets `player.current_target` and incurs canonical cursor-target acquisition gate (50ms). |
| `ATTACK` | `target: Actor` | Swings weapon at current target. Verifies range and weapon attack speed (e.g. Knight One-Hand Sword = 920ms canonical delay). |
| `CAST_SKILL` | `skill_id: int, target: Actor` | Casts a spell or combat technique, consuming MP and applying global cast cooldown. |
| `USE_ITEM` | `item_or_id: Any` | Uses an inventory consumable (Red/Orange/Clear Potion, Green Potion, Bravery Potion, Escape Scroll). |
| `LOOT` | `ground_item: GroundItem` | Moves to and picks up a dropped item from the ground into player inventory. |
| `EQUIP` | `item: Item` | Equips a weapon or armor piece, updating player combat statistics. |
| `UNEQUIP` | `item: Item` | Removes equipped gear back to backpack. |
| `NPC_INTERACT` | `npc: Actor` | Engages an NPC in dialogue or opens service interface. |
| `BUY_SUPPLY` | `npc: Actor, item_id: int, count: int` | Purchases supplies from a merchant NPC, deducting Adena and adding items. |
| `TRAVEL` | `target_pos: Position` | High-level pathing navigation across map coordinates. |
| `RETURN_TOWN` | `method: ReturnMethod` | Teleports or returns to town restart point (via Escape Scroll or death). |
| `TRANSITION_MAP`| `portal: Dict[str, Any]` | Steps onto cross-map transition portal (e.g. Map 0 -> Map 1). |
| `ROAM` | None | Wanders in hunting grounds searching for monster targets. |
| `STANDBY` | `duration_ms: int` | Idles or rests to regenerate HP/MP. |

---

## 3. The `SELECT_TARGET` Requirement

In real Lineage 1 gameplay, a player cannot attack an arbitrary monster without first acquiring cursor focus or clicking on the monster.
Similarly, `SELECT_TARGET` is a discrete, mandatory Player Operation prior to `ATTACK`:

1. **Perception**: The player's perception detects monster actors within radius 15.
2. **Selection**: Policy selects the optimal target based on targeting rules (e.g., nearest distance, priority monster).
3. **Discrete Action**: Emits `PlayerOperation(PlayerOperationType.SELECT_TARGET, target=monster)`.
4. **State Gate**: Sets `player.current_target = monster` and schedules target acquisition cadence (`select_target_gate`).
5. **Attack Execution**: Subsequent `PlayerOperation(PlayerOperationType.ATTACK, target=monster)` validates that `player.current_target == monster` before resolving damage.

If the target dies or leaves perception, `player.current_target` is cleared to `None`.

---

## 4. Execution Equivalence (Manual vs Automation)

A core tenet of MVP-05 is that **Manual Player Operations** and **Helper-Generated Operations** flow through the exact same execution pipeline:

```python
# Path A: Manual player action (e.g. from UI, CLI, or test script)
op = PlayerOperation(PlayerOperationType.USE_ITEM, item_id=104)
bot.execute_player_operation(op)

# Path B: Automation helper action (from rule evaluation)
rule_op = policy.evaluate_rules(world_state)
bot.execute_player_operation(rule_op)
```

Both invocations:
- Validate player state (is dead, is moving, cooldowns).
- Incur canonical temporal delays via `Scheduler`.
- Modify inventory/HP strictly through Layer 2 rules.
- Emit standard player trace logs: `[T=...] [PLAYER] USE_ITEM: Item 104`.

This equivalence is formally verified in `tests/test_player_operation.py:test_manual_vs_automation_path_equivalence`.
