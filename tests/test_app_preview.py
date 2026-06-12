import numpy as np

from biofilm_analyzer.app import _normalize_slice_uint8, _overlay_masks_rgb


def test_normalize_slice_uint8_handles_constant_image() -> None:
    image = np.full((3, 4), 5, dtype=np.float32)

    normalized = _normalize_slice_uint8(image, 1, 99)

    assert normalized.shape == image.shape
    assert normalized.dtype == np.uint8
    assert np.all(normalized == 0)


def test_overlay_masks_rgb_blends_selected_pixels_only() -> None:
    image = np.array([[0, 10], [20, 30]], dtype=np.float32)
    mask = np.array([[False, True], [False, False]])

    rgb = _overlay_masks_rgb(image, [(mask, (0, 255, 0))], 1.0, 0, 100)

    assert rgb.shape == (2, 2, 3)
    assert np.array_equal(rgb[0, 1], np.array([0, 255, 0], dtype=np.uint8))
    assert np.array_equal(rgb[0, 0], np.array([0, 0, 0], dtype=np.uint8))
    assert not np.array_equal(rgb[1, 1], np.array([0, 255, 0], dtype=np.uint8))
