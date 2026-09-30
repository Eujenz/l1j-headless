# Scenario 004: Canonical Real Map Import Specification

## 1. Objective
Establish the definitive vertical slice for importing real Lineage 1.82 legacy map binaries into a decoupled, canonical map representation, enabling the existing Native Movement and Collision engines (`WorldMapGrid`, `MovementEngine`, `AStarPlanner`) to operate on authentic world terrain without exposing legacy binary formats or coupling to legacy Java infrastructure.

---

## 2. Scope & Target Selection
- **Target Map**: **Map 0** (Talking Island Surface)
  - Continuity: Serves as the origin map for Scenario 003's certified cross-map portal transition (`portal_ti_to_tid1`).
  - Spatial Coverage: 512 x 512 grid (262,144 discrete world coordinates).
  - Bounding Box: `locX1 = 32256`, `locX2 = 32767`, `locY1 = 32768`, `locY2 = 33279`.
- **Primary Deliverables**:
  - Offline Map Ingestion Pipeline: `tools/import_real_map.py`
  - Canonical Map Model: `CanonicalMapDefinition`
  - Conformance Verification: `scenario_004_differential.py` comparing Legacy Java `WorldMap` oracle against Native canonical geometry.

---

## 3. Legacy Map Loader Archaeology (`WorldMap.java`)
Source Reference: `Eujenz/182c:src/net/world/WorldMap.java` (lines 39-63, 149-248).

### 3.1 Loader Lifecycle
1. Server initialization checks directory `maps/Cache`.
2. Metadata is read line-by-line from `maps/maps.csv`.
3. If cache files exist, `readCache` reads `maps/Cache/{readID}.data` directly into `byte[] data` using `BufferedInputStream.read(data)`.
4. If cache does not exist, `readText` parses CSV text from `maps/Text/{readID}.txt` and serializes cache files via `writeCache`.

### 3.2 The Historic Two-Byte Truncation Anomaly
In `WorldMap.java:readText()`:
```java
int TotalSize = -1;
...
while ((line = lnr.readLine()) != null) {
    for (int i = 0; i < size; i++) {
        temp[++TotalSize] = (byte)t;
    }
}
byte[] MAP = new byte[TotalSize - 1]; // Anomaly: Allocates (TotalSize - 1) instead of (TotalSize + 1)
```
- For a map of dimensions `W * H`, `TotalSize` reaches `(W * H) - 1`.
- The allocation `new byte[TotalSize - 1]` allocates exactly `(W * H) - 2` bytes.
- This results in every `.data` file in `maps/Cache/` being exactly `W * H - 2` bytes (e.g. Map 0 is `262,142` bytes instead of `262,144` bytes).
- At runtime, `WorldMap.get_map(x, y, map)` accessing coordinates whose linear index falls in `[W*H-2, W*H-1]` throws `ArrayIndexOutOfBoundsException`, which is caught by `catch (Exception e) {}` returning `0`.
- **Archaeological Status**: `LEGACY_OBSERVED`. The Native decoder handles this by padding missing trailing bytes with `0x00`, matching legacy runtime behavior bit-for-bit.

---

## 4. `maps.csv` Semantics
Source Reference: `Eujenz/182c:maps/maps.csv` (SHA-256: `c44417c44c624f85434ea33b10a95934af06047a26310d39b9ff5b4f68c18298`).
Format: `map_id,locX1,locX2,locY1,locY2,size`

For Map 0:
`0,32256,32767,32768,33279,512`
- `map_id`: `0`
- `locX1`: `32256` (inclusive Western boundary)
- `locX2`: `32767` (inclusive Eastern boundary)
- `locY1`: `32768` (inclusive Northern boundary)
- `locY2`: `33279` (inclusive Southern boundary)
- `size`: `512` (row stride / width)

---

## 5. Binary Format
- **Structure**: Uncompressed, unpadded raw byte grid.
- **Header**: None (no magic bytes, no version header, no embedded dimensions).
- **Compression**: None.
- **Dimensions**:
  - `width = locX2 - locX1 + 1 = 512`
  - `height = locY2 - locY1 + 1 = 512`
  - `total_cells = width * height = 262,144`
- **File Length**: `262,142` bytes (SHA-256: `9ff8acdbe12e846329bcc4207c8a88dda956ccfc409641a93ecf7cd1b8acd486`).

---

## 6. Coordinate Mapping
Line 47 & 60 of `WorldMap.java`:
```java
index = (locX2 - locX1) * (y - locY1) + (x - locX1) + (y - locY1);
```
Algebraic simplification:
`index = (width - 1) * dy + dx + dy = width * dy + dx`
where:
- `dx = x - locX1`
- `dy = y - locY1`
- `width = locX2 - locX1 + 1`

### Grid Orientation
- Row-Major (Y-Major):
  - Outer loop / high stride: `y` (North to South, `32768` to `33279`)
  - Inner loop / unit stride: `x` (West to East, `32256` to `32767`)

---

## 7. Tile Semantics & Bitmask Definitions
Empirically verified across all 92 maps in `maps/Cache/` (byte values strictly within `[0x00..0x2F]`):

| Bit Flag | Hex Value | Decimal | Meaning in Legacy Source |
| :--- | :--- | :--- | :--- |
| Bit 0 | `0x01` | 1 | **East Passable**: Actor can traverse East (`IsThroughObject` dir 2) |
| Bit 1 | `0x02` | 2 | **North Passable**: Actor can traverse North (`IsThroughObject` dir 0) |
| Bit 2 | `0x04` | 4 | **East Attack Passable**: Projectiles/Spells pass East (`IsThroughAttack` dir 2) |
| Bit 3 | `0x08` | 8 | **North Attack Passable**: Projectiles/Spells pass North (`IsThroughAttack` dir 0) |
| Bit 4 | `0x10` | 16 | **Safety Zone**: Combat prohibited (`SafetyZone`) |
| Bit 5 | `0x20` | 32 | **Combat Zone**: Free PK / Siege arena (`CombatZone`) |
| Bit 6..7 | `0x40..0x80` | 64..128 | Unused in static binary (always 0) |

