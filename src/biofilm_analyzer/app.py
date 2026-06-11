"""Streamlit GUI for 3D biofilm segmentation and analysis."""

from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Iterable

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from biofilm_analyzer.analysis import SegmentationOptions, analyze_biofilm
from biofilm_analyzer.demo import create_demo_stack
from biofilm_analyzer.io import BiofilmStack, load_nd2_stack, load_png_stack


def main() -> None:
    st.set_page_config(page_title="Biofilm 3D Analyzer", layout="wide")
    st.title("3D Biofilm Segmentation and Analysis")
    st.caption(
        "Analyze AO/PI live-dead biofilm stacks from Nikon ND2 files or "
        "filename-labeled PNG z-stacks."
    )

    input_mode = st.sidebar.radio("Input format", ["Demo synthetic stack", "PNG stack", "ND2 file"])
    voxel_size_um = (
        st.sidebar.number_input("Z spacing (um)", min_value=0.001, value=1.0, step=0.1),
        st.sidebar.number_input("Y pixel size (um)", min_value=0.001, value=1.0, step=0.1),
        st.sidebar.number_input("X pixel size (um)", min_value=0.001, value=1.0, step=0.1),
    )

    stack = _load_stack(input_mode, voxel_size_um)
    if stack is None:
        _show_getting_started(input_mode)
        return

    st.success(
        f"Loaded {stack.source_name}: z={stack.shape[0]}, y={stack.shape[1]}, "
        f"x={stack.shape[2]}, channels={', '.join(stack.channel_names)}"
    )

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
    left, right = st.columns([0.45, 0.55], gap="large")
    with left:
        st.subheader("Biofilm statistics")
        st.dataframe(stats_df, use_container_width=True, hide_index=True)
        st.download_button(
            "Download statistics CSV",
            data=stats_df.to_csv(index=False).encode("utf-8"),
            file_name="biofilm_statistics.csv",
            mime="text/csv",
        )
    with right:
        st.subheader("Segmentation summary")
        st.metric("Biofilm density", _format_percent(result.statistics.density_fraction))
        st.metric("Live fraction", _format_percent(result.statistics.live_fraction_of_occupied))
        st.metric("Dead fraction", _format_percent(result.statistics.dead_fraction_of_occupied))
        st.metric("Biovolume", f"{result.statistics.biovolume_um3:,.2f} um3")
        st.metric("Roughness coefficient", f"{result.statistics.roughness_coefficient:.3f}")
        st.metric("Substratum coverage", _format_percent(result.statistics.substratum_coverage_fraction))

    st.subheader("COMSTAT-style profiles and object analysis")
    profile_df = _z_profile_dataframe(result.z_profile)
    object_df = _object_dataframe(result.object_statistics)
    profile_tab, thickness_tab, object_tab = st.tabs(["Z profiles", "Thickness map", "3D objects"])
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

    st.subheader("3D reconstructions")
    max_points = st.slider(
        "Maximum rendered voxels per reconstruction",
        min_value=1_000,
        max_value=100_000,
        value=25_000,
        step=1_000,
        help="Lower values keep large stacks responsive in the browser.",
    )
    marker_size = st.slider("3D marker size", min_value=1, max_value=8, value=2)
    marker_opacity = st.slider("3D marker opacity", min_value=0.05, max_value=1.0, value=0.55, step=0.05)
    live_tab, dead_tab, merge_tab = st.tabs(["Live signal (AO)", "Dead signal (PI)", "Merge"])
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
    voxel_size_um: tuple[float, float, float],
) -> BiofilmStack | None:
    if input_mode == "Demo synthetic stack":
        st.sidebar.header("Demo data")
        z_slices = st.sidebar.slider("Demo z-slices", min_value=8, max_value=64, value=28, step=2)
        image_size = st.sidebar.slider("Demo x/y size", min_value=48, max_value=160, value=96, step=8)
        seed = st.sidebar.number_input("Demo random seed", min_value=0, value=7, step=1)
        return create_demo_stack(
            z_slices=int(z_slices),
            height=int(image_size),
            width=int(image_size),
            seed=int(seed),
            voxel_size_um=voxel_size_um,
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
                voxel_size_um=voxel_size_um,
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
            voxel_size_um=voxel_size_um,
            source_name=f"{len(paths)} PNG slices",
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
    st.sidebar.header("Channels")
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
    st.sidebar.header("Segmentation options")
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
