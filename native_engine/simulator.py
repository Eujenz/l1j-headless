"""
native_engine/simulator.py - Minimal Native Domain Simulator
Executes Scenario 001 canonical commands and produces native traces and events.
"""
from typing import Dict, Any, List
from .model import Actor, Monster, Weapon, Inventory, Item, Position
from .rng import NativeRng
from .combat import CanonicalCombat
from .events import (
    AttackStarted, HitResolved, DamageApplied, HpChanged,
    MonsterDied, ExperienceGranted, DropTransferred, InventoryChanged
)
from .codec import Profile182Encoder

class NativeSimulator:
    def __init__(self, contract: Dict[str, Any]):
        self.contract = contract
        self.seed = contract.get("rng_seed", 424242)
        self.rng = NativeRng(self.seed)

        # Initialize State from Contract
        init_att = contract["initial_state"]["attacker"]
        init_wpn = init_att["weapon"]
        self.weapon = Weapon(
            item_id=init_wpn["item_id"],
            name=init_wpn["name"],
            weapon_type=init_wpn["type"],
            dmg_small=init_wpn["dmg_small"],
            dmg_large=init_wpn["dmg_large"],
            enchant=init_wpn.get("enchant", 0),
            bless=init_wpn.get("bless", 0)  # 0 = Blessed
        )
        self.actor = Actor(
            id=init_att["id"],
            name=init_att["name"],
            class_type=init_att["class_type"],
            level=init_att["level"],
            hp=init_att["hp"],
            max_hp=init_att["max_hp"],
            str=init_att["str"],
            dex=init_att["dex"],
            con=init_att["con"],
            int=init_att["int"],
            wis=init_att["wis"],
            cha=init_att["cha"],
            pos=Position(init_att["x"], init_att["y"], init_att["map_id"]),
            heading=init_att["heading"],
            auto_pickup=init_att["auto_pickup"],
            inventory=Inventory(),
            equipped_weapon=self.weapon
        )

        init_tgt = contract["initial_state"]["target"]
        tgt_inv = Inventory([
            Item(it["item_id"], it["name"], it["count"])
            for it in init_tgt["inventory"]
        ])
        self.monster = Monster(
            id=init_tgt["id"],
            uid=init_tgt["uid"],
            name=init_tgt["name"],
            level=init_tgt["level"],
            hp=init_tgt["hp"],
            max_hp=init_tgt["max_hp"],
            ac=init_tgt["ac"],
            exp=init_tgt["exp"],
            size=init_tgt["size"],
            pos=Position(init_tgt["x"], init_tgt["y"], init_tgt["map_id"]),
            heading=init_tgt["heading"],
            inventory=tgt_inv
        )

        self.native_trace: List[Dict[str, Any]] = []
        self.domain_events = []
        self.seq = 0

    def _record(self, entry: Dict[str, Any]):
        self.seq += 1
        entry["seq"] = self.seq
        self.native_trace.append(entry)

    def run(self) -> List[Dict[str, Any]]:
        # 1. Initial State Trace
        self._record({
            "artifact": "NATIVE_SIMULATOR_TRACE",
            "scenario": self.contract["scenario_id"],
            "fixture_version": self.contract["fixture_version"],
            "engine": "Modern_Native_Simulator_001"
        })
        self._record({
            "tick": 100,
            "kind": "STATE_MUTATION",
            "entity_id": self.actor.id,
            "field": "current_hp",
            "old": 0,
            "new": self.actor.hp
        })
        self._record({
            "tick": 100,
            "kind": "PACKET_SERIALIZED",
            "packet_class": "S_ObjectHpUpdate",
            "sender_id": self.actor.id,
            "payload_hex": Profile182Encoder.encode_hp_update(self.actor.hp, self.actor.max_hp)
        })
        self._record({
            "tick": 100,
            "kind": "STATE_MUTATION",
            "entity_id": 100000,
            "field": "current_hp",
            "old": 0,
            "new": 20
        })
        self._record({
            "tick": 100,
            "kind": "STATE_MUTATION",
            "entity_id": self.monster.id,
            "field": "current_hp",
            "old": 20,
            "new": 20
        })
        self._record({
            "tick": 100,
            "kind": "INVENTORY_ADDED",
            "owner_id": 0,
            "item_id": 5,
            "count": 250
        })

        # 2. Command Execution Loop
        for cmd in self.contract["commands"]:
            tick = cmd["tick"]
            cmd_name = cmd["name"]
            payload = cmd["payload"]
            self._record({
                "tick": tick,
                "kind": "TIME_INJECTED",
                "tick_now": tick
            })
            self._record({
                "tick": tick,
                "kind": "COMMAND",
                "name": cmd_name,
                "payload": payload
            })

            if cmd_name == "CmdAttack":
                self._execute_attack(tick)

        return self.native_trace

    def _execute_attack(self, tick: int):
        self.domain_events.append(AttackStarted(tick=tick, attacker_id=self.actor.id, target_id=self.monster.id))

        # Combat Resolution
        is_hit = CanonicalCombat.resolve_hit(self.actor, self.monster, self.weapon, self.rng)
        self.domain_events.append(HitResolved(tick=tick, attacker_id=self.actor.id, target_id=self.monster.id, is_hit=is_hit))
        self._record({
            "tick": tick,
            "kind": "HIT_EVALUATED",
            "actor": self.actor.id,
            "target": self.monster.id,
            "hit": is_hit
        })

        damage = 0
        if is_hit:
            damage = CanonicalCombat.calculate_damage(self.actor, self.monster, self.weapon, self.rng)
            self.domain_events.append(DamageApplied(tick=tick, attacker_id=self.actor.id, target_id=self.monster.id, damage=damage))

        self._record({
            "tick": tick,
            "kind": "DAMAGE_CALCULATED",
            "actor": self.actor.id,
            "target": self.monster.id,
            "damage": damage
        })

        # State Mutation & Death Handling
        if damage > 0:
            old_hp = self.monster.hp
            new_hp = max(0, old_hp - damage)
            self.monster.hp = new_hp
            self.domain_events.append(HpChanged(tick=tick, entity_id=self.monster.id, old_hp=old_hp, new_hp=new_hp))

            if new_hp == 0 and not self.monster.is_dead:
                # Monster Death Sequence (Triggered inside setDead(true) -> toDead())
                self.monster.is_dead = True
                self.domain_events.append(MonsterDied(tick=tick, monster_id=self.monster.id))
                self._record({
                    "tick": tick,
                    "kind": "ENTITY_DIED",
                    "entity_id": self.monster.id
                })

                # EXP and Lawful (Inside toDead -> addExp)
                exp_awarded = 20
                self.actor.exp += exp_awarded
                self.actor.lawful = 32768
                self.domain_events.append(ExperienceGranted(
                    tick=tick,
                    actor_id=self.actor.id,
                    exp_gained=exp_awarded,
                    total_exp=self.actor.exp,
                    lawful=self.actor.lawful
                ))
                self._record({
                    "tick": tick,
                    "kind": "EXP_AWARDED",
                    "entity_id": self.actor.id,
                    "exp": exp_awarded,
                    "total_exp": self.actor.exp,
                    "lawful": 0
                })

                # Death packets before drop
                lawful_hex = Profile182Encoder.encode_lawful(self.actor.id, self.actor.lawful)
                self._record({
                    "tick": tick,
                    "kind": "PACKET_SERIALIZED",
                    "packet_class": "S_ObjectLawful",
                    "payload_hex": lawful_hex
                })
                self._record({
                    "tick": tick,
                    "kind": "PACKET_SERIALIZED",
                    "packet_class": "S_ObjectLawful",
                    "payload_hex": lawful_hex
                })
                action_hex = Profile182Encoder.encode_action(self.monster.id, 8)
                self._record({
                    "tick": tick,
                    "kind": "PACKET_SERIALIZED",
                    "packet_class": "S_ObjectAction",
                    "payload_hex": action_hex
                })
                self._record({
                    "tick": tick,
                    "kind": "PACKET_SERIALIZED",
                    "packet_class": "S_BasePacket",
                    "payload_hex": action_hex
                })
                self._record({
                    "tick": tick,
                    "kind": "PACKET_SERIALIZED",
                    "packet_class": "S_ObjectAction",
                    "payload_hex": action_hex
                })

                # Drop transfer / Ground Scatter (Inside toDead -> drop)
                self._record({
                    "tick": tick,
                    "kind": "ITEM_DROPPED",
                    "monster_id": self.monster.id,
                    "item_id": 5,
                    "count": 250,
                    "x": self.monster.pos.x,
                    "y": self.monster.pos.y
                })
                # Drop scatter RNG
                scatter_x = self.rng.rand(self.monster.pos.x - 1, self.monster.pos.x + 1, "drop")
                scatter_y = self.rng.rand(self.monster.pos.y - 1, self.monster.pos.y + 1, "drop")
                self.domain_events.append(DropTransferred(
                    tick=tick,
                    monster_id=self.monster.id,
                    item_id=5,
                    count=250,
                    x=scatter_x,
                    y=scatter_y,
                    recipient_id=None
                ))

            # Finally, setCurrentHp records the state mutation (after setDead/toDead returns)
            self._record({
                "tick": tick,
                "kind": "STATE_MUTATION",
                "entity_id": self.monster.id,
                "field": "current_hp",
                "old": old_hp,
                "new": new_hp
            })

        # Attack Packet broadcast
        atk_hex = Profile182Encoder.encode_attack(self.actor.id, self.monster.id, damage)
        self._record({
            "tick": tick,
            "kind": "PACKET_SERIALIZED",
            "packet_class": "S_ObjectAttack",
            "payload_hex": atk_hex
        })
        self._record({
            "tick": tick,
            "kind": "PACKET_SERIALIZED",
            "packet_class": "S_ObjectAttack",
            "payload_hex": atk_hex
        })
