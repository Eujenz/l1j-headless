"""
tools/map_decoder.py - Legacy Map Binary Decoder
Decodes uncompressed .data binary grids into CanonicalMapDefinition.
Archaeologically accounts for the historic 2-byte truncation bug observed in
L1J 1.82 WorldMap.readText/writeCache.
"""
import hashlib
import os
from typing import Tuple
from native_engine.model import CanonicalMapDefinition
from .map_metadata import MapMetadata


class LegacyMapDecoder:
    @staticmethod
    def compute_sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @classmethod
    def decode_legacy_map(
        cls,
        data_path: str,
        metadata: MapMetadata
    ) -> Tuple[CanonicalMapDefinition, str]:
        """
        Ingests a legacy .data file and decodes it into a CanonicalMapDefinition.
        Returns:
            Tuple[CanonicalMapDefinition, source_file_sha256]
        """
        if not os.path.exists(data_path):
            raise FileNotFoundError(f"Legacy map data file not found: {data_path}")

        with open(data_path, "rb") as f:
            raw_bytes = f.read()

        source_sha256 = cls.compute_sha256(raw_bytes)
        expected_cells = metadata.cell_count
        raw_len = len(raw_bytes)

        # Handle archaeological 2-byte truncation anomaly
        if raw_len == expected_cells - 2:
            # Pad the 2 missing trailing bytes with 0x00 matching legacy get_map exception handler
            canonical_bytes = raw_bytes + b"\x00\x00"
        elif raw_len == expected_cells:
            canonical_bytes = raw_bytes
        else:
            raise ValueError(
                f"Unexpected file size for map {metadata.map_id}: "
                f"expected {expected_cells} (or {expected_cells - 2}) bytes, got {raw_len}"
            )

        # Canonical digest computed over exactly width * height cells in row-major order
        canonical_digest = cls.compute_sha256(canonical_bytes)

        map_def = CanonicalMapDefinition(
            map_id=metadata.map_id,
            loc_x1=metadata.loc_x1,
            loc_x2=metadata.loc_x2,
            loc_y1=metadata.loc_y1,
            loc_y2=metadata.loc_y2,
            width=metadata.width,
            height=metadata.height,
            raw_tiles=canonical_bytes,
            canonical_geometry_digest=canonical_digest
        )

        return map_def, source_sha256
