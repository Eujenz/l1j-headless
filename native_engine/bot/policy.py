"""
native_engine/bot/policy.py - Headless Bot Decision Policy

Architecture Note:
  THIS MODULE IMPLEMENTS AUTONOMOUS BOT DECISION POLICY.
  IT IS STRICTLY SEPARATED FROM L1J 1.82 CANONICAL WORLD RULES.
  Bot policy defines "how the player agent decides what to do next",
  while Native Engine defines "what the world permits and resolves".

State Machine:
  IDLE / SEARCH_TARGET
       ↓
  MOVE_TO_TARGET (Approach)
       ↓
  ATTACK (Melee engagement)
       ↓
  TARGET_DEAD → LOOT (Pick up nearby items)
       ↓
  SEARCH_TARGET (Persistent loop; if no targets, patrol/scan instead of terminating)
"""
from enum import Enum, auto
from typing import Optional, Tuple
from ..model import Monster
from .perception import PerceptionSnapshot
from .drop import GroundDrop


class BotState(Enum):
    IDLE = auto()
    SEARCH_TARGET = auto()
    MOVE_TO_TARGET = auto()
    ATTACK = auto()
    LOOT = auto()
    RECOVER = auto()
    DEAD = auto()


class BotActionType(Enum):
    STANDBY = auto()
    ROAM = auto()
    MOVE_STEP = auto()
    ATTACK = auto()
    LOOT = auto()
    USE_POTION = auto()


class BotAction:
    def __init__(self, action_type: BotActionType, target: Optional[any] = None, detail: str = ""):
        self.action_type = action_type
        self.target = target
        self.detail = detail

    def __repr__(self):
        return f"<BotAction {self.action_type.name} target={self.target} detail='{self.detail}'>"


class BotPolicy:
    """
    Autonomous decision-making engine for the Headless Bot.
    """

    def __init__(self, hp_recovery_threshold_percent: float = 0.30):
        self.hp_recovery_threshold = hp_recovery_threshold_percent

    def select_target(
        self, snapshot: PerceptionSnapshot, map_grid: Optional[any] = None
    ) -> Optional[Monster]:
        """
        BOT POLICY: Target Selection.
        Considers:
        1. Alive & HP > 0
        2. Reachable (A* path exists or already in melee dist <= 1)
        3. Hostile / Agro monsters first (agro > 0)
        4. Closest Chebyshev distance
        """
        # Filter: only alive monsters within realistic level range (level <= player.level + 6)
        # Avoids suicide attacks on mini-bosses (e.g. Elder Lv30) by novice players
        candidates = [m for m in snapshot.nearby_monsters if not m.is_dead and m.hp > 0 and (m.level <= snapshot.level + 6)]
        if not candidates:
            return None

        valid_candidates = []
        for m in candidates:
            dx = abs(m.pos.x - snapshot.pos.x)
            dy = abs(m.pos.y - snapshot.pos.y)
            dist = max(dx, dy)
            if dist <= 1:
                valid_candidates.append((m, dist))
            elif map_grid is not None:
                from ..navigation import AStarPlanner
                path = AStarPlanner.find_path(map_grid, snapshot.pos.x, snapshot.pos.y, m.pos.x, m.pos.y)
                if path is not None:
                    valid_candidates.append((m, dist))
            else:
                valid_candidates.append((m, dist))

        if not valid_candidates:
            return None

        # Sort: melee reach (0 before 1), level suitability, distance ASC, agro, uid
        def priority_key(item):
            m, dist = item
            is_melee = 0 if dist <= 1 else 1
            too_high_level = 1 if (m.level > snapshot.level + 4) else 0
            is_agro = 0 if m.agro > 0 else 1
            return (is_melee, too_high_level, dist, is_agro, m.uid)

        valid_candidates.sort(key=priority_key)
        return valid_candidates[0][0]

    def select_loot_target(self, snapshot: PerceptionSnapshot) -> Optional[GroundDrop]:
        """
        BOT POLICY: Loot Target Selection.
        Selects closest ground drop within reach.
        """
        if not snapshot.nearby_drops:
            return None

        def drop_dist(d: GroundDrop):
            return max(abs(d.pos.x - snapshot.pos.x), abs(d.pos.y - snapshot.pos.y))

        drops_sorted = sorted(snapshot.nearby_drops, key=drop_dist)
        return drops_sorted[0]

    def decide_next_action(
        self, state: BotState, snapshot: PerceptionSnapshot, map_grid: Optional[any] = None
    ) -> Tuple[BotState, BotAction]:
        """
        Determines next state transition and concrete action given the current snapshot.
        """
        if snapshot.is_dead:
            return BotState.DEAD, BotAction(BotActionType.STANDBY, detail="Player is dead")

        # Emergency HP check
        if snapshot.hp < (snapshot.max_hp * self.hp_recovery_threshold):
            # Check for red potion (item 104) in inventory
            red_pot = next((item for item in snapshot.inventory.items if item.item_id == 104 and item.count > 0), None)
            if red_pot:
                return BotState.RECOVER, BotAction(BotActionType.USE_POTION, target=red_pot, detail="Drinking Red Potion")

        # 1. LOOT Priority: if there are drops directly on current tile or immediately adjacent
        loot_target = self.select_loot_target(snapshot)
        if loot_target:
            dist = max(abs(loot_target.pos.x - snapshot.pos.x), abs(loot_target.pos.y - snapshot.pos.y))
            if dist == 0:
                return BotState.LOOT, BotAction(BotActionType.LOOT, target=loot_target, detail=f"Looting {loot_target.item.name}")
            elif dist <= 3 and snapshot.combat_state != "IN_COMBAT":
                # Move to drop position to loot
                return BotState.LOOT, BotAction(BotActionType.MOVE_STEP, target=loot_target.pos, detail=f"Moving to loot {loot_target.item.name}")

        # 2. IN_COMBAT / Target active
        target = snapshot.target_monster
        if target is not None and not target.is_dead and target.hp > 0:
            if snapshot.is_target_in_melee:
                return BotState.ATTACK, BotAction(BotActionType.ATTACK, target=target, detail=f"Attacking {target.name}")
            else:
                return BotState.MOVE_TO_TARGET, BotAction(BotActionType.MOVE_STEP, target=target.pos, detail=f"Approaching {target.name}")

        # 3. SEARCH_TARGET: find new reachable target
        new_target = self.select_target(snapshot, map_grid=map_grid)
        if new_target:
            dist = max(abs(new_target.pos.x - snapshot.pos.x), abs(new_target.pos.y - snapshot.pos.y))
            if dist <= 1:
                return BotState.ATTACK, BotAction(BotActionType.ATTACK, target=new_target, detail=f"Engaging {new_target.name}")
            else:
                return BotState.MOVE_TO_TARGET, BotAction(BotActionType.MOVE_STEP, target=new_target.pos, detail=f"Approaching {new_target.name}")

        # 4. PERSISTENT HUNTING: No targets in sight -> Roam / Patrol, NEVER TERMINATE!
        return BotState.SEARCH_TARGET, BotAction(BotActionType.ROAM, detail="Scanning & roaming for targets")

