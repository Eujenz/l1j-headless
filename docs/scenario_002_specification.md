# Scenario 002: Movement, Collision & Autonomous Navigation Specification

## 1. Scope & Objective
Establish the first vertical slice representing spatial existence and autonomous navigation in a Headless L1 World:
- Three-Layer Architecture: Navigation (Planner) -> Movement Rules (Arbiter) -> World Geometry (Map Data).
- Pure discrete topological steps, strictly decoupled from real-time timing and AOI presentation.
- Autonomous GoTo planner generating canonical `CmdMove(heading)` commands down to the movement arbiter.

## 2. Heading to Delta Mapping
Strictly canonical 8-direction clockwise mapping:
- 0: North (dx=0, dy=-1)
- 1: North-East (dx=+1, dy=-1)
- 2: East (dx=+1, dy=0)
- 3: South-East (dx=+1, dy=+1)
- 4: South (dx=0, dy=+1)
- 5: South-West (dx=-1, dy=+1)
- 6: West (dx=-1, dy=0)
- 7: North-West (dx=-1, dy=-1)

## 3. Map Geometry & Indexing Formula
- Standard 2D Row-Major formula: `index = width * (y - y1) + (x - x1)`, where `width = x2 - x1 + 1`.
- Tile bitmask flags:
  - `0x01`: East Passable
  - `0x02`: North Passable
- Edge sharing:
  - South: Neighbor `(x, y+1)` North flag (`& 0x02`)
  - West: Neighbor `(x-1, y)` East flag (`& 0x01`)
- Diagonal Corner Clearance:
  - Heading 1 (NE): North then East (`(x,y)&0x2 > 0 && (x,y-1)&0x1 > 0`)
  - Headings 3, 5, 7 (SE, SW, NW): Dual-route disjunction (Route 1 open OR Route 2 open)

## 4. Architectural Boundaries
- Legacy Server Fact: `PcInstance.toMove` relies on client-side collision prediction and does not check static collision.
- Modern Design Decision: In Headless Native Engine, static collision (`can_move`) is mandatory for player movement.
- Navigation vs Movement Separation: Planners never directly mutate position; only Movement Engine mutates state.