### Common Tile Compositions:
- `0x00`: Impassable wall / void barrier.
- `0x0F` (15): Fully open normal terrain (`0x01 | 0x02 | 0x04 | 0x08`).
- `0x1F` (31): Fully open terrain in Safety Zone (`0x0F | 0x10`).
- `0x2F` (47): Fully open terrain in Combat Zone (`0x0F | 0x20`).
- `0x0C` (12): Low obstacle / water (`0x04 | 0x08`, arrows pass, actors blocked).

---

## 8. Runtime Overlay vs. Static Map Distinction
- **Static Map Binary**: Stores persistent base terrain passability (`0x00..0x2F`).
- **Dynamic Overlays**:
  - `DungeonTable.java:37`: At startup, sets portal entry tiles to `100` (`WorldMap.set_map(x, y, m, 100)`).
  - `DoorInstance.java:37-52`: Toggles door tiles between `31` (open/passable) and `16` (closed/blocked).
- **Architectural Boundary**:
  - Scenario 004 strictly imports **Static Map Geometry**.
  - Dynamic triggers (e.g. portal tile `100`) belong to the Transition/Entity layer, not the base map binary.

---

## 9. Canonical Map Model (`native_engine/model.py` / `native_engine/map.py`)
```text
MapDefinition
├── map_id: int
├── bounds: Tuple[int, int, int, int] (x1, x2, y1, y2)
├── width: int
├── height: int
└── raw_tiles: bytes (length = width * height)
```
- **Storage**: Dense, contiguous immutable `bytes` representation for zero-overhead memory and fast indexing.
- **Decoupling**: No references to `.data` file offsets, filesystem paths, or Java classes.

---

## 10. Native Integration Boundary
- Existing `WorldMapGrid` consumes `bounds` and `raw_tiles: bytes`.
- Existing `movement.py` (`can_move`, `is_through_object`) and `navigation.py` (`AStarPlanner`) interface directly with `WorldMapGrid` without any modifications to movement rules.

---

## 11. Differential Verification Plan
- **Legacy Oracle**:
  - Execute instrumented `net.world.WorldMap.getInstance().get_map(x, y, 0)` across all 262,144 coordinates.
  - Produce canonical coordinate-order SHA-256 geometry digest.
  - Certified Oracle Digest: `7fe59f4a4f28fa0c87e69c67506ea578b2860d48e11ef61ffd7b66aef97ff9e5`.
- **Native Verification**:
  - Native decoder ingests `maps/Cache/0.data` + `maps/maps.csv`.
  - Computes SHA-256 over all 262,144 cells in identical Y-major coordinate traversal.
  - Asserts bit-exact equality: `Native Digest == Legacy Digest`.

---

## 12. Test Matrix
- **T01**: Format identification & headerless byte grid validation.
- **T02**: `maps.csv` metadata parsing (Map 0 bounds and dimensions).
- **T03**: File size validation (`W*H - 2` legacy truncation handling).
- **T04**: Coordinate corner mapping (`x1, y1`, `x2, y1`, `x1, y2`, `x2, y2`).
- **T05**: Out-of-bounds rejection (coordinates outside `[x1..x2, y1..y2]` return 0).
- **T06**: Representative tile semantics (open, wall, safety zone, directional edge).
- **T07**: Full canonical geometry digest conformance against Legacy Oracle.
- **T08**: Real map integration into `WorldMapGrid`.
- **T09**: Movement smoke test using existing `MovementEngine` on real Map 0 coordinates.
- **T10**: Deterministic repeated import (Import A digest == Import B digest).

---

## 13. Provenance Taxonomy
- **`LEGACY_OBSERVED`**:
  - `maps.csv` bounding box coordinates and size column.
  - Raw byte layout and linear index formula `width * dy + dx`.
  - Historic 2-byte truncation in `maps/Cache/*.data`.
  - Bitmask flags `0x01` (East), `0x02` (North), `0x04` (AtkEast), `0x08` (AtkNorth), `0x10` (Safety), `0x20` (Combat).
  - Runtime mutation `set_map(..., 100)` by `DungeonTable`.
- **`DERIVED_CANONICAL`**:
  - `CanonicalMapDefinition` container.
  - Standardized coordinate-order SHA-256 geometry digest.
- **`CONTROLLED_SUBSTITUTION`**:
  - Padding the 2 truncated trailing bytes with `0x00` in memory to form a clean `W * H` contiguous grid.
- **`MODERN_DESIGN`**:
  - Offline CLI tool `tools/import_real_map.py`.
  - Dense immutable `bytes` tile storage in `WorldMapGrid`.
- **`UNKNOWN`**:
  - None for static terrain passability of Map 0.

---

## 14. Non-Goals
- Importing all 92 game maps at once (Scenario 004 validates single canonical real map import).
- Client graphical tile asset decoding or rendering.
- Modifying existing movement or collision rules.
- Real-time network streaming of map data.
- Global world routing across multiple real maps (deferred to future scenarios).

---

## 15. Implementation Readiness
All archaeological questions (Q1–Q7) are fully answered by verified code evidence and empirical byte analysis. The specification is complete, mathematically proven, and ready to be frozen.
