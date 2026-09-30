"""
tools/map_metadata.py - Legacy Map Metadata Parser
Extracts map bounding boxes and dimensions from maps.csv without coupling
to legacy database tables or Java classes.
"""
from dataclasses import dataclass
from typing import Dict, Optional
import os


@dataclass(frozen=True)
class MapMetadata:
    map_id: int
    loc_x1: int
    loc_x2: int
    loc_y1: int
    loc_y2: int
    size: int
    width: int
    height: int
    cell_count: int


class MapsCsvReader:
    @staticmethod
    def read_metadata(maps_csv_path: str) -> Dict[int, MapMetadata]:
        if not os.path.exists(maps_csv_path):
            raise FileNotFoundError(f"maps.csv not found at: {maps_csv_path}")

        records: Dict[int, MapMetadata] = {}
        with open(maps_csv_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = [p.strip() for p in line.split(",")]
                if len(parts) < 6:
                    continue
                map_id = int(parts[0])
                x1 = int(parts[1])
                x2 = int(parts[2])
                y1 = int(parts[3])
                y2 = int(parts[4])
                size = int(parts[5])

                width = x2 - x1 + 1
                height = y2 - y1 + 1
                cell_count = width * height

                records[map_id] = MapMetadata(
                    map_id=map_id,
                    loc_x1=x1,
                    loc_x2=x2,
                    loc_y1=y1,
                    loc_y2=y2,
                    size=size,
                    width=width,
                    height=height,
                    cell_count=cell_count
                )
        return records

    @staticmethod
    def get_map(maps_csv_path: str, map_id: int) -> MapMetadata:
        all_maps = MapsCsvReader.read_metadata(maps_csv_path)
        if map_id not in all_maps:
            raise KeyError(f"Map ID {map_id} not present in {maps_csv_path}")
        return all_maps[map_id]
