from pathlib import Path

import numpy as np
from PIL import Image
import pytest

from biofilm_analyzer.io import _nd2_voxel_size_um, load_png_stack


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


def test_nd2_voxel_size_reads_direct_voxel_size_metadata() -> None:
    class VoxelSize:
        x = 0.12
        y = 0.13
        z = 0.5

    class FakeND2File:
        def voxel_size(self) -> VoxelSize:
            return VoxelSize()

    assert _nd2_voxel_size_um(FakeND2File()) == (0.5, 0.13, 0.12)


def test_nd2_voxel_size_reads_axes_calibration_fallback() -> None:
    class Volume:
        axes = "XYZ"
        axesCalibration = (0.2, 0.25, 0.9)

    class Channel:
        volume = Volume()

    class Metadata:
        channels = [Channel()]

    class FakeND2File:
        metadata = Metadata()

        def voxel_size(self) -> None:
            return None

    assert _nd2_voxel_size_um(FakeND2File()) == (0.9, 0.25, 0.2)


def test_nd2_voxel_size_returns_none_without_usable_metadata() -> None:
    class FakeND2File:
        metadata = object()

        def voxel_size(self) -> tuple[int, int, int]:
            return (0, 0, 0)

    assert _nd2_voxel_size_um(FakeND2File()) is None


def _write_png(path: Path, array: np.ndarray) -> None:
    Image.fromarray(array).save(path)
