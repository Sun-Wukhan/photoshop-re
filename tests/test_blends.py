import numpy as np
import pytest

from pslab import blends
from pslab.blends import blend


def px(values):
    return np.array([[values]], dtype=np.float64)


def test_mode_count_and_names():
    # 26 modes are implemented. Dissolve is excluded on purpose
    # because it is randomised and has no closed form formula.
    assert len(blends.BLEND_MODES) == 26
    assert "dissolve" not in blends.BLEND_MODES
    for name in ("normal", "multiply", "screen", "overlay",
                 "soft_light", "hard_mix", "hue", "luminosity"):
        assert name in blends.BLEND_MODES


def test_multiply_mid_grey():
    out = blend("multiply", px([0.5, 0.5, 0.5]), px([0.5, 0.5, 0.5]))
    assert out[0, 0] == pytest.approx([0.25, 0.25, 0.25])


def test_multiply_white_is_neutral_black_is_absorbing():
    b = px([0.3, 0.6, 0.9])
    assert blend("multiply", b, px([1, 1, 1]))[0, 0] == pytest.approx(b[0, 0])
    assert blend("multiply", b, px([0, 0, 0]))[0, 0] == pytest.approx([0, 0, 0])


def test_screen_is_inverse_multiply():
    rng = np.random.default_rng(7)
    b = rng.random((4, 5, 3))
    s = rng.random((4, 5, 3))
    screened = blend("screen", b, s)
    expected = 1.0 - blend("multiply", 1 - b, 1 - s)
    assert screened == pytest.approx(expected)
    assert blend("screen", px([0.5] * 3), px([0.5] * 3))[0, 0] == \
        pytest.approx([0.75] * 3)


def test_overlay_mid_grey_source_is_neutral():
    rng = np.random.default_rng(3)
    b = rng.random((6, 6, 3))
    out = blend("overlay", b, np.full_like(b, 0.5))
    assert out == pytest.approx(b)


def test_overlay_hand_value():
    # b = 0.25 (below half): 2 * 0.25 * 0.5 = 0.25
    out = blend("overlay", px([0.25] * 3), px([0.5] * 3))
    assert out[0, 0] == pytest.approx([0.25] * 3)
    # b = 0.75 (above half): 1 - 2 * 0.25 * 0.5 = 0.75
    out = blend("overlay", px([0.75] * 3), px([0.5] * 3))
    assert out[0, 0] == pytest.approx([0.75] * 3)


def test_soft_light_mid_grey_neutral():
    rng = np.random.default_rng(11)
    b = rng.random((5, 5, 3))
    out = blend("soft_light", b, np.full_like(b, 0.5))
    assert out == pytest.approx(b, abs=1e-9)


def test_darken_and_lighten():
    b = px([0.2, 0.8, 0.5])
    s = px([0.6, 0.4, 0.5])
    assert blend("darken", b, s)[0, 0] == pytest.approx([0.2, 0.4, 0.5])
    assert blend("lighten", b, s)[0, 0] == pytest.approx([0.6, 0.8, 0.5])


def test_linear_burn_and_dodge():
    assert blend("linear_burn", px([0.7] * 3), px([0.5] * 3))[0, 0] == \
        pytest.approx([0.2] * 3)
    assert blend("linear_dodge", px([0.7] * 3), px([0.5] * 3))[0, 0] == \
        pytest.approx([1.0] * 3)


def test_difference_identical_is_black_and_white_inverts():
    b = px([0.25, 0.5, 0.75])
    assert blend("difference", b, b)[0, 0] == pytest.approx([0, 0, 0])
    assert blend("difference", b, px([1, 1, 1]))[0, 0] == \
        pytest.approx([0.75, 0.5, 0.25])


def test_exclusion_black_neutral_white_inverts():
    b = px([0.25, 0.5, 0.75])
    assert blend("exclusion", b, px([0, 0, 0]))[0, 0] == pytest.approx(b[0, 0])
    assert blend("exclusion", b, px([1, 1, 1]))[0, 0] == \
        pytest.approx(1 - b[0, 0])


