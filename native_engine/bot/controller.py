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
from ..temporal import VirtualClock, Scheduler
from ..spr_action import get_pc_action_interval
from .perception import PerceptionSystem, PerceptionSnapshot
from .policy import BotPolicy, BotState, BotAction, BotActionType
from .drop import DropSystem, GroundDrop


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
        clock: Optional[VirtualClock] = None,
        scheduler: Optional[Scheduler] = None,
        rng: Optional[any] = None,
        log_callback: Optional[Callable[[str], None]] = None,
        respawn_delay_override_ms: Optional[int] = None,
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

        # Bot subsystems
        self.perception_sys = PerceptionSystem(sight_radius=14)
        self.policy = BotPolicy()
        self.drop_system = DropSystem(self.rng)

        # Movement engine for current map
        self._current_map_grid = self.world_maps[self.player.map_id]
        self.movement_engine = MovementEngine(self._current_map_grid)

        # Bot State
        self.state = BotState.SEARCH_TARGET
        self.active_target: Optional[Monster] = None
        self.kills = 0
        self.total_damage_dealt = 0
        self.total_damage_taken = 0
        self.items_looted: List[Item] = []
        self.trace_log: List[str] = []

        # Action Intervals (Resolved dynamically via SprTable: GFX + Weapon)
        self.move_interval_ms = getattr(player, "move_speed_ms", 640)
        self.attack_interval_ms = get_pc_action_interval(
            player.gfx, player.equipped_weapon, fallback=getattr(player, "attack_speed_ms", 920)
        )
        self.player.attack_speed_ms = self.attack_interval_ms

        # Autonomous Multi-Actor State
        self._monster_busy_until: Dict[int, int] = {}
        self.respawn_delay_override_ms = respawn_delay_override_ms
        self.respawn_count = 0

        # Roaming wander direction counter
        self._roam_heading = 0
        self._roam_steps_remaining = 0

        # Recurring HP regeneration timer (10s TIC, HpMpTimer.java:48-73)
        self.scheduler.schedule_after(10000, self._hp_mp_regen_tick, name="hp_mp_regen_tick")

        # Starter supplies: ensure player has basic Red Potions (item 104) for persistent hunt
        if not any(item.item_id == 104 for item in self.player.inventory.items):
            starter_pot = Item(item_id=104, name="Red Potion", count=30)
            self.player.inventory.add(starter_pot)

        self._log(f"PLAYER SPAWN: {player.name} (Lv{player.level} HP:{player.hp}/{player.max_hp}) at Map {player.map_id} ({player.x}, {player.y}) with {player.equipped_weapon.name if player.equipped_weapon else 'Bare Hands'}")

    def _hp_mp_regen_tick(self) -> None:
        """
        Natural HP regeneration TIC (HpMpTimer.java: 10s TIC).
        Recurring world event scheduled on VirtualClock.
        """
        if not self.player.is_dead:
            if self.player.hp < self.player.max_hp:
                regen = 5
                self.player.hp = min(self.player.max_hp, self.player.hp + regen)
                self._log(f"HP_REGEN: Player recovered {regen} HP -> HP: {self.player.hp}/{self.player.max_hp}")
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

    def step(self) -> None:
        """
        Executes one logical decision-and-action step.
        """
        if self.player.is_dead:
            self.state = BotState.DEAD
            return

        self._sync_map_grid()

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

        # 2. Policy Decision
        next_state, action = self.policy.decide_next_action(
            self.state, snapshot, map_grid=self._current_map_grid
        )
        self.state = next_state

        # 3. Action Execution
        if action.action_type == BotActionType.MOVE_STEP:
            target_pos = action.target
            self._execute_move_step(target_pos)

        elif action.action_type == BotActionType.ATTACK:
            monster = action.target
            self._execute_attack(monster)

        elif action.action_type == BotActionType.LOOT:
            drop = action.target
            self._execute_loot(drop)

        elif action.action_type == BotActionType.ROAM:
            self._execute_roam()

        elif action.action_type == BotActionType.USE_POTION:
            potion = action.target
            self._execute_use_potion(potion)

        elif action.action_type == BotActionType.STANDBY:
            # Standby 200ms
            self.scheduler.schedule_after(200, self.step, name="standby_tick")

    def _execute_move_step(self, target_pos: Position) -> None:
        """
        Step one tile toward target_pos along A* path.
        """
        if self.player.pos.map_id != target_pos.map_id:
            # Cannot walk across map without transition
            self.scheduler.schedule_after(self.move_interval_ms, self.step, name="step_tick")
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
                self.scheduler.schedule_after(self.move_interval_ms, self.step, name="step_tick")
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

        # Gate action interval: 640ms PC walking
        self.scheduler.schedule_after(self.move_interval_ms, self.step, name="move_action_gate")

    def _execute_attack(self, monster: Monster) -> None:
        """
        Execute PC physical attack against monster.
        Canonical Damage Timing: IMMEDIATE (T = 0).
        Canonical Action Interval Gate: player.attack_speed_ms (920ms).
        """
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

        # 3. Monster Death Check
        if new_hp == 0:
            monster.is_dead = True
            monster.target = None
            self.population.despawn(monster)
            self.kills += 1

            # Progression
            exp_gained = monster.exp
            self.player.exp += exp_gained
            self._log(f"MONSTER DIED: {monster.name} slain! Granted +{exp_gained} EXP (Total EXP: {self.player.exp})")

            # Level-up Check
            lu = self.progression.check_level_up(self.player)
            if lu:
                old_lv, new_lv, new_max_hp = lu
                self._log(f"LEVEL UP: Ding! Lv{old_lv} → Lv{new_lv}! MaxHP increased to {new_max_hp}")

            # Drop Generation (1.82 canonical droplist)
            drops = self.drop_system.roll_drops(monster.id, monster.name, monster.pos, self.clock.now())
            for d in drops:
                self._log(f"GROUND DROP: {monster.name} dropped {d.item.name} x{d.item.count} at ({d.pos.x}, {d.pos.y})")

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

            self.active_target = None
            # Schedule next step after attack interval
            self.scheduler.schedule_after(self.attack_interval_ms, self.step, name="attack_action_gate")
            return

        # 4. Monster Agro & Autonomous Counter-Attack (Asynchronous Scheduler Event)
        monster.target = self.player
        if self.clock.now() >= self._monster_busy_until.get(monster.uid, 0):
            # MonAi 30ms reaction tick
            self._schedule_monster_action(monster, delay_ms=30)

        # 5. Gate player action interval: attack_interval_ms
        self.scheduler.schedule_after(self.attack_interval_ms, self.step, name="attack_action_gate")

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
                self._log(f"PLAYER DIED: Slain by {monster.name}")
                return

            # Action gate: monster.attack_speed_ms (modespeed(GfxMode + 1))
            self._schedule_monster_action(monster, delay_ms=monster.attack_speed_ms)

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

            # Action gate: monster.move_speed_ms (modespeed(GfxMode))
            self._schedule_monster_action(monster, delay_ms=monster.move_speed_ms)
        else:
            # Target lost
            monster.target = None

    def _execute_loot(self, drop: GroundDrop) -> None:
        """
        Pick up item from ground into player inventory.
        """
        # If already on the tile, pick up
        if self.player.x == drop.pos.x and self.player.y == drop.pos.y:
            self.player.inventory.add(drop.item)
            self.items_looted.append(drop.item)
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

        # Schedule next action after 640ms walk interval
        self.scheduler.schedule_after(self.move_interval_ms, self.step, name="roam_action_gate")

    def _execute_use_potion(self, potion: Item) -> None:
        """Drink potion for HP recovery."""
        heal = self.rng.rand(15, 30, "PotionHeal")
        old_hp = self.player.hp
        self.player.hp = min(self.player.max_hp, self.player.hp + heal)
        potion.count -= 1
        if potion.count <= 0 and potion in self.player.inventory.items:
            self.player.inventory.items.remove(potion)
        self._log(f"POTION: Drank {potion.name} (+{heal} HP) -> HP: {self.player.hp}/{self.player.max_hp}")
        self.scheduler.schedule_after(600, self.step, name="potion_action_gate")

    def run_session(self, max_kills: Optional[int] = 5, max_virtual_ms: int = 600000) -> Dict[str, Any]:
        """
        Executes persistent autonomous hunting loop in Virtual Time.

        Stops only when:
        1. max_kills is reached (if max_kills is not None and > 0), OR
        2. max_virtual_ms is reached, OR
        3. player dies.
        """
        # Bootstrap first step
        self.step()

        while (
            (max_kills is None or max_kills <= 0 or self.kills < max_kills)
            and self.clock.now() < max_virtual_ms
            and not self.player.is_dead
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
            "trace_log": self.trace_log,
        }
