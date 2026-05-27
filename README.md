# SiCnw Crack Width Statistics

A desktop Python tool for measuring crack length and width distributions from
binarized microscopy images. The repository is organized in a lightweight
research-code style similar to `krkaufma/ML-EFA`: a small `src/` directory for
the analysis program, environment files at the repository root, and separate
metadata files for authorship, citation, and licensing.

## Features

- Converts binarized crack regions into single-pixel skeleton centerlines.
- Computes crack length using 8-neighborhood pixel geometry: horizontal and
  vertical links count as `1 px`, diagonal links count as `sqrt(2) px`.
- Estimates local crack width with a distance transform and reports width as
  `2 * distance_to_edge`.
- Generates width intervals from a total range and step size. For example,
  `0` to `3` with step `0.5` produces `0-0.5`, `0.5-1`, `1-1.5`,
  `1.5-2`, `2-2.5`, and `2.5-3`.
- Provides a Tkinter GUI for browsing images, viewing overlays, and exporting
  Excel summaries plus preview images.

## Repository Layout

```text
.
├── src/
│   └── crack_width_app.py
├── data/
│   └── README.md
├── AUTHORS.rst
├── CITATION.cff
├── LICENSE
├── environment.yml
├── requirements.txt
└── run_app.bat
```

## Installation

Create the Conda environment:

```bat
conda env create -f environment.yml
conda activate crack_width_stats
```

If the environment already exists:

```bat
conda activate crack_width_stats
```

## Usage

Start the application:

```bat
python src\crack_width_app.py
```

On Windows, you can also double-click `run_app.bat`.

## Windows Executable

A Windows executable is available from the GitHub release page when a release
is published. To rebuild it locally:

```bat
build_exe.bat
```

The generated file is `dist\SiCnwCrackWidthStats.exe`.

The default data layout is:

```text
SiCnw-bu/
└── crop_20260219_194515/
    ├── 原图/
    ├── 二值化图/
    └── scale_info.txt
```

The GUI lets you choose a different data directory. The selected directory
should contain `原图` and `二值化图` subfolders. Statistics are computed from
the binarized images, and matching source images are used for overlays.

## Width Intervals

Use `宽度下限`, `宽度上限`, and `区间步长` in the GUI to define the width
range. Values below the lower bound or above the upper bound are not included
in the interval summary table.

## Outputs

The export button creates:

- per-image crack segment statistics;
- per-image width-interval length statistics;
- a global segment summary;
- a global width-interval summary;
- overlay preview images for manual checking.

## Citation

If you use this software, cite the associated manuscript and the archived
release of this repository. A `CITATION.cff` file is included so that GitHub
can display citation metadata for the repository.
