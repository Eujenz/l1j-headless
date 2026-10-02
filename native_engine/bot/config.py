"""
native_engine/bot/config.py - Player-Configurable Autonomous Policy Schema

Architecture Note:
  STRICT SEPARATION OF CONCERNS:
  - World Rules (L1J 1.82 Legacy Server): Potion heal formulas, cooldown intervals,
    teleport destination tables, NPC shop catalogs and pricing.
  - User Config (Autonomous Policy): Drink thresholds, emergency survival triggers,
    town return conditions, target inventory quantities, hunting destination.
  - Bot Policy Engine: Evaluates User Config against current Perception Snapshot
    to issue deterministic ActionIntents to the Controller.

Reference:
  - L1J-3.8-launcher (aux_mod/runtime/types.rs, drink.rs, profile.rs)
"""
from dataclasses import dataclass, field, asdict
from enum import Enum
import json
from typing import Dict, List, Optional, Any, Union


class PotionThresholdMode(str, Enum):
    HP_PERCENT = "HP_PERCENT"
    ABSOLUTE_HP = "ABSOLUTE_HP"


@dataclass
class PotionRule:
    """
    Individual potion drinking rule evaluated in priority order.
    Higher priority value is evaluated first.
    """
    enabled: bool = True
    threshold_mode: PotionThresholdMode = PotionThresholdMode.HP_PERCENT
    threshold: float = 30.0  # 30% or 30 HP depending on threshold_mode
    item: str = "Red Potion"
    item_id: int = 104
    priority: int = 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "threshold_mode": self.threshold_mode.value if isinstance(self.threshold_mode, PotionThresholdMode) else self.threshold_mode,
            "threshold": self.threshold,
            "item": self.item,
            "item_id": self.item_id,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PotionRule":
        mode = data.get("threshold_mode", "HP_PERCENT")
        if isinstance(mode, str):
            mode = PotionThresholdMode(mode)
        return cls(
            enabled=data.get("enabled", True),
            threshold_mode=mode,
            threshold=float(data.get("threshold", 30.0)),
            item=str(data.get("item", "Red Potion")),
            item_id=int(data.get("item_id", 104)),
            priority=int(data.get("priority", 100)),
        )


class EmergencyConditionType(str, Enum):
    HP_PERCENT = "HP_PERCENT"
    HP_ABSOLUTE = "HP_ABSOLUTE"
    MP_PERCENT = "MP_PERCENT"


class EmergencyOperator(str, Enum):
    LE = "LE"  # <=
    LT = "LT"  # <


@dataclass
class EmergencyCondition:
    type: EmergencyConditionType = EmergencyConditionType.HP_PERCENT
    operator: EmergencyOperator = EmergencyOperator.LE
    value: float = 15.0

    def evaluate(self, hp: int, max_hp: int, mp: int, max_mp: int) -> bool:
        if self.type == EmergencyConditionType.HP_PERCENT:
            current_pct = (hp / max_hp) * 100.0 if max_hp > 0 else 0.0
            return current_pct <= self.value if self.operator == EmergencyOperator.LE else current_pct < self.value
        elif self.type == EmergencyConditionType.HP_ABSOLUTE:
            return hp <= self.value if self.operator == EmergencyOperator.LE else hp < self.value
        elif self.type == EmergencyConditionType.MP_PERCENT:
            current_pct = (mp / max_mp) * 100.0 if max_mp > 0 else 0.0
            return current_pct <= self.value if self.operator == EmergencyOperator.LE else current_pct < self.value
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value if isinstance(self.type, EmergencyConditionType) else self.type,
            "operator": self.operator.value if isinstance(self.operator, EmergencyOperator) else self.operator,
            "value": self.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EmergencyCondition":
        ctype = data.get("type", "HP_PERCENT")
        if isinstance(ctype, str):
            ctype = EmergencyConditionType(ctype)
        cop = data.get("operator", "LE")
        if isinstance(cop, str):
            cop = EmergencyOperator(cop)
        return cls(
            type=ctype,
            operator=cop,
            value=float(data.get("value", 15.0)),
        )


