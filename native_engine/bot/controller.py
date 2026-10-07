"""
native_engine/bot/controller.py - L1J 1.82 Headless Bot Controller

Architecture:
  - Autonomous player controller operating purely in Virtual Time via VirtualClock & Scheduler.
  - Decoupled from graphical client, OCR, and wall-clock time.
  - Implements the complete Vertical Slice:
      Perception -> Policy Decision -> Movement (640ms) -> Combat (IMMEDIATE damage) -> Loot -> Progression
  - Persistent hunting: no-targets state triggers autonomous roaming/patrol, never premature termination.
"""
from typing import List, Optional, Tuple, Dict, Any, Callable
from ..model import Actor, Monster, Position, Item, Weapon
from ..map import WorldMapGrid
from ..population import PopulationManager
from ..progression import ProgressionManager
from ..combat import CanonicalCombat
from ..navigation import AStarPlanner
from ..movement import MovementEngine, can_move, HEADING_DELTA
from ..temporal import BaseClock, VirtualClock, Scheduler
from ..spr_action import get_pc_action_interval, SprTable
from ..status import StatusManager, StatusType
from ..skill import SkillEngine
from .perception import PerceptionSystem, PerceptionSnapshot
from .policy import BotPolicy, BotState, BotAction, BotActionType
from .drop import DropSystem, GroundDrop
from .config import AutonomousConfig


