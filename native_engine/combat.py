"""
native_engine/combat.py - Canonical Combat Rules
Strictly reimplements 182 HitFigure and DmgSystem behavior without relying on Java class hierarchies.
"""
from .model import Actor, Monster, Weapon
from .rng import NativeRng

class CanonicalCombat:
    @staticmethod
    def resolve_hit(attacker: Actor, target: Monster, weapon: Weapon, rng: NativeRng) -> bool:
        """
        182 Character.HitFigure dual-dice 0..29 competition rule.
        """
        basic_flee = 5
        # Knight level hit bonus: level // 3
        if attacker.class_type == 1:
            basic_flee += attacker.level // 3
        else:
            basic_flee += attacker.level // 5

        # Strength hit bonus
        stat = attacker.str - 10
        # Original stat hit: for STR 16 Knight, sum = 0
        if attacker.class_type == 1:
            extra_str = attacker.str - 16
            if extra_str >= 1:
                stat += 2
            if extra_str >= 3:
                stat += 2

        # Target defense flee
        target_flee = target.ac // 3
        if target.level >= attacker.level + 5:
            target_flee += target.level - attacker.level + 5

        basic_flee += stat
        basic_flee += stat // 3
        basic_flee -= target_flee

        max_flee = 29
        if basic_flee <= max_flee:
            roll_a = rng.rand(0, max_flee, "HitFigure")
            roll_b = rng.rand(basic_flee, max_flee, "HitFigure")
            return roll_a < roll_b
        return True

    @staticmethod
    def calculate_damage(attacker: Actor, target: Monster, weapon: Weapon, rng: NativeRng) -> int:
        """
        182 Character.DmgSystem melee physical damage formula.
        """
        # 1. Person base damage: DmgFigure
        dmg = 0
        if attacker.class_type == 1:
            dmg += rng.rand(0, attacker.level // 10, "DmgFigure")

        # STR bonus
        str_val = attacker.str
        stat = 0
        if str_val <= 8:
            stat = -2
        elif 9 <= str_val <= 10:
            stat = -1
        elif 11 <= str_val <= 12:
            stat = 0
        elif 13 <= str_val <= 14:
            stat = 1
        elif 15 <= str_val <= 16:
            stat = 2
        elif 17 <= str_val <= 18:
            stat = 3
        elif 19 <= str_val <= 20:
            stat = 4
        elif 21 <= str_val <= 22:
            stat = 5
        elif 23 <= str_val <= 26:
            stat = 6
        elif 27 <= str_val <= 28:
            stat = 7
        elif 29 <= str_val <= 30:
            stat = 8
        elif str_val >= 31:
            stat = 9
        if str_val > 31:
            stat += str_val - 31

        if stat < 0:
            dmg += rng.rand(stat, 0, "dmgFigureCalcStr")
        else:
            dmg += rng.rand(0, stat, "dmgFigureCalcStr")

        # Original stat damage: Knight STR 16 base = 0
        if attacker.class_type == 1 and (attacker.str - 16) >= 2:
            dmg += 2

        # 2. Weapon damage: DmgWeaponFigure
        is_small = (target.size.lower() == "small")
        base_weapon_max = weapon.dmg_small if is_small else weapon.dmg_large
        d = base_weapon_max + weapon.enchant
        d_roll = rng.rand(0, d, "DmgWeaponFigure")

        # 3. Blessed weapon bonus (bless == 0 in 182 is Blessed)
        bless_check = rng.rand(0, 100, "DmgWeaponFigure")
        bless_extra = 0
        if weapon.bless == 0 and bless_check <= 10:
            bless_extra = rng.rand(0, 2, "DmgWeaponFigure")

        total = dmg + d_roll + bless_extra
        return total
