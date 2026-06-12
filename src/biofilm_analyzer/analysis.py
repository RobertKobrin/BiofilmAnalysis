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
    opening_radius_voxels: int = 0
    closing_radius_voxels: int = 0
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
    roughness_coefficient: float
    substratum_coverage_fraction: float
    areal_biomass_um3_per_um2: float
    estimated_surface_area_um2: float
    surface_to_biovolume_ratio_um_inv: float
    average_diffusion_distance_um: float
    max_diffusion_distance_um: float
    connected_components: int
    live_threshold: float
    dead_threshold: float

    def as_dict(self) -> dict[str, float | int | str | tuple[int, int, int] | tuple[float, float, float]]:
        return asdict(self)


@dataclass(frozen=True)
class ObjectStatistics:
    """Measurements for one connected 3D biofilm object."""

    object_id: int
    voxel_count: int
    volume_um3: float
    centroid_z_um: float
    centroid_y_um: float
    centroid_x_um: float
    bbox_z_um: float
    bbox_y_um: float
    bbox_x_um: float
    live_fraction: float
    dead_fraction: float
    mean_live_intensity: float
    mean_dead_intensity: float

    def as_dict(self) -> dict[str, float | int]:
        return asdict(self)


@dataclass(frozen=True)
class ZProfileRow:
    """Per-slice biomass and signal profile."""

    z_index: int
    z_um: float
    occupied_voxels: int
    live_voxels: int
    dead_voxels: int
    occupied_area_fraction: float
    live_area_fraction: float
    dead_area_fraction: float
    mean_live_intensity: float
    mean_dead_intensity: float

    def as_dict(self) -> dict[str, float | int]:
        return asdict(self)


