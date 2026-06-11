from pathlib import Path

import numpy as np
from PIL import Image
import pytest

from biofilm_analyzer.io import load_png_stack


def test_load_png_stack_groups_channels_and_sorts_slices(tmp_path: Path) -> None:
    _write_png(tmp_path / "sample_AO_z002.png", np.full((3, 4), 20, dtype=np.uint8))
    _write_png(tmp_path / "sample_AO_z001.png", np.full((3, 4), 10, dtype=np.uint8))
    _write_png(tmp_path / "sample_PI_z002.png", np.full((3, 4), 15, dtype=np.uint8))
    _write_png(tmp_path / "sample_PI_z001.png", np.full((3, 4), 5, dtype=np.uint8))

    stack = load_png_stack(sorted(tmp_path.glob("*.png")))

    assert stack.data.shape == (2, 3, 4, 2)
    assert stack.channel_names == ("AO", "PI")
    assert np.all(stack.data[0, :, :, 0] == 10)
    assert np.all(stack.data[1, :, :, 0] == 20)
    assert np.all(stack.data[0, :, :, 1] == 5)
    assert np.all(stack.data[1, :, :, 1] == 15)


def test_load_png_stack_requires_channel_labels(tmp_path: Path) -> None:
    _write_png(tmp_path / "sample_z001.png", np.ones((3, 4), dtype=np.uint8))

    with pytest.raises(ValueError, match="Could not infer channel"):
        load_png_stack([tmp_path / "sample_z001.png"])


def _write_png(path: Path, array: np.ndarray) -> None:
    Image.fromarray(array).save(path)
