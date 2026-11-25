import numpy as np
import pytest
from PIL import Image

from pslab.psd import decode_composite_image, parse_psd
from pslab.psd_writer import write_psd


def _composite_image(width=10, height=7):
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    arr[..., 0] = 200
    arr[..., 1] = 100
    arr[..., 2] = 50
    arr[0, 0] = (10, 20, 30)
    arr[-1, -1] = (250, 240, 230)
    return Image.fromarray(arr, mode="RGB")


def _layers(width=10, height=7):
    bottom = Image.new("RGBA", (width, height), (40, 80, 120, 255))
    top = Image.new("RGBA", (width, height), (220, 180, 60, 200))
    return [
        {"name": "Backdrop", "image": bottom, "blend_mode": "normal",
         "opacity": 1.0, "visible": True},
        {"name": "Tint", "image": top, "blend_mode": "multiply",
         "opacity": 0.5, "visible": False},
    ]


@pytest.mark.parametrize("compression", [0, 1])
def test_roundtrip_header_and_composite(tmp_path, compression):
    path = tmp_path / f"roundtrip_{compression}.psd"
    write_psd(path, _composite_image(), _layers(),
              compression=compression)
    parsed = parse_psd(path)
    assert parsed["signature"] == "8BPS"
    assert parsed["version"] == 1
    assert parsed["width"] == 10
    assert parsed["height"] == 7
    assert parsed["channels"] == 3
    assert parsed["depth"] == 8
    assert parsed["colour_mode"] == 3
    assert parsed["colour_mode_name"] == "RGB"
    assert parsed["composite_compression"] == compression
    image = decode_composite_image(parsed)
    assert image.size == (10, 7)
    assert np.array_equal(np.asarray(image),
                          np.asarray(_composite_image()))


@pytest.mark.parametrize("compression", [0, 1])
def test_roundtrip_layers(tmp_path, compression):
    path = tmp_path / f"layers_{compression}.psd"
    write_psd(path, _composite_image(), _layers(),
              compression=compression)
    parsed = parse_psd(path)
    assert parsed["layer_count"] == 2
    by_name = {layer["name"]: layer for layer in parsed["layers"]}
    assert set(by_name) == {"Backdrop", "Tint"}
    tint = by_name["Tint"]
    assert tint["blend_mode"] == "mul "
    assert tint["opacity"] == 128  # 0.5 * 255 rounds to 128
    assert tint["visible"] is False
    assert tint["bounds"] == {"top": 0, "left": 0, "bottom": 7,
                              "right": 10}
    assert tint["width"] == 10 and tint["height"] == 7
    channel_ids = {c["id"] for c in tint["channels"]}
    assert channel_ids == {0, 1, 2, -1}
    backdrop = by_name["Backdrop"]
    assert backdrop["blend_mode"] == "norm"
    assert backdrop["opacity"] == 255
    assert backdrop["visible"] is True


def test_roundtrip_layer_pixels_decoded(tmp_path):
    path = tmp_path / "pixels.psd"
    write_psd(path, _composite_image(), _layers(), compression=1)
    parsed = parse_psd(path)
    # Layers are stored top first in the file.
    top_pixels = parsed["_layer_channel_pixels"][0]
    red_plane = np.frombuffer(top_pixels[0], dtype=np.uint8)
    assert red_plane.size == 70
    assert (red_plane == 220).all()  # Tint layer red channel
    alpha_plane = np.frombuffer(top_pixels[-1], dtype=np.uint8)
    assert (alpha_plane == 200).all()


def test_roundtrip_no_layers(tmp_path):
    path = tmp_path / "flat.psd"
    write_psd(path, _composite_image(), [], compression=1)
    parsed = parse_psd(path)
    assert parsed["layer_count"] == 0
    image = decode_composite_image(path)
    assert np.array_equal(np.asarray(image),
                          np.asarray(_composite_image()))


def test_roundtrip_offset_layer_bounds(tmp_path):
    small = Image.new("RGBA", (4, 3), (10, 200, 90, 255))
    layers = [{"name": "Patch", "image": small,
               "blend_mode": "screen", "opacity": 0.25,
               "visible": True, "top": 2, "left": 3}]
    path = tmp_path / "offset.psd"
    write_psd(path, _composite_image(), layers, compression=0)
    parsed = parse_psd(path)
    (layer,) = parsed["layers"]
    assert layer["bounds"] == {"top": 2, "left": 3, "bottom": 5,
                               "right": 7}
    assert layer["blend_mode"] == "scrn"
    assert layer["opacity"] == 64  # 0.25 * 255 rounds to 64


def test_parse_rejects_non_psd(tmp_path):
    path = tmp_path / "nope.psd"
    path.write_bytes(b"this is not a psd file at all......")
    with pytest.raises(ValueError):
        parse_psd(path)
