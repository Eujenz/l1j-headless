"""
ui/world_canvas.py - 2D World Viewport for L1J Headless Player

Rendering rules (presentation only - never mutates simulation state):
  - Terrain is derived from the REAL imported Legacy map (WorldMapGrid) using the
    same edge bitmask semantics as movement (0x01 = east edge, 0x02 = north edge).
    A tile is "floor" if at least one of its four edges is passable.
  - Outside map bounds = void (black). Walls touching floor = bright boundary.
  - Terrain is rendered into one cached PhotoImage (rebuilt only when the viewport
    origin / map changes), so per-frame cost is only the dynamic overlay.
  - Dynamic overlay (tag "dyn"): ground loot, monsters, target, player, floating text.
  - Click on a monster -> select target callback (goes through PlayerOperation path).
"""
import time
import tkinter as tk
from typing import Optional, Dict, List, Any, Tuple, Callable

VIEWPORT_W = 41
VIEWPORT_H = 31
TILE_SIZE = 10
CANVAS_W = VIEWPORT_W * TILE_SIZE
CANVAS_H = VIEWPORT_H * TILE_SIZE

COLOR_VOID = "#000000"
COLOR_WALL = "#0c0c18"
COLOR_WALL_EDGE = "#5d5d8a"
COLOR_FLOOR = "#2b3150"
COLOR_PLAYER = "#00cc44"
COLOR_MONSTER = "#cc3333"
COLOR_TARGET = "#ff8800"
COLOR_HP_BG = "#440000"
COLOR_HP_FG = "#ff4444"
COLOR_LOOT = "#ffd700"

FLOAT_LIFETIME_S = 1.0


def tile_walkable(grid, x: int, y: int) -> bool:
    """A tile is standable if any of its 4 edges is open (Legacy edge bitmask)."""
    if not grid.is_in_bounds(x, y):
        return False
    t = grid.get_tile(x, y)
    if t & 0x03:
        return True
    return bool(grid.get_tile(x, y + 1) & 0x02) or bool(grid.get_tile(x - 1, y) & 0x01)


def build_terrain_rows(grid, origin_x: int, origin_y: int,
                       w: int = VIEWPORT_W, h: int = VIEWPORT_H) -> List[List[str]]:
    """Return rows of color strings for the viewport (pure function, testable)."""
    # compute with a 1-tile margin so wall-edge detection is correct on borders
    floor = {}
    for ty in range(origin_y - 1, origin_y + h + 1):
        for tx in range(origin_x - 1, origin_x + w + 1):
            floor[(tx, ty)] = tile_walkable(grid, tx, ty)
    rows: List[List[str]] = []
    for ty in range(origin_y, origin_y + h):
        row = []
        for tx in range(origin_x, origin_x + w):
            if floor[(tx, ty)]:
                row.append(COLOR_FLOOR)
            elif not grid.is_in_bounds(tx, ty):
                row.append(COLOR_VOID)
            else:
                near_floor = any(
                    floor[(tx + dx, ty + dy)]
                    for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy
                )
                row.append(COLOR_WALL_EDGE if near_floor else COLOR_WALL)
        rows.append(row)
    return rows


class _FloatText:
    __slots__ = ("text", "color", "wx", "wy", "born")

    def __init__(self, text: str, color: str, wx: int, wy: int):
        self.text, self.color, self.wx, self.wy = text, color, wx, wy
        self.born = time.perf_counter()


