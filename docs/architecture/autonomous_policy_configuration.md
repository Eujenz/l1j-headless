# Autonomous Policy Configuration Architecture

## 1. Architectural Philosophy: Strict Separation of Concerns

A core principle of the `l1j-headless` Native Runtime is the absolute decoupling between:

1. **Legacy World Rules (Canon)**:
   - Server gameplay mechanics extracted from `Eujenz/182c` (e.g., potion heal formulas `2d4 + 14`, potion cooldown `0.2s / 200ms`, escape scroll effects, shop item listings and prices, map portals, collision masks).
   - Inviolable, unalterable by player configuration, shared by all actors.
2. **Autonomous Policy Layer (Player Configuration)**:
   - The strategic intentions, preferences, and risk tolerances of the player bot.
   - For example: "drink a red potion when HP falls below 75%", "use escape scroll if HP < 25%", "resupply red potions up to 30 when reaching town", "hunt at Talking Island Dungeon 1F".
   - Persisted via declarative JSON configuration files (`configs/*.json`).
3. **Bot Controller & Decision Engine (Runtime)**:
   - Evaluates the policy hierarchy against current player state, world perception, and virtual clock.
   - Emits concrete, deterministic gameplay actions (`USE_ITEM`, `BUY_SUPPLY`, `MOVE`, `ATTACK`, `PICKUP`, `TRANSITION_MAP`).

```text
┌─────────────────────────────────────────────────────────┐
│                 Player Configuration                    │
│             (configs/autonomous_default.json)           │
│   • Potion Rules      • Emergency Escape Rules          │
│   • Resupply Profile  • Hunting Destination             │
└────────────────────────────┬────────────────────────────┘
                             │ loads via AutonomousConfig
                             ▼
┌─────────────────────────────────────────────────────────┐
│              Bot Decision Engine (policy.py)            │
│   • Rule Priority Evaluation (Emergency > Hunt)         │
│   • High-Level State Machine (Town Resupply Flow)       │
└────────────────────────────┬────────────────────────────┘
                             │ decides next action
                             ▼
┌─────────────────────────────────────────────────────────┐
│            Bot Controller (controller.py)               │
│   • Interacts with Inventory, Navigation, NPC Shop      │
│   • Dispatches Native Engine Operations                 │
└────────────────────────────┬────────────────────────────┘
                             │ executes against
                             ▼
┌─────────────────────────────────────────────────────────┐
│           L1J 1.82 Native World & Rules Engine          │
│   • Virtual Time Temporal Scheduler                     │
│   • Real Map Collision & Spatial Partitioning           │
│   • Canonical Combat & Item Formulas                    │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Decision Hierarchy & Priority

The decision engine in `native_engine/bot/policy.py` follows a strict priority cascade on every update step:

1. **Dead State Check**:
   - If player is dead (`is_dead == True`), respawn at Talking Island Town (`32599, 32931`). Reset hunt state and initiate town resupply.
2. **Emergency Action Rules**:
   - Evaluated first. Compares current HP percentage against configured emergency rules (ordered by priority ascending).
   - If triggered: transitions state to `RETURNING_TO_TOWN`, triggering escape scroll execution or walk return.
3. **Consumable / Potion Rules**:
   - Evaluated during any active state (hunting or traveling). Checks HP thresholds against cooldown timers in virtual time (`next_potion_time <= current_time`).
   - If triggered: emits `USE_ITEM` action to consume the designated potion.
4. **Autonomous State Machine**:
   - **`RETURNING_TO_TOWN`**: If in dungeon/field, use escape scroll or navigate to town center. Once in town, transitions to `NAVIGATING_TO_SHOP`.
   - **`NAVIGATING_TO_SHOP`**: Computes A* path to NPC shop (e.g. Pandora at `32644, 32955`). Upon reaching interaction proximity ($\le 2$ tiles), transitions to `BUYING_SUPPLIES`.
   - **`BUYING_SUPPLIES`**: Iterates configured `ResupplyItem` list. Computes shortage:
     $$\Delta = \text{target\_quantity} - \text{current\_inventory\_quantity}$$
     If $\Delta > 0$, executes `BUY_SUPPLY` with Pandora. If funds are insufficient or partial, logs transaction trace and finishes resupply pass. Transitions to `TRAVELING_TO_HUNT`.
   - **`TRAVELING_TO_HUNT`**: If player is on surface (Map 0) and destination is Map 1, navigates along surface road to portal at `(32477, 32851)`. Upon stepping on portal, executes `TRANSITION_MAP`.
   - **`HUNTING`**: Autonomous combat loop (perception $\to$ targeting $\to$ A* approach $\to$ attack $\to$ loot $\to$ respawn). Also evaluates `ReturnToTownPolicy` (e.g., return if red potions $< 3$ and player has sufficient adena to resupply).

---

## 3. Safe Fallbacks & Robustness

- **Insufficient Adena Protection**:
  If a bot runs out of potions in the field but has zero or insufficient adena to buy new potions, it will not waste escape scrolls looping at town. Instead, it logs an economic alert and resumes field combat with HP natural regeneration.
- **Single-Pass Shop Guard**:
  When visiting an NPC shop, the bot attempts purchases in a single pass (`resupply_attempted_this_visit`). If partial funds allow buying only 3 out of 30 potions, the bot accepts the partial resupply and immediately sets out to hunt rather than halting or endlessly re-querying the shop.
- **Long-Distance Navigation Limits**:
  A* search iteration limits (`LIMIT_LOOP`) are calibrated to 2000, ensuring complete paths can be computed from town coordinates `(32644, 32955)` all the way to dungeon entrance `(32477, 32851)` (~199 grid steps) in single-digit milliseconds.
