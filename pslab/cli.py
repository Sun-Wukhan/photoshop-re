"""Command line interface.

Usage:
    python -m pslab info file.psd
    python -m pslab flatten file.psd out.png
    python -m pslab demo out.png
"""

from __future__ import annotations

import argparse
import json
import sys

import numpy as np

from .composite import composite, layer_from_image, to_image
from .psd import decode_composite_image, parse_psd


def _public_report(parsed: dict) -> dict:
    return {k: v for k, v in parsed.items() if not k.startswith("_")}


def cmd_info(args) -> int:
    parsed = parse_psd(args.file)
    print(json.dumps(_public_report(parsed), indent=2))
    return 0


def cmd_flatten(args) -> int:
    image = decode_composite_image(args.file)
    image.save(args.out)
    print(f"wrote {args.out} ({image.size[0]}x{image.size[1]}, "
          f"mode {image.mode})")
    return 0


def _gradient(width, height, top, bottom):
    from PIL import Image
    top = np.array(top, dtype=np.float64)
    bottom = np.array(bottom, dtype=np.float64)
    t = np.linspace(0.0, 1.0, height)[:, None, None]
    row = top[None, None, :] * (1 - t) + bottom[None, None, :] * t
    arr = np.repeat(row, width, axis=1)
    rgba = np.dstack([arr, np.ones((height, width))])
    return Image.fromarray((rgba * 255).astype(np.uint8), mode="RGBA")


def _disc(width, height, centre, radius, colour):
    from PIL import Image
    yy, xx = np.mgrid[0:height, 0:width]
    dist = np.sqrt((xx - centre[0]) ** 2 + (yy - centre[1]) ** 2)
    alpha = np.clip(radius - dist, 0.0, 1.0)
    rgb = np.zeros((height, width, 3))
    for i in range(3):
        rgb[..., i] = colour[i]
    rgba = np.dstack([rgb, alpha])
    return Image.fromarray((rgba * 255).astype(np.uint8), mode="RGBA")


def cmd_demo(args) -> int:
    """Build a synthetic composition with the engine itself: a
    gradient backdrop, a multiply disc, a screen disc and an
    overlay band, then save the flattened result."""
    from PIL import Image
    width, height = 320, 240
    backdrop = layer_from_image(
        _gradient(width, height, (0.20, 0.35, 0.65),
                  (0.85, 0.90, 0.98)), "normal", 1.0)
    shadow = layer_from_image(
        _disc(width, height, (110, 105), 70, (0.15, 0.10, 0.35)),
        "multiply", 0.85)
    glow = layer_from_image(
        _disc(width, height, (215, 90), 55, (0.95, 0.75, 0.35)),
        "screen", 0.9)
    band_arr = np.zeros((height, width, 4))
    band_arr[150:190, :, :3] = (0.9, 0.3, 0.25)
    band_arr[150:190, :, 3] = 1.0
    band = {"rgba": band_arr, "blend_mode": "overlay",
            "opacity": 0.7, "mask": None, "visible": True}
    result = composite([backdrop, shadow, glow, band], width, height)
    image = to_image(result)
    image.convert("RGB").save(args.out)
    check = Image.open(args.out)
    check.load()
    print(f"wrote {args.out} ({check.size[0]}x{check.size[1]}, "
          f"mode {check.mode})")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="pslab",
        description="Clean room PSD parser and blend engine.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_info = sub.add_parser("info", help="print a JSON report for a PSD")
    p_info.add_argument("file")
    p_info.set_defaults(func=cmd_info)

    p_flat = sub.add_parser("flatten",
                            help="render the composite image to PNG")
    p_flat.add_argument("file")
    p_flat.add_argument("out")
    p_flat.set_defaults(func=cmd_flatten)

    p_demo = sub.add_parser("demo",
                            help="generate a synthetic composition")
    p_demo.add_argument("out")
    p_demo.set_defaults(func=cmd_demo)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
