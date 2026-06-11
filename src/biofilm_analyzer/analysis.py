"""Segmentation and quantitative biofilm statistics."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal, Mapping

import numpy as np
from scipy import ndimage as ndi
from skimage import filters, measure, morphology

from biofilm_analyzer.io import BiofilmStack

ThresholdMethod = Literal["otsu", "yen", "li", "manual"]


@dataclass(frozen=True)
class SegmentationOptions:
    """Parameters used to segment live/dead stain channels."""

    threshold_method: ThresholdMethod = "otsu"
    gaussian_sigma: float = 1.0
    min_object_size_voxels: int = 64
    fill_holes: bool = True
    background_percentile: float = 0.0
    manual_thresholds: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class SegmentedChannel:
    """A binary segmentation mask and the threshold used to create it."""

    mask: np.ndarray
    threshold: float
    processed_image: np.ndarray


@dataclass(frozen=True)
class BiofilmStatistics:
    """Summary statistics for a two-channel biofilm stack."""

    source_name: str
    dimensions_zyx: tuple[int, int, int]
    voxel_size_um: tuple[float, float, float]
    total_voxels: int
    occupied_voxels: int
    live_voxels: int
    dead_voxels: int
    live_only_voxels: int
    dead_only_voxels: int
    overlap_voxels: int
    density_fraction: float
    biovolume_um3: float
    live_fraction_of_occupied: float
    dead_fraction_of_occupied: float
    overlap_fraction_of_occupied: float
    live_dead_ratio: float
    mean_live_intensity_in_live_mask: float
    mean_dead_intensity_in_dead_mask: float
    mean_thickness_um: float
    max_thickness_um: float
    estimated_surface_area_um2: float
    connected_components: int
    live_threshold: float
    dead_threshold: float

    def as_dict(self) -> dict[str, float | int | str | tuple[int, int, int] | tuple[float, float, float]]:
        return asdict(self)


@dataclass(frozen=True)
class BiofilmAnalysisResult:
    """Segmented masks and statistics ready for GUI display or export."""

    live: SegmentedChannel
    dead: SegmentedChannel
    occupied_mask: np.ndarray
    statistics: BiofilmStatistics


def analyze_biofilm(
    stack: BiofilmStack,
    *,
    live_channel: str = "AO",
    dead_channel: str = "PI",
    options: SegmentationOptions | None = None,
) -> BiofilmAnalysisResult:
    """Segment live/dead channels and compute 3D biofilm statistics."""

    segmentation_options = options or SegmentationOptions()
    live_image = stack.channel(live_channel)
    dead_image = stack.channel(dead_channel)

    live = segment_channel(live_image, live_channel, segmentation_options)
    dead = segment_channel(dead_image, dead_channel, segmentation_options)

    occupied = np.logical_or(live.mask, dead.mask)
    live_only = np.logical_and(live.mask, ~dead.mask)
    dead_only = np.logical_and(dead.mask, ~live.mask)
    overlap = np.logical_and(live.mask, dead.mask)
    occupied_voxels = int(np.count_nonzero(occupied))
    total_voxels = int(occupied.size)
    voxel_volume = float(np.prod(stack.voxel_size_um))

    components = measure.label(occupied, connectivity=1)
    component_count = int(components.max())
    thickness_values = _column_thicknesses_um(occupied, stack.voxel_size_um[0])

    statistics = BiofilmStatistics(
        source_name=stack.source_name,
        dimensions_zyx=tuple(int(size) for size in occupied.shape),
        voxel_size_um=stack.voxel_size_um,
        total_voxels=total_voxels,
        occupied_voxels=occupied_voxels,
        live_voxels=int(np.count_nonzero(live.mask)),
        dead_voxels=int(np.count_nonzero(dead.mask)),
        live_only_voxels=int(np.count_nonzero(live_only)),
        dead_only_voxels=int(np.count_nonzero(dead_only)),
        overlap_voxels=int(np.count_nonzero(overlap)),
        density_fraction=_safe_divide(occupied_voxels, total_voxels),
        biovolume_um3=occupied_voxels * voxel_volume,
        live_fraction_of_occupied=_safe_divide(np.count_nonzero(live.mask), occupied_voxels),
        dead_fraction_of_occupied=_safe_divide(np.count_nonzero(dead.mask), occupied_voxels),
        overlap_fraction_of_occupied=_safe_divide(np.count_nonzero(overlap), occupied_voxels),
        live_dead_ratio=_safe_divide(np.count_nonzero(live.mask), np.count_nonzero(dead.mask)),
        mean_live_intensity_in_live_mask=_masked_mean(live_image, live.mask),
        mean_dead_intensity_in_dead_mask=_masked_mean(dead_image, dead.mask),
        mean_thickness_um=float(thickness_values.mean()) if thickness_values.size else 0.0,
        max_thickness_um=float(thickness_values.max()) if thickness_values.size else 0.0,
        estimated_surface_area_um2=_estimate_surface_area_um2(occupied, stack.voxel_size_um),
        connected_components=component_count,
        live_threshold=live.threshold,
        dead_threshold=dead.threshold,
    )

    return BiofilmAnalysisResult(
        live=live,
        dead=dead,
        occupied_mask=occupied,
        statistics=statistics,
    )


def segment_channel(
    image: np.ndarray,
    channel_name: str,
    options: SegmentationOptions | None = None,
) -> SegmentedChannel:
    """Segment a single 3D fluorescence channel."""

    segmentation_options = options or SegmentationOptions()
    processed = np.asarray(image, dtype=np.float32)
    if segmentation_options.background_percentile > 0:
        background = np.percentile(processed, segmentation_options.background_percentile)
        processed = np.clip(processed - background, a_min=0, a_max=None)
    if segmentation_options.gaussian_sigma > 0:
        processed = ndi.gaussian_filter(processed, sigma=segmentation_options.gaussian_sigma)

    threshold = _threshold(processed, channel_name, segmentation_options)
    mask = processed > threshold
    if segmentation_options.fill_holes:
        mask = ndi.binary_fill_holes(mask)
    if segmentation_options.min_object_size_voxels > 1:
        mask = morphology.remove_small_objects(
            mask.astype(bool),
            min_size=segmentation_options.min_object_size_voxels,
            connectivity=1,
        )

    return SegmentedChannel(mask=mask.astype(bool, copy=False), threshold=threshold, processed_image=processed)


def _threshold(image: np.ndarray, channel_name: str, options: SegmentationOptions) -> float:
    finite_values = image[np.isfinite(image)]
    if finite_values.size == 0:
        raise ValueError("Cannot segment an image with no finite intensity values.")

    if options.threshold_method == "manual":
        if channel_name not in options.manual_thresholds:
            raise ValueError(f"Manual threshold for {channel_name!r} was not provided.")
        return float(options.manual_thresholds[channel_name])

    nonzero = finite_values[finite_values > 0]
    values = nonzero if nonzero.size else finite_values
    if np.all(values == values.flat[0]):
        if nonzero.size and finite_values.min() <= 0:
            return float(values.flat[0] / 2)
        return float(values.flat[0])

    if options.threshold_method == "otsu":
        return float(filters.threshold_otsu(values))
    if options.threshold_method == "yen":
        return float(filters.threshold_yen(values))
    if options.threshold_method == "li":
        return float(filters.threshold_li(values))
    raise ValueError(f"Unsupported threshold method: {options.threshold_method!r}.")


def _masked_mean(image: np.ndarray, mask: np.ndarray) -> float:
    if not np.any(mask):
        return 0.0
    return float(np.asarray(image)[mask].mean())


def _safe_divide(numerator: int | float, denominator: int | float) -> float:
    return float(numerator / denominator) if denominator else 0.0


def _column_thicknesses_um(mask: np.ndarray, z_size_um: float) -> np.ndarray:
    any_signal = mask.any(axis=0)
    if not np.any(any_signal):
        return np.array([], dtype=np.float32)

    z_indices = np.arange(mask.shape[0], dtype=np.float32)[:, np.newaxis, np.newaxis]
    first = np.where(mask, z_indices, np.inf).min(axis=0)
    last = np.where(mask, z_indices, -np.inf).max(axis=0)
    thickness = (last - first + 1) * z_size_um
    return thickness[any_signal]


def _estimate_surface_area_um2(mask: np.ndarray, voxel_size_um: tuple[float, float, float]) -> float:
    z_um, y_um, x_um = voxel_size_um
    padded = np.pad(mask.astype(np.int8), pad_width=1, mode="constant", constant_values=0)
    z_faces = np.abs(np.diff(padded, axis=0)).sum()
    y_faces = np.abs(np.diff(padded, axis=1)).sum()
    x_faces = np.abs(np.diff(padded, axis=2)).sum()
    return float(
        z_faces * y_um * x_um
        + y_faces * z_um * x_um
        + x_faces * z_um * y_um
    )
