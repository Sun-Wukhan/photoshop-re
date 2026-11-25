"""Layer compositing.

Layers are dictionaries with:

* ``rgba``: float array, shape (height, width, 4), values 0 to 1.
* ``blend_mode``: name from pslab.blends (default ``"normal"``).
* ``opacity``: 0 to 1 (default 1).
* ``mask``: optional float array, shape (height, width), values
  0 to 1, multiplying the layer alpha (white reveals, black hides).
* ``visible``: False skips the layer entirely.

Compositing follows the standard blend then source over model used
by PDF and Photoshop style renderers: the source colour is blended
with the accumulated backdrop colour, then the result is combined
by coverage using the effective alpha (source alpha times opacity
times mask). Layers are supplied bottom first.
"""

from __future__ import annotations

import numpy as np

from .blends import blend


def composite_layer(backdrop_rgba, layer) -> np.ndarray:
    """Composite one layer over an RGBA float backdrop."""
    if not layer.get("visible", True):
        return backdrop_rgba
    source = np.asarray(layer["rgba"], dtype=np.float64)
    if source.shape != backdrop_rgba.shape:
        raise ValueError("layer size must match the canvas")
    opacity = float(layer.get("opacity", 1.0))
    src_rgb = source[..., :3]
    src_alpha = source[..., 3] * opacity
    mask = layer.get("mask")
    if mask is not None:
        src_alpha = src_alpha * np.asarray(mask, dtype=np.float64)
    back_rgb = backdrop_rgba[..., :3]
    back_alpha = backdrop_rgba[..., 3]

    mode = layer.get("blend_mode", "normal")
    if mode == "normal":
        blended = src_rgb
    else:
        blended = blend(mode, back_rgb, src_rgb)
    # Weight the blended colour by how much backdrop there is, as
    # in the PDF compositing model: where the backdrop is empty the
    # raw source colour shows, where it is opaque the blend shows.
    mixed = (1.0 - back_alpha[..., None]) * src_rgb + \
        back_alpha[..., None] * blended

    a = src_alpha
    out_alpha = a + back_alpha * (1.0 - a)
    safe_alpha = np.where(out_alpha == 0, 1.0, out_alpha)
    out_rgb = (mixed * a[..., None] +
               back_rgb * (back_alpha * (1.0 - a))[..., None]) / \
        safe_alpha[..., None]
    out = np.dstack([np.clip(out_rgb, 0.0, 1.0), out_alpha])
    return out


def composite(layers, width: int, height: int) -> np.ndarray:
    """Composite a bottom first list of layers onto a transparent
    canvas of the given size. Returns a float RGBA array."""
    canvas = np.zeros((height, width, 4), dtype=np.float64)
    for layer in layers:
        canvas = composite_layer(canvas, layer)
    return canvas


def to_image(rgba) -> "object":
    """Convert a float RGBA array to a Pillow Image, flattening
    transparency onto transparency (kept as an alpha channel)."""
    from PIL import Image
    arr = np.clip(np.round(np.asarray(rgba) * 255.0), 0, 255)
    return Image.fromarray(arr.astype(np.uint8), mode="RGBA")


def layer_from_image(image, blend_mode="normal", opacity=1.0,
                     mask=None, visible=True) -> dict:
    """Build a layer dictionary from a Pillow Image (any mode)."""
    rgba = image.convert("RGBA")
    arr = np.asarray(rgba, dtype=np.float64) / 255.0
    return {
        "rgba": arr,
        "blend_mode": blend_mode,
        "opacity": opacity,
        "mask": mask,
        "visible": visible,
    }
