"""
ui/world_canvas.py - 2D World Viewport for L1J Headless Player

Architecture:
  - Renders a player-centered 2D tile view using Tkinter Canvas.
  - Viewport: 41 × 31 tiles centered on player position.
  - Each tile: 10 × 10 pixels by default.
  - Renders: map terrain, player, monsters, target highlight, ground loot.
  - Visual interpolation for smoother player movement (UI-only, no world state mutation).
  - NOT a Legacy Client emulator - simple ASCII-style tile rendering only.

Performance:
  - Only queries map passability for the current viewport (bounded tiles, O(viewport area)).
  - Nearby monsters capped at 20 from snapshot (pre-filtered by runtime).
  - Full canvas clear-and-redraw at ~12 FPS (every 80ms polling).
  - Does NOT redraw on every simulation tick.
"""
import tkinter as tk
from typing import Optional, Dict, List, Any, Tuple


# Viewport dimensions (in tiles)
VIEWPORT_W = 41   # tiles wide
VIEWPORT_H = 31   # tiles tall
TILE_SIZE = 10    # pixels per tile

# Canvas size
CANVAS_W = VIEWPORT_W * TILE_SIZE  # 410
CANVAS_H = VIEWPORT_H * TILE_SIZE  # 310

# Color palette
COLOR_PASSABLE    = "#1a1a2e"   # dark blue-black background
COLOR_WALL        = "#2d2d44"   # darker wall tiles
COLOR_GRID        = "#222233"   # subtle grid
COLOR_PLAYER      = "#00cc44"   # bright green player dot
COLOR_PLAYER_TXT  = "#ffffff"   # white player name label
COLOR_MONSTER     = "#cc3333"   # red monster dot
COLOR_TARGET      = "#ff8800"   # orange target highlight
COLOR_TARGET_HP_BG = "#440000"  # dark red HP bar background
COLOR_TARGET_HP_FG = "#ff4444"  # red HP bar fill
COLOR_LOOT        = "#ffd700"   # gold loot dot
COLOR_NPC         = "#6699ff"   # blue NPC dot
COLOR_INDICATOR   = "#ffffff"   # text indicators


