"""A minimal PSD writer, written from scratch.

It exists mainly so the test suite can generate its own fixture
files and prove the parser by round trip: nothing here needs a
file produced by any other application. It writes 8 bit RGB files
with a merged composite image and basic layer records (name,
bounds, blend mode key, opacity, visibility), using either raw
(compression 0) or PackBits RLE (compression 1) image data.
"""

from __future__ import annotations

import struct

import numpy as np
from PIL import Image

from .blends import MODE_TO_PSD_KEY
from .packbits import packbits_encode


def _pascal_name(name: str, pad_to: int) -> bytes:
    raw = name.encode("latin-1")[:255]
    field = bytes([len(raw)]) + raw
    padding = (-len(field)) % pad_to
    return field + b"\x00" * padding


def _encode_planes(planes: list[np.ndarray], compression: int):
    """Encode channel planes. Returns (header_bytes, body_bytes)
    where the header holds per row byte counts for RLE."""
    height = planes[0].shape[0]
    if compression == 0:
        body = b"".join(plane.tobytes() for plane in planes)
        return b"", body
    counts = []
    chunks = []
    for plane in planes:
        for row in range(height):
            encoded = packbits_encode(plane[row].tobytes())
            counts.append(len(encoded))
            chunks.append(encoded)
    header = b"".join(struct.pack(">H", c) for c in counts)
    return header, b"".join(chunks)


def _layer_channel_block(layer: dict, compression: int) -> bytes:
    """Encode one layer's channel image data, matching the lengths
    recorded in its layer record."""
    rgba = layer["_rgba"]
    height, width = rgba.shape[0], rgba.shape[1]
    channels = [(0, rgba[..., 0]), (1, rgba[..., 1]), (2, rgba[..., 2]),
                (-1, rgba[..., 3])]
    out = bytearray()
    for _channel_id, plane in channels:
        out += struct.pack(">H", compression)
        if compression == 0:
            out += plane.tobytes()
        else:
            counts = []
            chunks = []
            for row in range(height):
                encoded = packbits_encode(plane[row].tobytes())
                counts.append(len(encoded))
                chunks.append(encoded)
            out += b"".join(struct.pack(">H", c) for c in counts)
            out += b"".join(chunks)
    return bytes(out)


def _channel_lengths(layer: dict, compression: int) -> list[tuple[int, int]]:
    rgba = layer["_rgba"]
    height, width = rgba.shape[0], rgba.shape[1]
    lengths = []
    for channel_id in (0, 1, 2, -1):
        plane = rgba[..., channel_id if channel_id >= 0 else 3]
        if compression == 0:
            length = 2 + width * height
        else:
            total = 2 + height * 2
            for row in range(height):
                total += len(packbits_encode(plane[row].tobytes()))
            length = total
        lengths.append((channel_id, length))
    return lengths


def _layer_record(layer: dict, compression: int) -> bytes:
    top = int(layer.get("top", 0))
    left = int(layer.get("left", 0))
    height, width = layer["_rgba"].shape[0], layer["_rgba"].shape[1]
    bottom = top + height
    right = left + width
    lengths = _channel_lengths(layer, compression)
    out = bytearray()
    out += struct.pack(">iiii", top, left, bottom, right)
    out += struct.pack(">H", len(lengths))
    for channel_id, length in lengths:
        out += struct.pack(">hI", channel_id, length)
    blend_key = MODE_TO_PSD_KEY[layer.get("blend_mode", "normal")]
    out += b"8BIM" + blend_key.encode("latin-1")
    opacity = int(round(float(layer.get("opacity", 1.0)) * 255))
    flags = 0 if layer.get("visible", True) else 0x02
    out += bytes([opacity, 0, flags, 0])
    extra = bytearray()
    extra += struct.pack(">I", 0)  # layer mask data length
    extra += struct.pack(">I", 0)  # blending ranges length
    extra += _pascal_name(layer.get("name", "Layer"), 4)
    out += struct.pack(">I", len(extra))
    out += extra
    return bytes(out)


def write_psd(path, composite_image, layers=None, compression=1):
    """Write a minimal PSD file.

    ``composite_image`` is a Pillow Image (converted to RGB).
    ``layers`` is a bottom first list of dictionaries with keys
    ``name``, ``image`` (Pillow Image, converted to RGBA, may be
    smaller than the canvas if ``top``/``left`` are given),
    ``blend_mode`` (engine name such as ``"multiply"``),
    ``opacity`` (0 to 1) and ``visible``. PSD stores layer records
    top first, so the list is reversed on disk.
    """
    composite = composite_image.convert("RGB")
    width, height = composite.size
    rgb = np.asarray(composite, dtype=np.uint8)
    planes = [rgb[..., 0], rgb[..., 1], rgb[..., 2]]

    prepared = []
    for layer in layers or []:
        image = layer["image"].convert("RGBA")
        entry = dict(layer)
        entry["_rgba"] = np.asarray(image, dtype=np.uint8)
        prepared.append(entry)

    # Layer and mask information section.
    layer_section = bytearray()
    if prepared:
        records = bytearray()
        channel_blocks = bytearray()
        # PSD order: top layer first.
        for entry in reversed(prepared):
            records += _layer_record(entry, compression)
            channel_blocks += _layer_channel_block(entry, compression)
        layer_info = bytearray()
        layer_info += struct.pack(">h", len(prepared))
        layer_info += records
        layer_info += channel_blocks
        if len(layer_info) % 2 == 1:
            layer_info += b"\x00"
        layer_section += struct.pack(">I", len(layer_info))
        layer_section += layer_info
        layer_section += struct.pack(">I", 0)  # global layer mask
    layer_mask_section = struct.pack(">I", len(layer_section)) + \
        bytes(layer_section)

    counts_header, body = _encode_planes(planes, compression)
    image_data = struct.pack(">H", compression) + counts_header + body

    out = bytearray()
    out += b"8BPS" + struct.pack(">H", 1) + b"\x00" * 6
    out += struct.pack(">H", 3)                    # channels
    out += struct.pack(">I", height)
    out += struct.pack(">I", width)
    out += struct.pack(">H", 8)                    # depth
    out += struct.pack(">H", 3)                    # colour mode RGB
    out += struct.pack(">I", 0)                    # colour mode data
    out += struct.pack(">I", 0)                    # image resources
    out += layer_mask_section
    out += image_data
    with open(path, "wb") as handle:
        handle.write(bytes(out))
    return path
