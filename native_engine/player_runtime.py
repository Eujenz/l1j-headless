"""
native_engine/player_runtime.py - Headless Player Runtime Facade

Architecture:
  - HeadlessPlayerRuntime: Unified facade orchestrating World, Player, HeadlessBot,
    Clock, Scheduler, and Configurable Automation.
  - PlayerRuntimeSnapshot: Thread-safe, decoupled state projection for UI / clients.
  - Strict Player Operation Equivalence: Both manual human actions and automated
    helper decisions funnel exclusively through the canonical PlayerOperation pipeline.
  - Decoupled Pacing: Supports RealTimeClock background worker threading and
    VirtualClock deterministic synchronous execution.
  - Zero-Teleport Invariant: Characters start at authentic contract spawn positions
    and navigate via discrete physical movements and map transitions.
"""
from collections import deque
from dataclasses import dataclass, field
import os
import threading
import time
from typing import Deque, Dict, List, Optional, Any, Callable

from .bot import (
    HeadlessBot,
    AutonomousConfig,
    HelperModulesConfig,
    AVAILABLE_DESTINATIONS,
    HuntingDestination,
    BotState,
)
from .clock import RealTimeClock, VirtualClock, BaseClock
from .model import Actor, Monster, Position, Item, Weapon, SLOT_NAMES
from .player_operation import PlayerOperation, PlayerOperationType
from .session import GameSession
from .temporal import Scheduler


@dataclass
class PlayerRuntimeSnapshot:
    """Thread-safe projection of the live Headless Player game state."""
    player_name: str
    class_type: int
    level: int
    hp: int
    max_hp: int
    mp: int
    max_mp: int
    exp: int
    adena: int
    x: int
    y: int
    heading: int
    map_id: int
    map_name: str
    is_dead: bool
    equipped_weapon_name: str
    active_target: Optional[Dict[str, Any]]
    nearby_monsters: List[Dict[str, Any]]
    inventory: List[Dict[str, Any]]
    helper_paused: bool
    bot_state: str
    hunting_destination_name: str
    helper_modules: Dict[str, bool]
    operations_count: Dict[str, int]
    recent_logs: List[str]          # debug trace (--debug mode)
    game_events: List[Any]          # PlayerGameEvent list for UI activity log
    virtual_time_ms: int
    speed: float
    ground_drops: List[Dict[str, Any]] = field(default_factory=list)
    exp_base: int = 0      # cumulative EXP at start of current level
    exp_next: int = 0      # cumulative EXP needed for next level (0 = max)
    str: int = 16
    dex: int = 12
    con: int = 14
    int: int = 8
    wis: int = 9
    cha: int = 12
    ac: int = 10
    mr: int = 0
    weight_pct: int = 0
    current_weight: int = 0
    max_weight: int = 1000
    weight_30_bar: int = 0
    equipped_slots: Dict[str, str] = field(default_factory=dict)