class WorldCanvas(tk.Canvas):
    """
    2D tile viewport centered on the player.
    Updated by calling update_view(snapshot) from the UI polling loop.
    """

    def __init__(self, parent, **kwargs):
        kwargs.setdefault("width", CANVAS_W)
        kwargs.setdefault("height", CANVAS_H)
        kwargs.setdefault("bg", COLOR_PASSABLE)
        kwargs.setdefault("highlightthickness", 1)
        kwargs.setdefault("highlightbackground", "#444466")
        super().__init__(parent, **kwargs)

        # Last known state for interpolation
        self._player_tile: Optional[Tuple[int, int]] = None
        self._map_grid = None   # WorldMapGrid or None (injected via set_map_grid)
        self._snap = None       # last PlayerRuntimeSnapshot
        self._visible_offset = (0, 0)  # (origin_x, origin_y) in world tile coords

        # Draw initial "loading" state
        self._draw_loading()

    def set_map_grid(self, map_grid) -> None:
        """Inject the WorldMapGrid for the current map. Called when map changes."""
        self._map_grid = map_grid

    def update_view(self, snap, map_grid=None) -> None:
        """
        Full repaint of the 2D viewport from snapshot.
        Called by PlayerWindow polling loop at ~12 FPS.
        """
        self._snap = snap
        if map_grid is not None:
            self._map_grid = map_grid

        # Compute viewport origin (top-left tile in world coords)
        px, py = snap.x, snap.y
        origin_x = px - VIEWPORT_W // 2
        origin_y = py - VIEWPORT_H // 2
        self._visible_offset = (origin_x, origin_y)

        # Clear canvas
        self.delete("all")

        # 1. Draw terrain tiles
        self._draw_terrain(origin_x, origin_y, snap.map_id)

        # 2. Draw ground loot
        # (loot info not yet in snapshot - reserved for future)
        # self._draw_loot(origin_x, origin_y)

        # 3. Draw monsters
        self._draw_monsters(snap.nearby_monsters, snap.active_target, origin_x, origin_y)

        # 4. Draw player
        self._draw_player(px, py, snap.player_name, origin_x, origin_y)

        # 5. Draw target HP bar
        if snap.active_target:
            self._draw_target_info(snap.active_target, origin_x, origin_y)

        # 6. Draw map name overlay
        self._draw_map_label(snap.map_name)

    def _draw_loading(self) -> None:
        self.delete("all")
        self.create_text(
            CANVAS_W // 2, CANVAS_H // 2,
            text="正在載入世界...",
            fill=COLOR_INDICATOR, font=("Helvetica", 12), anchor=tk.CENTER
        )

    def _tile_to_canvas(self, tx: int, ty: int, origin_x: int, origin_y: int) -> Tuple[int, int]:
        """Convert world tile coordinate to canvas pixel coordinate (top-left of tile)."""
        cx = (tx - origin_x) * TILE_SIZE
        cy = (ty - origin_y) * TILE_SIZE
        return cx, cy

    def _draw_terrain(self, origin_x: int, origin_y: int, map_id: int) -> None:
        """Draw passable/wall tiles for the visible viewport."""
        grid = self._map_grid
        for ty_rel in range(VIEWPORT_H):
            ty = origin_y + ty_rel
            for tx_rel in range(VIEWPORT_W):
                tx = origin_x + tx_rel
                cx = tx_rel * TILE_SIZE
                cy = ty_rel * TILE_SIZE

                # Determine passability
                if grid is not None:
                    try:
                        passable = grid.is_passable(tx, ty)
                    except Exception:
                        passable = True
                else:
                    passable = True

                color = COLOR_PASSABLE if passable else COLOR_WALL
                if color != COLOR_PASSABLE:  # Only draw walls explicitly (saves render time)
                    self.create_rectangle(
                        cx, cy, cx + TILE_SIZE - 1, cy + TILE_SIZE - 1,
                        fill=color, outline="", width=0
                    )

    def _draw_monsters(
        self,
        monsters: List[Dict[str, Any]],
        active_target: Optional[Dict[str, Any]],
        origin_x: int,
        origin_y: int
    ) -> None:
        """Draw monster dots. Target monster highlighted in orange."""
        target_uid = active_target["uid"] if active_target else None
        RADIUS = 4

        for m in monsters[:20]:  # cap at 20 for performance
            mx, my = m["x"], m["y"]
            cx, cy = self._tile_to_canvas(mx, my, origin_x, origin_y)
            # Skip if outside viewport
            if cx < -TILE_SIZE or cx > CANVAS_W + TILE_SIZE:
                continue
            if cy < -TILE_SIZE or cy > CANVAS_H + TILE_SIZE:
                continue

            is_target = (m.get("uid") == target_uid)
            dot_color = COLOR_TARGET if is_target else COLOR_MONSTER
            cx_c = cx + TILE_SIZE // 2
            cy_c = cy + TILE_SIZE // 2

            if is_target:
                # Draw larger highlighted circle for target
                self.create_oval(
                    cx_c - RADIUS - 2, cy_c - RADIUS - 2,
                    cx_c + RADIUS + 2, cy_c + RADIUS + 2,
                    fill=dot_color, outline="#ffcc00", width=2
                )
                # HP bar above target
                hp_ratio = m["hp"] / max(1, m["max_hp"])
                bar_w = 30
                bar_h = 4
                bar_x = cx_c - bar_w // 2
                bar_y = cy_c - RADIUS - 8
                self.create_rectangle(bar_x, bar_y, bar_x + bar_w, bar_y + bar_h,
                                      fill=COLOR_TARGET_HP_BG, outline="")
                self.create_rectangle(bar_x, bar_y, bar_x + int(bar_w * hp_ratio), bar_y + bar_h,
                                      fill=COLOR_TARGET_HP_FG, outline="")
                # Monster name
                self.create_text(
                    cx_c, cy_c - RADIUS - 12,
                    text=m["name"], fill="#ffcc00",
                    font=("Helvetica", 7), anchor=tk.CENTER
                )
            else:
                self.create_oval(
                    cx_c - RADIUS, cy_c - RADIUS,
                    cx_c + RADIUS, cy_c + RADIUS,
                    fill=dot_color, outline="#990000", width=1
                )

    def _draw_player(
        self, px: int, py: int, name: str,
        origin_x: int, origin_y: int
    ) -> None:
        """Draw player dot at world position (px, py)."""
        cx, cy = self._tile_to_canvas(px, py, origin_x, origin_y)
        cx_c = cx + TILE_SIZE // 2
        cy_c = cy + TILE_SIZE // 2
        RADIUS = 5

        # Glow effect (larger faint circle)
        self.create_oval(
            cx_c - RADIUS - 3, cy_c - RADIUS - 3,
            cx_c + RADIUS + 3, cy_c + RADIUS + 3,
            fill="", outline="#005500", width=2
        )
        # Player dot
        self.create_oval(
            cx_c - RADIUS, cy_c - RADIUS,
            cx_c + RADIUS, cy_c + RADIUS,
            fill=COLOR_PLAYER, outline="#00ff66", width=1
        )
        # Player name label below dot
        self.create_text(
            cx_c, cy_c + RADIUS + 7,
            text=name, fill=COLOR_PLAYER_TXT,
            font=("Helvetica", 7, "bold"), anchor=tk.CENTER
        )

    def _draw_target_info(self, target: Dict[str, Any], origin_x: int, origin_y: int) -> None:
        """Draw extra target info at the bottom of canvas."""
        hp = target["hp"]
        max_hp = target["max_hp"]
        name = target["name"]
        hp_ratio = hp / max(1, max_hp)

        # Bottom info bar
        bar_y = CANVAS_H - 22
        self.create_rectangle(0, bar_y - 2, CANVAS_W, CANVAS_H,
                              fill="#11112a", outline="")
        self.create_text(
            8, bar_y + 6,
            text=f"目標: {name}  HP {hp}/{max_hp}",
            fill=COLOR_TARGET, font=("Helvetica", 8), anchor=tk.W
        )
        # HP bar
        bar_x, bar_w = 8, CANVAS_W - 16
        self.create_rectangle(bar_x, bar_y + 14, bar_x + bar_w, bar_y + 18,
                              fill=COLOR_TARGET_HP_BG, outline="")
        self.create_rectangle(bar_x, bar_y + 14, bar_x + int(bar_w * hp_ratio), bar_y + 18,
                              fill=COLOR_TARGET_HP_FG, outline="")

    def _draw_map_label(self, map_name: str) -> None:
        """Draw map name in top-right corner."""
        self.create_text(
            CANVAS_W - 4, 4,
            text=map_name, fill="#aaaacc",
            font=("Helvetica", 8), anchor=tk.NE
        )
