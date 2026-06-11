"""Streamlit GUI for 3D biofilm segmentation and analysis."""

from __future__ import annotations

from html import escape
from pathlib import Path
import tempfile
from typing import Iterable

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from biofilm_analyzer.analysis import BiofilmAnalysisResult, SegmentationOptions, analyze_biofilm
from biofilm_analyzer.demo import create_demo_stack
from biofilm_analyzer.io import BiofilmStack, load_nd2_stack, load_png_stack


def main() -> None:
    st.set_page_config(
        page_title="BiofilmAnalysis",
        page_icon=":microscope:",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _apply_theme()
    _hero_header()
    _sidebar_intro()

    st.sidebar.markdown("### 1. Data source")
    input_mode = st.sidebar.radio("Input format", ["Demo synthetic stack", "PNG stack", "ND2 file"])
    voxel_size_um, use_nd2_metadata_calibration = _voxel_size_controls(input_mode)

    stack = _load_stack(input_mode, voxel_size_um, use_nd2_metadata_calibration)
    if stack is None:
        _show_getting_started(input_mode)
        return

    _stack_status_card(stack)

    live_channel, dead_channel = _channel_controls(stack)
    options = _segmentation_controls(stack, live_channel, dead_channel)

    try:
        result = analyze_biofilm(
            stack,
            live_channel=live_channel,
            dead_channel=dead_channel,
            options=options,
        )
    except Exception as exc:
        st.error(f"Analysis failed: {exc}")
        return

    stats_df = _stats_dataframe(result.statistics.as_dict())
    profile_df = _z_profile_dataframe(result.z_profile)
    object_df = _object_dataframe(result.object_statistics)

    overview_tab, preview_tab, quant_tab, recon_tab = st.tabs(
        ["Overview", "Tune segmentation", "Quantification", "3D reconstructions"]
    )
    with overview_tab:
        _overview_section(result, profile_df)
    with preview_tab:
        _segmentation_preview_section(stack, result, live_channel, dead_channel)
    with quant_tab:
        _quantification_section(stats_df, profile_df, object_df, result)
    with recon_tab:
        _reconstruction_section(result)


def _apply_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --biofilm-navy: #102033;
            --biofilm-blue: #1f77b4;
            --biofilm-green: #2fbf71;
            --biofilm-red: #ef5350;
            --biofilm-gold: #f3d44e;
            --biofilm-muted: #667085;
        }
        .block-container {
            padding-top: 1.4rem;
            padding-bottom: 3rem;
        }
        [data-testid="stSidebar"] {
            border-right: 1px solid rgba(16, 32, 51, 0.08);
        }
        .biofilm-hero {
            background: linear-gradient(135deg, #102033 0%, #17456b 56%, #1f7a72 100%);
            color: #f8fbff;
            border-radius: 24px;
            padding: 1.45rem 1.65rem;
            margin-bottom: 1rem;
            box-shadow: 0 18px 40px rgba(16, 32, 51, 0.14);
        }
        .biofilm-hero h1 {
            color: #f8fbff;
            margin: 0;
            font-size: 2.2rem;
            letter-spacing: -0.03em;
        }
        .biofilm-hero p {
            color: rgba(248, 251, 255, 0.86);
            max-width: 920px;
            margin: 0.45rem 0 0;
            font-size: 1rem;
        }
        .biofilm-pill-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
            margin-top: 0.9rem;
        }
        .biofilm-pill {
            background: rgba(255, 255, 255, 0.12);
            border: 1px solid rgba(255, 255, 255, 0.22);
            border-radius: 999px;
            color: #f8fbff;
            padding: 0.25rem 0.65rem;
            font-size: 0.82rem;
        }
        .biofilm-step {
            border-left: 3px solid #2fbf71;
            padding-left: 0.75rem;
            color: #344054;
            margin: 0.35rem 0;
            font-size: 0.92rem;
        }
        .biofilm-status {
            border: 1px solid rgba(16, 32, 51, 0.1);
            border-radius: 18px;
            padding: 0.9rem 1rem;
            margin: 0.9rem 0 1rem;
            background: #fbfcfe;
        }
        .biofilm-status strong {
            color: #102033;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _hero_header() -> None:
    st.markdown(
        """
        <div class="biofilm-hero">
            <h1>BiofilmAnalysis</h1>
            <p>
                Segment AO/PI live-dead biofilm stacks, tune masks slice-by-slice,
                and export COMSTAT-style 3D statistics from a streamlined research UI.
            </p>
            <div class="biofilm-pill-row">
                <span class="biofilm-pill">ND2 + PNG stacks</span>
                <span class="biofilm-pill">Real-time slice preview</span>
                <span class="biofilm-pill">Live/dead quantification</span>
                <span class="biofilm-pill">Interactive 3D views</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _sidebar_intro() -> None:
    st.sidebar.title("BiofilmAnalysis")
    st.sidebar.caption("Work left-to-right: load data, confirm calibration, choose channels, tune segmentation.")
    st.sidebar.markdown(
        """
        <div class="biofilm-step"><strong>1.</strong> Load a stack</div>
        <div class="biofilm-step"><strong>2.</strong> Confirm voxel size</div>
        <div class="biofilm-step"><strong>3.</strong> Select AO/PI channels</div>
        <div class="biofilm-step"><strong>4.</strong> Tune masks in preview</div>
        """,
        unsafe_allow_html=True,
    )
    st.sidebar.divider()


def _stack_status_card(stack: BiofilmStack) -> None:
    source_name = escape(stack.source_name)
    channel_names = escape(", ".join(stack.channel_names))
    st.markdown(
        f"""
        <div class="biofilm-status">
            <strong>Loaded:</strong> {source_name}
            &nbsp; | &nbsp; <strong>Volume:</strong> z={stack.shape[0]}, y={stack.shape[1]}, x={stack.shape[2]}
            &nbsp; | &nbsp; <strong>Channels:</strong> {channel_names}
            <br/>
            <strong>Voxel size:</strong>
            z={stack.voxel_size_um[0]:.6g} um,
            y={stack.voxel_size_um[1]:.6g} um,
            x={stack.voxel_size_um[2]:.6g} um
        </div>
        """,
        unsafe_allow_html=True,
    )


def _overview_section(result: BiofilmAnalysisResult, profile_df: pd.DataFrame) -> None:
    st.subheader("Analysis overview")
    st.caption("High-level live/dead state and COMSTAT-style morphology at a glance.")
    metric_columns = st.columns(6)
    metrics = [
        ("Density", _format_percent(result.statistics.density_fraction)),
        ("Live", _format_percent(result.statistics.live_fraction_of_occupied)),
        ("Dead", _format_percent(result.statistics.dead_fraction_of_occupied)),
        ("Biovolume", f"{result.statistics.biovolume_um3:,.2f} um3"),
        ("Coverage", _format_percent(result.statistics.substratum_coverage_fraction)),
        ("Roughness", f"{result.statistics.roughness_coefficient:.3f}"),
    ]
    for column, (label, value) in zip(metric_columns, metrics):
        column.metric(label, value)

    left, right = st.columns([0.55, 0.45], gap="large")
    with left:
        st.plotly_chart(_z_profile_figure(profile_df), use_container_width=True)
    with right:
        st.markdown("#### Recommended workflow")
        st.markdown(
            """
            1. Open **Tune segmentation** and inspect representative top/middle/bottom slices.
            2. Adjust thresholding, smoothing, object size, and morphology controls in the sidebar.
            3. Return here to confirm live/dead fractions and morphology metrics.
            4. Export tables from **Quantification** and inspect volume geometry in **3D reconstructions**.
            """
        )


def _quantification_section(
    stats_df: pd.DataFrame,
    profile_df: pd.DataFrame,
    object_df: pd.DataFrame,
    result: BiofilmAnalysisResult,
) -> None:
    st.subheader("Quantification and exports")
    st.caption("Download global statistics, z-profiles, thickness maps, and object-level measurements.")
    stats_tab, profile_tab, thickness_tab, object_tab = st.tabs(
        ["Global statistics", "Z profiles", "Thickness map", "3D objects"]
    )
    with stats_tab:
        st.dataframe(stats_df, use_container_width=True, hide_index=True)
        st.download_button(
            "Download global statistics CSV",
            data=stats_df.to_csv(index=False).encode("utf-8"),
            file_name="biofilm_statistics.csv",
            mime="text/csv",
        )
    with profile_tab:
        st.plotly_chart(_z_profile_figure(profile_df), use_container_width=True)
        st.dataframe(profile_df, use_container_width=True, hide_index=True)
        st.download_button(
            "Download z-profile CSV",
            data=profile_df.to_csv(index=False).encode("utf-8"),
            file_name="biofilm_z_profile.csv",
            mime="text/csv",
        )
    with thickness_tab:
        st.plotly_chart(_thickness_heatmap(result.thickness_map_um), use_container_width=True)
        st.download_button(
            "Download thickness map CSV",
            data=pd.DataFrame(result.thickness_map_um).to_csv(index=False).encode("utf-8"),
            file_name="biofilm_thickness_map_um.csv",
            mime="text/csv",
        )
    with object_tab:
        if object_df.empty:
            st.info("No connected biofilm objects were detected.")
        else:
            st.dataframe(object_df, use_container_width=True, hide_index=True)
            st.download_button(
                "Download object statistics CSV",
                data=object_df.to_csv(index=False).encode("utf-8"),
                file_name="biofilm_object_statistics.csv",
                mime="text/csv",
            )


def _reconstruction_section(result: BiofilmAnalysisResult) -> None:
    st.subheader("3D reconstructions")
    st.caption("Inspect segmented biomass in live, dead, and merged 3D views.")
    controls = st.columns(3)
    with controls[0]:
        max_points = st.slider(
            "Maximum rendered voxels",
            min_value=1_000,
            max_value=100_000,
            value=25_000,
            step=1_000,
            help="Lower values keep large stacks responsive in the browser.",
        )
    with controls[1]:
        marker_size = st.slider("Marker size", min_value=1, max_value=8, value=2)
    with controls[2]:
        marker_opacity = st.slider("Marker opacity", min_value=0.05, max_value=1.0, value=0.55, step=0.05)

    live_tab, dead_tab, merge_tab = st.tabs(["Live signal", "Dead signal", "Merged live/dead"])
    with live_tab:
        st.plotly_chart(
            _single_channel_figure(result.live.mask, "Live signal", "green", max_points, marker_size, marker_opacity),
            use_container_width=True,
        )
    with dead_tab:
        st.plotly_chart(
            _single_channel_figure(result.dead.mask, "Dead signal", "red", max_points, marker_size, marker_opacity),
            use_container_width=True,
        )
    with merge_tab:
        st.plotly_chart(
            _merge_figure(result.live.mask, result.dead.mask, max_points, marker_size, marker_opacity),
            use_container_width=True,
        )


def _load_stack(
    input_mode: str,
    voxel_size_um: tuple[float, float, float] | None,
    use_nd2_metadata_calibration: bool,
) -> BiofilmStack | None:
    if input_mode == "Demo synthetic stack":
        st.sidebar.markdown("#### Demo stack settings")
        z_slices = st.sidebar.slider("Demo z-slices", min_value=8, max_value=64, value=28, step=2)
        image_size = st.sidebar.slider("Demo x/y size", min_value=48, max_value=160, value=96, step=8)
        seed = st.sidebar.number_input("Demo random seed", min_value=0, value=7, step=1)
        return create_demo_stack(
            z_slices=int(z_slices),
            height=int(image_size),
            width=int(image_size),
            seed=int(seed),
            voxel_size_um=voxel_size_um or (1.0, 1.0, 1.0),
        )

    if input_mode == "ND2 file":
        uploaded = st.sidebar.file_uploader("Upload ND2 file", type=["nd2"])
        time_index = st.sidebar.number_input("Time index", min_value=0, value=0, step=1)
        position_index = st.sidebar.number_input("Position index", min_value=0, value=0, step=1)
        if uploaded is None:
            return None
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / uploaded.name
            path.write_bytes(uploaded.getbuffer())
            return load_nd2_stack(
                path,
                time_index=int(time_index),
                position_index=int(position_index),
                voxel_size_um=None if use_nd2_metadata_calibration else voxel_size_um,
            )

    uploaded_files = st.sidebar.file_uploader(
        "Upload labeled PNG slices",
        type=["png"],
        accept_multiple_files=True,
        help="Use filenames such as sample_AO_z001.png and sample_PI_z001.png.",
    )
    live_aliases = st.sidebar.text_input("Live channel filename labels", value="AO, live, green")
    dead_aliases = st.sidebar.text_input("Dead channel filename labels", value="PI, dead, red")
    if not uploaded_files:
        return None

    aliases = {
        "AO": _split_aliases(live_aliases),
        "PI": _split_aliases(dead_aliases),
    }
    with tempfile.TemporaryDirectory() as tmp_dir:
        paths: list[Path] = []
        for uploaded in uploaded_files:
            path = Path(tmp_dir) / uploaded.name
            path.write_bytes(uploaded.getbuffer())
            paths.append(path)
        return load_png_stack(
            paths,
            channel_aliases=aliases,
            voxel_size_um=voxel_size_um or (1.0, 1.0, 1.0),
            source_name=f"{len(paths)} PNG slices",
        )


def _voxel_size_controls(input_mode: str) -> tuple[tuple[float, float, float] | None, bool]:
    st.sidebar.markdown("### 2. Voxel calibration")
    use_nd2_metadata = False
    if input_mode == "ND2 file":
        use_nd2_metadata = st.sidebar.checkbox(
            "Read z spacing and x/y pixel size from ND2 metadata",
            value=True,
            help="Uses physical calibration embedded by the microscope when available.",
        )
        if use_nd2_metadata:
            st.sidebar.caption(
                "If calibration cannot be read from the ND2 file, the app falls back to 1.0 um for z/y/x."
            )
            return None, True

    return (
        (
            st.sidebar.number_input("Z spacing (um)", min_value=0.001, value=1.0, step=0.1),
            st.sidebar.number_input("Y pixel size (um)", min_value=0.001, value=1.0, step=0.1),
            st.sidebar.number_input("X pixel size (um)", min_value=0.001, value=1.0, step=0.1),
        ),
        use_nd2_metadata,
    )


def _show_getting_started(input_mode: str) -> None:
    st.info("Upload image data in the sidebar to begin.")
    if input_mode == "Demo synthetic stack":
        st.markdown(
            "The demo mode generates a synthetic AO/PI biofilm volume and should "
            "display statistics plus live, dead, and merged 3D reconstructions immediately."
        )
    elif input_mode == "PNG stack":
        st.markdown(
            """
            **PNG stack naming convention**

            Upload one grayscale PNG per z-slice per channel. Each filename must
            include a channel label and a sortable z index, for example:

            - `experiment1_AO_z001.png`
            - `experiment1_AO_z002.png`
            - `experiment1_PI_z001.png`
            - `experiment1_PI_z002.png`
            """
        )
    else:
        st.markdown(
            "ND2 files are read with the `nd2` package. Multi-timepoint or "
            "multi-position files use the selected time/position index."
        )


def _channel_controls(stack: BiofilmStack) -> tuple[str, str]:
    st.sidebar.markdown("### 3. Channels")
    channel_names = list(stack.channel_names)
    live_default = _default_channel_index(channel_names, ("ao", "live", "green"))
    dead_default = _default_channel_index(channel_names, ("pi", "dead", "red"))
    live_channel = st.sidebar.selectbox("Live stain channel (AO)", channel_names, index=live_default)
    dead_channel = st.sidebar.selectbox("Dead stain channel (PI)", channel_names, index=dead_default)
    return live_channel, dead_channel


def _segmentation_controls(
    stack: BiofilmStack,
    live_channel: str,
    dead_channel: str,
) -> SegmentationOptions:
    st.sidebar.markdown("### 4. Segmentation")
    threshold_method = st.sidebar.selectbox("Threshold method", ["otsu", "yen", "li", "manual"])
    gaussian_sigma = st.sidebar.number_input(
        "Gaussian smoothing sigma",
        min_value=0.0,
        value=1.0,
        step=0.25,
    )
    min_size = st.sidebar.number_input(
        "Minimum object size (voxels)",
        min_value=0,
        value=64,
        step=8,
    )
    opening_radius = st.sidebar.slider(
        "3D opening radius (voxels)",
        min_value=0,
        max_value=5,
        value=0,
        help="Removes small protrusions and isolated bright speckles before filling holes.",
    )
    closing_radius = st.sidebar.slider(
        "3D closing radius (voxels)",
        min_value=0,
        max_value=5,
        value=0,
        help="Bridges small gaps in segmented biofilm objects before filling holes.",
    )
    fill_holes = st.sidebar.checkbox("Fill holes", value=True)
    background_percentile = st.sidebar.slider(
        "Background percentile subtraction",
        min_value=0.0,
        max_value=25.0,
        value=0.0,
        step=0.5,
    )

    manual_thresholds: dict[str, float] = {}
    if threshold_method == "manual":
        live_image = stack.channel(live_channel)
        dead_image = stack.channel(dead_channel)
        manual_thresholds[live_channel] = st.sidebar.number_input(
            f"{live_channel} manual threshold",
            value=float(np.percentile(live_image, 95)),
        )
        manual_thresholds[dead_channel] = st.sidebar.number_input(
            f"{dead_channel} manual threshold",
            value=float(np.percentile(dead_image, 95)),
        )

    return SegmentationOptions(
        threshold_method=threshold_method,  # type: ignore[arg-type]
        gaussian_sigma=float(gaussian_sigma),
        min_object_size_voxels=int(min_size),
        fill_holes=fill_holes,
        opening_radius_voxels=int(opening_radius),
        closing_radius_voxels=int(closing_radius),
        background_percentile=float(background_percentile),
        manual_thresholds=manual_thresholds,
    )


def _segmentation_preview_section(
    stack: BiofilmStack,
    result: BiofilmAnalysisResult,
    live_channel: str,
    dead_channel: str,
) -> None:
    st.subheader("Real-time segmentation preview")
    st.caption(
        "Adjust the sidebar segmentation controls and inspect this slice preview. "
        "Streamlit reruns the analysis automatically after each choice."
    )

    controls, display = st.columns([0.28, 0.72], gap="large")
    with controls:
        z_index = st.slider(
            "Preview z-slice",
            min_value=0,
            max_value=stack.shape[0] - 1,
            value=stack.shape[0] // 2,
            help="Choose the optical section to inspect while tuning segmentation.",
        )
        preview_mode = st.radio(
            "Preview mode",
            ["Merged overlay", "Live overlay", "Dead overlay", "Raw channels"],
        )
        overlay_opacity = st.slider("Mask overlay opacity", 0.05, 1.0, 0.45, 0.05)
        lower_percentile, upper_percentile = st.slider(
            "Display contrast percentiles",
            min_value=0,
            max_value=100,
            value=(1, 99),
            help="Display-only contrast stretch; does not change segmentation.",
        )

        z_um = z_index * stack.voxel_size_um[0]
        live_slice_fraction = float(result.live.mask[z_index].mean())
        dead_slice_fraction = float(result.dead.mask[z_index].mean())
        occupied_slice_fraction = float(result.occupied_mask[z_index].mean())
        st.metric("Slice depth", f"{z_um:.3f} um")
        st.metric("Occupied on slice", _format_percent(occupied_slice_fraction))
        st.metric("Live mask on slice", _format_percent(live_slice_fraction))
        st.metric("Dead mask on slice", _format_percent(dead_slice_fraction))
        st.caption(
            f"Thresholds: {live_channel}={result.live.threshold:.6g}, "
            f"{dead_channel}={result.dead.threshold:.6g}"
        )

    live_image = stack.channel(live_channel)
    dead_image = stack.channel(dead_channel)
    live_slice = live_image[z_index]
    dead_slice = dead_image[z_index]
    live_mask = result.live.mask[z_index]
    dead_mask = result.dead.mask[z_index]

    with display:
        if preview_mode == "Raw channels":
            live_col, dead_col = st.columns(2)
            with live_col:
                st.plotly_chart(
                    _slice_preview_figure(
                        f"Raw {live_channel} z={z_index}",
                        _grayscale_rgb(live_slice, lower_percentile, upper_percentile),
                    ),
                    use_container_width=True,
                )
            with dead_col:
                st.plotly_chart(
                    _slice_preview_figure(
                        f"Raw {dead_channel} z={z_index}",
                        _grayscale_rgb(dead_slice, lower_percentile, upper_percentile),
                    ),
                    use_container_width=True,
                )
        elif preview_mode == "Live overlay":
            st.plotly_chart(
                _slice_preview_figure(
                    f"{live_channel} raw signal with live mask overlay",
                    _overlay_masks_rgb(
                        live_slice,
                        [(live_mask, (0, 255, 0))],
                        overlay_opacity,
                        lower_percentile,
                        upper_percentile,
                    ),
                ),
                use_container_width=True,
            )
        elif preview_mode == "Dead overlay":
            st.plotly_chart(
                _slice_preview_figure(
                    f"{dead_channel} raw signal with dead mask overlay",
                    _overlay_masks_rgb(
                        dead_slice,
                        [(dead_mask, (255, 0, 0))],
                        overlay_opacity,
                        lower_percentile,
                        upper_percentile,
                    ),
                ),
                use_container_width=True,
            )
        else:
            merged_base = np.maximum(
                _normalize_slice_uint8(live_slice, lower_percentile, upper_percentile),
                _normalize_slice_uint8(dead_slice, lower_percentile, upper_percentile),
            )
            live_only = np.logical_and(live_mask, ~dead_mask)
            dead_only = np.logical_and(dead_mask, ~live_mask)
            overlap = np.logical_and(live_mask, dead_mask)
            st.plotly_chart(
                _slice_preview_figure(
                    "Merged raw signal with live/dead segmentation overlay",
                    _overlay_masks_rgb(
                        merged_base,
                        [
                            (live_only, (0, 255, 0)),
                            (dead_only, (255, 0, 0)),
                            (overlap, (255, 225, 0)),
                        ],
                        overlay_opacity,
                        0,
                        100,
                    ),
                ),
                use_container_width=True,
            )
            st.caption("Overlay colors: live-only green, dead-only red, overlap yellow.")


def _stats_dataframe(stats: dict[str, object]) -> pd.DataFrame:
    labels = {
        "source_name": "Source",
        "dimensions_zyx": "Dimensions (z, y, x)",
        "voxel_size_um": "Voxel size (z, y, x um)",
        "total_voxels": "Total voxels",
        "occupied_voxels": "Occupied voxels",
        "live_voxels": "Live voxels",
        "dead_voxels": "Dead voxels",
        "live_only_voxels": "Live-only voxels",
        "dead_only_voxels": "Dead-only voxels",
        "overlap_voxels": "Overlap voxels",
        "density_fraction": "Density fraction",
        "biovolume_um3": "Biovolume (um3)",
        "live_fraction_of_occupied": "Live fraction of occupied",
        "dead_fraction_of_occupied": "Dead fraction of occupied",
        "overlap_fraction_of_occupied": "Overlap fraction of occupied",
        "live_dead_ratio": "Live/dead ratio",
        "mean_live_intensity_in_live_mask": "Mean live intensity",
        "mean_dead_intensity_in_dead_mask": "Mean dead intensity",
        "mean_thickness_um": "Mean thickness (um)",
        "max_thickness_um": "Max thickness (um)",
        "roughness_coefficient": "Roughness coefficient",
        "substratum_coverage_fraction": "Substratum coverage fraction",
        "areal_biomass_um3_per_um2": "Areal biomass (um3/um2)",
        "estimated_surface_area_um2": "Estimated surface area (um2)",
        "surface_to_biovolume_ratio_um_inv": "Surface/biovolume ratio (1/um)",
        "average_diffusion_distance_um": "Average diffusion distance (um)",
        "max_diffusion_distance_um": "Max diffusion distance (um)",
        "connected_components": "Connected components",
        "live_threshold": "Live threshold",
        "dead_threshold": "Dead threshold",
    }
    rows = [
        {"Metric": labels.get(key, key), "Value": _format_value(value)}
        for key, value in stats.items()
    ]
    return pd.DataFrame(rows)


def _z_profile_dataframe(profile_rows: Iterable[object]) -> pd.DataFrame:
    return pd.DataFrame([row.as_dict() for row in profile_rows])


def _object_dataframe(object_rows: Iterable[object]) -> pd.DataFrame:
    return pd.DataFrame([row.as_dict() for row in object_rows])


def _normalize_slice_uint8(
    image_slice: np.ndarray,
    lower_percentile: float,
    upper_percentile: float,
) -> np.ndarray:
    image = np.asarray(image_slice, dtype=np.float32)
    finite = image[np.isfinite(image)]
    if finite.size == 0:
        return np.zeros(image.shape, dtype=np.uint8)

    low = float(np.percentile(finite, lower_percentile))
    high = float(np.percentile(finite, upper_percentile))
    if high <= low:
        high = float(finite.max())
        low = float(finite.min())
    if high <= low:
        return np.zeros(image.shape, dtype=np.uint8)

    normalized = np.clip((image - low) / (high - low), 0, 1)
    return (normalized * 255).astype(np.uint8)


def _grayscale_rgb(
    image_slice: np.ndarray,
    lower_percentile: float,
    upper_percentile: float,
) -> np.ndarray:
    gray = _normalize_slice_uint8(image_slice, lower_percentile, upper_percentile)
    return np.repeat(gray[:, :, np.newaxis], 3, axis=2)


def _overlay_masks_rgb(
    image_slice: np.ndarray,
    masks_and_colors: list[tuple[np.ndarray, tuple[int, int, int]]],
    overlay_opacity: float,
    lower_percentile: float,
    upper_percentile: float,
) -> np.ndarray:
    rgb = _grayscale_rgb(image_slice, lower_percentile, upper_percentile).astype(np.float32)
    alpha = float(np.clip(overlay_opacity, 0, 1))
    for mask, color in masks_and_colors:
        mask_bool = np.asarray(mask, dtype=bool)
        if not np.any(mask_bool):
            continue
        color_array = np.array(color, dtype=np.float32)
        rgb[mask_bool] = (1 - alpha) * rgb[mask_bool] + alpha * color_array
    return np.clip(rgb, 0, 255).astype(np.uint8)


def _slice_preview_figure(title: str, rgb_image: np.ndarray) -> go.Figure:
    fig = go.Figure(data=go.Image(z=rgb_image))
    fig.update_layout(
        title=title,
        xaxis_title="X",
        yaxis_title="Y",
        height=620,
        margin={"l": 0, "r": 0, "b": 0, "t": 40},
    )
    fig.update_yaxes(scaleanchor="x")
    return fig


def _z_profile_figure(profile_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    series = [
        ("occupied_area_fraction", "Occupied area fraction", "blue"),
        ("live_area_fraction", "Live area fraction", "green"),
        ("dead_area_fraction", "Dead area fraction", "red"),
    ]
    for column, label, color in series:
        fig.add_trace(
            go.Scatter(
                x=profile_df["z_um"],
                y=profile_df[column],
                mode="lines+markers",
                name=label,
                line={"color": color},
            )
        )
    fig.update_layout(
        title="Per-slice biofilm profile",
        xaxis_title="Z depth (um)",
        yaxis_title="Area fraction",
        yaxis_tickformat=".0%",
        height=420,
        margin={"l": 0, "r": 0, "b": 0, "t": 40},
    )
    return fig


def _thickness_heatmap(thickness_map_um: np.ndarray) -> go.Figure:
    fig = go.Figure(
        data=go.Heatmap(
            z=thickness_map_um,
            colorscale="Viridis",
            colorbar={"title": "Thickness (um)"},
        )
    )
    fig.update_layout(
        title="Local biofilm thickness map",
        xaxis_title="X",
        yaxis_title="Y",
        height=520,
        margin={"l": 0, "r": 0, "b": 0, "t": 40},
    )
    return fig


def _single_channel_figure(
    mask: np.ndarray,
    title: str,
    color: str,
    max_points: int,
    marker_size: int,
    marker_opacity: float,
) -> go.Figure:
    coords = _sample_coordinates(mask, max_points)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter3d(
            x=coords[:, 2],
            y=coords[:, 1],
            z=coords[:, 0],
            mode="markers",
            marker={"size": marker_size, "color": color, "opacity": marker_opacity},
            name=title,
        )
    )
    return _style_3d_figure(fig, title)


def _merge_figure(
    live_mask: np.ndarray,
    dead_mask: np.ndarray,
    max_points: int,
    marker_size: int,
    marker_opacity: float,
) -> go.Figure:
    fig = go.Figure()
    masks = [
        ("Live only", np.logical_and(live_mask, ~dead_mask), "green"),
        ("Dead only", np.logical_and(dead_mask, ~live_mask), "red"),
        ("Overlap", np.logical_and(live_mask, dead_mask), "yellow"),
    ]
    for label, mask, color in masks:
        coords = _sample_coordinates(mask, max_points // len(masks))
        fig.add_trace(
            go.Scatter3d(
                x=coords[:, 2],
                y=coords[:, 1],
                z=coords[:, 0],
                mode="markers",
                marker={"size": marker_size, "color": color, "opacity": marker_opacity},
                name=label,
            )
        )
    return _style_3d_figure(fig, "Live/dead merge")


def _sample_coordinates(mask: np.ndarray, max_points: int) -> np.ndarray:
    coords = np.argwhere(mask)
    if coords.size == 0:
        return np.empty((0, 3), dtype=np.int64)
    if coords.shape[0] <= max_points:
        return coords
    step = int(np.ceil(coords.shape[0] / max_points))
    return coords[::step]


def _style_3d_figure(fig: go.Figure, title: str) -> go.Figure:
    fig.update_layout(
        title=title,
        scene={
            "xaxis_title": "X",
            "yaxis_title": "Y",
            "zaxis_title": "Z",
            "aspectmode": "data",
        },
        margin={"l": 0, "r": 0, "b": 0, "t": 40},
        height=650,
    )
    return fig


def _split_aliases(labels: str) -> tuple[str, ...]:
    return tuple(label.strip() for label in labels.split(",") if label.strip())


def _default_channel_index(channel_names: Iterable[str], aliases: tuple[str, ...]) -> int:
    for index, channel_name in enumerate(channel_names):
        lowered = channel_name.lower()
        if lowered in aliases or any(alias in lowered for alias in aliases):
            return index
    return 0


def _format_percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def _format_value(value: object) -> object:
    if isinstance(value, float):
        return f"{value:.6g}"
    return value


if __name__ == "__main__":
    main()
