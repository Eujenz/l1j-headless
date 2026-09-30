"""
native_engine/codec.py - 182 Profile Packet Encoder
Translates domain events into the exact binary wire layout expected by Lineage 182 clients,
including the mandatory 8-byte boundary padding (S_BasePacket.getBytes() gab rule).
"""
import struct

def pad8(data: bytes) -> bytes:
    """Lineage 182 S_BasePacket gab alignment rule (size % 8 == 0)"""
    gab = len(data) % 8
    if gab != 0:
        data += b"\x00" * (8 - gab)
    return data

class Profile182Encoder:
    @staticmethod
    def encode_hp_update(current_hp: int, max_hp: int) -> str:
        # Opcode: 0x0D (13)
        # short current_hp, short max_hp
        raw = struct.pack("<BHH", 13, current_hp, max_hp)
        return pad8(raw).hex()

    @staticmethod
    def encode_attack(attacker_id: int, target_id: int, damage: int, heading: int = 1) -> str:
        # Opcode: 0x23 (35)
        # byte action (1), int attacker, int target, byte damage, byte heading, int 0, byte 0
        raw = struct.pack("<BBIIBBIB", 35, 1, attacker_id, target_id, damage, heading, 0, 0)
        return pad8(raw).hex()

    @staticmethod
    def encode_lawful(actor_id: int, lawful: int) -> str:
        # Opcode: 0x59 (89)
        # int actor_id (4 bytes), int lawful (4 bytes) -> 9 bytes raw, 16 bytes padded
        raw = struct.pack("<BII", 89, actor_id, lawful)
        return pad8(raw).hex()

    @staticmethod
    def encode_action(target_id: int, action: int) -> str:
        # Opcode: 0x20 (32)
        # int target_id, byte action
        raw = struct.pack("<BIB", 32, target_id, action)
        return pad8(raw).hex()
