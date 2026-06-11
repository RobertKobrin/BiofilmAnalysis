import numpy as np

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
    assert result.occupied_mask.shape == (4, 5, 6)
