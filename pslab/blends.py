"""Clean room blend modes.

Each function takes two numpy arrays of float RGB values in the
range 0.0 to 1.0, the backdrop (base) first and the source (blend)
second, with shape (..., 3), and returns the blended result in the
same range. The formula for each mode is stated in plain words in
its docstring. These are original implementations of widely
documented mathematical operations; no Adobe code was used.

Dissolve is deliberately not implemented: it is a randomised
dither that scatters source and backdrop pixels based on opacity,
so it has no closed form formula to reimplement faithfully.
"""

from __future__ import annotations

import numpy as np

EPS = 1e-12


def _clip(values):
    return np.clip(values, 0.0, 1.0)


# --- Darken family -------------------------------------------------

def darken(b, s):
    """Per channel minimum of backdrop and source."""
    return np.minimum(b, s)


def multiply(b, s):
    """Per channel product. White source leaves the backdrop
    unchanged; black source gives black."""
    return b * s


def color_burn(b, s):
    """Inverted, divided, inverted again: 1 - (1 - b) / s.
    A zero source channel gives black."""
    return _clip(1.0 - (1.0 - b) / np.where(s == 0, EPS, s)) * (s != 0)


def linear_burn(b, s):
    """Sum minus one, clipped at zero: max(b + s - 1, 0)."""
    return _clip(b + s - 1.0)


def _luminance(rgb):
    """Rec. 601 style luma used for whole pixel comparisons."""
    return rgb @ np.array([0.299, 0.587, 0.114])


def darker_color(b, s):
    """Whole pixel comparison: whichever pixel is darker overall
    (by summed luminance) wins, channels are not mixed."""
    choose_s = (_luminance(s) < _luminance(b))[..., None]
    return np.where(choose_s, s, b)


# --- Lighten family ------------------------------------------------

def lighten(b, s):
    """Per channel maximum of backdrop and source."""
    return np.maximum(b, s)


def screen(b, s):
    """Inverted multiply of the inverses: 1 - (1 - b)(1 - s).
    Black source leaves the backdrop unchanged."""
    return 1.0 - (1.0 - b) * (1.0 - s)


def color_dodge(b, s):
    """Backdrop divided by the inverted source: b / (1 - s).
    A white source channel gives white."""
    return _clip(b / np.where(s == 1, EPS, 1.0 - s)) * (s != 1) + (s == 1) * 1.0


def linear_dodge(b, s):
    """Plain sum, clipped at one: min(b + s, 1). Also called add."""
    return _clip(b + s)


def lighter_color(b, s):
    """Whole pixel comparison: whichever pixel is lighter overall
    wins, channels are not mixed."""
    choose_s = (_luminance(s) > _luminance(b))[..., None]
    return np.where(choose_s, s, b)


# --- Contrast family -----------------------------------------------

def overlay(b, s):
    """Multiply below mid grey, screen above it, keyed on the
    backdrop: 2bs when b < 0.5, else 1 - 2(1 - b)(1 - s).
    A 50 percent grey source is neutral."""
    return np.where(b < 0.5, 2.0 * b * s,
                    1.0 - 2.0 * (1.0 - b) * (1.0 - s))


def _pegtop_soft_light(b, s):
    """A smooth soft light curve: for s below 0.5 the backdrop is
    darkened by a scaled multiply, above 0.5 it is lightened using
    a square root based screen like term."""
    d = ((16.0 * b - 12.0) * b + 4.0) * b  # polynomial approximation
    return np.where(s <= 0.5,
                    b - (1.0 - 2.0 * s) * b * (1.0 - b),
                    b + (2.0 * s - 1.0) * (d - b))


def soft_light(b, s):
    """A gentle version of overlay keyed on the source, using the
    Pegtop style smooth curve. 50 percent grey source is neutral."""
    return _clip(_pegtop_soft_light(b, s))


def hard_light(b, s):
    """Overlay with the roles swapped, keyed on the source:
    2bs when s < 0.5, else 1 - 2(1 - b)(1 - s)."""
    return np.where(s < 0.5, 2.0 * b * s,
                    1.0 - 2.0 * (1.0 - b) * (1.0 - s))


def vivid_light(b, s):
    """Colour burn for dark sources, colour dodge for light ones,
    with the source doubled away from mid grey."""
    dark = color_burn(b, 2.0 * s)
    light = color_dodge(b, 2.0 * (s - 0.5))
    return np.where(s < 0.5, dark, light)


def linear_light(b, s):
    """Linear burn for dark sources, linear dodge for light ones,
    with the source doubled away from mid grey."""
    return _clip(np.where(s < 0.5, b + 2.0 * s - 1.0, b + 2.0 * (s - 0.5)))


def pin_light(b, s):
    """Darken for dark sources, lighten for light ones, with the
    source doubled away from mid grey."""
    return np.where(s < 0.5, np.minimum(b, 2.0 * s),
                    np.maximum(b, 2.0 * (s - 0.5)))


def hard_mix(b, s):
    """Vivid light pushed to the nearest extreme: every channel
    becomes either 0 or 1 depending on whether vivid light is
    below or at least 0.5."""
    return (vivid_light(b, s) >= 0.5).astype(np.float64)


# --- Inversion family ----------------------------------------------

def difference(b, s):
    """Absolute per channel difference: abs(b - s). Identical
    colours give black; white source inverts."""
    return np.abs(b - s)


