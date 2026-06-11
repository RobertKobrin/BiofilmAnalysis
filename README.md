# BiofilmAnalysis

BiofilmAnalysis is a Streamlit research application for segmenting and
quantifying 3D bacterial biofilms from Nikon `.nd2` files or labeled PNG
z-stacks. It is designed for AO/PI live-dead staining workflows.

## Features

- Load a built-in synthetic demo stack, Nikon ND2 files, or grayscale PNG stacks.
- Infer live/dead PNG channels from filename labels such as `AO` and `PI`.
- Select the live stain channel (AO) and dead stain channel (PI).
- Configure segmentation:
  - Otsu, Yen, Li, or manual thresholds
  - Gaussian smoothing
  - Background percentile subtraction
  - Minimum 3D object size
  - Optional 3D opening and closing for speckle removal or gap filling
  - Hole filling
- Display quantitative biofilm statistics:
  - Live, dead, live-only, dead-only, and overlapping voxels
  - Biofilm density
  - Biovolume
  - Live/dead ratio
  - Mean live/dead signal intensity
  - Mean and maximum thickness
  - Roughness coefficient
  - Substratum coverage
  - Areal biomass
  - Estimated surface area
  - Surface-to-biovolume ratio
  - Average and maximum diffusion distance
  - Connected component count
- Display BiofilmQ/COMSTAT-style secondary outputs:
  - Per-z-slice live/dead/occupied profiles
  - Local thickness heatmap
  - Per-object volume, centroid, bounding box, live/dead fraction, and signal
    intensity
- Render interactive 3D reconstructions for live signal, dead signal, and
  merged live/dead signal.
- Export statistics, z-profiles, thickness maps, and object tables as CSV.

## Installation

```bash
scripts/setup_environment.sh
source .venv/bin/activate
```

## Run the GUI

```bash
scripts/run_app.sh
```

The app listens on `0.0.0.0:8501` by default so cloud workspaces and forwarded
ports can open the Streamlit UI in a browser.

For a quick visual smoke test, choose **Demo synthetic stack** in the sidebar.
The app will immediately segment a generated AO/PI biofilm volume and display
statistics plus live, dead, and merged 3D reconstructions.

## Generate demo PNG data

To create uploadable PNG slices that follow the expected naming convention:

```bash
make demo-data
```

This writes files such as `demo_data/png_stack/demo_AO_z001.png` and
`demo_data/png_stack/demo_PI_z001.png`. In the GUI, choose **PNG stack** and
upload the generated files to exercise the file-upload workflow.

## PNG stack naming

For PNG input, upload one image per z-slice per channel. Filenames must include
a channel label and sortable z index.

Example:

```text
experiment1_AO_z001.png
experiment1_AO_z002.png
experiment1_PI_z001.png
experiment1_PI_z002.png
```

Default live-channel labels are `AO`, `live`, and `green`. Default dead-channel
labels are `PI`, `dead`, and `red`. These labels can be edited in the sidebar.

## ND2 input

ND2 support uses the `nd2` Python package. The importer normalizes image data to
`z, y, x, channel` order. For time-lapse or multi-position files, select the time
and position index in the sidebar before analysis.

## Development

Run tests with:

```bash
make test
```
