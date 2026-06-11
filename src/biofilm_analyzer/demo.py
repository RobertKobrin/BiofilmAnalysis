"""Synthetic data helpers for quick visualization and smoke testing."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from biofilm_analyzer.io import BiofilmStack


def create_demo_stack(
    *,
    z_slices: int = 28,
    height: int = 96,
    width: int = 96,
    seed: int = 7,
    voxel_size_um: tuple[float, float, float] = (0.8, 0.25, 0.25),
) -> BiofilmStack:
    """Create a deterministic AO/PI biofilm-like stack.

    The generated volume contains several smooth ellipsoidal colonies with
    partly overlapping live and dead signal, plus low background noise.
    """

    if z_slices <= 0 or height <= 0 or width <= 0:
        raise ValueError("Demo stack dimensions must be positive.")

    rng = np.random.default_rng(seed)
    live = rng.normal(loc=8, scale=2, size=(z_slices, height, width)).astype(np.float32)
    dead = rng.normal(loc=6, scale=2, size=(z_slices, height, width)).astype(np.float32)

    zz, yy, xx = np.indices((z_slices, height, width), dtype=np.float32)
    colonies = [
        ((0.38, 0.38, 0.42), (0.28, 0.22, 0.22), 145, 28),
        ((0.58, 0.62, 0.58), (0.24, 0.20, 0.18), 120, 95),
        ((0.44, 0.68, 0.30), (0.18, 0.16, 0.16), 110, 80),
        ((0.68, 0.34, 0.72), (0.16, 0.18, 0.14), 90, 130),
    ]

    for center, radii, live_peak, dead_peak in colonies:
        zc, yc, xc = (
            center[0] * (z_slices - 1),
            center[1] * (height - 1),
            center[2] * (width - 1),
        )
        rz, ry, rx = (
            max(radii[0] * z_slices, 1),
            max(radii[1] * height, 1),
            max(radii[2] * width, 1),
        )
        distance = ((zz - zc) / rz) ** 2 + ((yy - yc) / ry) ** 2 + ((xx - xc) / rx) ** 2
        colony = np.exp(-2.8 * distance)
        live += live_peak * colony

        dead_shift = ((zz - (zc + rz * 0.25)) / (rz * 0.75)) ** 2
        dead_shift += ((yy - (yc - ry * 0.15)) / (ry * 0.85)) ** 2
        dead_shift += ((xx - (xc + rx * 0.18)) / (rx * 0.85)) ** 2
        dead += dead_peak * np.exp(-2.5 * dead_shift)

    live = np.clip(live, 0, 255)
    dead = np.clip(dead, 0, 255)
    data = np.stack([live, dead], axis=-1).astype(np.float32, copy=False)
    return BiofilmStack(
        data=data,
        channel_names=("AO", "PI"),
        source_name="Synthetic demo biofilm",
        voxel_size_um=voxel_size_um,
    )


def write_demo_png_stack(
    output_dir: str | Path,
    *,
    z_slices: int = 28,
    height: int = 96,
    width: int = 96,
    seed: int = 7,
) -> tuple[Path, ...]:
    """Write a synthetic AO/PI stack using the PNG naming convention."""

    stack = create_demo_stack(z_slices=z_slices, height=height, width=width, seed=seed)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for z_index in range(stack.shape[0]):
        for channel_index, channel_name in enumerate(stack.channel_names):
            image = stack.data[z_index, :, :, channel_index]
            path = destination / f"demo_{channel_name}_z{z_index + 1:03d}.png"
            Image.fromarray(image.astype(np.uint8)).save(path)
            written.append(path)
    return tuple(written)