@dataclass
class EmergencyAction:
    type: str = "USE_ITEM"  # USE_ITEM
    item: str = "Escape Scroll"
    item_id: int = 139

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "item": self.item,
            "item_id": self.item_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EmergencyAction":
        return cls(
            type=str(data.get("type", "USE_ITEM")),
            item=str(data.get("item", "Escape Scroll")),
            item_id=int(data.get("item_id", 139)),
        )


@dataclass
class EmergencyActionRule:
    """
    Emergency survival rule (e.g. HP <= 10% -> Use Escape Scroll).
    """
    enabled: bool = True
    condition: EmergencyCondition = field(default_factory=EmergencyCondition)
    action: EmergencyAction = field(default_factory=EmergencyAction)
    priority: int = 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "condition": self.condition.to_dict(),
            "action": self.action.to_dict(),
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EmergencyActionRule":
        cond = EmergencyCondition.from_dict(data.get("condition", {}))
        act = EmergencyAction.from_dict(data.get("action", {}))
        return cls(
            enabled=data.get("enabled", True),
            condition=cond,
            action=act,
            priority=int(data.get("priority", 100)),
        )


class ReturnTriggerType(str, Enum):
    LOW_POTION = "LOW_POTION"
    LOW_RESOURCE = "LOW_RESOURCE"
    LOW_HP = "LOW_HP"
    LOW_MP = "LOW_MP"
    BAG_WEIGHT_EXCEEDED = "BAG_WEIGHT_EXCEEDED"
    EMERGENCY = "EMERGENCY"
    DEATH_RECOVERY = "DEATH_RECOVERY"


class ReturnMethod(str, Enum):
    USE_ESCAPE_ITEM = "USE_ESCAPE_ITEM"
    WALK_TO_TOWN = "WALK_TO_TOWN"


@dataclass
class ReturnTrigger:
    type: ReturnTriggerType = ReturnTriggerType.LOW_POTION
    item: str = "Red Potion"
    item_id: int = 104
    threshold: int = 5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value if isinstance(self.type, ReturnTriggerType) else self.type,
            "item": self.item,
            "item_id": self.item_id,
            "threshold": self.threshold,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReturnTrigger":
        ttype = data.get("type", "LOW_POTION")
        if isinstance(ttype, str):
            ttype = ReturnTriggerType(ttype)
        return cls(
            type=ttype,
            item=str(data.get("item", "Red Potion")),
            item_id=int(data.get("item_id", 104)),
            threshold=int(data.get("threshold", 5)),
        )


@dataclass
class ReturnToTownPolicy:
    """
    Policy governing when and how the player returns to town for resupply.
    """
    enabled: bool = True
    return_method: ReturnMethod = ReturnMethod.USE_ESCAPE_ITEM
    escape_item: str = "Escape Scroll"
    escape_item_id: int = 139
    triggers: List[ReturnTrigger] = field(default_factory=lambda: [
        ReturnTrigger(type=ReturnTriggerType.LOW_POTION, item="Red Potion", item_id=104, threshold=5)
    ])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "return_method": self.return_method.value if isinstance(self.return_method, ReturnMethod) else self.return_method,
            "escape_item": self.escape_item,
            "escape_item_id": self.escape_item_id,
            "triggers": [t.to_dict() for t in self.triggers],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReturnToTownPolicy":
        method = data.get("return_method", "USE_ESCAPE_ITEM")
        if isinstance(method, str):
            method = ReturnMethod(method)
        raw_triggers = data.get("triggers", [])
        triggers = [ReturnTrigger.from_dict(t) for t in raw_triggers] if raw_triggers else [
            ReturnTrigger(type=ReturnTriggerType.LOW_POTION, item="Red Potion", item_id=104, threshold=5)
        ]
        return cls(
            enabled=data.get("enabled", True),
            return_method=method,
            escape_item=str(data.get("escape_item", "Escape Scroll")),
            escape_item_id=int(data.get("escape_item_id", 139)),
            triggers=triggers,
        )