def exclusion(b, s):
    """A softer difference: b + s - 2bs. Mid grey source gives a
    low contrast result; white inverts, black is neutral."""
    return b + s - 2.0 * b * s


def subtract(b, s):
    """Backdrop minus source, clipped at zero: max(b - s, 0).
    Negative results become black."""
    return _clip(b - s)


def divide(b, s):
    """Backdrop divided by source: b / s. White source is neutral,
    a zero source channel gives white."""
    return _clip(b / np.where(s == 0, EPS, s)) * (s != 0) + (s == 0) * 1.0


# --- Component (non separable) modes -------------------------------
# These treat the colour as a whole. They use the luminosity and
# saturation helpers from the PDF reference blend mode
# specification, which Photoshop style component modes follow.

def _lum(c):
    return c @ np.array([0.30, 0.59, 0.11])


def _sat(c):
    return c.max(axis=-1) - c.min(axis=-1)


def _clip_colour(c):
    """Clip a colour back into gamut while holding luminosity."""
    lum = _lum(c)[..., None]
    cmin = c.min(axis=-1, keepdims=True)
    cmax = c.max(axis=-1, keepdims=True)
    out = c.copy()
    below = (cmin < 0.0)[..., 0]
    if np.any(below):
        cc = out[below]
        ll = lum[below]
        out[below] = ll + (cc - ll) * (ll / (ll - cmin[below]))
    above = (cmax > 1.0)[..., 0]
    if np.any(above):
        cc = out[above]
        ll = lum[above]
        out[above] = ll + (cc - ll) * ((1.0 - ll) / (cmax[above] - ll))
    return out


def _set_lum(c, lum):
    return _clip_colour(c + (lum - _lum(c))[..., None])


def _set_sat(c, sat):
    """Rescale a colour so its saturation (max minus min channel)
    equals the requested value, keeping channel ordering."""
    cmin = c.min(axis=-1, keepdims=True)
    cmax = c.max(axis=-1, keepdims=True)
    spread = cmax - cmin
    out = np.zeros_like(c)
    has_spread = (spread[..., 0] > 0)
    if np.any(has_spread):
        cc = c[has_spread]
        mn = cmin[has_spread]
        mx = cmax[has_spread]
        # Shifting by the minimum puts the smallest channel at 0;
        # scaling by sat / spread puts the largest at sat, and any
        # middle channel lands proportionally in between.
        out[has_spread] = (cc - mn) * (sat[has_spread][:, None] /
                                       (mx - mn))
    return out


def hue(b, s):
    """Saturation and hue of the source, luminosity of the
    backdrop."""
    return _set_lum(_set_sat(s, _sat(b)), _lum(b))


def saturation(b, s):
    """Saturation of the source, hue and luminosity of the
    backdrop."""
    return _set_lum(_set_sat(b, _sat(s)), _lum(b))


def color(b, s):
    """Hue and saturation of the source (its colour), luminosity
    of the backdrop. The classic colourise mode."""
    return _set_lum(s, _lum(b))


def luminosity(b, s):
    """Luminosity of the source, hue and saturation of the
    backdrop. The inverse of colour."""
    return _set_lum(b, _lum(s))


def normal(b, s):
    """The source replaces the backdrop (blending step only;
    opacity and alpha are applied by the compositor)."""
    return s.copy()


BLEND_MODES = {
    "normal": normal,
    "darken": darken,
    "multiply": multiply,
    "color_burn": color_burn,
    "linear_burn": linear_burn,
    "darker_color": darker_color,
    "lighten": lighten,
    "screen": screen,
    "color_dodge": color_dodge,
    "linear_dodge": linear_dodge,
    "lighter_color": lighter_color,
    "overlay": overlay,
    "soft_light": soft_light,
    "hard_light": hard_light,
    "vivid_light": vivid_light,
    "linear_light": linear_light,
    "pin_light": pin_light,
    "hard_mix": hard_mix,
    "difference": difference,
    "exclusion": exclusion,
    "subtract": subtract,
    "divide": divide,
    "hue": hue,
    "saturation": saturation,
    "color": color,
    "luminosity": luminosity,
}

# PSD files store blend modes as four character keys.
PSD_KEY_TO_MODE = {
    "norm": "normal",
    "dark": "darken",
    "mul ": "multiply",
    "idiv": "color_burn",
    "lbrn": "linear_burn",
    "dkCl": "darker_color",
    "lite": "lighten",
    "scrn": "screen",
    "div ": "color_dodge",
    "lddg": "linear_dodge",
    "ltCl": "lighter_color",
    "over": "overlay",
    "sLit": "soft_light",
    "hLit": "hard_light",
    "vLit": "vivid_light",
    "lLit": "linear_light",
    "pLit": "pin_light",
    "hMix": "hard_mix",
    "diff": "difference",
    "smud": "exclusion",
    "fsub": "subtract",
    "fdiv": "divide",
    "hue ": "hue",
    "sat ": "saturation",
    "colr": "color",
    "lum ": "luminosity",
}

MODE_TO_PSD_KEY = {v: k for k, v in PSD_KEY_TO_MODE.items()}


def blend(name: str, backdrop, source):
    """Apply a named blend mode to float RGB arrays."""
    try:
        function = BLEND_MODES[name]
    except KeyError:
        raise ValueError(f"unknown blend mode {name!r}") from None
    b = np.asarray(backdrop, dtype=np.float64)
    s = np.asarray(source, dtype=np.float64)
    return _clip(function(b, s))
