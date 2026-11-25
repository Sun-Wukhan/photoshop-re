"""A PSD parser written from scratch.

The layout implemented here follows the publicly documented PSD file
format: a fixed 26 byte header, then four length prefixed sections
(colour mode data, image resources, layer and mask information, and
the merged image data). Only 8 bit per channel files are decoded to
pixels; other depths are still parsed for metadata.

No Adobe code was used or consulted. This is an original
implementation written from the published format description.
"""

from __future__ import annotations

import io
import struct

from .packbits import packbits_decode

SIGNATURE = b"8BPS"
BLEND_SIGNATURE = b"8BIM"

COLOUR_MODES = {
    0: "Bitmap",
    1: "Grayscale",
    2: "Indexed",
    3: "RGB",
    4: "CMYK",
    7: "Multichannel",
    8: "Duotone",
    9: "Lab",
}


class _Reader:
    """Small big endian cursor over a bytes object."""

    def __init__(self, data: bytes, start: int = 0, end: int | None = None):
        self.data = data
        self.pos = start
        self.end = len(data) if end is None else end

    def read(self, count: int) -> bytes:
        chunk = self.data[self.pos:self.pos + count]
        if len(chunk) != count:
            raise ValueError("unexpected end of file")
        self.pos += count
        return chunk

    def u8(self) -> int:
        return self.read(1)[0]

    def u16(self) -> int:
        return struct.unpack(">H", self.read(2))[0]

    def i16(self) -> int:
        return struct.unpack(">h", self.read(2))[0]

    def u32(self) -> int:
        return struct.unpack(">I", self.read(4))[0]

    def i32(self) -> int:
        return struct.unpack(">i", self.read(4))[0]

    def remaining(self) -> int:
        return self.end - self.pos


def _read_pascal_string(reader: _Reader, pad_to: int) -> str:
    """Read a Pascal string (length byte plus bytes) padded so the
    total field size, length byte included, is a multiple of pad_to."""
    length = reader.u8()
    raw = reader.read(length) if length else b""
    total = 1 + length
    padding = (-total) % pad_to
    if padding:
        reader.read(padding)
    return raw.decode("latin-1")


def _decode_channel_data(raw: bytes, compression: int, width: int,
                         height: int, row_counts: list[int] | None):
    """Decode one channel plane of width by height bytes."""
    expected = width * height
    if expected == 0:
        return b""
    if compression == 0:
        return raw[:expected]
    if compression == 1:
        if row_counts is None:
            raise ValueError("RLE channel data without row counts")
        out = bytearray()
        offset = 0
        for row in range(height):
            count = row_counts[row]
            packet = raw[offset:offset + count]
            offset += count
            out.extend(packbits_decode(packet, width))
        return bytes(out)
    raise ValueError(f"unsupported compression {compression}")


def _parse_image_resources(data: bytes) -> list[dict]:
    resources = []
    reader = _Reader(data)
    while reader.remaining() >= 4:
        signature = reader.read(4)
        if signature not in (b"8BIM", b"8B64", b"PSIR"):
            break
        unique_id = reader.u16()
        name = _read_pascal_string(reader, 2)
        size = reader.u32()
        reader.read(size)
        if size % 2 == 1:
            reader.read(1)
        resources.append({
            "signature": signature.decode("latin-1"),
            "id": unique_id,
            "name": name,
            "size": size,
        })
    return resources


def _parse_layer_record(reader: _Reader) -> dict:
    top = reader.i32()
    left = reader.i32()
    bottom = reader.i32()
    right = reader.i32()
    channel_count = reader.u16()
    channels = []
    for _ in range(channel_count):
        channel_id = reader.i16()
        length = reader.u32()
        channels.append({"id": channel_id, "length": length})
    blend_signature = reader.read(4)
    if blend_signature != BLEND_SIGNATURE:
        raise ValueError(f"bad blend mode signature {blend_signature!r}")
    blend_key = reader.read(4).decode("latin-1")
    opacity = reader.u8()
    clipping = reader.u8()
    flags = reader.u8()
    reader.u8()  # filler
    extra_length = reader.u32()
    extra_start = reader.pos
    # Layer mask data.
    mask_length = reader.u32()
    reader.read(mask_length)
    # Layer blending ranges.
    ranges_length = reader.u32()
    reader.read(ranges_length)
    # Layer name, Pascal string padded to a multiple of 4.
    name = _read_pascal_string(reader, 4)
    # Skip any remaining extra data (adjustment layers and so on).
    reader.pos = extra_start + extra_length
    return {
        "name": name,
        "bounds": {"top": top, "left": left, "bottom": bottom, "right": right},
        "width": max(0, right - left),
        "height": max(0, bottom - top),
        "channels": channels,
        "blend_mode": blend_key,
        "opacity": opacity,
        "opacity_fraction": round(opacity / 255.0, 4),
        "clipping": bool(clipping),
        "visible": not bool(flags & 0x02),
        "flags": flags,
    }