@dataclass
class ResupplyItem:
    """
    Item to purchase in town up to target_quantity.
    Semantics: purchase = max(0, target_quantity - current_inventory_count).
    """
    enabled: bool = True
    item: str = "Red Potion"
    item_id: int = 104
    target_quantity: int = 50
    priority: int = 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "item": self.item,
            "item_id": self.item_id,
            "target_quantity": self.target_quantity,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResupplyItem":
        return cls(
            enabled=data.get("enabled", True),
            item=str(data.get("item", "Red Potion")),
            item_id=int(data.get("item_id", 104)),
            target_quantity=int(data.get("target_quantity", 50)),
            priority=int(data.get("priority", 100)),
        )


@dataclass
class ResupplyProfile:
    """
    Full town resupply configuration.
    """
    enabled: bool = True
    shop_npc_id: int = 3  # Pandora
    items: List[ResupplyItem] = field(default_factory=lambda: [
        ResupplyItem(enabled=True, item="Red Potion", item_id=104, target_quantity=50, priority=100),
        ResupplyItem(enabled=True, item="Green Potion", item_id=108, target_quantity=10, priority=80),
        ResupplyItem(enabled=True, item="Escape Scroll", item_id=139, target_quantity=5, priority=60),
    ])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "shop_npc_id": self.shop_npc_id,
            "items": [i.to_dict() for i in self.items],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResupplyProfile":
        raw_items = data.get("items", [])
        items = [ResupplyItem.from_dict(i) for i in raw_items] if raw_items else [
            ResupplyItem(enabled=True, item="Red Potion", item_id=104, target_quantity=50, priority=100),
            ResupplyItem(enabled=True, item="Green Potion", item_id=108, target_quantity=10, priority=80),
            ResupplyItem(enabled=True, item="Escape Scroll", item_id=139, target_quantity=5, priority=60),
        ]
        return cls(
            enabled=data.get("enabled", True),
            shop_npc_id=int(data.get("shop_npc_id", 3)),
            items=items,
        )


@dataclass
class HuntingDestination:
    """
    Destination where bot hunts monsters.
    """
    name: str = "ti_dungeon_1f"
    map_id: int = 1
    target_x: int = 32671
    target_y: int = 32804
    portal_map_id: int = 0
    portal_x: int = 32477
    portal_y: int = 32851

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "map_id": self.map_id,
            "target_x": self.target_x,
            "target_y": self.target_y,
            "portal_map_id": self.portal_map_id,
            "portal_x": self.portal_x,
            "portal_y": self.portal_y,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HuntingDestination":
        return cls(
            name=str(data.get("name", "ti_dungeon_1f")),
            map_id=int(data.get("map_id", 1)),
            target_x=int(data.get("target_x", 32671)),
            target_y=int(data.get("target_y", 32804)),
            portal_map_id=int(data.get("portal_map_id", 0)),
            portal_x=int(data.get("portal_x", 32477)),
            portal_y=int(data.get("portal_y", 32851)),
        )


@dataclass
class HuntingPolicy:
    destination: HuntingDestination = field(default_factory=HuntingDestination)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "destination": self.destination.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HuntingPolicy":
        dest = HuntingDestination.from_dict(data.get("destination", {}))
        return cls(destination=dest)


@dataclass
class CharacterConfig:
    name: str = "Arthur"
    class_type: int = 1  # 1 = Knight
    level: int = 1
    str: int = 16
    dex: int = 12
    con: int = 14
    int: int = 8
    wis: int = 9
    cha: int = 12
    starting_weapon_id: int = 2
    starting_adena: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "class_type": self.class_type,
            "level": self.level,
            "str": self.str,
            "dex": self.dex,
            "con": self.con,
            "int": self.int,
            "wis": self.wis,
            "cha": self.cha,
            "starting_weapon_id": self.starting_weapon_id,
            "starting_adena": self.starting_adena,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CharacterConfig":
        return cls(
            name=str(data.get("name", "Arthur")),
            class_type=int(data.get("class_type", 1)),
            level=int(data.get("level", 1)),
            str=int(data.get("str", 16)),
            dex=int(data.get("dex", 12)),
            con=int(data.get("con", 14)),
            int=int(data.get("int", 8)),
            wis=int(data.get("wis", 9)),
            cha=int(data.get("cha", 12)),
            starting_weapon_id=int(data.get("starting_weapon_id", 2)),
            starting_adena=int(data.get("starting_adena", 0)),
        )