class HeadlessPlayerRuntime:
    """
    Facade providing an interactive, controllable runtime for a Headless L1J 1.82 Player.
    Bridges between Player UI (Tkinter) and Native L1J Engine.
    """

    def __init__(
        self,
        config_path: str = "configs/autonomous_default.json",
        contract_path: Optional[str] = None,
        seed: Optional[int] = 777777,
        speed: float = 1.0,
        instant: bool = False,
        legacy_root: Optional[str] = None,
    ):
        self.lock = threading.RLock()
        self.subscribers: List[Callable[[PlayerRuntimeSnapshot], None]] = []

        # 1. Load Autonomous Configuration
        self.config_path = config_path
        if os.path.exists(config_path):
            self.config = AutonomousConfig.load_json(config_path)
        else:
            self.config = AutonomousConfig()

        # 2. Clock & Scheduler Setup
        self.speed = speed
        self.instant = instant
        if instant or speed <= 0:
            self.clock: BaseClock = VirtualClock(0)
        else:
            self.clock = RealTimeClock(initial_time_ms=0, time_scale=speed)
        self.scheduler = Scheduler(self.clock)

        # 3. Initialize GameSession from Contract (AUTHENTIC START - NO TELEPORT)
        from mvp import initialize_s007_session, resolve_path
        contract_file = resolve_path(contract_path or "scenario_007_contract.json")
        self.session: GameSession = initialize_s007_session(
            contract_path=contract_file,
            legacy_root_arg=legacy_root,
            seed_override=seed,
            clock=self.clock,
        )
        self.player: Actor = self.session.player

        # 4. Initialize Headless Bot Controller
        self.trace_logs: List[str] = []  # Debug trace (all events)
        self._game_events: deque = deque(maxlen=500)  # Player-visible game events (bounded)
        self._event_seq = 0

        def log_sink(msg: str):
            with self.lock:
                # Debug trace (keep bounded at 500 lines)
                self.trace_logs.append(msg)
                if len(self.trace_logs) > 500:
                    self.trace_logs.pop(0)

                # Parse player-visible game event (Chinese)
                try:
                    from ui.game_events import GameEventFormatter
                    evt = GameEventFormatter.parse(msg, self.clock.now())
                    if evt is not None:
                        self._event_seq += 1
                        evt.seq = self._event_seq
                        self._game_events.append(evt)
                except Exception:
                    pass  # Never crash the game loop due to event parsing

        self.bot = HeadlessBot(
            player=self.player,
            world_maps=self.session.world.maps,
            population=self.session.population,
            progression=self.session.progression,
            clock=self.clock,
            scheduler=self.scheduler,
            rng=self.session.population.rng,
            log_callback=log_sink,
            config=self.config,
            provide_starter_supplies=False,
        )

        # Bootstrap initial decision
        self.bot.step()

        # 5. Background Thread Management
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._is_running = False


    # ---------------------------------------------------------------------------
    # Lifecycle & Pacing
    # ---------------------------------------------------------------------------

    def start_background(self) -> None:
        """Starts real-time simulation in a background worker thread."""
        with self.lock:
            if self._is_running:
                return
            self._is_running = True
            self._stop_event.clear()
            self._worker_thread = threading.Thread(
                target=self._run_loop, name="HeadlessPlayerWorker", daemon=True
            )
            self._worker_thread.start()

    def stop_background(self) -> None:
        """Stops background worker thread."""
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.5)
        self._is_running = False

    def is_running(self) -> bool:
        return self._is_running

    def _run_loop(self) -> None:
        """Background thread loop stepping scheduler and bot."""
        # Initial step
        with self.lock:
            self.bot.step()

        while not self._stop_event.is_set():
            with self.lock:
                next_event = self.scheduler.peek_next()
                if next_event is None:
                    self.bot.step()
                    target_time = self.clock.now() + 50
                else:
                    target_time = next_event.timestamp

            # Wait for wall-clock pacing OUTSIDE the lock so the UI thread's
            # get_snapshot()/manual ops are never blocked by simulation sleeps.
            if isinstance(self.clock, RealTimeClock):
                self._pace_outside_lock(target_time)
                if self._stop_event.is_set():
                    break

            with self.lock:
                # Re-validate: schedule may have changed while waiting
                if target_time < self.clock.now():
                    continue
                self.scheduler.run_until(target_time)

            # Cooperative yield for Tkinter / UI thread
            if isinstance(self.clock, VirtualClock):
                time.sleep(0.005)

    def _pace_outside_lock(self, target_time_ms: int) -> None:
        """Sleep (in short slices, lock-free) until wall time reaches target_time_ms."""
        clk = self.clock
        while not self._stop_event.is_set():
            expected = ((target_time_ms - clk._logical_start) / 1000.0) / clk.time_scale
            wait_s = expected - (time.perf_counter() - clk._wall_start)
            if wait_s <= 0.001:
                return
            time.sleep(min(wait_s, 0.02))

    def step(self) -> None:
        """Executes a single step synchronously (used in tests or batch mode)."""
        with self.lock:
            next_event = self.scheduler.peek_next()
            if next_event is None:
                self.bot.step()
                target_time = self.clock.now() + 50
            else:
                target_time = next_event.timestamp
            self.scheduler.run_until(target_time)

    def run_until(self, target_virtual_ms: int) -> Dict[str, Any]:
        """Runs simulation until target_virtual_ms synchronously."""
        with self.lock:
            return self.bot.run_session(max_kills=None, max_virtual_ms=target_virtual_ms, allow_respawn=True)

    def set_speed(self, speed: float) -> None:
        """Sets playback speed multiplier (e.g. 1.0, 2.0, 5.0)."""
        with self.lock:
            self.speed = max(0.1, float(speed))
            if isinstance(self.clock, RealTimeClock):
                self.clock.time_scale = self.speed
                self.clock._logical_start = self.clock.now()
                self.clock._wall_start = time.perf_counter()

    # ---------------------------------------------------------------------------
    # Automation Helper Controls
    # ---------------------------------------------------------------------------

    def pause_helper(self) -> None:
        """Pauses automation helper. Player retains manual control."""
        with self.lock:
            self.bot.pause_helper()

    def resume_helper(self) -> None:
        """Resumes automation helper."""
        with self.lock:
            self.bot.resume_helper()

    def is_helper_paused(self) -> bool:
        with self.lock:
            return self.bot.helper_paused

    # ---------------------------------------------------------------------------
    # Manual Player Operations (Exact Same Execution Pipeline as Helper)
    # ---------------------------------------------------------------------------

    def manual_move(self, heading: int) -> None:
        """
        Issues manual MOVE_STEP toward chosen heading (0~7).
        Calculates destination tile and enqueues canonical PlayerOperation.
        """
        from .movement import HEADING_DELTA
        with self.lock:
            dx, dy = HEADING_DELTA.get(heading, (0, 0))
            target_pos = Position(self.player.x + dx, self.player.y + dy, map_id=self.player.map_id)
            op = PlayerOperation(
                PlayerOperationType.MOVE_STEP,
                target=target_pos,
                detail=f"Manual Move heading={heading} to ({target_pos.x}, {target_pos.y})",
            )
            self.bot.enqueue_manual_operation(op)

    def manual_select_target(self, monster_uid: int) -> Optional[Monster]:
        """
        Issues manual SELECT_TARGET for a visible monster.
        """
        with self.lock:
            target = next(
                (m for m in self.session.population.active_monsters if getattr(m, "uid", None) == monster_uid and not m.is_dead),
                None
            )
            if target:
                op = PlayerOperation(
                    PlayerOperationType.SELECT_TARGET,
                    target=target,
                    detail=f"Manual Select Target: {target.name}#{monster_uid}",
                )
                self.bot.enqueue_manual_operation(op)
                return target
            return None

    def manual_attack(self) -> None:
        """
        Issues manual ATTACK on current target or closest visible monster.
        """
        with self.lock:
            target = self.bot.active_target
            if not target or target.is_dead:
                # Find closest reachable monster
                visible = [
                    m for m in self.session.population.active_monsters
                    if not m.is_dead and m.map_id == self.player.map_id
                ]
                if visible:
                    target = min(visible, key=lambda m: max(abs(m.x - self.player.x), abs(m.y - self.player.y)))
                    self.bot.active_target = target

            if target:
                dist = max(abs(target.x - self.player.x), abs(target.y - self.player.y))
                if dist <= 1:
                    op = PlayerOperation(
                        PlayerOperationType.ATTACK,
                        target=target,
                        detail=f"Manual Attack: {target.name}",
                    )
                else:
                    op = PlayerOperation(
                        PlayerOperationType.MOVE_STEP,
                        target=target.pos,
                        detail=f"Manual Approach: {target.name}",
                    )
                self.bot.enqueue_manual_operation(op)

    def manual_use_item(self, item_id: int) -> bool:
        """
        Issues manual USE_ITEM for an item in inventory.
        """
        with self.lock:
            item = next((i for i in self.player.inventory.items if i.item_id == item_id and i.count > 0), None)
            if item:
                op = PlayerOperation(
                    PlayerOperationType.USE_ITEM,
                    target=item,
                    detail=f"Manual Use Item: {item.name}",
                )
                self.bot.enqueue_manual_operation(op)
                return True
            return False

    def manual_toggle_equip(self, item_id: int) -> bool:
        """
        Toggles equip/unequip on equipment or uses consumable (C_ItemClick.java).
        """
        with self.lock:
            if self.player.equipped_weapon and self.player.equipped_weapon.item_id == item_id:
                op = PlayerOperation(PlayerOperationType.UNEQUIP, target=self.player.equipped_weapon, detail="Manual Unequip Weapon")
                self.bot.enqueue_manual_operation(op)
                return True

            item = next((i for i in self.player.inventory.items if i.item_id == item_id and i.count > 0), None)
            if not item:
                return False

            if getattr(item, "is_equipped", False):
                op = PlayerOperation(PlayerOperationType.UNEQUIP, target=item, detail=f"Manual Unequip: {item.name}")
            elif getattr(item, "type1", 0) in (1, 2) or getattr(item, "equip_slot", -1) >= 0:
                op = PlayerOperation(PlayerOperationType.EQUIP, target=item, detail=f"Manual Equip: {item.name}")
            else:
                op = PlayerOperation(PlayerOperationType.USE_ITEM, target=item, detail=f"Manual Use: {item.name}")

            self.bot.enqueue_manual_operation(op)
            return True

    def manual_return_town(self) -> None:
        """
        Issues manual RETURN_TOWN.
        """
        with self.lock:
            scroll = next((i for i in self.player.inventory.items if i.item_id in (139, 454) and i.count > 0), None)
            if scroll:
                op = PlayerOperation(
                    PlayerOperationType.USE_ITEM,
                    target=scroll,
                    detail="Manual Return Town via Escape Scroll",
                )
            else:
                exit_portal = Position(32669, 32802, map_id=1)
                op = PlayerOperation(
                    PlayerOperationType.MOVE_STEP,
                    target=exit_portal,
                    detail="Manual Return Town (Walking to portal)",
                )
            self.bot.enqueue_manual_operation(op)

    # ---------------------------------------------------------------------------
    # Configuration Management (On-the-Fly Mutation)
    # ---------------------------------------------------------------------------

    def update_config(self, new_config: AutonomousConfig) -> None:
        """
        Updates active configuration immediately without restarting world or resetting player.
        """
        with self.lock:
            self.config = new_config
            self.bot.config = new_config
            self.bot.policy.config = new_config

    def set_destination(self, dest_key: str) -> bool:
        """
        Sets hunting destination from canonical repository registry.
        """
        with self.lock:
            if dest_key in AVAILABLE_DESTINATIONS:
                self.config.hunting.destination = AVAILABLE_DESTINATIONS[dest_key]
                self.bot.policy.config.hunting.destination = AVAILABLE_DESTINATIONS[dest_key]
                # If away from new destination, transition state to TRAVELING_TO_HUNT
                dest = self.config.hunting.destination
                if self.player.map_id != dest.map_id or max(abs(self.player.x - dest.target_x), abs(self.player.y - dest.target_y)) > 4:
                    self.bot.state = BotState.TRAVELING_TO_HUNT
                return True
            return False

    def save_profile(self, filepath: str) -> None:
        with self.lock:
            self.config.save_json(filepath)

    def load_profile(self, filepath: str) -> bool:
        with self.lock:
            if os.path.exists(filepath):
                loaded = AutonomousConfig.load_json(filepath)
                self.update_config(loaded)
                return True
            return False

    # ---------------------------------------------------------------------------
    # State Snapshot Projection for UI
    # ---------------------------------------------------------------------------

    def get_snapshot(self) -> PlayerRuntimeSnapshot:
        """
        Extracts a clean, thread-safe projection of the runtime state.
        """
        with self.lock:
            p = self.player
            px, py = p.x, p.y

            # Nearby monsters within perception range
            nearby: List[Dict[str, Any]] = []
            for m in self.session.population.active_monsters:
                if not m.is_dead and m.map_id == p.map_id:
                    d = max(abs(m.x - px), abs(m.y - py))
                    if d <= 14:
                        nearby.append({
                            "uid": getattr(m, "uid", m.id),
                            "name": m.name,
                            "level": getattr(m, "level", 1),
                            "hp": m.hp,
                            "max_hp": m.max_hp,
                            "x": m.x,
                            "y": m.y,
                            "dist": d,
                        })
            nearby.sort(key=lambda item: item["dist"])
            nearby = nearby[:20]  # Cap at 20 nearest monsters for UI performance

            # Active Target projection
            active_tgt_proj = None
            if self.bot.active_target and not self.bot.active_target.is_dead:
                at = self.bot.active_target
                active_tgt_proj = {
                    "uid": getattr(at, "uid", at.id),
                    "name": at.name,
                    "hp": at.hp,
                    "max_hp": at.max_hp,
                    "x": at.x,
                    "y": at.y,
                }

            # Equipped slots projection (Legacy 14 slots)
            equipped_slots_proj = {}
            for slot_id, slot_name in SLOT_NAMES.items():
                eq = p.equipped_slots.get(slot_id) if hasattr(p, "equipped_slots") else None
                if eq:
                    en_prefix = f"+{getattr(eq, 'enchant', 0)} " if getattr(eq, 'enchant', 0) > 0 else ""
                    equipped_slots_proj[slot_name] = f"{en_prefix}{eq.name}"
                else:
                    equipped_slots_proj[slot_name] = "無"

            # Inventory projection
            inv_proj = [
                {
                    "item_id": i.item_id,
                    "name": i.name,
                    "count": i.count,
                    "type1": getattr(i, "type1", 0),
                    "equip_slot": getattr(i, "equip_slot", -1),
                    "weight": getattr(i, "weight", 10),
                    "enchant": getattr(i, "enchant", 0),
                    "is_equipped": getattr(i, "is_equipped", False) or bool(p.equipped_weapon and p.equipped_weapon.item_id == i.item_id),
                }
                for i in p.inventory.items
            ]

            # Adena item
            adena_item = next((i for i in p.inventory.items if i.item_id == 40308 or i.name == "Adena"), None)
            adena_cnt = adena_item.count if adena_item else 0

            # Weapon name
            weapon_name = p.equipped_weapon.name if p.equipped_weapon else "Bare Hands"

            # Map Name (Chinese for UI)
            map_names = {0: "話島村莊", 1: "話島地監 1F", 2: "話島地監 2F"}
            map_str = map_names.get(p.map_id, f"地圖 {p.map_id}")

            # Helper modules dict
            modules = getattr(self.config, "helper_modules", None)
            mod_dict = modules.to_dict() if modules else {}

            # Recent game events (player-visible, Chinese)
            recent_game_events = list(self._game_events)[-50:]

            return PlayerRuntimeSnapshot(
                player_name=p.name,
                class_type=getattr(p, "class_type", 1),
                level=p.level,
                hp=p.hp,
                max_hp=p.max_hp,
                mp=p.mp,
                max_mp=p.max_mp,
                exp=p.exp,
                adena=adena_cnt,
                x=p.x,
                y=p.y,
                heading=p.heading,
                map_id=p.map_id,
                map_name=map_str,
                is_dead=p.is_dead,
                equipped_weapon_name=weapon_name,
                active_target=active_tgt_proj,
                nearby_monsters=nearby,
                inventory=inv_proj,
                helper_paused=self.bot.helper_paused,
                bot_state=self.bot.state.name if hasattr(self.bot.state, "name") else str(self.bot.state),
                hunting_destination_name=self.config.hunting.destination.name,
                helper_modules=mod_dict,
                operations_count=dict(self.bot.operations_count),
                recent_logs=list(self.trace_logs[-50:]),
                game_events=recent_game_events,
                virtual_time_ms=self.clock.now(),
                speed=self.speed,
                ground_drops=[
                    {"x": d.pos.x, "y": d.pos.y, "name": d.item.name}
                    for d in self.bot.drop_system.ground_drops
                    if d.pos.map_id == p.map_id and max(abs(d.pos.x - px), abs(d.pos.y - py)) <= 20
                ][:40],
                exp_base=self.session.progression.get_exp_for_level(p.level),
                exp_next=self.session.progression.next_level_exp(p) or 0,
                str=getattr(p, "total_str", p.str),
                dex=getattr(p, "total_dex", p.dex),
                con=getattr(p, "total_con", p.con),
                int=getattr(p, "total_int", p.int),
                wis=getattr(p, "total_wis", p.wis),
                cha=getattr(p, "total_cha", p.cha),
                ac=getattr(p, "total_ac", p.ac),
                mr=getattr(p, "total_mr", 0),
                weight_pct=getattr(p, "weight_pct", 0),
                current_weight=getattr(p, "current_weight", 0),
                max_weight=getattr(p, "max_weight", 1000),
                weight_30_bar=getattr(p, "weight_30_bar", 0),
                equipped_slots=equipped_slots_proj,
            )

    def subscribe(self, callback: Callable[[PlayerRuntimeSnapshot], None]) -> None:
        self.subscribers.append(callback)
