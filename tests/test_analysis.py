import numpy as np
import pytest

from biofilm_analyzer.analysis import SegmentationOptions, analyze_biofilm, segment_channel
from biofilm_analyzer.io import BiofilmStack


def test_segment_channel_recovers_constant_object_on_zero_background() -> None:
    image = np.zeros((4, 5, 6), dtype=np.float32)
    image[1:3, 2:4, 2:4] = 10

    result = segment_channel(
        image,
        "AO",
        SegmentationOptions(
            threshold_method="otsu",
            gaussian_sigma=0,
            min_object_size_voxels=1,
            fill_holes=False,
        ),
    )

    assert result.threshold == 5
    assert int(result.mask.sum()) == 8


def test_analyze_biofilm_computes_live_dead_statistics() -> None:
    data = np.zeros((4, 5, 6, 2), dtype=np.float32)
    data[1:3, 1:4, 1:4, 0] = 10
    data[2:4, 2:5, 2:5, 1] = 20
    stack = BiofilmStack(
        data=data,
        channel_names=("AO", "PI"),
        source_name="synthetic",
        voxel_size_um=(2.0, 1.0, 1.0),
    )

    result = analyze_biofilm(
        stack,
        options=SegmentationOptions(
            threshold_method="manual",
            gaussian_sigma=0,
            min_object_size_voxels=1,
            fill_holes=False,
            manual_thresholds={"AO": 5, "PI": 5},
        ),
    )

    stats = result.statistics
    assert stats.live_voxels == 18
    assert stats.dead_voxels == 18
    assert stats.overlap_voxels == 4
    assert stats.occupied_voxels == 32
    assert stats.biovolume_um3 == 64
    assert stats.density_fraction == 32 / (4 * 5 * 6)
    assert stats.live_dead_ratio == 1
    assert stats.connected_components == 1
    assert stats.mean_live_intensity_in_live_mask == 10
    assert stats.mean_dead_intensity_in_dead_mask == 20
    assert stats.substratum_coverage_fraction == 14 / 30
    assert stats.areal_biomass_um3_per_um2 == 64 / 30
    assert stats.mean_thickness_um == pytest.approx(64 / 14)
    assert stats.roughness_coefficient == pytest.approx(0.1785714)
    assert stats.surface_to_biovolume_ratio_um_inv > 0
    assert stats.average_diffusion_distance_um > 0
    assert stats.max_diffusion_distance_um >= stats.average_diffusion_distance_um
    assert result.occupied_mask.shape == (4, 5, 6)
    assert result.thickness_map_um.shape == (5, 6)
    assert len(result.object_statistics) == 1
    assert result.object_statistics[0].volume_um3 == 64
    assert result.object_statistics[0].live_fraction == 18 / 32
    assert result.object_statistics[0].dead_fraction == 18 / 32
    assert [row.occupied_voxels for row in result.z_profile] == [0, 9, 14, 9]
    assert [row.live_voxels for row in result.z_profile] == [0, 9, 9, 0]
    assert [row.dead_voxels for row in result.z_profile] == [0, 0, 9, 9]


def test_opening_radius_removes_isolated_voxel() -> None:
    image = np.zeros((5, 5, 5), dtype=np.float32)
    image[2, 2, 2] = 10

    result = segment_channel(
        image,
        "AO",
        SegmentationOptions(
            threshold_method="manual",
            gaussian_sigma=0,
            min_object_size_voxels=1,
            fill_holes=False,
            opening_radius_voxels=1,
            manual_thresholds={"AO": 5},
        ),
    )

    assert not result.mask.any()
