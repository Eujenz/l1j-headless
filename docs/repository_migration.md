# Repository Migration Provenance

## Metadata

- **Source Repository**: [`Eujenz/182c`](https://github.com/Eujenz/182c)
- **Source Commit**: `7eeacbc53222883444c63eb26981cefae702ee74` (`7eeacbc`)
- **Source Commit Message**: `checkpoint: scenario-003 differential conformance certified`
- **Target Repository**: [`Eujenz/l1j-headless`](https://github.com/Eujenz/l1j-headless)
- **Extraction Type**: Native Runtime / Compatibility Artifact Clean Extraction
- **Legacy Source Retention**: Complete legacy history and reference implementation retained in `Eujenz/182c`
- **Migration Date**: 2026-09-30

---

## Purpose & Architectural Rationale

This migration establishes a formal boundary between legacy evidence and modern native software:

1. **Evidence vs. Product**:
   - `Eujenz/182c` serves as the historical **Evidence & Legacy Reference** repository, containing legacy Java source code, MySQL schemas, database dumps, game client files, and archaeological instrumentation.
   - `Eujenz/l1j-headless` is the active **Native Runtime & Compatibility Project**, housing the headless world engine, compatibility contracts, replay runners, and verification artifacts.

2. **Decoupling**:
   - Keeping the native runtime in a clean repository ensures that the runtime never inadvertently depends on the legacy Java classpath, local filesystem paths, or legacy database connections.
   - It keeps large legacy client, binary, map, database, and server artifacts outside the active Native Runtime repository, ensuring fast CI and lightweight deployment.

---

## Assets Migrated

The following components were extracted from `Eujenz/182c@7eeacbc`:

1. **Native Engine (`native_engine/`)**:
   - `__init__.py`: Package initialization.
   - `codec.py`: Wire encoder for Lineage 182 packet structures (conformance testing primitive).
   - `combat.py`: HitFigure and DmgSystem combat calculators.
   - `events.py`: Domain event definitions.
   - `map.py`: 2D tile grid with `IsThroughObject` bitmask evaluation.
   - `model.py`: Domain entity models (Actor, Monster, Item, Position).
   - `movement.py`: 8-direction movement arbiter and collision checking.
   - `navigation.py`: Local A* pathfinding and `CmdMove` generation.
   - `rng.py`: 48-bit LCG random number generator.
   - `simulator.py`: Scenario 001 combat simulation harness.
   - `transition.py`: Cross-map portal transition resolver.
   - `world.py`: World container managing multi-map spatial registries.

2. **Specifications & Documentation (`docs/`)**:
   - `scenario_001_specification.md`
   - `scenario_002_specification.md`
   - `scenario_003_specification.md`
   - `architecture.md`
   - `methodology.md`
   - `repository_migration.md`

3. **Compatibility Contracts**:
   - `scenario_001_contract.json`
   - `scenario_002_contract.json`
   - `scenario_003_contract.json`
   - `build_contract.py`
   - `build_scenario_002_contract.py`
   - `build_scenario_003_contract.py`

4. **Replay & Conformance Verification**:
   - `scenario_001_replay.py`
   - `scenario_002_replay.py`
   - `scenario_003_replay.py`
   - `scenario_003_differential.py`
   - `harness_scenario_001.py`
   - `tests/test_scenarios.py`

5. **Oracle & Native Traces (Certification Evidence)**:
   - `oracle_trace_scenario_001.jsonl`: Certified legacy oracle trace for Scenario 001.
   - `oracle_trace_scenario_002.jsonl`: Certified legacy oracle trace for Scenario 002.
   - `oracle_trace_scenario_003.jsonl`: Certified legacy oracle trace for Scenario 003.
   - `native_trace.jsonl`: Emitted native execution trace for Scenario 001.
   - `native_trace_002.jsonl`: Emitted native execution trace for Scenario 002.
   - `native_trace_003.jsonl`: Emitted native execution trace for Scenario 003.
   *(Note: Redundant duplicate files `oracle_trace_scenario_001_runA.jsonl` and `runB.jsonl` were audited, verified byte-identical to `oracle_trace_scenario_001.jsonl`, and removed during post-migration baseline cleanup.)*

---

## Assets Intentionally Excluded

The following legacy assets remain exclusively in `Eujenz/182c` and were NOT copied:
- `src/**` (Legacy Java source files, including instrumented drivers `HeadlessScenario001/002/003.java`)
- `db/**` (MySQL database schemas, table definitions, and data dumps)
- `maps/**` (Legacy map binary archives)
- `data/**` (Legacy game data files)
- `client/**` (Legacy game client files)
- `lib/**` (Java third-party dependencies)
- `bin/**` (Compiled Java `.class` files)
- `config/**` (Legacy server configuration `.properties`)
- `log/**` (Historical server execution logs)
- `l1jserver.exe`, `start.bat` (Legacy server launchers)
