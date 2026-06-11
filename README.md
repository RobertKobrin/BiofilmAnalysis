# BiofilmAnalysis

BiofilmAnalysis is a Streamlit research application for segmenting and
quantifying 3D bacterial biofilms from Nikon `.nd2` files or labeled PNG
z-stacks. It is designed for AO/PI live-dead staining workflows.

## Features

- Load Nikon ND2 files or grayscale PNG stacks.
- Infer live/dead PNG channels from filename labels such as `AO` and `PI`.
- Select the live stain channel (AO) and dead stain channel (PI).
- Configure segmentation:
  - Otsu, Yen, Li, or manual thresholds
  - Gaussian smoothing
  - Background percentile subtraction
  - Minimum 3D object size
  - Hole filling
- Display quantitative biofilm statistics:
  - Live, dead, live-only, dead-only, and overlapping voxels
  - Biofilm density
  - Biovolume
  - Live/dead ratio
  - Mean live/dead signal intensity
  - Mean and maximum thickness
  - Estimated surface area
  - Connected component count
- Render interactive 3D reconstructions for live signal, dead signal, and
  merged live/dead signal.
- Export statistics as CSV.

## Installation

```bash
python -m pip install -e ".[dev]"
```

## Run the GUI

```bash
streamlit run src/biofilm_analyzer/app.py
```

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
pytest
```
