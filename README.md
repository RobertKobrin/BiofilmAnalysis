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
- Preview segmentation choices on individual z-slices:
  - Raw AO and PI views
  - Live, dead, and merged mask overlays
  - Adjustable overlay opacity and display contrast
  - Per-slice occupied/live/dead mask percentages
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

## Real-time segmentation preview

After loading a stack, use the **Real-time segmentation preview** section near
the top of the app to inspect a selected z-slice. Change the thresholding,
smoothing, background subtraction, object-size filtering, opening/closing, or
hole-filling controls in the sidebar; the slice overlay updates on rerun so you
can tune the segmentation before relying on the final statistics. The preview
supports raw channel views, live-only overlay, dead-only overlay, and merged
live/dead overlay.

## Install a desktop icon

On Linux desktops, install a clickable launcher with:

```bash
make desktop-icon
```

This creates an application-menu entry at
`~/.local/share/applications/biofilm-analysis.desktop` and, if `~/Desktop`
exists, a desktop icon at `~/Desktop/biofilm-analysis.desktop`. Clicking it
starts BiofilmAnalysis on `http://127.0.0.1:8501` and opens the app in your
default browser. If the app is already running, the launcher just opens the
browser tab.

If your desktop environment blocks newly created launchers, right-click the icon
and choose an option such as **Allow Launching** or **Trust and Launch**.

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

By default, ND2 input reads physical calibration from the file metadata and uses
it for volume, thickness, surface area, diffusion distance, and object-size
statistics. The GUI displays the voxel size actually used after loading. If an
ND2 file is missing calibration metadata, the app falls back to `1.0 um` for
z/y/x; uncheck **Read z spacing and x/y pixel size from ND2 metadata** in the
sidebar to enter manual calibration values instead.

## Development

Run tests with:

```bash
make test
```
