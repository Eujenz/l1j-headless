"""
native_engine/session.py - GameSession Orchestrator for Playable MVP (MODERN_DESIGN)
Orchestrates player intents, real map navigation, turn-based combat, and state views.
Strictly decoupled from UI/CLI presentations and legacy socket protocols.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from native_engine.combat import CanonicalCombat
from native_engine.events import (
    DomainEvent,
    AttackStarted,
    HitResolved,
    DamageApplied,
    HpChanged,
    MonsterDied,
    ExperienceGranted
)
from native_engine.model import Actor, Monster, Position, Inventory, Weapon
from native_engine.rng import NativeRng
from native_engine.transition import TransitionEngine
from native_engine.world import World
from native_engine.world_route import (
    WorldRoutePlanner,
    WorldRouteExecutor,
    WorldTransitionProvider
)


@dataclass(frozen=True)
class HuntingArea:
    id: str
    name: str
    map_id: int
    goal_x: int
    goal_y: int
    monster_type: str


@dataclass(frozen=True)
class MonsterTemplate:
    id: int
    name: str
    level: int
    hp: int
    max_hp: int
    ac: int
    exp: int
    size: str
    atk_min: int
    atk_max: int


class GameSession:
    """
    Playable MVP Game Session Orchestrator.
    Manages player lifecycle, world route navigation, encounters, and turn-based combat.
    """
    def __init__(
        self,
        world: World,
        player: Actor,
        transition_engine: TransitionEngine,
        transition_provider: WorldTransitionProvider,
        areas: Dict[str, HuntingArea],
        monsters: Dict[str, MonsterTemplate],
        seed: int = 424242
    ):
        self.world = world
        self.player = player
        self.transition_engine = transition_engine
        self.transition_provider = transition_provider
        self.areas = areas
        self.monsters = monsters
        self.rng = NativeRng(seed)

        self.state = "MENU"
        self.current_area: Optional[HuntingArea] = None
        self.active_monster: Optional[Monster] = None
        self.events_history: List[DomainEvent] = []
        self.tick = 100

    def get_status(self) -> dict:
        """Returns structured, machine-readable player and session state."""
        return {
            "player": {
                "name": self.player.name,
                "level": self.player.level,
                "hp": self.player.hp,
                "max_hp": self.player.max_hp,
                "exp": self.player.exp,
                "map_id": self.player.map_id,
                "x": self.player.x,
                "y": self.player.y,
                "heading": self.player.heading,
                "alive": not self.player.is_dead
            },
            "location": {
                "map_id": self.player.map_id,
                "x": self.player.x,
                "y": self.player.y,
                "area_id": self.current_area.id if self.current_area else None,
                "area_name": self.current_area.name if self.current_area else "Starting Grounds"
            },
            "target": {
                "name": self.active_monster.name,
                "level": self.active_monster.level,
                "hp": self.active_monster.hp,
                "max_hp": self.active_monster.max_hp,
                "alive": not self.active_monster.is_dead
            } if self.active_monster else None,
            "session_state": self.state
        }

    def select_hunting_area(self, area_id: str) -> Tuple[bool, str, List[DomainEvent]]:
        """
        Plans and executes real-world navigation to the specified hunting area.
        Uses WorldRoutePlanner (BFS) + WorldRouteExecutor (A* + Portals).
        """
        if area_id not in self.areas:
            return False, "INVALID_AREA", []

        if self.player.is_dead:
            return False, "PLAYER_DEAD", []

        target_area = self.areas[area_id]

        # Check if already standing at the destination
        if (self.player.map_id, self.player.x, self.player.y) == (target_area.map_id, target_area.goal_x, target_area.goal_y):
            self.current_area = target_area
            self.state = "HUNTING"
            return True, "ALREADY_AT_DESTINATION", []

        self.state = "TRAVELING"

        # 1. Plan World Route
        route = WorldRoutePlanner.plan(
            start_map=self.player.map_id,
            start_x=self.player.x,
            start_y=self.player.y,
            goal_map=target_area.map_id,
            goal_x=target_area.goal_x,
            goal_y=target_area.goal_y,
            transition_provider=self.transition_provider,
            map_registry=self.world.maps
        )

        if not route.is_valid:
            self.state = "MENU"
            return False, f"ROUTE_FAILED_{route.error_reason}", []

        # 2. Execute World Route
        success, nav_events, status = WorldRouteExecutor.execute(
            world=self.world,
            actor_id=self.player.id,
            route=route,
            start_pos=(self.player.x, self.player.y),
            goal_pos=(target_area.goal_x, target_area.goal_y),
            transition_engine=self.transition_engine,
            start_tick=self.tick
        )

        self.events_history.extend(nav_events)
        if nav_events:
            self.tick = nav_events[-1].tick + 10

        if not success:
            self.state = "MENU"
            return False, f"EXECUTION_FAILED_{status}", nav_events

        self.current_area = target_area
        self.state = "HUNTING"
        self.active_monster = None
        return True, "ARRIVED", nav_events

    def hunt(self) -> Tuple[bool, Optional[Monster], str]:
        """Triggers a monster encounter at the current hunting area."""
        if self.player.is_dead:
            return False, None, "PLAYER_DEAD"

        if not self.current_area:
            return False, None, "NO_HUNTING_AREA_SELECTED"

        tmpl = self.monsters.get(self.current_area.monster_type)
        if not tmpl:
            return False, None, "UNKNOWN_MONSTER_TEMPLATE"

        monster = Monster(
            id=tmpl.id,
            uid=tmpl.id,
            name=tmpl.name,
            level=tmpl.level,
            hp=tmpl.hp,
            max_hp=tmpl.max_hp,
            ac=tmpl.ac,
            exp=tmpl.exp,
            size=tmpl.size,
            pos=Position(self.player.x, self.player.y, self.player.map_id),
            heading=4,
            inventory=Inventory(),
            is_dead=False
        )

        self.active_monster = monster
        self.state = "COMBAT"
        return True, monster, "ENCOUNTER_STARTED"

    def attack(self) -> Tuple[bool, dict, str]:
        """
        Executes a single turn of turn-based combat:
        1. Player attacks Monster (Canonical Hit & Damage)
        2. If monster dies -> Victory, awards EXP
        3. If monster survives -> Monster counter-attacks Player
        4. If player dies -> Defeat
        """
        if self.player.is_dead:
            return False, {}, "PLAYER_DEAD"

        if not self.active_monster or self.active_monster.is_dead:
            return False, {}, "NO_ACTIVE_TARGET"

        self.tick += 10
        cur_tick = self.tick

        # --- 1. PLAYER ATTACK TURN ---
        self.events_history.append(AttackStarted(tick=cur_tick, attacker_id=self.player.id, target_id=self.active_monster.id))
        is_hit = CanonicalCombat.resolve_hit(self.player, self.active_monster, self.player.equipped_weapon, self.rng)
        self.events_history.append(HitResolved(tick=cur_tick, attacker_id=self.player.id, target_id=self.active_monster.id, is_hit=is_hit))

        p_dmg = 0
        if is_hit:
            p_dmg = CanonicalCombat.calculate_damage(self.player, self.active_monster, self.player.equipped_weapon, self.rng)
            self.events_history.append(DamageApplied(tick=cur_tick, attacker_id=self.player.id, target_id=self.active_monster.id, damage=p_dmg))

        old_m_hp = self.active_monster.hp
        new_m_hp = max(0, old_m_hp - p_dmg)
        self.active_monster.hp = new_m_hp
        self.events_history.append(HpChanged(tick=cur_tick, entity_id=self.active_monster.id, old_hp=old_m_hp, new_hp=new_m_hp))

        # Check Monster Death
        if new_m_hp == 0:
            self.active_monster.is_dead = True
            self.events_history.append(MonsterDied(tick=cur_tick, monster_id=self.active_monster.id))

            exp_gained = self.active_monster.exp
            self.player.exp += exp_gained
            self.events_history.append(ExperienceGranted(
                tick=cur_tick,
                actor_id=self.player.id,
                exp_gained=exp_gained,
                total_exp=self.player.exp,
                lawful=self.player.lawful
            ))

            self.state = "HUNTING"
            turn_result = {
                "player_hit": is_hit,
                "player_dmg": p_dmg,
                "monster_hp": self.active_monster.hp,
                "monster_max_hp": self.active_monster.max_hp,
                "monster_hit": False,
                "monster_dmg": 0,
                "player_hp": self.player.hp,
                "player_max_hp": self.player.max_hp,
                "exp_gained": exp_gained,
                "outcome": "VICTORY"
            }
            return True, turn_result, "VICTORY"

        # --- 2. MONSTER COUNTER-ATTACK TURN ---
        self.tick += 10
        cur_tick = self.tick

        tmpl = self.monsters.get(self.current_area.monster_type)
        m_atk_min = tmpl.atk_min if tmpl else 3
        m_atk_max = tmpl.atk_max if tmpl else 6

        # Roll monster hit check against player
        hit_roll = self.rng.rand(1, 20, "MonsterHitCheck")
        m_hit = (hit_roll >= 5)  # 80% hit probability baseline

        m_dmg = 0
        if m_hit:
            m_dmg = self.rng.rand(m_atk_min, m_atk_max, "MonsterDmgRoll")
            self.events_history.append(DamageApplied(tick=cur_tick, attacker_id=self.active_monster.id, target_id=self.player.id, damage=m_dmg))

        old_p_hp = self.player.hp
        new_p_hp = max(0, old_p_hp - m_dmg)
        self.player.hp = new_p_hp
        self.events_history.append(HpChanged(tick=cur_tick, entity_id=self.player.id, old_hp=old_p_hp, new_hp=new_p_hp))

        if new_p_hp == 0:
            self.player.is_dead = True
            self.state = "DEAD"
            outcome = "DEFEAT"
        else:
            outcome = "ONGOING"

        turn_result = {
            "player_hit": is_hit,
            "player_dmg": p_dmg,
            "monster_hp": self.active_monster.hp,
            "monster_max_hp": self.active_monster.max_hp,
            "monster_hit": m_hit,
            "monster_dmg": m_dmg,
            "player_hp": self.player.hp,
            "player_max_hp": self.player.max_hp,
            "exp_gained": 0,
            "outcome": outcome
        }
        return True, turn_result, outcome