def _parse_layer_and_mask(data: bytes) -> dict:
    if not data:
        return {"layer_count": 0, "layers": [], "absolute_alpha": False}
    reader = _Reader(data)
    layer_info_length = reader.u32()
    layer_info_end = reader.pos + layer_info_length
    signed_count = reader.i16()
    absolute_alpha = signed_count < 0
    layer_count = abs(signed_count)
    layers = []
    for _ in range(layer_count):
        layers.append(_parse_layer_record(reader))
    # Channel image data follows the records, layer by layer, in the
    # same order. Each channel starts with a 2 byte compression tag.
    for layer in layers:
        height = layer["height"]
        width = layer["width"]
        decoded = {}
        for channel in layer["channels"]:
            data_length = channel["length"]
            channel_start = reader.pos
            compression = reader.u16()
            payload_length = data_length - 2
            payload = reader.read(payload_length)
            channel_height = height
            channel_width = width
            row_counts = None
            body = payload
            if compression == 1 and channel_height > 0:
                row_counts = []
                counts_bytes = channel_height * 2
                for r in range(channel_height):
                    row_counts.append(
                        struct.unpack(">H", payload[r * 2:r * 2 + 2])[0])
                body = payload[counts_bytes:]
            if channel_width > 0 and channel_height > 0:
                decoded[channel["id"]] = _decode_channel_data(
                    body, compression, channel_width, channel_height,
                    row_counts)
            else:
                decoded[channel["id"]] = b""
            reader.pos = channel_start + data_length
        layer["_channel_pixels"] = decoded
    reader.pos = layer_info_end
    # Whatever remains is the global layer mask info and any
    # additional layer information blocks; we do not decode them.
    return {
        "layer_count": layer_count,
        "layers": layers,
        "absolute_alpha": absolute_alpha,
    }


def parse_psd(path) -> dict:
    """Parse a PSD file and return a dictionary describing it.

    Keys include the header fields, the image resource blocks found,
    layer metadata (name, bounds, channels, blend mode key, opacity,
    visibility), the compression used by the merged image data, and
    the raw merged channel planes under ``_composite_planes`` (used by
    :func:`decode_composite_image`; strip keys starting with an
    underscore if you serialise the report).
    """
    with open(path, "rb") as handle:
        data = handle.read()
    reader = _Reader(data)
    signature = reader.read(4)
    if signature != SIGNATURE:
        raise ValueError(f"not a PSD file: signature {signature!r}")
    version = reader.u16()
    reader.read(6)  # reserved, must be zero
    channels = reader.u16()
    height = reader.u32()
    width = reader.u32()
    depth = reader.u16()
    colour_mode = reader.u16()

    colour_mode_length = reader.u32()
    colour_mode_data = reader.read(colour_mode_length)

    resources_length = reader.u32()
    resources = _parse_image_resources(reader.read(resources_length))

    layer_mask_length = reader.u32()
    layer_section = reader.read(layer_mask_length)
    layer_info = _parse_layer_and_mask(layer_section)

    # Merged image data.
    compression = reader.u16()
    planes = []
    if depth == 8:
        total_rows = channels * height
        row_counts = None
        body_start = reader.pos
        if compression == 1:
            row_counts = [reader.u16() for _ in range(total_rows)]
            body_start = reader.pos
        body = data[body_start:]
        offset = 0
        pos = 0  # byte offset into the RLE body, shared across planes
        for channel_index in range(channels):
            if compression == 0:
                plane = body[offset:offset + width * height]
                offset += width * height
            elif compression == 1:
                rows = row_counts[channel_index * height:
                                   (channel_index + 1) * height]
                plane_bytes = bytearray()
                for row in range(height):
                    count = rows[row]
                    packet = body[pos:pos + count]
                    pos += count
                    plane_bytes.extend(packbits_decode(packet, width))
                plane = bytes(plane_bytes)
            else:
                raise ValueError(
                    f"unsupported composite compression {compression}")
            planes.append(plane)
    layers_public = []
    for layer in layer_info["layers"]:
        public = {k: v for k, v in layer.items()
                  if not k.startswith("_")}
        layers_public.append(public)
    return {
        "signature": "8BPS",
        "version": version,
        "channels": channels,
        "width": width,
        "height": height,
        "depth": depth,
        "colour_mode": colour_mode,
        "colour_mode_name": COLOUR_MODES.get(colour_mode, "Unknown"),
        "colour_mode_data_length": colour_mode_length,
        "image_resources": resources,
        "layer_count": layer_info["layer_count"],
        "absolute_alpha": layer_info["absolute_alpha"],
        "layers": layers_public,
        "composite_compression": compression,
        "_composite_planes": planes,
        "_layer_channel_pixels": [
            layer.get("_channel_pixels", {})
            for layer in layer_info["layers"]
        ],
    }


def decode_composite_image(parsed_or_path):
    """Decode the merged (composite) image into a Pillow Image.

    Accepts either a path or the dictionary returned by parse_psd.
    Supports 8 bit RGB (3 or 4 channels) and Grayscale (1 channel).
    """
    import numpy as np
    from PIL import Image

    parsed = (parse_psd(parsed_or_path)
              if isinstance(parsed_or_path, (str, bytes)) or
              hasattr(parsed_or_path, "__fspath__")
              else parsed_or_path)
    planes = parsed.get("_composite_planes") or []
    width, height, channels = parsed["width"], parsed["height"], parsed["channels"]
    if not planes:
        raise ValueError("no decodable composite image data (depth must be 8)")
    arrays = []
    for plane in planes:
        arr = np.frombuffer(plane, dtype=np.uint8)
        if arr.size != width * height:
            raise ValueError("composite plane size mismatch")
        arrays.append(arr.reshape(height, width))
    if channels == 1:
        return Image.fromarray(arrays[0], mode="L")
    rgb = np.stack(arrays[:3], axis=-1)
    if channels >= 4:
        rgba = np.dstack([rgb, arrays[3]])
        return Image.fromarray(rgba, mode="RGBA")
    return Image.fromarray(rgb, mode="RGB")


def composite_bytes(parsed: dict) -> bytes:
    """Return the composite image encoded as PNG bytes (helper)."""
    image = decode_composite_image(parsed)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
