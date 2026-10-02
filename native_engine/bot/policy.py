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
from typing import Optional, Tuple, List, Dict, Any
from ..model import Monster, Position
from .perception import PerceptionSnapshot
from .drop import GroundDrop
from .config import (
    AutonomousConfig,
    PotionThresholdMode,
    EmergencyConditionType,
    EmergencyOperator,
    ReturnTriggerType,
    ReturnMethod,
)


class BotState(Enum):
    IDLE = auto()
    SEARCH_TARGET = auto()
    MOVE_TO_TARGET = auto()
    ATTACK = auto()
    LOOT = auto()
    RECOVER = auto()
    DEAD = auto()
    RETURNING_TO_TOWN = auto()
    NAVIGATING_TO_SHOP = auto()
    BUYING_SUPPLIES = auto()
    TRAVELING_TO_HUNT = auto()


class BotActionType(Enum):
    STANDBY = auto()
    ROAM = auto()
    MOVE_STEP = auto()
    ATTACK = auto()
    LOOT = auto()
    USE_POTION = auto()
    CAST_SKILL = auto()
    USE_ITEM = auto()
    BUY_SUPPLY = auto()
    TRANSITION_MAP = auto()


class BotAction:
    def __init__(
        self,
        action_type: BotActionType,
        target: Optional[any] = None,
        detail: str = "",
        skill_id: Optional[int] = None,
    ):
        self.action_type = action_type
        self.target = target
        self.detail = detail
        self.skill_id = skill_id

    def __repr__(self):
        return f"<BotAction {self.action_type.name} target={self.target} skill={self.skill_id} detail='{self.detail}'>"


