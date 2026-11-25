"""Generate a piece of art using only the pslab engine.

A layered composition in the Photoshop style: a gradient sky as the
base layer, a sun blended with screen, a warm glow blended with
colour dodge through a radial mask, mountain silhouettes blended
with multiply, and foreground hills blended with overlay. The
flattened result is finished with the levels and hue/saturation
filters. No image editor and no third party assets are involved;
every pixel comes from numpy arrays composited by pslab.

Run:  python examples/make_engine_art.py examples/engine-art.png
"""

from __future__ import annotations

import math
import sys

import numpy as np

from pslab.composite import composite, to_image
from pslab.filters import gaussian_blur, hue_saturation, levels

WIDTH, HEIGHT = 960, 640


def rgba_from_rgb(rgb, alpha=1.0):
    alpha_arr = np.full(rgb.shape[:2] + (1,), alpha, dtype=np.float64)
    return np.dstack([rgb, alpha_arr])


def gradient(top, bottom):
    t = np.linspace(0.0, 1.0, HEIGHT)[:, None, None]
    top = np.array(top, dtype=np.float64)[None, None, :]
    bottom = np.array(bottom, dtype=np.float64)[None, None, :]
    return np.repeat((top * (1.0 - t) + bottom * t), WIDTH, axis=1)


def disc(cx, cy, radius, colour):
    yy, xx = np.mgrid[0:HEIGHT, 0:WIDTH]
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    alpha = np.clip((radius - dist) / 6.0, 0.0, 1.0)
    rgb = np.zeros((HEIGHT, WIDTH, 3), dtype=np.float64)
    rgb[:] = colour
    return np.dstack([rgb, alpha])


def radial_mask(cx, cy, radius):
    yy, xx = np.mgrid[0:HEIGHT, 0:WIDTH]
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    return np.clip(1.0 - dist / radius, 0.0, 1.0) ** 2


def ridge(base_y, amp, colour, seed):
    rng = np.random.default_rng(seed)
    xs = np.arange(WIDTH, dtype=np.float64)
    line = base_y + amp * np.sin(xs / 90.0 + seed) \
        + (amp / 2.5) * np.sin(xs / 37.0 + seed * 2.0)
    smooth = np.convolve(
        np.pad(line, 12, mode="edge"), np.ones(25) / 25.0, mode="valid")
    yy = np.arange(HEIGHT, dtype=np.float64)[:, None]
    alpha = (yy >= smooth[None, :]).astype(np.float64)
    rgb = np.zeros((HEIGHT, WIDTH, 3), dtype=np.float64)
    rgb[:] = colour
    return np.dstack([rgb, alpha])


def main(out_path):
    sky = rgba_from_rgb(gradient((0.10, 0.16, 0.38), (0.98, 0.55, 0.28)))
    sun = disc(620, 330, 92, (1.0, 0.83, 0.45))
    glow_rgb = np.zeros((HEIGHT, WIDTH, 3), dtype=np.float64)
    glow_rgb[:] = (1.0, 0.45, 0.15)
    glow = gaussian_blur(
        np.dstack([glow_rgb, np.ones((HEIGHT, WIDTH))]), radius=30.0)
    far = ridge(395, 26, (0.32, 0.24, 0.42), seed=3)
    near = ridge(480, 34, (0.16, 0.20, 0.30), seed=7)

    layers = [
        {"rgba": sky, "blend_mode": "normal", "opacity": 1.0},
        {"rgba": glow, "blend_mode": "color_dodge", "opacity": 0.55,
         "mask": radial_mask(620, 330, 420)},
        {"rgba": sun, "blend_mode": "screen", "opacity": 0.95},
        {"rgba": far, "blend_mode": "multiply", "opacity": 0.85},
        {"rgba": near, "blend_mode": "overlay", "opacity": 0.92},
    ]
    result = composite(layers, WIDTH, HEIGHT)
    result = levels(result, in_black=0.02, in_white=0.98, gamma=1.05)
    result = hue_saturation(result, saturation=0.12)
    image = to_image(result)
    image.save(out_path)
    print(f"wrote {out_path}: {image.size[0]}x{image.size[1]} {image.mode}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "examples/engine-art.png")