def test_color_burn_and_dodge_edges():
    assert blend("color_burn", px([0.5] * 3), px([0.0] * 3))[0, 0] == \
        pytest.approx([0] * 3)
    assert blend("color_dodge", px([0.5] * 3), px([1.0] * 3))[0, 0] == \
        pytest.approx([1] * 3)
    # color burn by white is neutral, dodge by black is neutral
    b = px([0.3, 0.6, 0.9])
    assert blend("color_burn", b, px([1, 1, 1]))[0, 0] == pytest.approx(b[0, 0])
    assert blend("color_dodge", b, px([0, 0, 0]))[0, 0] == pytest.approx(b[0, 0])


def test_subtract_and_divide():
    assert blend("subtract", px([0.8] * 3), px([0.3] * 3))[0, 0] == \
        pytest.approx([0.5] * 3)
    assert blend("subtract", px([0.2] * 3), px([0.5] * 3))[0, 0] == \
        pytest.approx([0] * 3)
    assert blend("divide", px([0.4] * 3), px([0.5] * 3))[0, 0] == \
        pytest.approx([0.8] * 3)
    b = px([0.3, 0.6, 0.9])
    assert blend("divide", b, px([1, 1, 1]))[0, 0] == pytest.approx(b[0, 0])


def test_hard_mix_only_extremes():
    rng = np.random.default_rng(5)
    out = blend("hard_mix", rng.random((8, 8, 3)), rng.random((8, 8, 3)))
    assert set(np.unique(out)).issubset({0.0, 1.0})


def test_darker_and_lighter_color_pick_whole_pixels():
    dark = px([0.1, 0.1, 0.1])
    light = px([0.9, 0.2, 0.2])  # brighter overall than dark
    assert blend("darker_color", light, dark)[0, 0] == pytest.approx(dark[0, 0])
    assert blend("lighter_color", dark, light)[0, 0] == \
        pytest.approx(light[0, 0])


def test_luminosity_takes_source_luminance():
    b = px([0.4, 0.5, 0.6])
    s = px([0.8, 0.2, 0.2])
    out = blend("luminosity", b, s)
    lum_out = float(out[0, 0] @ np.array([0.30, 0.59, 0.11]))
    lum_s = float(s[0, 0] @ np.array([0.30, 0.59, 0.11]))
    assert lum_out == pytest.approx(lum_s, abs=0.02)


def test_color_takes_backdrop_luminance():
    b = px([0.4, 0.5, 0.6])
    s = px([0.8, 0.2, 0.2])
    out = blend("color", b, s)
    lum_out = float(out[0, 0] @ np.array([0.30, 0.59, 0.11]))
    lum_b = float(b[0, 0] @ np.array([0.30, 0.59, 0.11]))
    assert lum_out == pytest.approx(lum_b, abs=0.02)


def test_hue_and_saturation_run_and_stay_in_range():
    rng = np.random.default_rng(9)
    b = rng.random((4, 4, 3))
    s = rng.random((4, 4, 3))
    for mode in ("hue", "saturation", "color", "luminosity"):
        out = blend(mode, b, s)
        assert out.min() >= 0.0 and out.max() <= 1.0


def test_grey_backdrop_stays_grey_for_component_modes():
    grey = px([0.5, 0.5, 0.5])
    s = px([0.9, 0.1, 0.3])
    out = blend("saturation", grey, s)
    assert out[0, 0] == pytest.approx([0.5, 0.5, 0.5], abs=0.02)


def test_unknown_mode_raises():
    with pytest.raises(ValueError):
        blend("dissolve", px([0.5] * 3), px([0.5] * 3))


def test_psd_key_mapping_round_trip():
    from pslab.blends import MODE_TO_PSD_KEY, PSD_KEY_TO_MODE
    assert PSD_KEY_TO_MODE["mul "] == "multiply"
    assert PSD_KEY_TO_MODE["norm"] == "normal"
    for mode, key in MODE_TO_PSD_KEY.items():
        assert PSD_KEY_TO_MODE[key] == mode
    assert len(MODE_TO_PSD_KEY) == 26
