import numpy as np
import pytest

from pslab import filters
from pslab.composite import composite, composite_layer


def solid(height, width, rgba):
    arr = np.zeros((height, width, 4))
    arr[..., 0] = rgba[0]
    arr[..., 1] = rgba[1]
    arr[..., 2] = rgba[2]
    arr[..., 3] = rgba[3]
    return arr


def layer(rgba, mode="normal", opacity=1.0, mask=None, visible=True):
    return {"rgba": rgba, "blend_mode": mode, "opacity": opacity,
            "mask": mask, "visible": visible}


def test_opacity_zero_leaves_backdrop_unchanged():
    backdrop = solid(3, 3, (0.2, 0.4, 0.6, 1.0))
    top = layer(solid(3, 3, (1.0, 0.0, 0.0, 1.0)), opacity=0.0)
    out = composite_layer(backdrop, top)
    assert out == pytest.approx(backdrop)


def test_opaque_normal_top_replaces_backdrop():
    backdrop = solid(2, 2, (0.2, 0.4, 0.6, 1.0))
    top = layer(solid(2, 2, (0.9, 0.1, 0.3, 1.0)))
    out = composite_layer(backdrop, top)
    assert out[..., :3] == pytest.approx(
        np.full((2, 2, 3), [0.9, 0.1, 0.3]))
    assert out[..., 3] == pytest.approx(np.ones((2, 2)))


def test_half_opacity_normal_blends_halfway():
    backdrop = solid(2, 2, (0.0, 0.0, 0.0, 1.0))
    top = layer(solid(2, 2, (1.0, 1.0, 1.0, 1.0)), opacity=0.5)
    out = composite_layer(backdrop, top)
    assert out[..., :3] == pytest.approx(np.full((2, 2, 3), 0.5))


def test_hidden_layer_is_skipped():
    backdrop = solid(2, 2, (0.3, 0.3, 0.3, 1.0))
    top = layer(solid(2, 2, (1.0, 1.0, 1.0, 1.0)), visible=False)
    out = composite_layer(backdrop, top)
    assert out == pytest.approx(backdrop)


def test_mask_hides_layer_where_black():
    backdrop = solid(2, 2, (0.0, 0.0, 1.0, 1.0))
    mask = np.array([[0.0, 1.0], [1.0, 0.0]])
    top = layer(solid(2, 2, (1.0, 0.0, 0.0, 1.0)), mask=mask)
    out = composite_layer(backdrop, top)
    assert out[0, 0, :3] == pytest.approx([0.0, 0.0, 1.0])
    assert out[0, 1, :3] == pytest.approx([1.0, 0.0, 0.0])
    assert out[1, 0, :3] == pytest.approx([1.0, 0.0, 0.0])
    assert out[1, 1, :3] == pytest.approx([0.0, 0.0, 1.0])


def test_multiply_layer_over_white_backdrop():
    white = layer(solid(2, 2, (1.0, 1.0, 1.0, 1.0)))
    grey = layer(solid(2, 2, (0.5, 0.5, 0.5, 1.0)), mode="multiply")
    out = composite([white, grey], 2, 2)
    assert out[..., :3] == pytest.approx(np.full((2, 2, 3), 0.5))


def test_transparent_canvas_keeps_alpha():
    half = layer(solid(2, 2, (1.0, 0.0, 0.0, 0.5)))
    out = composite([half], 2, 2)
    assert out[..., 3] == pytest.approx(np.full((2, 2), 0.5))
    assert out[..., 0] == pytest.approx(np.ones((2, 2)))


def test_filters_invert_and_grayscale():
    arr = np.array([[[0.25, 0.5, 1.0]]])
    assert filters.invert(arr)[0, 0] == pytest.approx([0.75, 0.5, 0.0])
    grey = filters.grayscale(np.array([[[0.5, 0.5, 0.5]]]))
    assert grey[0, 0] == pytest.approx([0.5, 0.5, 0.5])
    coloured = filters.grayscale(np.array([[[1.0, 0.0, 0.0]]]))
    assert coloured[0, 0] == pytest.approx([0.299, 0.299, 0.299])


def test_filters_levels_identity_and_stretch():
    arr = np.array([[[0.25, 0.5, 0.75]]])
    assert filters.levels(arr)[0, 0] == pytest.approx(arr[0, 0])
    stretched = filters.levels(arr, in_black=0.25, in_white=0.75)
    assert stretched[0, 0] == pytest.approx([0.0, 0.5, 1.0])


def test_filters_brightness_contrast():
    arr = np.array([[[0.5, 0.5, 0.5]]])
    assert filters.brightness_contrast(arr, brightness=0.25)[0, 0] == \
        pytest.approx([0.75, 0.75, 0.75])
    assert filters.brightness_contrast(arr, contrast=0.5)[0, 0] == \
        pytest.approx([0.5, 0.5, 0.5])  # mid grey is the pivot


def test_filters_blur_keeps_constant_image():
    arr = np.full((9, 9, 3), 0.4)
    out = filters.gaussian_blur(arr, radius=2.0)
    assert out.shape == arr.shape
    assert out == pytest.approx(arr, abs=0.01)


def test_filters_hue_saturation_desaturate():
    red = np.array([[[1.0, 0.0, 0.0]]])
    out = filters.hue_saturation(red, saturation=-1.0)
    assert out[0, 0, 0] == pytest.approx(out[0, 0, 1], abs=0.02)
    assert out[0, 0, 1] == pytest.approx(out[0, 0, 2], abs=0.02)
    unchanged = filters.hue_saturation(red)
    assert unchanged[0, 0] == pytest.approx([1.0, 0.0, 0.0], abs=0.02)
