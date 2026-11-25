"""Basic image adjustments, implemented from scratch on numpy
arrays (with Pillow used only for the blur kernel and colour space
conversion in the hue and saturation adjustment).

All functions accept and return float arrays with values 0 to 1,
shape (height, width, 3) for RGB (alpha channels, if present, are
passed through untouched by the adjustments that work per channel).
"""

from __future__ import annotations

import numpy as np


def _split_alpha(arr):
    arr = np.asarray(arr, dtype=np.float64)
    if arr.shape[-1] == 4:
        return arr[..., :3], arr[..., 3:4]
    return arr, None


def _join(rgb, alpha):
    if alpha is None:
        return rgb
    return np.concatenate([rgb, alpha], axis=-1)


def gaussian_blur(arr, radius: float = 2.0):
    """Gaussian blur via Pillow's kernel, applied per plane so an
    alpha channel blurs the same way as the colour channels."""
    from PIL import Image, ImageFilter
    planes = []
    source = np.asarray(arr, dtype=np.float64)
    for index in range(source.shape[-1]):
        plane = Image.fromarray(
            np.clip(source[..., index] * 255, 0, 255).astype(np.uint8))
        blurred = plane.filter(ImageFilter.GaussianBlur(radius))
        planes.append(np.asarray(blurred, dtype=np.float64) / 255.0)
    return np.stack(planes, axis=-1)


def levels(arr, in_black=0.0, in_white=1.0, gamma=1.0,
           out_black=0.0, out_white=1.0):
    """Levels adjustment: remap the input range to the output range
    with a mid tone gamma curve in between, per channel."""
    if in_white <= in_black:
        raise ValueError("in_white must be greater than in_black")
    rgb, alpha = _split_alpha(arr)
    mapped = np.clip((rgb - in_black) / (in_white - in_black), 0.0, 1.0)
    if gamma != 1.0:
        mapped = np.power(mapped, 1.0 / gamma)
    out = out_black + mapped * (out_white - out_black)
    return _join(np.clip(out, 0.0, 1.0), alpha)


def brightness_contrast(arr, brightness=0.0, contrast=0.0):
    """Brightness shifts every value (range -1 to 1); contrast
    scales values around mid grey (range -1 to 1, positive values
    increase contrast using the standard tangent style factor)."""
    rgb, alpha = _split_alpha(arr)
    out = rgb + brightness
    if contrast != 0.0:
        factor = (1.0 + contrast) / max(1e-6, (1.0 - contrast)) \
            if contrast >= 0 else (1.0 + contrast)
        out = (out - 0.5) * factor + 0.5
    return _join(np.clip(out, 0.0, 1.0), alpha)


def hue_saturation(arr, hue_shift=0.0, saturation=0.0, lightness=0.0):
    """Hue, saturation and lightness adjustment in HSL space.
    hue_shift is in turns (-0.5 to 0.5), saturation and lightness
    are -1 to 1 adjustments (saturation scales multiplicatively
    above zero and fades to grey below zero)."""
    from PIL import Image
    rgb, alpha = _split_alpha(arr)
    image = Image.fromarray(
        np.clip(rgb * 255, 0, 255).astype(np.uint8), mode="RGB")
    hsv = np.asarray(image.convert("HSV"), dtype=np.float64)
    hsv[..., 0] = (hsv[..., 0] + hue_shift * 255.0) % 255.0
    # Saturation scales multiplicatively: -1 removes all colour,
    # +1 doubles it (clipped). Predictable at both extremes.
    s = np.clip((hsv[..., 1] / 255.0) * (1.0 + saturation), 0.0, 1.0)
    hsv[..., 1] = s * 255.0
    v = hsv[..., 2] / 255.0
    v = np.clip(v + lightness, 0.0, 1.0)
    hsv[..., 2] = v * 255.0
    out = Image.fromarray(hsv.astype(np.uint8), mode="HSV").convert("RGB")
    return _join(np.asarray(out, dtype=np.float64) / 255.0, alpha)


def invert(arr):
    """Photographic negative: every colour channel becomes 1 - v.
    Alpha is untouched."""
    rgb, alpha = _split_alpha(arr)
    return _join(1.0 - rgb, alpha)


def grayscale(arr):
    """Desaturate to luminance (Rec. 601 weights), keeping three
    identical channels so the result is still an RGB array."""
    rgb, alpha = _split_alpha(arr)
    lum = rgb @ np.array([0.299, 0.587, 0.114])
    grey = np.stack([lum, lum, lum], axis=-1)
    return _join(grey, alpha)


# Friendly alias matching the usual menu wording.
desaturate = grayscale
