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
class AutonomousConfig:
    """
    Root user policy configuration.
    Fully serializable to/from JSON.
    """
    potion_rules: List[PotionRule] = field(default_factory=lambda: [
        PotionRule(enabled=True, threshold_mode=PotionThresholdMode.HP_PERCENT, threshold=30.0, item="Red Potion", item_id=104, priority=100),
        PotionRule(enabled=True, threshold_mode=PotionThresholdMode.HP_PERCENT, threshold=15.0, item="Orange Potion", item_id=103, priority=200),
    ])
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
    hunting: HuntingPolicy = field(default_factory=HuntingPolicy)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "potion_rules": [r.to_dict() for r in self.potion_rules],
            "emergency_rules": [r.to_dict() for r in self.emergency_rules],
            "return_to_town": self.return_to_town.to_dict(),
            "resupply": self.resupply.to_dict(),
            "hunting": self.hunting.to_dict(),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AutonomousConfig":
        p_rules = [PotionRule.from_dict(r) for r in data.get("potion_rules", [])] if "potion_rules" in data else None
        e_rules = [EmergencyActionRule.from_dict(r) for r in data.get("emergency_rules", [])] if "emergency_rules" in data else None
        ret = ReturnToTownPolicy.from_dict(data.get("return_to_town", {})) if "return_to_town" in data else None
        resup = ResupplyProfile.from_dict(data.get("resupply", {})) if "resupply" in data else None
        hunt = HuntingPolicy.from_dict(data.get("hunting", {})) if "hunting" in data else None

        kwargs = {}
        if p_rules is not None:
            kwargs["potion_rules"] = p_rules
        if e_rules is not None:
            kwargs["emergency_rules"] = e_rules
        if ret is not None:
            kwargs["return_to_town"] = ret
        if resup is not None:
            kwargs["resupply"] = resup
        if hunt is not None:
            kwargs["hunting"] = hunt

        return cls(**kwargs)

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