class BotPolicy:
    """
    Autonomous decision-making engine for the Headless Bot.
    Evaluates player-configured AutonomousConfig against perception snapshots.
    """

    def __init__(
        self,
        config: Optional[AutonomousConfig] = None,
        hp_recovery_threshold_percent: Optional[float] = None,
    ):
        self.config = config or AutonomousConfig()
        if hp_recovery_threshold_percent is not None:
            self.hp_recovery_threshold = hp_recovery_threshold_percent
            if self.config.potion_rules:
                self.config.potion_rules[0].threshold = hp_recovery_threshold_percent * 100.0
        else:
            if self.config.potion_rules:
                self.hp_recovery_threshold = (
                    self.config.potion_rules[0].threshold / 100.0
                    if self.config.potion_rules[0].threshold_mode == PotionThresholdMode.HP_PERCENT
                    else (self.config.potion_rules[0].threshold / 100.0)
                )
            else:
                self.hp_recovery_threshold = 0.30
        self.resupply_attempted_this_visit: bool = False

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
        Evaluates User Config in priority order:
          1. Dead Check
          2. Emergency Survival Rules
          3. Potion Rules
          4. Haste Maintenance
          5. Town Resupply / Cross-Map Navigation Cycle
          6. Return-to-Town Policy
          7. Looting Priority
          8. Active Combat / Approaching Target
          9. New Target Search
          10. Autonomous Patrol & Roaming
        """
        if snapshot.is_dead:
            return BotState.DEAD, BotAction(BotActionType.STANDBY, detail="Player is dead")

        # 1. EMERGENCY RULES EVALUATION (Highest Priority)
        for rule in sorted([r for r in self.config.emergency_rules if r.enabled], key=lambda r: r.priority, reverse=True):
            if rule.condition.evaluate(snapshot.hp, snapshot.max_hp, snapshot.mp, snapshot.max_mp):
                item = next(
                    (i for i in snapshot.inventory.items if (i.item_id == rule.action.item_id or i.name == rule.action.item) and i.count > 0),
                    None
                )
                hp_pct = (snapshot.hp / snapshot.max_hp * 100.0) if snapshot.max_hp > 0 else 0.0
                if item:
                    detail = f"[POLICY] HP={hp_pct:.1f}% Rule=EmergencyEscape Action=USE_ITEM Item={item.name} Reason={rule.condition.type} {rule.condition.operator} {rule.condition.value}"
                    return BotState.RETURNING_TO_TOWN, BotAction(BotActionType.USE_ITEM, target=item, detail=detail)

        # 2. CONFIGURED POTION RULES EVALUATION
        for rule in sorted([r for r in self.config.potion_rules if r.enabled], key=lambda r: r.priority, reverse=True):
            if rule.threshold_mode == PotionThresholdMode.HP_PERCENT:
                hp_pct = (snapshot.hp / snapshot.max_hp * 100.0) if snapshot.max_hp > 0 else 0.0
                triggered = hp_pct <= rule.threshold
            else:
                triggered = snapshot.hp <= rule.threshold

            if triggered:
                item = next(
                    (i for i in snapshot.inventory.items if (i.item_id == rule.item_id or i.name == rule.item) and i.count > 0),
                    None
                )
                if item:
                    detail = f"[POLICY] HP={snapshot.hp}/{snapshot.max_hp} Rule=PotionRule Action=USE_POTION Item={item.name} Reason={rule.threshold_mode} <= {rule.threshold}"
                    return BotState.RECOVER, BotAction(BotActionType.USE_POTION, target=item, detail=detail)
                elif snapshot.mp >= 4:
                    detail = f"[POLICY] Potion {rule.item} missing -> Fallback Lesser Heal"
                    return BotState.RECOVER, BotAction(BotActionType.CAST_SKILL, target=None, detail=detail, skill_id=1)

        # 3. HASTE MAINTENANCE: keep haste active if item/spell available
        if not snapshot.is_speed:
            green_pot = next((item for item in snapshot.inventory.items if item.item_id == 108 and item.count > 0), None)
            if green_pot:
                return BotState.RECOVER, BotAction(BotActionType.USE_POTION, target=green_pot, detail="Drinking Green Potion")
            elif snapshot.mp >= 25 and snapshot.hp >= 30:
                return BotState.RECOVER, BotAction(BotActionType.CAST_SKILL, target=None, detail="Casting Haste", skill_id=28)

        # 4. TOWN RESUPPLY & CROSS-MAP NAVIGATION CYCLE
        if snapshot.pos.map_id != 0:
            self.resupply_attempted_this_visit = False

        # When in Town (Map 0), handle shop navigation, purchasing, and returning to hunt
        if snapshot.pos.map_id == 0:
            needs_resupply = False
            if self.config.resupply.enabled and not self.resupply_attempted_this_visit:
                for r_item in self.config.resupply.items:
                    if r_item.enabled:
                        c_count = sum(i.count for i in snapshot.inventory.items if (i.item_id == r_item.item_id or i.name == r_item.item))
                        if c_count < r_item.target_quantity:
                            needs_resupply = True
                            break

            if needs_resupply:
                pandora_pos = Position(32644, 32955, map_id=0)
                dist_to_pandora = max(abs(snapshot.pos.x - pandora_pos.x), abs(snapshot.pos.y - pandora_pos.y))
                if dist_to_pandora <= 2:
                    return BotState.BUYING_SUPPLIES, BotAction(BotActionType.BUY_SUPPLY, target=pandora_pos, detail="Interacting with Pandora Shop")
                else:
                    return BotState.NAVIGATING_TO_SHOP, BotAction(BotActionType.MOVE_STEP, target=pandora_pos, detail="Navigating to Pandora Shop")
            else:
                # Supplies are fully satisfied! Travel to hunting portal
                dest = self.config.hunting.destination
                portal_pos = Position(dest.portal_x, dest.portal_y, map_id=dest.portal_map_id)
                dist_to_portal = max(abs(snapshot.pos.x - portal_pos.x), abs(snapshot.pos.y - portal_pos.y))
                if dist_to_portal == 0:
                    return BotState.TRAVELING_TO_HUNT, BotAction(BotActionType.TRANSITION_MAP, target=portal_pos, detail="Entering Hunting Portal to TI Dungeon 1F")
                else:
                    return BotState.TRAVELING_TO_HUNT, BotAction(BotActionType.MOVE_STEP, target=portal_pos, detail=f"Traveling to Portal at ({portal_pos.x}, {portal_pos.y})")

        # When in Hunting Map (Map 1) and traveling toward hunting destination
        if snapshot.pos.map_id == 1 and state == BotState.TRAVELING_TO_HUNT:
            dest = self.config.hunting.destination
            target_pos = Position(dest.target_x, dest.target_y, map_id=dest.map_id)
            dist_to_dest = max(abs(snapshot.pos.x - target_pos.x), abs(snapshot.pos.y - target_pos.y))
            if dist_to_dest > 4:
                return BotState.TRAVELING_TO_HUNT, BotAction(BotActionType.MOVE_STEP, target=target_pos, detail="Advancing to Dungeon Hunting Grounds")

        # 5. RETURN TO TOWN POLICY CHECK (When out in the field)
        if self.config.return_to_town.enabled and state not in (
            BotState.RETURNING_TO_TOWN,
            BotState.NAVIGATING_TO_SHOP,
            BotState.BUYING_SUPPLIES,
            BotState.TRAVELING_TO_HUNT,
        ):
            for trigger in self.config.return_to_town.triggers:
                should_return = False
                reason_str = ""
                if trigger.type == ReturnTriggerType.LOW_POTION:
                    cnt = sum(i.count for i in snapshot.inventory.items if (i.item_id == trigger.item_id or i.name == trigger.item))
                    if cnt < trigger.threshold:
                        adena_cnt = sum(i.count for i in snapshot.inventory.items if i.item_id in (40308, 5) or i.name == "Adena")
                        if adena_cnt >= 37:
                            should_return = True
                            reason_str = f"Item={trigger.item} current={cnt} < {trigger.threshold} (Adena={adena_cnt})"
                elif trigger.type == ReturnTriggerType.LOW_HP:
                    has_potions = any(i.item_id in (104, 103, 105, 106) and i.count > 0 for i in snapshot.inventory.items)
                    if snapshot.hp < (snapshot.max_hp * 0.20) and not has_potions:
                        should_return = True
                        reason_str = f"Low HP ({snapshot.hp}/{snapshot.max_hp}) and no potions"

                if should_return:
                    detail = f"[POLICY] {reason_str} Action=RETURN_TOWN Reason=RESUPPLY_REQUIRED"
                    if self.config.return_to_town.return_method == ReturnMethod.USE_ESCAPE_ITEM:
                        escape_item = next(
                            (i for i in snapshot.inventory.items if (i.item_id == self.config.return_to_town.escape_item_id or i.name == self.config.return_to_town.escape_item) and i.count > 0),
                            None
                        )
                        if escape_item:
                            return BotState.RETURNING_TO_TOWN, BotAction(BotActionType.USE_ITEM, target=escape_item, detail=detail)
                        else:
                            # Fallback: walk to exit portal if item missing
                            exit_portal = Position(32669, 32802, map_id=1)
                            dist_to_exit = max(abs(snapshot.pos.x - exit_portal.x), abs(snapshot.pos.y - exit_portal.y))
                            if dist_to_exit == 0:
                                return BotState.RETURNING_TO_TOWN, BotAction(BotActionType.TRANSITION_MAP, target=exit_portal, detail="Exiting Dungeon to Surface")
                            return BotState.RETURNING_TO_TOWN, BotAction(BotActionType.MOVE_STEP, target=exit_portal, detail=detail + " (Escape item missing, walking to exit)")
                    else:
                        exit_portal = Position(32669, 32802, map_id=1)
                        dist_to_exit = max(abs(snapshot.pos.x - exit_portal.x), abs(snapshot.pos.y - exit_portal.y))
                        if dist_to_exit == 0:
                            return BotState.RETURNING_TO_TOWN, BotAction(BotActionType.TRANSITION_MAP, target=exit_portal, detail="Exiting Dungeon to Surface")
                        return BotState.RETURNING_TO_TOWN, BotAction(BotActionType.MOVE_STEP, target=exit_portal, detail=detail + " (Walking to exit)")

        # 6. LOOT Priority: if there are drops directly on current tile or immediately adjacent
        loot_target = self.select_loot_target(snapshot)
        if loot_target:
            dist = max(abs(loot_target.pos.x - snapshot.pos.x), abs(loot_target.pos.y - snapshot.pos.y))
            if dist == 0:
                return BotState.LOOT, BotAction(BotActionType.LOOT, target=loot_target, detail=f"Looting {loot_target.item.name}")
            elif dist <= 3 and snapshot.combat_state != "IN_COMBAT":
                # Move to drop position to loot
                return BotState.LOOT, BotAction(BotActionType.MOVE_STEP, target=loot_target.pos, detail=f"Moving to loot {loot_target.item.name}")

        # 7. IN_COMBAT / Target active
        target = snapshot.target_monster
        if target is not None and not target.is_dead and target.hp > 0:
            if snapshot.is_target_in_melee:
                # Weave offensive magic (Energy Bolt) if MP is plentiful
                if snapshot.mp >= 10:
                    return BotState.ATTACK, BotAction(BotActionType.CAST_SKILL, target=target, detail="Casting Energy Bolt", skill_id=4)
                return BotState.ATTACK, BotAction(BotActionType.ATTACK, target=target, detail=f"Attacking {target.name}")
            else:
                return BotState.MOVE_TO_TARGET, BotAction(BotActionType.MOVE_STEP, target=target.pos, detail=f"Approaching {target.name}")

        # 8. SEARCH_TARGET: find new reachable target
        new_target = self.select_target(snapshot, map_grid=map_grid)
        if new_target:
            dist = max(abs(new_target.pos.x - snapshot.pos.x), abs(new_target.pos.y - snapshot.pos.y))
            if dist <= 1:
                if snapshot.mp >= 10:
                    return BotState.ATTACK, BotAction(BotActionType.CAST_SKILL, target=new_target, detail="Casting Energy Bolt", skill_id=4)
                return BotState.ATTACK, BotAction(BotActionType.ATTACK, target=new_target, detail=f"Engaging {new_target.name}")
            else:
                return BotState.MOVE_TO_TARGET, BotAction(BotActionType.MOVE_STEP, target=new_target.pos, detail=f"Approaching {new_target.name}")

        # 9. PERSISTENT HUNTING: No targets in sight -> Roam / Patrol, NEVER TERMINATE!
        return BotState.SEARCH_TARGET, BotAction(BotActionType.ROAM, detail="Scanning & roaming for targets")