class WorldCanvas(tk.Canvas):
    def __init__(self, parent, on_monster_click: Optional[Callable[[int], None]] = None, **kwargs):
        kwargs.setdefault("width", CANVAS_W)
        kwargs.setdefault("height", CANVAS_H)
        kwargs.setdefault("bg", COLOR_VOID)
        kwargs.setdefault("highlightthickness", 1)
        kwargs.setdefault("highlightbackground", "#444466")
        super().__init__(parent, **kwargs)
        self._map_grid = None
        self._snap = None
        self._origin = (0, 0)
        self._terrain_key = None
        self._terrain_img = None
        self._terrain_item = None
        self._floats: List[_FloatText] = []
        self._on_monster_click = on_monster_click
        self.bind("<Button-1>", self._on_click)
        self._draw_loading()

    # ------------------------------------------------------------------ API
    def set_map_grid(self, map_grid) -> None:
        self._map_grid = map_grid

    def has_active_effects(self) -> bool:
        return bool(self._floats)

    def add_float_text(self, text: str, color: str, wx: int, wy: int) -> None:
        if len(self._floats) < 30:
            self._floats.append(_FloatText(text, color, wx, wy))

    def update_view(self, snap, map_grid=None) -> None:
        self._snap = snap
        if map_grid is not None:
            self._map_grid = map_grid
        ox = snap.x - VIEWPORT_W // 2
        oy = snap.y - VIEWPORT_H // 2
        self._origin = (ox, oy)

        self._ensure_terrain(ox, oy, snap.map_id)
        self.delete("dyn")
        self._draw_loot(getattr(snap, "ground_drops", []), ox, oy)
        self._draw_monsters(snap.nearby_monsters, snap.active_target, ox, oy)
        self._draw_player(snap.x, snap.y, snap.player_name, ox, oy)
        self._draw_floats(ox, oy)
        self._draw_map_label(snap.map_name)

    # ------------------------------------------------------------- terrain
    def _ensure_terrain(self, ox: int, oy: int, map_id: int) -> None:
        key = (map_id, ox, oy)
        if key == self._terrain_key:
            return
        self._terrain_key = key
        grid = self._map_grid
        if grid is None:
            self.delete("terrain")
            self._terrain_item = None
            return
        rows = build_terrain_rows(grid, ox, oy)
        img = tk.PhotoImage(master=self, width=VIEWPORT_W, height=VIEWPORT_H)
        img.put(" ".join("{" + " ".join(r) + "}" for r in rows))
        img = img.zoom(TILE_SIZE, TILE_SIZE)
        self._terrain_img = img  # keep reference
        if self._terrain_item is None:
            self._terrain_item = self.create_image(0, 0, image=img, anchor=tk.NW, tags="terrain")
            self.tag_lower("terrain")
        else:
            self.itemconfig(self._terrain_item, image=img)

    def _draw_loading(self) -> None:
        self.delete("all")
        self._terrain_key = None
        self._terrain_item = None
        self.create_text(CANVAS_W // 2, CANVAS_H // 2, text="正在載入世界...",
                         fill="#ffffff", font=("Helvetica", 12), anchor=tk.CENTER, tags="dyn")

    # -------------------------------------------------------------- helpers
    def _center(self, wx: int, wy: int, ox: int, oy: int) -> Tuple[int, int]:
        return ((wx - ox) * TILE_SIZE + TILE_SIZE // 2,
                (wy - oy) * TILE_SIZE + TILE_SIZE // 2)

    def _in_view(self, cx: int, cy: int) -> bool:
        return -TILE_SIZE <= cx <= CANVAS_W + TILE_SIZE and -TILE_SIZE <= cy <= CANVAS_H + TILE_SIZE

    # ----------------------------------------------------------------- draw
    def _draw_loot(self, drops: List[Dict[str, Any]], ox: int, oy: int) -> None:
        for d in drops[:40]:
            cx, cy = self._center(d["x"], d["y"], ox, oy)
            if self._in_view(cx, cy):
                self.create_rectangle(cx - 2, cy - 2, cx + 2, cy + 2,
                                      fill=COLOR_LOOT, outline="#996600", tags="dyn")

    def _draw_monsters(self, monsters, active_target, ox: int, oy: int) -> None:
        target_uid = active_target["uid"] if active_target else None
        R = 4
        for m in monsters[:20]:
            cx, cy = self._center(m["x"], m["y"], ox, oy)
            if not self._in_view(cx, cy):
                continue
            if m.get("uid") == target_uid:
                self.create_oval(cx - R - 2, cy - R - 2, cx + R + 2, cy + R + 2,
                                 fill=COLOR_TARGET, outline="#ffcc00", width=2, tags="dyn")
                ratio = m["hp"] / max(1, m["max_hp"])
                bx, by = cx - 15, cy - R - 9
                self.create_rectangle(bx, by, bx + 30, by + 4, fill=COLOR_HP_BG, outline="", tags="dyn")
                self.create_rectangle(bx, by, bx + int(30 * ratio), by + 4,
                                      fill=COLOR_HP_FG, outline="", tags="dyn")
                self.create_text(cx, cy - R - 14, text=m["name"], fill="#ffcc00",
                                 font=("Helvetica", 7), tags="dyn")
            else:
                self.create_oval(cx - R, cy - R, cx + R, cy + R,
                                 fill=COLOR_MONSTER, outline="#990000", tags="dyn")

    def _draw_player(self, px: int, py: int, name: str, ox: int, oy: int) -> None:
        cx, cy = self._center(px, py, ox, oy)
        R = 5
        self.create_oval(cx - R - 3, cy - R - 3, cx + R + 3, cy + R + 3,
                         outline="#00aa44", width=2, tags="dyn")
        self.create_oval(cx - R, cy - R, cx + R, cy + R,
                         fill=COLOR_PLAYER, outline="#00ff66", tags="dyn")
        self.create_text(cx, cy + R + 8, text=name, fill="#ffffff",
                         font=("Helvetica", 7, "bold"), tags="dyn")

    def _draw_floats(self, ox: int, oy: int) -> None:
        now = time.perf_counter()
        alive = []
        for f in self._floats:
            age = now - f.born
            if age >= FLOAT_LIFETIME_S:
                continue
            alive.append(f)
            cx, cy = self._center(f.wx, f.wy, ox, oy)
            rise = int(age / FLOAT_LIFETIME_S * 22)
            self.create_text(cx, cy - 14 - rise, text=f.text, fill=f.color,
                             font=("Helvetica", 9, "bold"), tags="dyn")
        self._floats = alive

    def _draw_map_label(self, map_name: str) -> None:
        self.create_text(CANVAS_W - 4, 4, text=map_name, fill="#aaaacc",
                         font=("Helvetica", 8), anchor=tk.NE, tags="dyn")

    # ---------------------------------------------------------------- input
    def _on_click(self, event) -> None:
        if not self._snap or not self._on_monster_click:
            return
        ox, oy = self._origin
        wx = ox + event.x // TILE_SIZE
        wy = oy + event.y // TILE_SIZE
        best = None
        for m in self._snap.nearby_monsters[:20]:
            d = max(abs(m["x"] - wx), abs(m["y"] - wy))
            if d <= 1 and (best is None or d < best[0]):
                best = (d, m["uid"])
        if best:
            self._on_monster_click(best[1])
