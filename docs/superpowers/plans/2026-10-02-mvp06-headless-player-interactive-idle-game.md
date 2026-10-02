# MVP-06: Headless Player Interactive Idle Game Implementation Plan

## Overview
Transform `l1j-headless` from an autonomous-profile-only script runner into an interactive Headless Player idle game.
The player can select a character, choose a hunting area, customize helper rules (potions, emergency escape, return to town, resupply quantities, module toggles), start real-time gameplay, watch live operations, pause the helper at any time, intervene with manual actions (movement, targeting, attack, items), adjust helper rules on the fly without world restarts, and resume automation.

Key Architectural Principle: **Manual and Automation use the EXACT SAME execution path:**
```text
Manual: UI -> PlayerOperation -> Controller -> Native World
Helper: Perception -> Policy -> PlayerOperation -> Controller -> Native World
```

---

## File Structure & Responsibilities

1. **`native_engine/bot/config.py`**:
   - Add `HelperModulesConfig` (granular boolean toggles for `auto_target`, `auto_attack`, `auto_move`, `auto_potion`, `auto_buff`, `auto_loot`, `auto_return`, `auto_resupply`).
   - Add `AVAILABLE_DESTINATIONS` registry (`ti_dungeon_1f`, `ti_surface_field`).
   - Ensure full serialization round-trip (`to_dict`, `from_dict`, `to_json`, `from_json`).

2. **`native_engine/bot/policy.py`**:
   - Respect `helper_modules` toggles in `decide_next_action`.

3. **`native_engine/bot/controller.py`**:
   - Add `helper_paused: bool` property and `manual_operation_queue`.
   - In `step()`, if helper is paused, do not query autonomous policy; instead process queued manual operations or enter standby.
   - Monster behavior and natural HP/MP regen continue ticking on the scheduler.

4. **`native_engine/player_runtime.py`** *(NEW)*:
   - `HeadlessPlayerRuntime` facade orchestrating World, Player, HeadlessBot, Clock, Scheduler, and Config.
   - Threaded background execution with `RealTimeClock` pacing.
   - Thread-safe APIs for manual commands: `manual_move(heading)`, `manual_select_target(uid)`, `manual_attack()`, `manual_use_item(item_id)`, `manual_return_town()`.
   - Control APIs: `pause_helper()`, `resume_helper()`, `is_helper_paused()`, `set_speed(speed: float)`.
   - Config APIs: `update_config(new_config)`, `save_profile(path)`, `load_profile(path)`.
   - Snapshot API: `get_snapshot() -> PlayerRuntimeSnapshot`.

5. **`ui/`** *(NEW)*:
   - `ui/__init__.py`
   - `ui/player_view_model.py`: State adapter between `HeadlessPlayerRuntime` and Tkinter widgets.
   - `ui/config_panel.py`: Tkinter configuration editor (potion rules, emergency rules, return triggers, resupply target quantities, helper module toggles, profile save/load).
   - `ui/player_window.py`: Main interactive player window (Character HUD, Helper HUD, Nearby Monster Listbox, Manual D-pad & Actions, Live Trace Log, Inventory Listbox, embedded Config dialog).

6. **`mvp.py`**:
   - `python mvp.py`: Launches Tkinter GUI by default.
   - `python mvp.py --headless`: Runs headless batch mode.
   - Preserves all legacy CLI flags (`--demo`, `--s007`, `--interactive`, `--speed`, `--duration`, `--seed`, `--config`).

7. **Tests**:
   - `tests/test_player_runtime.py` *(NEW)*: 10 required architectural tests.
   - `tests/test_player_config_ui.py` *(NEW)*: Headless Tkinter UI smoke & integration tests.
   - `tests/test_mvp_entrypoint.py`: Updated for default GUI vs `--headless`.

8. **Documentation**:
   - `docs/architecture/headless_player_runtime.md`
   - `docs/architecture/player_ui.md`
   - `docs/architecture/manual_and_automation_equivalence.md`
   - `README.md` updated with MVP-06 charter.

---

## Detailed Task Breakdown

### Phase 1: Configuration & Policy Modules
- [ ] **Task 1.1**: Define `HelperModulesConfig` in `native_engine/bot/config.py` and register canonical hunting destinations.
- [ ] **Task 1.2**: Update `BotPolicy.decide_next_action` in `native_engine/bot/policy.py` to check `helper_modules` flags before generating actions.
- [ ] **Task 1.3**: Add `helper_paused` state and `enqueue_manual_operation` in `HeadlessBot` (`native_engine/bot/controller.py`).

### Phase 2: Headless Player Runtime Facade
- [ ] **Task 2.1**: Implement `native_engine/player_runtime.py` with `HeadlessPlayerRuntime` and `PlayerRuntimeSnapshot`.
- [ ] **Task 2.2**: Write `tests/test_player_runtime.py` covering all 10 contract tests:
  - Test 1: Config serialization
  - Test 2: In-game HP threshold update
  - Test 3: Destination selection
  - Test 4: Contract start position (no teleport)
  - Test 5: Natural movement & map transition
  - Test 6: Pause helper stops autonomous operations
  - Test 7: Manual target selection
  - Test 8: Manual attack through same controller path
  - Test 9: Resume helper restarts autonomous operations
  - Test 10: Profile save/load round-trip

### Phase 3: Tkinter GUI Components
- [ ] **Task 3.1**: Create `ui/player_view_model.py`.
- [ ] **Task 3.2**: Create `ui/config_panel.py`.
- [ ] **Task 3.3**: Create `ui/player_window.py`.
- [ ] **Task 3.4**: Write `tests/test_player_config_ui.py` with headless Tkinter smoke tests.

### Phase 4: Entrypoint Integration & CLI Convergence
- [ ] **Task 4.1**: Refactor `mvp.py` to route to GUI by default and support `--headless`.
- [ ] **Task 4.2**: Update `launcher.py` with GUI entrypoint.
- [ ] **Task 4.3**: Update `tests/test_mvp_entrypoint.py` to ensure CLI backward compatibility.

### Phase 5: Documentation & Full Verification
- [ ] **Task 5.1**: Write architecture docs (`docs/architecture/headless_player_runtime.md`, `player_ui.md`, `manual_and_automation_equivalence.md`) and update `README.md`.
- [ ] **Task 5.2**: Run full test discovery (`python -m unittest discover -s tests -p "test_*.py"`).
- [ ] **Task 5.3**: Run multi-profile behavioral variance verification (`autonomous_default.json`, `conservative_hunt.json`, `aggressive_hunt.json`).
