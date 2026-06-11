from pathlib import Path

from biofilm_analyzer.demo import create_demo_stack, write_demo_png_stack
from biofilm_analyzer.io import load_png_stack


def test_create_demo_stack_has_expected_channels_and_shape() -> None:
    stack = create_demo_stack(z_slices=6, height=24, width=32, seed=1)

    assert stack.data.shape == (6, 24, 32, 2)
    assert stack.channel_names == ("AO", "PI")
    assert stack.data[..., 0].max() > stack.data[..., 0].min()
    assert stack.data[..., 1].max() > stack.data[..., 1].min()


def test_write_demo_png_stack_can_be_loaded(tmp_path: Path) -> None:
    written = write_demo_png_stack(tmp_path, z_slices=4, height=16, width=20, seed=2)

    assert len(written) == 8
    stack = load_png_stack(written)
    assert stack.data.shape == (4, 16, 20, 2)
    assert stack.channel_names == ("AO", "PI")