@dataclass
class TargetingConfig:
    preferred_targets: List[str] = field(default_factory=list)
    avoid_targets: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "preferred_targets": list(self.preferred_targets),
            "avoid_targets": list(self.avoid_targets),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TargetingConfig":
        return cls(
            preferred_targets=list(data.get("preferred_targets", [])),
            avoid_targets=list(data.get("avoid_targets", [])),
        )


@dataclass
class MovementConfig:
    patrol_radius: int = 20
    search_behavior: str = "PATROL_CENTER"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "patrol_radius": self.patrol_radius,
            "search_behavior": self.search_behavior,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MovementConfig":
        return cls(
            patrol_radius=int(data.get("patrol_radius", 20)),
            search_behavior=str(data.get("search_behavior", "PATROL_CENTER")),
        )


@dataclass
class LootConfig:
    enabled: bool = True
    pickup_priority: List[str] = field(default_factory=lambda: ["Adena", "Potion", "Scroll", "Equip"])
    ignored_items: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "pickup_priority": list(self.pickup_priority),
            "ignored_items": list(self.ignored_items),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LootConfig":
        return cls(
            enabled=data.get("enabled", True),
            pickup_priority=list(data.get("pickup_priority", ["Adena", "Potion", "Scroll", "Equip"])),
            ignored_items=list(data.get("ignored_items", [])),
        )


@dataclass
class SkillRule:
    enabled: bool = True
    skill: str = "Energy Bolt"
    skill_id: int = 4
    condition_type: str = "MP_PERCENT_ABOVE"
    threshold: float = 30.0
    target: str = "CURRENT_TARGET"
    priority: int = 50

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "skill": self.skill,
            "skill_id": self.skill_id,
            "condition_type": self.condition_type,
            "threshold": self.threshold,
            "target": self.target,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillRule":
        return cls(
            enabled=data.get("enabled", True),
            skill=str(data.get("skill", "Energy Bolt")),
            skill_id=int(data.get("skill_id", 4)),
            condition_type=str(data.get("condition_type", "MP_PERCENT_ABOVE")),
            threshold=float(data.get("threshold", 30.0)),
            target=str(data.get("target", "CURRENT_TARGET")),
            priority=int(data.get("priority", 50)),
        )


@dataclass
class BuffRule:
    enabled: bool = True
    buff_name: str = "Haste"
    item_id: Optional[int] = 108
    skill_id: Optional[int] = None
    priority: int = 40

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "buff_name": self.buff_name,
            "item_id": self.item_id,
            "skill_id": self.skill_id,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BuffRule":
        return cls(
            enabled=data.get("enabled", True),
            buff_name=str(data.get("buff_name", "Haste")),
            item_id=data.get("item_id"),
            skill_id=data.get("skill_id"),
            priority=int(data.get("priority", 40)),
        )


