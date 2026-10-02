"""
native_engine/skill.py - L1J 1.82 Skill Engine & Mechanics

LEGACY_OBSERVED:
  - Source: skill_list.sql, Magic.java, EnergyBolt.java, Heal.java, Haste.java
  - Cast Action Intervals:
      Directional (Action 18): 880ms
      Non-directional (Action 19): 800ms
  - Damage & Effect Timing: IMMEDIATE (T = 0)
"""
from dataclasses import dataclass
from typing import Optional, Tuple, Any
from .model import Actor, Monster
from .status import StatusManager, StatusType


@dataclass
class SkillDefinition:
    skill_id: int
    name: str
    mp_consume: int
    hp_consume: int
    action_id: int             # 18 = Directional, 19 = Non-directional
    action_interval_ms: int    # 880ms or 800ms
    reuse_delay_ms: int        # Independent delay from skill_list.sql
    skill_type: str            # 'attack', 'buff', 'none'
    min_dmg: int
    max_dmg: int
    cast_gfx: int
    duration_s: int = 0


CANONICAL_SKILLS = {
    # 4: 光箭 (Energy Bolt)
    4: SkillDefinition(
        skill_id=4,
        name="Energy Bolt",
        mp_consume=3,
        hp_consume=0,
        action_id=18,
        action_interval_ms=880,
        reuse_delay_ms=0,
        skill_type="attack",
        min_dmg=1,
        max_dmg=2,
        cast_gfx=167,
    ),
    # 1: 初級治癒術 (Lesser Heal)
    1: SkillDefinition(
        skill_id=1,
        name="Lesser Heal",
        mp_consume=4,
        hp_consume=0,
        action_id=19,
        action_interval_ms=800,
        reuse_delay_ms=0,
        skill_type="buff",
        min_dmg=4,
        max_dmg=14,
        cast_gfx=744,
    ),
    # 28: 加速術 (Haste)
    28: SkillDefinition(
        skill_id=28,
        name="Haste",
        mp_consume=25,
        hp_consume=20,
        action_id=19,
        action_interval_ms=800,
        reuse_delay_ms=0,
        skill_type="buff",
        min_dmg=0,
        max_dmg=0,
        cast_gfx=755,
        duration_s=1200,
    ),
}


@dataclass
class SkillResult:
    success: bool
    damage: int = 0
    heal: int = 0
    cast_interval_ms: int = 800
    message: str = "OK"


class SkillEngine:
    """
    Executes canonical L1J 1.82 spell casts.
    """

    def __init__(self, rng: Optional[Any] = None):
        self.rng = rng

    @staticmethod
    def can_cast(caster: Actor, skill_id: int) -> Tuple[bool, str]:
        skill = CANONICAL_SKILLS.get(skill_id)
        if not skill:
            return False, "UNKNOWN_SKILL"
        if caster.mp < skill.mp_consume:
            return False, "INSUFFICIENT_MP"
        if caster.hp <= skill.hp_consume:
            return False, "INSUFFICIENT_HP"
        return True, "OK"

    def cast_energy_bolt(
        self,
        caster: Actor,
        target: Monster,
        rng: Optional[Any] = None,
    ) -> SkillResult:
        """
        Cast Energy Bolt (Skill 4).
        Returns: SkillResult(success, damage, heal, cast_interval_ms, message)
        """
        active_rng = rng or self.rng
        can, reason = self.can_cast(caster, 4)
        if not can:
            return SkillResult(success=False, cast_interval_ms=200, message=reason)

        skill = CANONICAL_SKILLS[4]
        caster.mp -= skill.mp_consume
        if skill.hp_consume > 0:
            caster.hp -= skill.hp_consume

        # Magic.java:164-176:
        # dmg = (rand(mindmg, sp) * maxdmg) + IntDmg; result = dmg / 2
        sp = max(1, getattr(caster, "int", 10) - 10)
        roll = active_rng.rand(skill.min_dmg, sp, "EnergyBoltRoll") if active_rng else skill.min_dmg
        dmg_raw = roll * skill.max_dmg
        dmg = max(1, int(dmg_raw / 2.0))

        # Immediate HP deduction
        old_hp = target.hp
        target.hp = max(0, old_hp - dmg)

        return SkillResult(success=True, damage=dmg, cast_interval_ms=skill.action_interval_ms, message="OK")

    def cast_heal(
        self,
        caster: Actor,
        target: Any,
        rng: Optional[Any] = None,
    ) -> SkillResult:
        """
        Cast Lesser Heal (Skill 1).
        Returns: SkillResult(success, damage, heal, cast_interval_ms, message)
        """
        active_rng = rng or self.rng
        can, reason = self.can_cast(caster, 1)
        if not can:
            return SkillResult(success=False, cast_interval_ms=200, message=reason)

        skill = CANONICAL_SKILLS[1]
        caster.mp -= skill.mp_consume
        if skill.hp_consume > 0:
            caster.hp -= skill.hp_consume

        heal_amount = active_rng.rand(skill.min_dmg, skill.max_dmg, "HealRoll") if active_rng else skill.min_dmg
        target.hp = min(target.max_hp, target.hp + heal_amount)

        return SkillResult(success=True, heal=heal_amount, damage=heal_amount, cast_interval_ms=skill.action_interval_ms, message="OK")

    def cast_haste(
        self,
        caster: Actor,
        status_mgr: StatusManager,
        target: Optional[Any] = None,
        log_callback: Optional[Any] = None,
    ) -> SkillResult:
        """
        Cast Haste (Skill 28).
        Returns: SkillResult(success, cast_interval_ms, message)
        """
        can, reason = self.can_cast(caster, 28)
        if not can:
            return SkillResult(success=False, cast_interval_ms=200, message=reason)

        skill = CANONICAL_SKILLS[28]
        caster.mp -= skill.mp_consume
        caster.hp -= skill.hp_consume

        target_actor = target or caster
        # Apply Haste status for duration_s * 1000 ms
        status_mgr.apply_status(
            target_actor,
            StatusType.HASTE,
            duration_ms=skill.duration_s * 1000,
            log_callback=log_callback,
        )

        return SkillResult(success=True, cast_interval_ms=skill.action_interval_ms, message="OK")