@dataclass(frozen=True)
class BiofilmAnalysisResult:
    """Segmented masks and statistics ready for GUI display or export."""

    live: SegmentedChannel
    dead: SegmentedChannel
    occupied_mask: np.ndarray
    statistics: BiofilmStatistics
    object_statistics: tuple[ObjectStatistics, ...]
    z_profile: tuple[ZProfileRow, ...]
    thickness_map_um: np.ndarray


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
    footprint_area_um2 = stack.shape[1] * stack.shape[2] * stack.voxel_size_um[1] * stack.voxel_size_um[2]

    components = measure.label(occupied, connectivity=1)
    component_count = int(components.max())
    thickness_map_um = _thickness_map_um(occupied, stack.voxel_size_um[0])
    thickness_values = thickness_map_um[thickness_map_um > 0]
    surface_area_um2 = _estimate_surface_area_um2(occupied, stack.voxel_size_um)
    diffusion_distances_um = _diffusion_distances_um(occupied, stack.voxel_size_um)
    object_statistics = _object_statistics(
        components,
        live.mask,
        dead.mask,
        live_image,
        dead_image,
        stack.voxel_size_um,
    )
    z_profile = _z_profile(
        occupied,
        live.mask,
        dead.mask,
        live_image,
        dead_image,
        stack.voxel_size_um,
    )

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
        roughness_coefficient=_roughness_coefficient(thickness_values),
        substratum_coverage_fraction=_safe_divide(np.count_nonzero(thickness_map_um), thickness_map_um.size),
        areal_biomass_um3_per_um2=_safe_divide(occupied_voxels * voxel_volume, footprint_area_um2),
        estimated_surface_area_um2=surface_area_um2,
        surface_to_biovolume_ratio_um_inv=_safe_divide(surface_area_um2, occupied_voxels * voxel_volume),
        average_diffusion_distance_um=float(diffusion_distances_um.mean()) if diffusion_distances_um.size else 0.0,
        max_diffusion_distance_um=float(diffusion_distances_um.max()) if diffusion_distances_um.size else 0.0,
        connected_components=component_count,
        live_threshold=live.threshold,
        dead_threshold=dead.threshold,
    )

    return BiofilmAnalysisResult(
        live=live,
        dead=dead,
        occupied_mask=occupied,
        statistics=statistics,
        object_statistics=object_statistics,
        z_profile=z_profile,
        thickness_map_um=thickness_map_um,
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
    if segmentation_options.opening_radius_voxels > 0:
        mask = morphology.opening(
            mask,
            footprint=morphology.ball(segmentation_options.opening_radius_voxels),
        )
    if segmentation_options.closing_radius_voxels > 0:
        mask = morphology.closing(
            mask,
            footprint=morphology.ball(segmentation_options.closing_radius_voxels),
        )
    if segmentation_options.fill_holes:
        mask = ndi.binary_fill_holes(mask)
    if segmentation_options.min_object_size_voxels > 1:
        mask = morphology.remove_small_objects(
            mask.astype(bool),
            max_size=segmentation_options.min_object_size_voxels - 1,
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


def _thickness_map_um(mask: np.ndarray, z_size_um: float) -> np.ndarray:
    any_signal = mask.any(axis=0)
    if not np.any(any_signal):
        return np.zeros(mask.shape[1:], dtype=np.float32)

    z_indices = np.arange(mask.shape[0], dtype=np.float32)[:, np.newaxis, np.newaxis]
    first = np.where(mask, z_indices, np.inf).min(axis=0)
    last = np.where(mask, z_indices, -np.inf).max(axis=0)
    thickness = np.zeros(mask.shape[1:], dtype=np.float32)
    thickness[any_signal] = (last[any_signal] - first[any_signal] + 1) * z_size_um
    return thickness


def _roughness_coefficient(thickness_values_um: np.ndarray) -> float:
    if thickness_values_um.size == 0:
        return 0.0
    mean_thickness = float(thickness_values_um.mean())
    if mean_thickness == 0:
        return 0.0
    return float(np.mean(np.abs(thickness_values_um - mean_thickness)) / mean_thickness)


def _diffusion_distances_um(mask: np.ndarray, voxel_size_um: tuple[float, float, float]) -> np.ndarray:
    if not np.any(mask):
        return np.array([], dtype=np.float32)
    distances = ndi.distance_transform_edt(mask, sampling=voxel_size_um)
    return distances[mask]


def _object_statistics(
    labels: np.ndarray,
    live_mask: np.ndarray,
    dead_mask: np.ndarray,
    live_image: np.ndarray,
    dead_image: np.ndarray,
    voxel_size_um: tuple[float, float, float],
) -> tuple[ObjectStatistics, ...]:
    if labels.max() == 0:
        return tuple()

    voxel_volume = float(np.prod(voxel_size_um))
    rows: list[ObjectStatistics] = []
    for region in measure.regionprops(labels):
        object_mask = labels == region.label
        voxel_count = int(region.area)
        z0, y0, x0, z1, y1, x1 = region.bbox
        centroid_z, centroid_y, centroid_x = region.centroid
        rows.append(
            ObjectStatistics(
                object_id=int(region.label),
                voxel_count=voxel_count,
                volume_um3=voxel_count * voxel_volume,
                centroid_z_um=float(centroid_z * voxel_size_um[0]),
                centroid_y_um=float(centroid_y * voxel_size_um[1]),
                centroid_x_um=float(centroid_x * voxel_size_um[2]),
                bbox_z_um=float((z1 - z0) * voxel_size_um[0]),
                bbox_y_um=float((y1 - y0) * voxel_size_um[1]),
                bbox_x_um=float((x1 - x0) * voxel_size_um[2]),
                live_fraction=_safe_divide(np.count_nonzero(np.logical_and(object_mask, live_mask)), voxel_count),
                dead_fraction=_safe_divide(np.count_nonzero(np.logical_and(object_mask, dead_mask)), voxel_count),
                mean_live_intensity=_masked_mean(live_image, object_mask),
                mean_dead_intensity=_masked_mean(dead_image, object_mask),
            )
        )
    return tuple(rows)


def _z_profile(
    occupied_mask: np.ndarray,
    live_mask: np.ndarray,
    dead_mask: np.ndarray,
    live_image: np.ndarray,
    dead_image: np.ndarray,
    voxel_size_um: tuple[float, float, float],
) -> tuple[ZProfileRow, ...]:
    slice_area_voxels = occupied_mask.shape[1] * occupied_mask.shape[2]
    rows: list[ZProfileRow] = []
    for z_index in range(occupied_mask.shape[0]):
        occupied_slice = occupied_mask[z_index]
        live_slice = live_mask[z_index]
        dead_slice = dead_mask[z_index]
        rows.append(
            ZProfileRow(
                z_index=z_index,
                z_um=float(z_index * voxel_size_um[0]),
                occupied_voxels=int(np.count_nonzero(occupied_slice)),
                live_voxels=int(np.count_nonzero(live_slice)),
                dead_voxels=int(np.count_nonzero(dead_slice)),
                occupied_area_fraction=_safe_divide(np.count_nonzero(occupied_slice), slice_area_voxels),
                live_area_fraction=_safe_divide(np.count_nonzero(live_slice), slice_area_voxels),
                dead_area_fraction=_safe_divide(np.count_nonzero(dead_slice), slice_area_voxels),
                mean_live_intensity=_masked_mean(live_image[z_index], live_slice),
                mean_dead_intensity=_masked_mean(dead_image[z_index], dead_slice),
            )
        )
    return tuple(rows)


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
