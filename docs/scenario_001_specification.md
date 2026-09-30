# Scenario 001: Combat & Death Lifecycle Specification

## 1. Scope & Objective
Establish the vertical slice for deterministic combat, damage evaluation, entity death, lawful point mutation, drop item transfer, inventory management, and packet wire serialization in the Headless L1 World:
- Canonical entity interaction: Knight (PC) vs Goblin (Monster).
- Strict separation between core domain logic and presentation/serialization layers.
- Multi-layer conformance verification: RNG sequence, state mutations, domain events, and binary packet layout.

## 2. Behavioral Rules & Formulae
- **Hit Determination**:
  - Legacy `Character.HitFigure` dual-dice 0..29 competition rule.
  - Attacker hit score vs Target evade score with STR/DEX and level modifiers.
- **Damage Evaluation**:
  - Legacy `Character.DmgSystem` melee physical damage formula.
  - Weapon damage dice roll scaled by blessed weapon status, STR bonuses, and weapon enchantment.
- **HP Mutation & Death**:
  - Target HP decreased atomically by damage.
  - On HP <= 0, trigger death transition: status mutated to dead, death action dispatched.
- **Reward & Looting**:
  - Monster EXP awarded to killer.
  - Lawful point update applied according to alignment formulas.
  - Monster inventory drop items transferred to killer's inventory or ground state.
- **Packet Serialization**:
  - Wire format conformance: Lineage 182 packet opcode and binary payload generation (`S_AttackPacket`, `S_HPUpdate`, `S_Lawful`, `S_DoActionGFX`, `S_AddItem`).

## 3. Four-Layer Conformance Audit
1. **RNG Sequence**: Bit-exact replication of Java LCG48 random generator (`Util.rand`).
2. **L1 Domain State**: Exact parity on HP, damage, EXP, alignment, and inventory transfers.
3. **L2 Domain Events**: Strict lifecycle ordering of semantic events (`AttackExecuted`, `DamageApplied`, `MonsterDied`, `DropTransferred`).
4. **L3 Wire Conformance**: Exact hex payload match against legacy reference server packet output.