class HeadlessBot:
    """
    Autonomous Headless Bot playing L1J 1.82 by canonical rules.
    """

    def __init__(
        self,
        player: Actor,
        world_maps: Dict[int, WorldMapGrid],
        population: PopulationManager,
        progression: ProgressionManager,
        clock: Optional[BaseClock] = None,
        scheduler: Optional[Scheduler] = None,
        rng: Optional[any] = None,
        log_callback: Optional[Callable[[str], None]] = None,
        respawn_delay_override_ms: Optional[int] = None,
        config: Optional[AutonomousConfig] = None,
        provide_starter_supplies: bool = True,
    ):
        self.player = player
        self.world_maps = world_maps
        self.population = population
        self.progression = progression
        self.rng = rng or population.rng
        self.log_callback = log_callback

        # Temporal Runtime
        self.clock = clock or VirtualClock(0)
        self.scheduler = scheduler or Scheduler(self.clock)

        # Status Manager & Skill Engine
        self.status_mgr = StatusManager(self.scheduler, self.clock)
        self.skill_engine = SkillEngine(self.rng)

        # Configurable Autonomous Policy
        self.config = config or AutonomousConfig()
        self.policy = BotPolicy(config=self.config)

        # Bot subsystems
        self.perception_sys = PerceptionSystem(sight_radius=14)
        self.drop_system = DropSystem(self.rng)

        # Movement engine for current map
        self._current_map_grid = self.world_maps[self.player.map_id]
        self.movement_engine = MovementEngine(self._current_map_grid)

        # Bot State & Statistics
        self.state = BotState.SEARCH_TARGET
        self.active_target: Optional[Monster] = None
        self.kills = 0
        self.total_damage_dealt = 0
        self.total_damage_taken = 0
        self.items_looted: List[Item] = []
        self.trace_log: List[str] = []

        # Long-Running Lifecycle Metrics
        self.emergency_escapes = 0
        self.town_visits = 0
        self.shop_purchases = 0
        self.adena_earned = 0
        self.adena_spent = 0
        self.resupply_cycles = 0
        self.hunt_cycles = 0
        self.maps_traversed = 0
        self.potions_consumed = 0

        # Action Intervals (Resolved dynamically via SprTable: GFX + Weapon)
        self.move_interval_ms = SprTable.get_instance().get_move_speed(
            player.gfx, getattr(player, "gfx_mode", 0)
        )
        if getattr(player, "move_speed_ms", None) is None or player.move_speed_ms == 640:
            player.move_speed_ms = self.move_interval_ms
        else:
            self.move_interval_ms = player.move_speed_ms

        self.attack_interval_ms = get_pc_action_interval(
            player.gfx, player.equipped_weapon, fallback=getattr(player, "attack_speed_ms", 920)
        )
        self.player.attack_speed_ms = self.attack_interval_ms

        # Autonomous Multi-Actor State
        self._player_busy_until: int = 0
        self._monster_busy_until: Dict[int, int] = {}
        self.respawn_delay_override_ms = respawn_delay_override_ms
        self.respawn_count = 0

        # Roaming wander direction counter
        self._roam_heading = 0
        self._roam_steps_remaining = 0

        # Recurring HP/MP regeneration timer (10s TIC, HpMpTimer.java:48-73)
        self.scheduler.schedule_after(10000, self._hp_mp_regen_tick, name="hp_mp_regen_tick")

        # Player Operations tracking
        from collections import defaultdict
        self.operations_count: Dict[str, int] = defaultdict(int)
        self.helper_paused: bool = False
        self.manual_queue: List[Any] = []

        # Initial state: If player is away from hunting destination, start by traveling to hunt
        dest = self.config.hunting.destination
        if self.player.map_id != dest.map_id or max(abs(self.player.x - dest.target_x), abs(self.player.y - dest.target_y)) > 4:
            self.state = BotState.TRAVELING_TO_HUNT
            self.policy.resupply_attempted_this_visit = True
        else:
            self.state = BotState.SEARCH_TARGET

        # Starter supplies: load from configured profile (Layer 4 User Configuration)
        configured_supplies = getattr(self.config.character, "starter_supplies", []) or getattr(self.config, "starter_supplies", [])
        if configured_supplies:
            for s in configured_supplies:
                iid = s.get("item_id", 0)
                name = s.get("name", "Item")
                count = s.get("count", 1)
                existing = next((i for i in self.player.inventory.items if i.item_id == iid), None)
                if existing:
                    existing.count += count
                else:
                    self.player.inventory.add(Item(item_id=iid, name=name, count=count))
        elif provide_starter_supplies:
            # Fallback starter supplies
            if not any(item.item_id == 104 for item in self.player.inventory.items):
                starter_pot = Item(item_id=104, name="Red Potion", count=30)
                self.player.inventory.add(starter_pot)
            if not any(item.item_id == 108 for item in self.player.inventory.items):
                starter_green_pot = Item(item_id=108, name="Green Potion", count=10)
                self.player.inventory.add(starter_green_pot)
            if not any(item.item_id in (139, 454) or "Escape" in item.name for item in self.player.inventory.items):
                starter_escape = Item(item_id=139, name="Escape Scroll", count=5)
                self.player.inventory.add(starter_escape)
            if not any(item.item_id == 40308 or item.name == "Adena" for item in self.player.inventory.items):
                starter_adena = Item(item_id=40308, name="Adena", count=1000)
                self.player.inventory.add(starter_adena)

        self._log(f"PLAYER SPAWN: {player.name} (Lv{player.level} HP:{player.hp}/{player.max_hp} MP:{player.mp}/{player.max_mp}) at Map {player.map_id} ({player.x}, {player.y}) with {player.equipped_weapon.name if player.equipped_weapon else 'Bare Hands'}")

    def _hp_mp_regen_tick(self) -> None:
        """
        Natural HP/MP regeneration TIC (HpMpTimer.java: 10s TIC).
        Recurring world event scheduled on VirtualClock.
        """
        if not self.player.is_dead:
            if self.player.hp < self.player.max_hp:
                regen = 5
                self.player.hp = min(self.player.max_hp, self.player.hp + regen)
                self._log(f"HP_REGEN: Player recovered {regen} HP -> HP: {self.player.hp}/{self.player.max_hp}")
            if self.player.mp < self.player.max_mp:
                mp_regen = 3
                self.player.mp = min(self.player.max_mp, self.player.mp + mp_regen)
                self._log(f"MP_REGEN: Player recovered {mp_regen} MP -> MP: {self.player.mp}/{self.player.max_mp}")
            self.scheduler.schedule_after(10000, self._hp_mp_regen_tick, name="hp_mp_regen_tick")

    def _log(self, message: str) -> None:
        """Record formatted timestamped event trace."""
        entry = f"[T={self.clock.now():06d}] {message}"
        self.trace_log.append(entry)
        if self.log_callback:
            self.log_callback(entry)

    def _sync_map_grid(self) -> None:
        if self._current_map_grid.map_id != self.player.map_id:
            self._current_map_grid = self.world_maps[self.player.map_id]
            self.movement_engine = MovementEngine(self._current_map_grid)

    def pause_helper(self) -> None:
        """Pause automation helper rules. Player can manually operate character."""
        self.helper_paused = True
        self.state = BotState.IDLE
        self._log("[HELPER] Paused by player - Manual mode active")

    def resume_helper(self) -> None:
        """Resume automation helper rules."""
        self.helper_paused = False
        dest = self.config.hunting.destination
        if self.player.map_id != dest.map_id or max(abs(self.player.x - dest.target_x), abs(self.player.y - dest.target_y)) > 4:
            self.state = BotState.TRAVELING_TO_HUNT
        else:
            self.state = BotState.SEARCH_TARGET
        self._log("[HELPER] Resumed by player - Automation active")
        self.step()

    def enqueue_manual_operation(self, op: Any) -> None:
        """
        Enqueue a manual player operation from UI.
        Processed with highest priority on the canonical Controller pipeline.
        Capped to prevent keyboard-repeat queue flooding while respecting action cadence.
        """
        if len(self.manual_queue) >= 5:
            return
        self.manual_queue.append(op)
        if self.helper_paused:
            from ..temporal import RealTimeClock
            from ..player_operation import PlayerOperationType
            op_type = getattr(op, "op_type", getattr(op, "action_type", None))
            is_non_physical = (op_type == PlayerOperationType.SELECT_TARGET)

            if is_non_physical or not isinstance(self.clock, RealTimeClock) or self.clock.now() >= self._player_busy_until:
                self.step()

    def step(self) -> None:
        """
        Executes one logical decision-and-action step.
        """
        if self.player.is_dead:
            self.state = BotState.DEAD
            return

        self._sync_map_grid()

        # Check manual operation queue first (highest priority for human player)
        if self.manual_queue:
            from ..temporal import RealTimeClock
            from ..player_operation import PlayerOperationType
            first_op = self.manual_queue[0]
            op_type = getattr(first_op, "op_type", getattr(first_op, "action_type", None))
            is_non_physical = (op_type == PlayerOperationType.SELECT_TARGET)

            # In real-time mode, physical actions must respect the player's action cadence gate
            if not is_non_physical and isinstance(self.clock, RealTimeClock) and self.clock.now() < self._player_busy_until:
                return

            manual_op = self.manual_queue.pop(0)
            op_name = getattr(manual_op, "op_type", getattr(manual_op, "action_type", None))
            name_str = op_name.name if hasattr(op_name, "name") else str(op_name)
            self._log(f"[MANUAL] Executing manual player operation: {name_str}")
            self.execute_player_operation(manual_op)
            return

        # Action interval cooldown: player cannot initiate new autonomous actions while busy
        from ..temporal import RealTimeClock
        if isinstance(self.clock, RealTimeClock) and self.clock.now() < self._player_busy_until:
            return

        # 1. Perception
        snapshot = self.perception_sys.perceive(
            player=self.player,
            population=self.population,
            ground_drops=self.drop_system.ground_drops,
            active_target=self.active_target,
        )

        # Autonomous agro check: nearby aggressive monsters acquire target and advance
        for m in snapshot.nearby_monsters:
            if not m.is_dead and m.target is None:
                dist = max(abs(m.x - self.player.x), abs(m.y - self.player.y))
                if dist <= 3 or getattr(m, "agro", False):
                    m.target = self.player
                    if self.clock.now() >= self._monster_busy_until.get(m.uid, 0):
                        self._schedule_monster_action(m, delay_ms=30)

        # If helper is paused, do NOT generate autonomous policy actions!
        if self.helper_paused:
            self.state = BotState.IDLE
            self.scheduler.schedule_after(200, self.step, name="paused_idle_tick")
            return

        # 2. Policy Decision (Layer 4 Automation)
        next_state, action = self.policy.decide_next_action(
            self.state, snapshot, map_grid=self._current_map_grid
        )
        self.state = next_state

        op_type = getattr(action, "action_type", None) or getattr(action, "op_type", None)
        if op_type is not None:
            from ..player_operation import PlayerOperationType
            op_name = op_type.name if hasattr(op_type, "name") else str(op_type)
            if op_type in (PlayerOperationType.SELECT_TARGET, PlayerOperationType.ATTACK, PlayerOperationType.CAST_SKILL):
                tgt = action.target or self.active_target or self.player.current_target
                if tgt:
                    dist = max(abs(tgt.x - self.player.x), abs(tgt.y - self.player.y))
                    self._log(f"[PERCEPTION] Target: {tgt.name} distance={dist} HP: {tgt.hp}/{tgt.max_hp}")
            elif op_type in (PlayerOperationType.USE_ITEM, PlayerOperationType.USE_POTION):
                hp_pct = int((self.player.hp / self.player.max_hp) * 100) if self.player.max_hp > 0 else 0
                self._log(f"[PERCEPTION] Player HP: {self.player.hp}/{self.player.max_hp} ({hp_pct}%)")
            self._log(f"[POLICY] Selected action: {op_name}")

        # 3. Action Execution via Player Operation (Layer 3 Player Action Model)
        self.execute_player_operation(action)

    def execute_player_operation(self, op: Any) -> None:
        """
        Executes a discrete PlayerOperation on the Native L1J World.
        This is the universal execution pipeline shared by:
          - Configurable Automation (BotPolicy)
          - Manual Player Commands (CLI / UI / Script)
          - Deterministic Replay / Regression Tests
        """
        from ..player_operation import PlayerOperationType

        op_type = getattr(op, "action_type", None) or getattr(op, "op_type", None)
        if op_type is not None:
            op_name = op_type.name if hasattr(op_type, "name") else str(op_type)
            if op_name == "USE_POTION":
                op_name = "USE_ITEM"
            self.operations_count[op_name] += 1

        if op_type == PlayerOperationType.SELECT_TARGET:
            target = op.target
            self.player.current_target = target
            self.active_target = target
            if target:
                self._log(f"[PLAYER] SELECT_TARGET -> {target.name}#{target.uid}")
                self._log(f"[PLAYER] Target locked: {target.name}#{target.uid}")
                self._log(f"[PLAYER] target={target.name}#{target.uid} (HP: {target.hp}/{target.max_hp})")
            self.scheduler.schedule_after(50, self.step, name="select_target_gate")

        elif op_type == PlayerOperationType.ATTACK:
            monster = op.target or self.player.current_target or self.active_target
            if monster:
                self._log(f"[PLAYER] ATTACK -> {monster.name}#{monster.uid}")
                self._execute_attack(monster)
            else:
                self.scheduler.schedule_after(200, self.step, name="attack_action_gate")

        elif op_type == PlayerOperationType.MOVE_STEP:
            target_pos = op.target
            self._execute_move_step(target_pos)

        elif op_type == PlayerOperationType.LOOT:
            drop = op.target
            self._execute_loot(drop)

        elif op_type == PlayerOperationType.ROAM:
            self._execute_roam()

        elif op_type in (PlayerOperationType.USE_ITEM, PlayerOperationType.USE_POTION):
            item = op.target or op.item_id
            self._execute_use_item(item)

        elif op_type == PlayerOperationType.CAST_SKILL:
            self._execute_cast_skill(op)

        elif op_type == PlayerOperationType.BUY_SUPPLY:
            self._log(f"[PLAYER] BUY_SUPPLY -> Pandora Shop")
            self._execute_buy_supply(op.target)

        elif op_type == PlayerOperationType.TRANSITION_MAP:
            target_pos = op.target
            self._log(f"[PLAYER] TRANSITION_MAP -> Portal at ({target_pos.x}, {target_pos.y})")
            self._execute_transition_map(target_pos)

        elif op_type == PlayerOperationType.EQUIP:
            self._execute_equip(op.target)

        elif op_type == PlayerOperationType.UNEQUIP:
            self._execute_unequip(op.target)

        elif op_type == PlayerOperationType.NPC_INTERACT:
            npc = op.target
            name = getattr(npc, "name", "NPC")
            pos = getattr(npc, "pos", self.player.pos)
            self._log(f"[PLAYER] NPC_INTERACT {name} at ({pos.x}, {pos.y}) Map {pos.map_id}")
            self.scheduler.schedule_after(200, self.step, name="npc_interact_gate")

        elif op_type == PlayerOperationType.RETURN_TOWN:
            self._log(f"[PLAYER] RETURN_TOWN -> Returning to town")
            scroll = next((i for i in self.player.inventory.items if i.item_id in (139, 454) and i.count > 0), None)
            if scroll:
                self._execute_use_item(scroll)
            else:
                self._execute_transition_map(Position(32669, 32802, map_id=1))

        elif op_type == PlayerOperationType.STANDBY:
            self.scheduler.schedule_after(200, self.step, name="standby_tick")
        else:
            # Fallback
            self.scheduler.schedule_after(200, self.step, name="default_tick")

    def _execute_equip(self, item_or_weapon: Any) -> None:
        if isinstance(item_or_weapon, Weapon):
            self.player.equip_item(item_or_weapon)
            self.player.attack_speed_ms = get_pc_action_interval(self.player.gfx, item_or_weapon)
            self._log(f"[PLAYER] EQUIP Weapon: {item_or_weapon.name} (AtkSpeed: {self.player.attack_speed_ms}ms)")
        elif hasattr(item_or_weapon, "equip_slot") and item_or_weapon.equip_slot >= 0:
            self.player.equip_item(item_or_weapon)
            if item_or_weapon.equip_slot == 11:
                self.player.attack_speed_ms = get_pc_action_interval(self.player.gfx, item_or_weapon)
            self._log(f"[PLAYER] EQUIP Gear: {item_or_weapon.name} (Slot: {item_or_weapon.equip_slot}, AC: {self.player.total_ac})")
        self._player_busy_until = self.clock.now() + 200
        self.scheduler.schedule_after(200, self.step, name="equip_action_gate")

    def _execute_unequip(self, item_or_weapon: Any) -> None:
        if isinstance(item_or_weapon, Weapon) or getattr(item_or_weapon, "equip_slot", -1) == 11:
            old_w = self.player.equipped_weapon
            self.player.unequip_slot(11)
            self.player.attack_speed_ms = get_pc_action_interval(self.player.gfx, None)
            self._log(f"[PLAYER] UNEQUIP Weapon: {old_w.name if old_w else 'None'} (AtkSpeed: {self.player.attack_speed_ms}ms)")
        elif hasattr(item_or_weapon, "equip_slot") and item_or_weapon.equip_slot >= 0:
            self.player.unequip_slot(item_or_weapon.equip_slot)
            self._log(f"[PLAYER] UNEQUIP Gear: {item_or_weapon.name} (Slot: {item_or_weapon.equip_slot}, AC: {self.player.total_ac})")
        elif isinstance(item_or_weapon, int):
            removed = self.player.unequip_slot(item_or_weapon)
            if item_or_weapon == 11:
                self.player.attack_speed_ms = get_pc_action_interval(self.player.gfx, None)
            self._log(f"[PLAYER] UNEQUIP Slot {item_or_weapon}: {removed.name if removed else 'None'} (AC: {self.player.total_ac})")
        self._player_busy_until = self.clock.now() + 200
        self.scheduler.schedule_after(200, self.step, name="unequip_action_gate")

    def _execute_move_step(self, target_pos: Position) -> None:
        """
        Step one tile toward target_pos along A* path.
        """
        if self.player.pos.map_id != target_pos.map_id:
            # Cannot walk across map without transition
            self.scheduler.schedule_after(self.player.effective_move_speed_ms, self.step, name="step_tick")
            return

        # Pathfind toward adjacent tile of target
        headings = AStarPlanner.find_path(
            self._current_map_grid,
            self.player.x,
            self.player.y,
            target_pos.x,
            target_pos.y,
        )

        if headings and len(headings) > 0:
            chosen_heading = headings[0]
            dx, dy = HEADING_DELTA[chosen_heading]
            new_x = self.player.x + dx
            new_y = self.player.y + dy

            # Check if entering a monster's tile (stop before stepping on monster if target)
            is_target_tile = (new_x == target_pos.x and new_y == target_pos.y)
            if is_target_tile and self.active_target is not None:
                # Already in melee range
                self._player_busy_until = self.clock.now() + 50
                self.scheduler.schedule_after(50, self.step, name="melee_ready_gate")
                return

            can_step, _ = can_move(self._current_map_grid, self.player.x, self.player.y, chosen_heading)
            if can_step:
                self.player.x = new_x
                self.player.y = new_y
                self.player.heading = chosen_heading
                self._log(f"MOVE: Advanced to ({self.player.x}, {self.player.y}) heading={chosen_heading}")
            else:
                self._log(f"MOVE_BLOCKED: Obstacle at ({new_x}, {new_y})")
        else:
            # Simple direct fallback step if pathfinder failed
            dx = 1 if target_pos.x > self.player.x else (-1 if target_pos.x < self.player.x else 0)
            dy = 1 if target_pos.y > self.player.y else (-1 if target_pos.y < self.player.y else 0)
            step_taken = False
            for h, (hdx, hdy) in HEADING_DELTA.items():
                if (hdx == dx or dx == 0) and (hdy == dy or dy == 0):
                    can_step, _ = can_move(self._current_map_grid, self.player.x, self.player.y, h)
                    if can_step:
                        self.player.x += hdx
                        self.player.y += hdy
                        self.player.heading = h
                        self._log(f"MOVE: Step to ({self.player.x}, {self.player.y}) toward ({target_pos.x}, {target_pos.y})")
                        step_taken = True
                        break
            if not step_taken:
                self._log(f"MOVE: Cannot navigate to ({target_pos.x}, {target_pos.y}), retrying")

        # Gate action interval: player.effective_move_speed_ms PC walking
        self._player_busy_until = self.clock.now() + self.player.effective_move_speed_ms
        self.scheduler.schedule_after(self.player.effective_move_speed_ms, self.step, name="move_action_gate")

    def _execute_attack(self, monster: Monster) -> None:
        """
        Execute PC physical attack against monster.
        Canonical Damage Timing: IMMEDIATE (T = 0).
        Canonical Action Interval Gate: player.attack_speed_ms (920ms).
        """
        self.player.current_target = monster
        self.active_target = monster
        weapon = self.player.equipped_weapon
        self._log(f"ATTACK TRIGGERED: Player attacks {monster.name} (HP: {monster.hp}/{monster.max_hp})")

        # 1. Resolve Hit via CanonicalCombat (HitFigure)
        if weapon:
            is_hit = CanonicalCombat.resolve_hit(self.player, monster, weapon, self.rng)
        else:
            is_hit = True

        p_dmg = 0
        if is_hit:
            if weapon:
                p_dmg = CanonicalCombat.calculate_damage(self.player, monster, weapon, self.rng)
            else:
                p_dmg = self.rng.rand(0, 1, "BareHand")

        # 2. IMMEDIATE Damage & HP Mutation
        old_hp = monster.hp
        new_hp = max(0, old_hp - p_dmg)
        monster.hp = new_hp
        self.total_damage_dealt += p_dmg

        self._log(f"DAMAGE RESOLVED: Player→{monster.name}: {'HIT' if is_hit else 'MISS'} for {p_dmg} dmg (IMMEDIATE) | Target HP: {new_hp}/{monster.max_hp}")
        self._log(f"[PLAYER] ATTACK {monster.name}#{monster.uid} | {'HIT' if is_hit else 'MISS'} for {p_dmg} dmg (IMMEDIATE) | Target HP: {new_hp}/{monster.max_hp}")

        # 3. Monster Death Check
        if new_hp == 0:
            monster.is_dead = True
            monster.target = None
            self.population.despawn(monster)
            self.kills += 1

            # Progression
            exp_gained = monster.exp
            self.player.exp += exp_gained
            self._log(f"[PLAYER] MONSTER DIED: {monster.name} slain! Granted +{exp_gained} EXP (Total EXP: {self.player.exp})")

            # Level-up Check
            lu = self.progression.check_level_up(self.player)
            if lu:
                old_lv, new_lv, new_max_hp = lu
                self._log(f"[PLAYER] LEVEL UP: Ding! Lv{old_lv} → Lv{new_lv}! MaxHP increased to {new_max_hp}")

            # Drop Generation (1.82 canonical droplist)
            drops = self.drop_system.roll_drops(monster.id, monster.name, monster.pos, self.clock.now())
            for d in drops:
                self._log(f"[PLAYER] GROUND DROP: {monster.name} dropped {d.item.name} x{d.item.count} at ({d.pos.x}, {d.pos.y})")

            # Schedule Canonical Respawn
            respawn_delay_ms = (
                self.respawn_delay_override_ms
                if self.respawn_delay_override_ms is not None
                else max(1000, monster.re_spawn * 1000)
            )
            self.scheduler.schedule_after(
                respawn_delay_ms,
                lambda m=monster: self._execute_respawn(m),
                name=f"respawn_{monster.uid}",
            )

            self.player.current_target = None
            self.active_target = None
            # Schedule next step after attack interval
            self._player_busy_until = self.clock.now() + self.player.effective_attack_speed_ms
            self.scheduler.schedule_after(self.player.effective_attack_speed_ms, self.step, name="attack_action_gate")
            return

        # 4. Monster Agro & Autonomous Counter-Attack (Asynchronous Scheduler Event)
        monster.target = self.player
        if self.clock.now() >= self._monster_busy_until.get(monster.uid, 0):
            # MonAi 30ms reaction tick
            self._schedule_monster_action(monster, delay_ms=30)

        # 5. Gate player action interval: effective_attack_speed_ms
        self._player_busy_until = self.clock.now() + self.player.effective_attack_speed_ms
        self.scheduler.schedule_after(self.player.effective_attack_speed_ms, self.step, name="attack_action_gate")

    def _schedule_monster_action(self, monster: Monster, delay_ms: int) -> None:
        """Schedule autonomous action for monster after delay_ms."""
        self._monster_busy_until[monster.uid] = self.clock.now() + delay_ms
        self.scheduler.schedule_after(
            delay_ms,
            lambda m=monster: self._monster_step(m),
            name=f"monster_step_{monster.uid}",
        )

    def _execute_respawn(self, monster: Monster) -> None:
        """
        Execute scheduled monster respawn into the active world.
        Parity with MonsterInstance.reSpawn() (MonsterInstance.java:527-551).
        """
        if not monster.is_dead:
            return
        new_pos = self.population.respawn_monster(monster, self._current_map_grid)
        self.respawn_count += 1
        self._log(f"RESPAWN: {monster.name} respawned at ({new_pos.x}, {new_pos.y}) HP: {monster.hp}/{monster.max_hp}")

    def _monster_step(self, monster: Monster) -> None:
        """
        Autonomous Monster AI step triggered via Scheduler.
        Implements canonical 1.82 MonsterInstance behavior:
        - Attack on modespeed(GfxMode + 1) if in attack range
        - Approach on modespeed(GfxMode) if within chase range
        - IMMEDIATE damage application upon attack
        """
        if monster.is_dead or self.player.is_dead:
            return
        if monster.target is None:
            return

        # Check distance to target
        dx = self.player.x - monster.x
        dy = self.player.y - monster.y
        dist = max(abs(dx), abs(dy))

        if dist <= 1:
            # In melee range: Monster Attack!
            m_min = monster.min_dmg
            m_max = monster.max_dmg
            if m_max > 0:
                m_raw = self.rng.rand(m_min, m_max, "MonsterDmg")
            else:
                m_raw = 0

            player_ac = getattr(self.player, "ac", 10)
            if player_ac > 0 and m_raw > 0:
                ac_reduce = self.rng.rand(1, player_ac, "MonsterAcReduce")
                m_dmg = max(0, m_raw - ac_reduce)
            else:
                m_dmg = m_raw

            old_p_hp = self.player.hp
            new_p_hp = max(0, old_p_hp - m_dmg)
            self.player.hp = new_p_hp
            self.total_damage_taken += m_dmg

            self._log(f"MONSTER ATTACK: {monster.name}→Player for {m_dmg} dmg | Player HP: {new_p_hp}/{self.player.max_hp}")

            if new_p_hp == 0:
                self.player.is_dead = True
                self.state = BotState.DEAD
                # Clear buffs and potion statuses upon death (PcInstance.java:789-858)
                self.status_mgr.clear_all(self.player)

                # Novice protection check (PcInstance.java:789-858)
                if self.player.level <= 9:
                    self._log(f"PLAYER DIED: Slain by {monster.name}. Novice protection active (Lv{self.player.level} <= 9), 0 EXP lost.")
                else:
                    lost_exp = int(self.player.exp * 0.10)
                    self.player.exp = max(0, self.player.exp - lost_exp)
                    self._log(f"PLAYER DIED: Slain by {monster.name}. Lost {lost_exp} EXP (10%).")

                # Schedule Town Respawn after 5000ms
                self.scheduler.schedule_after(5000, self._execute_player_respawn, name="player_respawn")
                return

            # Action gate: monster.effective_attack_speed_ms (modespeed(GfxMode + 1) with status)
            self._schedule_monster_action(monster, delay_ms=monster.effective_attack_speed_ms)

        elif dist <= 12:
            # In pursuit range: Monster Move!
            step_dx = 1 if dx > 0 else (-1 if dx < 0 else 0)
            step_dy = 1 if dy > 0 else (-1 if dy < 0 else 0)

            step_taken = False
            for h, (hdx, hdy) in HEADING_DELTA.items():
                if (hdx == step_dx or step_dx == 0) and (hdy == step_dy or step_dy == 0):
                    cand_x = monster.x + hdx
                    cand_y = monster.y + hdy
                    if cand_x == self.player.x and cand_y == self.player.y:
                        # Do not overlap player tile
                        break
                    can_step, _ = can_move(self._current_map_grid, monster.x, monster.y, h)
                    if can_step:
                        monster.x = cand_x
                        monster.y = cand_y
                        monster.heading = h
                        self._log(f"MONSTER MOVE: {monster.name} advanced to ({monster.x}, {monster.y}) pursuing Player")
                        step_taken = True
                        break

            # Action gate: monster.effective_move_speed_ms (modespeed(GfxMode) with status)
            self._schedule_monster_action(monster, delay_ms=monster.effective_move_speed_ms)
        else:
            # Target lost
            monster.target = None

    def _execute_player_respawn(self) -> None:
        """
        Respawn player at canonical Talking Island town coordinates.
        (Talking Island town: (32599, 32931) map 0, getback_restart.sql:223)
        """
        self.player.is_dead = False
        self.player.hp = max(1, self.player.max_hp // 2)
        old_map = self.player.map_id
        self.player.map_id = 0
        self.player.x = 32599
        self.player.y = 32931
        self.active_target = None
        self.state = BotState.SEARCH_TARGET
        self.town_visits += 1
        if old_map != 0:
            self.maps_traversed += 1
        self._sync_map_grid()
        self._log(f"PLAYER RESPAWN: Revived at Town ({self.player.x}, {self.player.y}) with HP: {self.player.hp}/{self.player.max_hp}")
        self.step()

    def _execute_loot(self, drop: GroundDrop) -> None:
        """
        Pick up item from ground into player inventory.
        """
        # If already on the tile, pick up
        if self.player.x == drop.pos.x and self.player.y == drop.pos.y:
            self.player.inventory.add(drop.item)
            self.items_looted.append(drop.item)
            if drop.item.item_id == 40308 or drop.item.name == "Adena":
                self.adena_earned += drop.item.count
            self.drop_system.remove_drop(drop)
            self._log(f"LOOT: Picked up {drop.item.name} x{drop.item.count} -> Added to Inventory")
            self.scheduler.schedule_after(200, self.step, name="loot_action_gate")
        else:
            # Move towards drop tile
            self._execute_move_step(drop.pos)

    def _execute_roam(self) -> None:
        """
        Autonomous patrol/roaming when no targets in sight.
        Never terminates the simulation; persistently searches for enemies.
        """
        if self._roam_steps_remaining <= 0:
            self._roam_heading = self.rng.rand(0, 7, "RoamHeading")
            self._roam_steps_remaining = self.rng.rand(2, 6, "RoamSteps")

        can_step, _ = can_move(self._current_map_grid, self.player.x, self.player.y, self._roam_heading)
        if can_step:
            dx, dy = HEADING_DELTA[self._roam_heading]
            self.player.x += dx
            self.player.y += dy
            self.player.heading = self._roam_heading
            self._roam_steps_remaining -= 1
            self._log(f"PATROL: Roaming ({self.player.x}, {self.player.y}) heading={self._roam_heading}")
        else:
            # Pick a new heading
            self._roam_heading = (self._roam_heading + 2) % 8
            self._roam_steps_remaining = 3

        # Schedule next action after effective walk interval
        self._player_busy_until = self.clock.now() + self.player.effective_move_speed_ms
        self.scheduler.schedule_after(self.player.effective_move_speed_ms, self.step, name="roam_action_gate")

    def _execute_use_potion(self, potion: Any) -> None:
        """
        Legacy compatibility wrapper delegating to universal _execute_use_item.
        """
        self._execute_use_item(potion)

    def _execute_use_item(self, item_or_id: Any) -> None:
        """
        Universal item usage executing canonical L1J 1.82 item semantics.
        Item effects (Layer 2) are strictly governed by legacy server rules:
          - Item 104 (Red Potion): heals 10~30 HP (LesserHealingPotion.java)
          - Item 103/105 (Orange Potion): heals 30~70 HP (HealingPotion.java)
          - Item 106 (Clear Potion): heals 70~150 HP (HealingPotion.java)
          - Item 108 (Green Potion): applies Haste status for 300s (HastePotion.java)
          - Item 110 (Bravery Potion): applies Brave status for 300s (BravePotion.java)
          - Item 139/454 (Escape Scroll): teleports to town restart point (ScrollEscape.java)
        """
        if isinstance(item_or_id, Item):
            item = item_or_id
        elif isinstance(item_or_id, int):
            item = next((i for i in self.player.inventory.items if i.item_id == item_or_id and i.count > 0), None)
        else:
            item = next((i for i in self.player.inventory.items if getattr(i, "name", "") == str(item_or_id) and i.count > 0), None)

        if not item or item.count <= 0:
            self._log(f"[PLAYER] USE_ITEM_FAILED: Item {item_or_id} not available in inventory")
            self._player_busy_until = self.clock.now() + 100
            self.scheduler.schedule_after(100, self.step, name="item_action_gate")
            return

        item_id = item.item_id
        name = item.name

        hp_pct = int((self.player.hp / self.player.max_hp) * 100) if self.player.max_hp > 0 else 0

        def _consume_item(target_item: Item) -> None:
            target_item.count -= 1
            if target_item.count <= 0 and target_item in self.player.inventory.items:
                self.player.inventory.items.remove(target_item)

        if item_id == 104 or "Red" in name:
            _consume_item(item)
            heal = self.rng.rand(10, 30, "RedPotionHeal")
            self.player.hp = min(self.player.max_hp, self.player.hp + heal)
            self.potions_consumed += 1
            self._log(f"[PLAYER] HP={hp_pct}% [PLAYER] USE_ITEM Red Potion (+{heal} HP) -> HP: {self.player.hp}/{self.player.max_hp}")
            self._player_busy_until = self.clock.now() + 600
            self.scheduler.schedule_after(600, self.step, name="potion_action_gate")

        elif item_id in (103, 105) or "Orange" in name:
            _consume_item(item)
            heal = self.rng.rand(30, 70, "OrangePotionHeal")
            self.player.hp = min(self.player.max_hp, self.player.hp + heal)
            self.potions_consumed += 1
            self._log(f"[PLAYER] HP={hp_pct}% [PLAYER] USE_ITEM Orange Potion (+{heal} HP) -> HP: {self.player.hp}/{self.player.max_hp}")
            self._player_busy_until = self.clock.now() + 600
            self.scheduler.schedule_after(600, self.step, name="potion_action_gate")

        elif item_id == 106 or "Clear" in name:
            _consume_item(item)
            heal = self.rng.rand(70, 150, "ClearPotionHeal")
            self.player.hp = min(self.player.max_hp, self.player.hp + heal)
            self.potions_consumed += 1
            self._log(f"[PLAYER] HP={hp_pct}% [PLAYER] USE_ITEM Clear Potion (+{heal} HP) -> HP: {self.player.hp}/{self.player.max_hp}")
            self._player_busy_until = self.clock.now() + 600
            self.scheduler.schedule_after(600, self.step, name="potion_action_gate")

        elif item_id == 108 or "Green" in name:
            _consume_item(item)
            self.status_mgr.apply_haste(self.player, duration_sec=300)
            self.potions_consumed += 1
            self._log(f"[PLAYER] USE_ITEM Green Potion -> Haste applied for 300s (Move: {self.player.effective_move_speed_ms}ms, Atk: {self.player.effective_attack_speed_ms}ms)")
            self._player_busy_until = self.clock.now() + 600
            self.scheduler.schedule_after(600, self.step, name="potion_action_gate")

        elif item_id in (110, 253) or "Bravery" in name or "勇敢" in name:
            # LEGACY_ARCHAEOLOGY: PotionofBravery.java:30 - Knight only (classType == 1)
            # Other classes receive S_ServerMessage(79) ("沒有任何事情發生")
            if getattr(self.player, "class_type", 1) != 1:
                self._log(f"[PLAYER] USE_ITEM_FAILED: Bravery Potion restricted to Knight (Message 79)")
                return
            _consume_item(item)
            self.status_mgr.apply_brave(self.player, duration_sec=300)
            self.potions_consumed += 1
            self._log(f"[PLAYER] USE_ITEM Bravery Potion -> Brave applied for 300s (Move: {self.player.effective_move_speed_ms}ms, Atk: {self.player.effective_attack_speed_ms}ms)")
            self._player_busy_until = self.clock.now() + 600
            self.scheduler.schedule_after(600, self.step, name="potion_action_gate")

        elif item_id in (56, 112) or "Wafer" in name or "Cookie" in name or "餅乾" in name:
            # LEGACY_ARCHAEOLOGY: ElvenWafer.java:29 - Elf only (classType == 2)
            # Other classes receive S_ServerMessage(79) ("沒有任何事情發生")
            if getattr(self.player, "class_type", 1) != 2:
                self._log(f"[PLAYER] USE_ITEM_FAILED: Elven Wafer restricted to Elf (Message 79)")
                return
            _consume_item(item)
            self.status_mgr.apply_brave(self.player, duration_sec=300)
            self.potions_consumed += 1
            self._log(f"[PLAYER] USE_ITEM Elven Wafer -> Brave applied for 300s (Move: {self.player.effective_move_speed_ms}ms, Atk: {self.player.effective_attack_speed_ms}ms)")
            self._player_busy_until = self.clock.now() + 600
            self.scheduler.schedule_after(600, self.step, name="potion_action_gate")

        elif item_id in (139, 454) or "Escape" in name or "回城" in name:
            _consume_item(item)
            self.emergency_escapes += 1
            self.town_visits += 1
            old_map = self.player.map_id
            # Teleport to Talking Island town center (GetBackRestartTable: 32599, 32931, map 0)
            self.player.map_id = 0
            self.player.x = 32599
            self.player.y = 32931
            self.player.current_target = None
            self.active_target = None
            if old_map != 0:
                self.maps_traversed += 1
            self._sync_map_grid()
            self._log(f"[PLAYER] USE_ITEM Escape Scroll -> Teleported to Town ({self.player.x}, {self.player.y}) Map 0")
            self._player_busy_until = self.clock.now() + 500
            self.scheduler.schedule_after(500, self.step, name="item_action_gate")

        else:
            # LEGACY_ARCHAEOLOGY: ItemInstance.java:182-184 - Unregistered / unusable items emit S_ServerMessage(74) ("沒有任何事情發生")
            # Must NOT deduct item count and must NOT mutate HP!
            self._log(f"[PLAYER] USE_ITEM_FAILED: {name} has no active function (Message 74: 沒有任何事情發生)")
            self._player_busy_until = self.clock.now() + 100
            self.scheduler.schedule_after(100, self.step, name="item_action_gate")

    def _execute_transition_map(self, portal_pos: Position) -> None:
        """
        Cross-map portal transition between Talking Island Surface (Map 0)
        and TI Dungeon 1F (Map 1).
        Canonical transitions from dungeon.sql:
          - Map 0 (32477, 32851) -> Map 1 (32669, 32802) (dungeon.sql: record 2)
          - Map 1 (32669, 32802) -> Map 0 (32477, 32853) (dungeon.sql: record 97)
        """
        if self.player.map_id == 0:
            # Entering TI Dungeon 1F
            self.player.map_id = 1
            self.player.x = 32669
            self.player.y = 32802
            self.maps_traversed += 1
            self.hunt_cycles += 1
            self._sync_map_grid()
            self._log(f"PORTAL_TRANSITION: Entered TI Dungeon 1F at ({self.player.x}, {self.player.y}) Map 1")
        elif self.player.map_id == 1:
            # Exiting to TI Surface
            self.player.map_id = 0
            self.player.x = 32477
            self.player.y = 32853
            self.maps_traversed += 1
            self.town_visits += 1
            self._sync_map_grid()
            self._log(f"PORTAL_TRANSITION: Exited to Surface at ({self.player.x}, {self.player.y}) Map 0")

        self._player_busy_until = self.clock.now() + 500
        self.scheduler.schedule_after(500, self.step, name="portal_action_gate")

    def _execute_buy_supply(self, target: Any) -> None:
        """
        Autonomous town resupply interaction at Pandora's Shop (NPC 3).
        Purchases configured items up to target_quantity.
        Handles partial funds and logs itemized trade breakdown.
        """
        from ..npc import PANDORA_SHOP
        shop = PANDORA_SHOP

        # Verify proximity (Chebyshev distance <= 2)
        dist = max(abs(self.player.x - shop.pos.x), abs(self.player.y - shop.pos.y))
        if self.player.map_id != shop.pos.map_id or dist > 2:
            self._log(f"[SHOP] CANNOT_INTERACT: Out of range from {shop.name} (dist={dist})")
            self._execute_move_step(shop.pos)
            return

        self._log(f"[SHOP] INTERACTION: Opened {shop.name} at ({shop.pos.x}, {shop.pos.y}) Map {shop.pos.map_id}")
        purchased_any = False

        resupply_profile = self.policy.config.resupply
        items_to_resupply = sorted([i for i in resupply_profile.items if i.enabled], key=lambda i: i.priority, reverse=True)

        for r_item in items_to_resupply:
            current_count = sum(
                i.count for i in self.player.inventory.items if (i.item_id == r_item.item_id or i.name == r_item.item)
            )
            needed = max(0, r_item.target_quantity - current_count)
            if needed <= 0:
                continue

            if r_item.item_id not in shop.catalog:
                self._log(f"[SHOP] ITEM_NOT_IN_SHOP: {r_item.item} (ID: {r_item.item_id}) not sold by {shop.name}")
                continue

            shop_entry = shop.catalog[r_item.item_id]
            price = shop_entry.price

            # Check player adena
            adena_item = next(
                (i for i in self.player.inventory.items if i.name == "Adena" or i.item_id == 40308),
                None
            )
            adena_balance = adena_item.count if adena_item else 0

            if adena_balance < price:
                self._log(f"[SHOP] INSUFFICIENT_FUNDS: Cannot afford {r_item.item} (price={price}, adena={adena_balance})")
                continue

            affordable = min(needed, adena_balance // price)
            cost = affordable * price
            adena_before = adena_balance
            success, msg = shop.buy_item(self.player, r_item.item_id, count=affordable, check_proximity=False)

            if success:
                purchased_any = True
                self.shop_purchases += 1
                self.adena_spent += cost
                adena_after = adena_item.count if adena_item in self.player.inventory.items else 0
                if affordable < needed:
                    self._log(f"[SHOP] PARTIAL_RESUPPLY: {r_item.item} current={current_count} target={r_item.target_quantity} price={price} buy={affordable} cost={cost} adena_before={adena_before} adena_after={adena_after}")
                else:
                    self._log(f"[SHOP] {r_item.item} current={current_count} target={r_item.target_quantity} price={price} buy={affordable} cost={cost} adena_before={adena_before} adena_after={adena_after}")

        if purchased_any:
            self.resupply_cycles += 1

        # Resupply finished -> transition state to TRAVELING_TO_HUNT
        self.policy.resupply_attempted_this_visit = True
        self.state = BotState.TRAVELING_TO_HUNT
        self.scheduler.schedule_after(800, self.step, name="shop_action_gate")

    def _execute_cast_skill(self, action: BotAction) -> None:
        """
        Execute skill casting in Virtual Time.
        Supports:
          - Energy Bolt (Skill ID 4): Immediate damage, action 18 (880ms)
          - Lesser Heal (Skill ID 1): Immediate HP restore, action 19 (800ms)
          - Haste (Skill ID 28): Haste buff (1200s), action 19 (800ms)
        """
        skill_id = action.skill_id
        if skill_id == 1:
            # Lesser Heal
            res = self.skill_engine.cast_heal(self.player, self.player)
            if res.success:
                self._log(f"SKILL CAST: Lesser Heal -> Restored {res.damage} HP | Player HP: {self.player.hp}/{self.player.max_hp} MP: {self.player.mp}/{self.player.max_mp}")
            else:
                self._log(f"SKILL FAILED: Lesser Heal failed ({res.message})")
            self._player_busy_until = self.clock.now() + res.cast_interval_ms
            self.scheduler.schedule_after(res.cast_interval_ms, self.step, name="skill_cast_gate")

        elif skill_id == 4:
            # Energy Bolt
            target = action.target or self.active_target
            if not target or target.is_dead:
                self._player_busy_until = self.clock.now() + 200
                self.scheduler.schedule_after(200, self.step, name="skill_cast_gate")
                return

            self.active_target = target
            res = self.skill_engine.cast_energy_bolt(self.player, target)
            if res.success:
                self.total_damage_dealt += res.damage
                self._log(f"SKILL CAST: Energy Bolt -> Hit {target.name} for {res.damage} magic dmg (IMMEDIATE) | Target HP: {target.hp}/{target.max_hp} MP: {self.player.mp}/{self.player.max_mp}")

                if target.hp == 0:
                    target.is_dead = True
                    target.target = None
                    self.population.despawn(target)
                    self.kills += 1

                    # Progression
                    exp_gained = target.exp
                    self.player.exp += exp_gained
                    self._log(f"MONSTER DIED: {target.name} slain by magic! Granted +{exp_gained} EXP (Total EXP: {self.player.exp})")

                    # Level-up Check
                    lu = self.progression.check_level_up(self.player)
                    if lu:
                        old_lv, new_lv, new_max_hp = lu
                        self._log(f"LEVEL UP: Ding! Lv{old_lv} → Lv{new_lv}! MaxHP increased to {new_max_hp}")

                    # Drops
                    drops = self.drop_system.roll_drops(target.id, target.name, target.pos, self.clock.now())
                    for d in drops:
                        self._log(f"GROUND DROP: {target.name} dropped {d.item.name} x{d.item.count} at ({d.pos.x}, {d.pos.y})")

                    # Respawn
                    respawn_delay_ms = (
                        self.respawn_delay_override_ms
                        if self.respawn_delay_override_ms is not None
                        else max(1000, target.re_spawn * 1000)
                    )
                    self.scheduler.schedule_after(
                        respawn_delay_ms,
                        lambda m=target: self._execute_respawn(m),
                        name=f"respawn_{target.uid}",
                    )
                    self.active_target = None
                else:
                    # Agro
                    target.target = self.player
                    if self.clock.now() >= self._monster_busy_until.get(target.uid, 0):
                        self._schedule_monster_action(target, delay_ms=30)
            else:
                self._log(f"SKILL FAILED: Energy Bolt failed ({res.message})")

            self._player_busy_until = self.clock.now() + res.cast_interval_ms
            self.scheduler.schedule_after(res.cast_interval_ms, self.step, name="skill_cast_gate")

        elif skill_id == 28:
            # Haste
            res = self.skill_engine.cast_haste(self.player, self.status_mgr)
            if res.success:
                self._log(f"SKILL CAST: Haste -> Haste applied for 1200s (Move: {self.player.effective_move_speed_ms}ms, Atk: {self.player.effective_attack_speed_ms}ms) | MP: {self.player.mp}/{self.player.max_mp}")
            else:
                self._log(f"SKILL FAILED: Haste failed ({res.message})")
            self._player_busy_until = self.clock.now() + res.cast_interval_ms
            self.scheduler.schedule_after(res.cast_interval_ms, self.step, name="skill_cast_gate")

        else:
            self._player_busy_until = self.clock.now() + 600
            self.scheduler.schedule_after(600, self.step, name="skill_cast_gate")

    def run_session(
        self,
        max_kills: Optional[int] = 5,
        max_virtual_ms: int = 600000,
        allow_respawn: bool = True,
    ) -> Dict[str, Any]:
        """
        Executes persistent autonomous hunting loop in Virtual Time.

        Stops only when:
        1. max_kills is reached (if max_kills is not None and > 0), OR
        2. max_virtual_ms is reached, OR
        3. player dies (if allow_respawn is False).
        """
        # Bootstrap first step
        self.step()

        while (
            (max_kills is None or max_kills <= 0 or self.kills < max_kills)
            and self.clock.now() < max_virtual_ms
            and (allow_respawn or not self.player.is_dead)
        ):
            # Run next due event or advance to next scheduled event
            next_event = self.scheduler.peek_next()
            if next_event is None:
                # No pending events, schedule immediate step
                self.step()
                continue

            target_time = min(next_event.timestamp, max_virtual_ms)
            self.scheduler.run_until(target_time)

        duration = self.clock.now()
        if self.player.is_dead:
            reason = "PLAYER_DEAD"
        elif max_kills is not None and max_kills > 0 and self.kills >= max_kills:
            reason = "KILL_LIMIT_REACHED"
        elif duration >= max_virtual_ms:
            reason = "SIMULATION_TIME_REACHED"
        else:
            reason = "SESSION_TERMINATED"

        self._log(f"SESSION END: Reason={reason} | Kills={self.kills} | Level={self.player.level} | EXP={self.player.exp} | VirtualTime={duration}ms")

        return {
            "reason": reason,
            "kills": self.kills,
            "respawns": self.respawn_count,
            "final_level": self.player.level,
            "final_exp": self.player.exp,
            "final_hp": self.player.hp,
            "max_hp": self.player.max_hp,
            "virtual_time_ms": duration,
            "damage_dealt": self.total_damage_dealt,
            "damage_taken": self.total_damage_taken,
            "items_looted": [f"{item.name} x{item.count}" for item in self.items_looted],
            "potions_consumed": self.potions_consumed,
            "emergency_returns": self.emergency_escapes,
            "town_visits": self.town_visits,
            "shop_purchases": self.shop_purchases,
            "adena_earned": self.adena_earned,
            "adena_spent": self.adena_spent,
            "loot_picked": len(self.items_looted),
            "maps_traversed": self.maps_traversed,
            "hunt_cycles": self.hunt_cycles,
            "resupply_cycles": self.resupply_cycles,
            "player_operations": dict(self.operations_count),
            "trace_log": self.trace_log,
        }
