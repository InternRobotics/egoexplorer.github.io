#!/usr/bin/env python3
"""Build compact, browser-ready previews from the environment PLY files."""

from pathlib import Path
import base64
import struct

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "gaussion"
DESTINATION = ROOT / "assets" / "point-clouds"
MAX_POINTS = 180_000
SCENES = (
    "laboratory",
    "industrial_workspace",
    "living_room",
    "food-prep_area",
    "study",
)
PLY_TYPES = {
    "char": "i1",
    "uchar": "u1",
    "short": "<i2",
    "ushort": "<u2",
    "int": "<i4",
    "uint": "<u4",
    "float": "<f4",
    "double": "<f8",
}


def read_vertex_header(path: Path):
    properties = []
    vertex_count = None
    vertex_element = False
    header_size = 0
    with path.open("rb") as stream:
        while True:
            line = stream.readline()
            if not line:
                raise ValueError(f"Missing end_header in {path}")
            header_size += len(line)
            fields = line.decode("ascii").strip().split()
            if fields[:2] == ["element", "vertex"]:
                vertex_count = int(fields[2])
                vertex_element = True
            elif fields and fields[0] == "element":
                vertex_element = False
            elif vertex_element and fields[:1] == ["property"]:
                if fields[1] == "list":
                    raise ValueError(f"Unexpected list property in vertex data: {path}")
                properties.append((fields[2], PLY_TYPES[fields[1]]))
            elif fields[:1] == ["end_header"]:
                break
    if vertex_count is None:
        raise ValueError(f"Missing vertex element in {path}")
    return vertex_count, np.dtype(properties), header_size


def build_preview(scene: str, seed: int):
    source_path = SOURCE / f"{scene}.ply"
    count, dtype, data_offset = read_vertex_header(source_path)
    vertices = np.memmap(source_path, mode="r", dtype=dtype, offset=data_offset, shape=(count,))

    rng = np.random.default_rng(seed)
    selected_count = min(count, MAX_POINTS)
    if count == selected_count:
        selected = np.arange(count)
    else:
        selected = np.sort(rng.choice(count, size=selected_count, replace=False))
    sampled = vertices[selected]

    positions = np.column_stack((sampled["x"], sampled["y"], sampled["z"])).astype(np.float32)
    colors = np.column_stack((sampled["red"], sampled["green"], sampled["blue"])).astype(np.uint8)
    valid = np.isfinite(positions).all(axis=1)
    positions = positions[valid]
    colors = colors[valid]
    minimum = positions.min(axis=0)
    maximum = positions.max(axis=0)
    center = (minimum + maximum) * 0.5
    extent = float(np.max(maximum - minimum))
    if not np.isfinite(extent) or extent <= 0:
        raise ValueError(f"Invalid point bounds in {source_path}")
    positions = (positions - center) * (2.0 / extent)

    records = np.zeros((len(positions), 16), dtype=np.uint8)
    records[:, :12] = positions.astype("<f4").view(np.uint8).reshape(-1, 12)
    records[:, 12:15] = colors
    records[:, 15] = 255

    DESTINATION.mkdir(parents=True, exist_ok=True)
    payload = b"EGO1" + struct.pack("<I", len(records)) + records.tobytes()
    encoded = base64.b64encode(payload).decode("ascii")
    output_path = DESTINATION / f"{scene}.js"
    output_path.write_text(
        "window.EGO_POINT_CLOUD_PREVIEWS = window.EGO_POINT_CLOUD_PREVIEWS || {};\n"
        f'window.EGO_POINT_CLOUD_PREVIEWS["{scene}"] = "{encoded}";\n',
        encoding="ascii",
    )
    print(f"{output_path.relative_to(ROOT)}: {len(records):,} points")


def main():
    for seed, scene in enumerate(SCENES, start=1):
        build_preview(scene, seed)


if __name__ == "__main__":
    main()
