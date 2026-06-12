"""Image-stack loading and normalization utilities."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from collections.abc import Mapping as MappingABC, Sequence as SequenceABC
from typing import Mapping, Sequence

import numpy as np
from PIL import Image


DEFAULT_CHANNEL_ALIASES: dict[str, tuple[str, ...]] = {
    "AO": ("ao", "live", "alive", "green"),
    "PI": ("pi", "dead", "red", "propidium"),
}


@dataclass(frozen=True)
class BiofilmStack:
    """A 3D, multi-channel biofilm image stack.

    Data is always stored as ``(z, y, x, channel)`` so importers and analysis
    code do not need to care about the source file format's axis order.
    """

    data: np.ndarray
    channel_names: tuple[str, ...]
    source_name: str
    voxel_size_um: tuple[float, float, float] = (1.0, 1.0, 1.0)

    def __post_init__(self) -> None:
        if self.data.ndim != 4:
            raise ValueError("BiofilmStack data must have shape (z, y, x, channel).")
        if self.data.shape[-1] != len(self.channel_names):
            raise ValueError("Number of channel names must match the data channel axis.")
        if any(size <= 0 for size in self.voxel_size_um):
            raise ValueError("Voxel sizes must be positive.")

    @property
    def shape(self) -> tuple[int, int, int, int]:
        return self.data.shape

    def channel_index(self, name: str) -> int:
        """Return the channel index matching a display name or known alias."""

        wanted = name.strip().lower()
        for index, channel_name in enumerate(self.channel_names):
            if channel_name.lower() == wanted:
                return index

        for canonical, aliases in DEFAULT_CHANNEL_ALIASES.items():
            all_names = (canonical.lower(), *aliases)
            if wanted in all_names:
                for index, channel_name in enumerate(self.channel_names):
                    if channel_name.lower() in all_names:
                        return index

        raise ValueError(f"Channel {name!r} was not found in {self.channel_names}.")

    def channel(self, name: str) -> np.ndarray:
        return self.data[..., self.channel_index(name)]


def load_png_stack(
    paths: Sequence[str | Path],
    *,
    channel_aliases: Mapping[str, Sequence[str]] | None = None,
    voxel_size_um: tuple[float, float, float] = (1.0, 1.0, 1.0),
    source_name: str = "PNG stack",
) -> BiofilmStack:
    """Load a multi-channel stack from PNG files labeled by channel in filenames.

    Filenames must include channel labels such as ``AO`` and ``PI``:
    ``sample_AO_z001.png``, ``sample_PI_z001.png``, etc. Slices are sorted by
    the numeric groups in the filename, then lexically.
    """

    if not paths:
        raise ValueError("At least one PNG file is required.")

    aliases = _normalized_aliases(channel_aliases)
    grouped_paths: dict[str, list[Path]] = {}
    for raw_path in paths:
        path = Path(raw_path)
        channel_name = _infer_channel_name(path.name, aliases)
        grouped_paths.setdefault(channel_name, []).append(path)

    channel_names = _ordered_channel_names(grouped_paths)
    stacks: list[np.ndarray] = []
    expected_shape: tuple[int, int, int] | None = None
    for channel_name in channel_names:
        channel_paths = sorted(grouped_paths[channel_name], key=_natural_sort_key)
        slices = [_read_png_grayscale(path) for path in channel_paths]
        channel_stack = np.stack(slices, axis=0).astype(np.float32, copy=False)
        if expected_shape is None:
            expected_shape = channel_stack.shape
        elif channel_stack.shape != expected_shape:
            raise ValueError(
                "All channels must have the same z/y/x shape. "
                f"{channel_name} has {channel_stack.shape}, expected {expected_shape}."
            )
        stacks.append(channel_stack)

    data = np.stack(stacks, axis=-1)
    return BiofilmStack(
        data=data,
        channel_names=tuple(channel_names),
        source_name=source_name,
        voxel_size_um=voxel_size_um,
    )


def load_nd2_stack(
    path: str | Path,
    *,
    time_index: int = 0,
    position_index: int = 0,
    voxel_size_um: tuple[float, float, float] | None = None,
) -> BiofilmStack:
    """Load an ND2 file and normalize it to ``(z, y, x, channel)``.

    The ``nd2`` package is imported lazily so the PNG workflow remains usable in
    environments that do not have Nikon ND2 support installed. If
    ``voxel_size_um`` is not supplied, physical pixel calibration is read from
    ND2 metadata when available.
    """

    try:
        import nd2  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - exercised only without deps
        raise RuntimeError(
            "ND2 support requires the optional 'nd2' package. Install project "
            "dependencies with `pip install -e .` before opening ND2 files."
        ) from exc

    nd2_path = Path(path)
    with nd2.ND2File(nd2_path) as nd2_file:
        array = nd2_file.asarray()
        axes = "".join(str(axis).upper() for axis in nd2_file.sizes.keys())
        channel_names = _nd2_channel_names(nd2_file, array, axes)
        metadata_voxel_size = _nd2_voxel_size_um(nd2_file)

    data = _coerce_to_zyxc(
        np.asarray(array),
        axes,
        time_index=time_index,
        position_index=position_index,
    ).astype(np.float32, copy=False)

    if data.shape[-1] != len(channel_names):
        channel_names = tuple(f"Channel {index + 1}" for index in range(data.shape[-1]))

    return BiofilmStack(
        data=data,
        channel_names=channel_names,
        source_name=nd2_path.name,
        voxel_size_um=voxel_size_um or metadata_voxel_size or (1.0, 1.0, 1.0),
    )


def _normalized_aliases(
    channel_aliases: Mapping[str, Sequence[str]] | None,
) -> dict[str, tuple[str, ...]]:
    raw_aliases = channel_aliases or DEFAULT_CHANNEL_ALIASES
    return {
        canonical: tuple({canonical.lower(), *(alias.lower() for alias in aliases)})
        for canonical, aliases in raw_aliases.items()
    }


def _infer_channel_name(filename: str, aliases: Mapping[str, Sequence[str]]) -> str:
    stem_tokens = {
        token.lower()
        for token in re.split(r"[^A-Za-z0-9]+", Path(filename).stem)
        if token
    }
    matches = [
        canonical
        for canonical, labels in aliases.items()
        if stem_tokens.intersection(label.lower() for label in labels)
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ValueError(
            f"Could not infer channel from {filename!r}. Include labels such as "
            "'AO' or 'PI' in each PNG filename."
        )
    raise ValueError(f"Ambiguous channel labels in {filename!r}: {matches}.")


def _ordered_channel_names(grouped_paths: Mapping[str, list[Path]]) -> list[str]:
    preferred = [name for name in ("AO", "PI") if name in grouped_paths]
    remaining = sorted(name for name in grouped_paths if name not in preferred)
    return [*preferred, *remaining]


def _natural_sort_key(path: Path) -> tuple[tuple[int, int | str], ...]:
    parts: list[tuple[int, int | str]] = []
    for part in re.split(r"(\d+)", path.name.lower()):
        if part.isdigit():
            parts.append((0, int(part)))
        elif part:
            parts.append((1, part))
    return tuple(parts)


def _read_png_grayscale(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        grayscale = image.convert("F")
        return np.asarray(grayscale, dtype=np.float32)


def _nd2_channel_names(nd2_file: object, array: np.ndarray, axes: str) -> tuple[str, ...]:
    try:
        channels = nd2_file.metadata.channels  # type: ignore[attr-defined]
        names = [channel.channel.name for channel in channels]
        if names:
            return tuple(str(name) for name in names)
    except Exception:
        pass

    channel_count = array.shape[axes.index("C")] if "C" in axes else 1
    return tuple(f"Channel {index + 1}" for index in range(channel_count))


def _nd2_voxel_size_um(nd2_file: object) -> tuple[float, float, float] | None:
    """Extract ND2 voxel size as ``(z, y, x)`` microns when metadata exists."""

    try:
        voxel_size = nd2_file.voxel_size()  # type: ignore[attr-defined]
    except Exception:
        voxel_size = None
    parsed = _calibration_to_zyx_um(voxel_size)
    if parsed is not None:
        return parsed

    for volume in _nd2_volume_metadata_candidates(nd2_file):
        calibration = getattr(volume, "axesCalibration", None)
        axes = getattr(volume, "axes", None)
        parsed = _calibration_to_zyx_um(calibration, axes=axes)
        if parsed is not None:
            return parsed

    return None


def _nd2_volume_metadata_candidates(nd2_file: object) -> tuple[object, ...]:
    candidates: list[object] = []
    metadata = getattr(nd2_file, "metadata", None)
    if metadata is None:
        return tuple()

    volume = getattr(metadata, "volume", None)
    if volume is not None:
        candidates.append(volume)

    channels = getattr(metadata, "channels", None)
    if channels is not None:
        for channel in channels:
            volume = getattr(channel, "volume", None)
            if volume is not None:
                candidates.append(volume)

    return tuple(candidates)


def _calibration_to_zyx_um(
    calibration: object,
    *,
    axes: object | None = None,
) -> tuple[float, float, float] | None:
    xyz = _calibration_to_xyz_um(calibration, axes=axes)
    if xyz is None:
        return None
    x_um, y_um, z_um = xyz
    return (z_um, y_um, x_um)


def _calibration_to_xyz_um(
    calibration: object,
    *,
    axes: object | None = None,
) -> tuple[float, float, float] | None:
    if calibration is None:
        return None

    axis_values: dict[str, float] = {}
    for axis_name in ("x", "y", "z"):
        value = _positive_float_or_none(getattr(calibration, axis_name, None))
        if value is None:
            value = _positive_float_or_none(getattr(calibration, axis_name.upper(), None))
        if value is not None:
            axis_values[axis_name] = value

    if len(axis_values) == 3:
        return (axis_values["x"], axis_values["y"], axis_values["z"])

    if isinstance(calibration, MappingABC):
        mapped = {
            axis_name: _positive_float_or_none(calibration.get(axis_name) or calibration.get(axis_name.upper()))
            for axis_name in ("x", "y", "z")
        }
        if all(value is not None for value in mapped.values()):
            return (float(mapped["x"]), float(mapped["y"]), float(mapped["z"]))

    if isinstance(calibration, SequenceABC) and not isinstance(calibration, (str, bytes)):
        values = [_positive_float_or_none(value) for value in calibration]
        if len(values) < 3 or any(value is None for value in values[:3]):
            return None
        axis_order = str(axes).lower() if axes is not None else "xyz"
        if all(axis in axis_order for axis in "xyz"):
            mapped = {
                axis_order[index]: float(value)
                for index, value in enumerate(values)
                if index < len(axis_order) and axis_order[index] in "xyz" and value is not None
            }
            if all(axis in mapped for axis in "xyz"):
                return (mapped["x"], mapped["y"], mapped["z"])
        return (float(values[0]), float(values[1]), float(values[2]))

    return None


def _positive_float_or_none(value: object) -> float | None:
    try:
        numeric = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if numeric > 0 and np.isfinite(numeric):
        return numeric
    return None


def _coerce_to_zyxc(
    array: np.ndarray,
    axes: str,
    *,
    time_index: int,
    position_index: int,
) -> np.ndarray:
    axes_list = list(axes.upper())
    result = array

    for axis_name, selected_index in (("T", time_index), ("P", position_index), ("M", position_index)):
        if axis_name in axes_list:
            axis = axes_list.index(axis_name)
            result = np.take(result, selected_index, axis=axis)
            axes_list.pop(axis)

    for axis_index in reversed(range(len(axes_list))):
        if axes_list[axis_index] not in {"Z", "Y", "X", "C"}:
            result = np.take(result, 0, axis=axis_index)
            axes_list.pop(axis_index)

    if "Z" not in axes_list:
        result = np.expand_dims(result, axis=0)
        axes_list.insert(0, "Z")
    if "C" not in axes_list:
        result = np.expand_dims(result, axis=-1)
        axes_list.append("C")

    required = ["Z", "Y", "X", "C"]
    missing = [axis for axis in required if axis not in axes_list]
    if missing:
        raise ValueError(f"Image data is missing required axes: {missing}.")

    source_axes = [axes_list.index(axis) for axis in required]
    return np.moveaxis(result, source_axes, range(len(required)))