@dataclass
class AutonomousConfig:
    """
    Root user policy configuration.
    Fully serializable to/from JSON.
    """
    version: str = "1.0.0"
    name: str = "default_knight_ti"
    character: CharacterConfig = field(default_factory=CharacterConfig)
    hunting: HuntingPolicy = field(default_factory=HuntingPolicy)
    targeting: TargetingConfig = field(default_factory=TargetingConfig)
    movement: MovementConfig = field(default_factory=MovementConfig)
    loot: LootConfig = field(default_factory=LootConfig)
    potion_rules: List[PotionRule] = field(default_factory=lambda: [
        PotionRule(enabled=True, threshold_mode=PotionThresholdMode.HP_PERCENT, threshold=30.0, item="Red Potion", item_id=104, priority=100),
        PotionRule(enabled=True, threshold_mode=PotionThresholdMode.HP_PERCENT, threshold=15.0, item="Orange Potion", item_id=103, priority=200),
    ])
    skill_rules: List[SkillRule] = field(default_factory=list)
    buff_rules: List[BuffRule] = field(default_factory=list)
    emergency_rules: List[EmergencyActionRule] = field(default_factory=lambda: [
        EmergencyActionRule(
            enabled=True,
            condition=EmergencyCondition(type=EmergencyConditionType.HP_PERCENT, operator=EmergencyOperator.LE, value=10.0),
            action=EmergencyAction(type="USE_ITEM", item="Escape Scroll", item_id=139),
            priority=100
        )
    ])
    return_to_town: ReturnToTownPolicy = field(default_factory=ReturnToTownPolicy)
    resupply: ResupplyProfile = field(default_factory=ResupplyProfile)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "name": self.name,
            "character": self.character.to_dict(),
            "hunting": self.hunting.to_dict(),
            "targeting": self.targeting.to_dict(),
            "movement": self.movement.to_dict(),
            "loot": self.loot.to_dict(),
            "potion_rules": [r.to_dict() for r in self.potion_rules],
            "skill_rules": [r.to_dict() for r in self.skill_rules],
            "buff_rules": [r.to_dict() for r in self.buff_rules],
            "emergency_rules": [r.to_dict() for r in self.emergency_rules],
            "return_to_town": self.return_to_town.to_dict(),
            "resupply": self.resupply.to_dict(),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AutonomousConfig":
        version = str(data.get("version", "1.0.0"))
        name = str(data.get("name", "default_knight_ti"))
        char = CharacterConfig.from_dict(data.get("character", {})) if "character" in data else CharacterConfig()
        hunt = HuntingPolicy.from_dict(data.get("hunting", {})) if "hunting" in data else HuntingPolicy()
        targeting = TargetingConfig.from_dict(data.get("targeting", {})) if "targeting" in data else TargetingConfig()
        movement = MovementConfig.from_dict(data.get("movement", {})) if "movement" in data else MovementConfig()
        loot = LootConfig.from_dict(data.get("loot", {})) if "loot" in data else LootConfig()

        p_rules = [PotionRule.from_dict(r) for r in data.get("potion_rules", [])] if "potion_rules" in data else [
            PotionRule(enabled=True, threshold_mode=PotionThresholdMode.HP_PERCENT, threshold=30.0, item="Red Potion", item_id=104, priority=100),
            PotionRule(enabled=True, threshold_mode=PotionThresholdMode.HP_PERCENT, threshold=15.0, item="Orange Potion", item_id=103, priority=200),
        ]
        s_rules = [SkillRule.from_dict(r) for r in data.get("skill_rules", [])] if "skill_rules" in data else []
        b_rules = [BuffRule.from_dict(r) for r in data.get("buff_rules", [])] if "buff_rules" in data else []
        e_rules = [EmergencyActionRule.from_dict(r) for r in data.get("emergency_rules", [])] if "emergency_rules" in data else [
            EmergencyActionRule(
                enabled=True,
                condition=EmergencyCondition(type=EmergencyConditionType.HP_PERCENT, operator=EmergencyOperator.LE, value=10.0),
                action=EmergencyAction(type="USE_ITEM", item="Escape Scroll", item_id=139),
                priority=100
            )
        ]
        ret = ReturnToTownPolicy.from_dict(data.get("return_to_town", {})) if "return_to_town" in data else ReturnToTownPolicy()
        resup = ResupplyProfile.from_dict(data.get("resupply", {})) if "resupply" in data else ResupplyProfile()

        return cls(
            version=version,
            name=name,
            character=char,
            hunting=hunt,
            targeting=targeting,
            movement=movement,
            loot=loot,
            potion_rules=p_rules,
            skill_rules=s_rules,
            buff_rules=b_rules,
            emergency_rules=e_rules,
            return_to_town=ret,
            resupply=resup,
        )

    @classmethod
    def from_json(cls, json_str: str) -> "AutonomousConfig":
        data = json.loads(json_str)
        return cls.from_dict(data)

    def save_json(self, file_path: str) -> None:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(self.to_json())

    @classmethod
    def load_json(cls, file_path: str) -> "AutonomousConfig":
        with open(file_path, "r", encoding="utf-8") as f:
            return cls.from_json(f.read())

