# Crack Width Statistics: English User Guide

## 1. Purpose

Crack Width Statistics measures crack centerline length and local crack width
from binarized microscopy images. It is intended for reproducible, image-based
materials characterization and provides both per-image and pooled statistics.

The application contains three main visual areas:

- the parameter and navigation panel on the left;
- the original-image overlay in the center;
- the width-colored skeleton, legend, and statistical tables on the right.

## 2. Prepare the Input Data

Create one dataset directory with the following structure:

```text
dataset/
|-- 原图/
|   |-- image_01.tif
|   `-- image_02.tif
|-- 二值化图/
|   |-- image_01.tif
|   `-- image_02.tif
`-- scale_info.txt                 # optional
```

Requirements:

- The folder names must be exactly `原图` and `二值化图`.
- The binarized images are mandatory; original images are optional but strongly
  recommended for visual verification.
- An original image is matched to a binary image by its complete file name.
- Supported formats are `.tif`, `.tiff`, `.png`, `.jpg`, `.jpeg`, and `.bmp`.
- White-on-black and black-on-white binary masks are supported.
- The crack region should form the foreground and the non-crack region should
  form the background.

The optional `scale_info.txt` file is UTF-8 text with this format:

```text
Unit: um
Pixels Per Unit: 1.79931
```

`Pixels Per Unit` means that 1.79931 image pixels correspond to one displayed
unit. When this file is absent, enter the scale manually.

## 3. Start the Application

### Windows executable

1. Download the newest Windows executable from the GitHub Releases page.
2. Double-click the `.exe` file.
3. Click `选择数据目录` and select the dataset directory, not either of its
   two image subfolders.

### Python source

```bat
conda env create -f environment.yml
conda activate crack_width_stats
python src\crack_width_app.py
```

## 4. Parameter Reference

### Pixel value (`像素值(px)`)

The number of pixels represented by the physical reference value below. If the
scale is 1.79931 pixels per micrometer, enter `1.79931` here.

### Corresponding physical width (`对应实际尺度`)

The physical value corresponding to the pixel value. With 1.79931 pixels per
micrometer, enter `1`.

The software calculates:

```text
physical units per pixel = corresponding physical width / pixel value
```

### Unit name (`单位名`)

The unit displayed in the interface and workbook, for example `um`, `mm`, or
`nm`. This text does not perform an additional conversion; the conversion is
defined by the two scale fields above.

### Binary threshold (`二值阈值`)

The grayscale threshold used to separate foreground from background. The
default is `128` for 8-bit images. Increase or decrease it if anti-aliased or
non-ideal binary images contain intermediate gray values.

### Minimum skeleton points (`最小骨架点数`)

Connected skeleton networks or branch-split segments with fewer points than
this value are excluded from segment-level statistics. The number of excluded
objects and points is recorded in the quality-control output.

### Width lower bound (`宽度下限`)

The lower end of the width-distribution range in the displayed physical unit.
Local widths below this value are counted as out of range.

### Width upper bound (`宽度上限`)

The upper end of the width-distribution range. Local widths above this value
are counted as out of range. The upper bound must be greater than the lower
bound.

### Interval step (`区间步长`)

The requested width-bin size. For a lower bound of `0`, upper bound of `3`, and
step of `0.5`, the bins are:

```text
0-0.5, 0.5-1, 1-1.5, 1.5-2, 2-2.5, 2.5-3
```

Bins are left-inclusive and right-exclusive (`[lower, upper)`), except for the
last bin, which includes the final upper bound.

### Over-threshold width (`超阈值宽度`)

A separate reporting threshold in the displayed physical unit. The application
reports the percentage of total centerline length for which:

```text
local width >= over-threshold width
```

For example, if the total crack length is 1000 um and 320 um of that length has
a local width of at least 1.5 um, the over-threshold length percentage is 32%.
This field does not change the width bins or remove cracks.

### Binary view with white background (`二值视图白底`)

Displays the width-colored skeleton on a white background. Clear the option to
use the alternative binary-view background.

### Show labels (`显示编号`)

Shows segment identifiers on the image previews. Turn this off when labels
obscure dense skeleton regions.

### Automatically identify crack color (`自动识别裂纹颜色`)

Automatically treats the less abundant threshold class as the crack
foreground. This is appropriate for most images in which cracks occupy less
than half of the image.

### Cracks are dark in manual mode (`手动模式下裂纹为深色`)

Used only when automatic foreground detection is disabled. Select it for dark
cracks on a bright background and clear it for bright cracks on a dark
background.

### Skeleton opacity (`骨架透明度`)

Controls the opacity of the overlay skeleton without changing any measurement.

### Skeleton line width (`骨架线宽`)

Controls preview line thickness without changing the one-pixel measurement
skeleton.

## 5. Analyze and Review One Image

1. Select the dataset directory.
2. Confirm the scale and segmentation parameters.
3. Click `重新统计当前图` after modifying a numeric or foreground parameter.
4. Use `上一张` and `下一张` to navigate through images.
5. Compare the blue centerline overlay with the source image.
6. Check whether the colored skeleton follows the expected width pattern.
7. Review the summary and the three table tabs.

The summary shows total crack length, length-weighted mean width, maximum width,
the width interval containing the greatest crack length, the over-threshold
length percentage, and the quality-control result.

## 6. Interactive Visual Inspection

### Select a crack segment

Open the `裂纹切段` tab and select a row. The corresponding segment is
highlighted in the image previews while the remaining skeleton is muted. This
is useful for checking segment length, mean width, and branch splitting.

### Select a width interval

Open the `宽度区间` tab and select a row. Only the skeleton locations in that
width interval are emphasized. This makes it possible to locate wide or narrow
parts of the crack network directly in the image.

### Zoom and pan

- Rotate the mouse wheel over an image to zoom in or out.
- Drag the image to pan after zooming.
- Double-click the image to fit it to the available panel again.

These actions affect only the preview.

### Batch quality preview

Click `批量质检预览` to create a scrollable thumbnail grid for all images. Each
tile shows the overlay, total length, weighted mean width, maximum width, and a
quality-control message. Review this page before exporting a large dataset.

## 7. Statistical Definitions

### Centerline length

The binary crack mask is skeletonized to one-pixel width. For each unique pair
of connected skeleton pixels:

- a horizontal or vertical connection contributes `1 px`;
- a diagonal connection contributes `sqrt(2) px`.

The sum is converted to the selected physical unit using the scale factor.

### Local width

The Euclidean distance transform gives the distance from each crack pixel to
the nearest boundary. At every retained skeleton location:

```text
local width = 2 * centerline-to-boundary distance
```

### Length-weighted width statistics

Each local width is weighted by the centerline length represented by its
skeleton location. The reported mean, median, P10, P90, standard deviation, and
over-threshold fraction therefore describe the distribution along crack length,
rather than giving every skeleton point equal influence.

### Crack networks and branch-split segments

A connected crack skeleton is retained as a merged network for total-length
statistics. Branch points are detected from the 8-neighborhood and the network
is split into smaller review segments between endpoints and branch regions.
Both the segment identifier and its parent network identifier are exported.

### Width-interval statistics

For each interval, the program reports:

- crack length within the interval;
- percentage of total crack length in the interval;
- cumulative percentage from the first interval;
- length and percentage at or above the interval lower bound;
- number of skeleton points in the interval.

## 8. Quality-Control Metrics

The `质量指标` tab and exported workbook include:

- original crack area in pixels squared;
- original and retained skeleton-point counts;
- merged-network count and branch-split segment count;
- numbers and points of filtered short networks and segments;
- endpoint, branch-point, and isolated-point counts;
- length and percentage outside the selected width range;
- centerline length associated with branch points but not assigned to a split
  segment;
- an overall quality-control message.

Interpretation guidance:

- Many filtered objects may indicate binary noise or an overly strict minimum
  skeleton size.
- Many endpoints may indicate fragmented segmentation.
- Many branch points may be physically meaningful, but they also warrant visual
  confirmation of the binary mask.
- A large out-of-range percentage means the chosen width range does not cover
  much of the measured distribution.
- A `通过` (`pass`) result means that none of the built-in warning rules was triggered;
  it does not replace inspection of the overlay and binary mask.

## 9. Export All Images

Click `一键输出全部`. A timestamped directory named
`裂纹统计输出_YYYYMMDD_HHMMSS` is created inside the selected dataset folder.

The directory contains:

```text
裂纹统计输出_YYYYMMDD_HHMMSS/
|-- crack_width_statistics.xlsx
|-- batch_quality_preview.png
`-- 预览图/
    |-- image_01_overlay.png
    |-- image_01_width_bins.png
    `-- ...
```

The Excel workbook contains:

- one worksheet per image with crack segments, width intervals, weighted width
  summaries, and quality-control metrics;
- `裂纹段总表`: all branch-split segments from all images;
- `各图宽度区间`: width-bin statistics for every image;
- `宽度区间总统计`: pooled width-bin lengths and percentages;
- `图片总览`: one quality and statistical summary row per image;
- `全局宽度统计`: length-weighted width statistics pooled across all images.

## 10. Recommended Reporting Practice

For reproducible publication results, record the software release, pixel scale,
binary threshold, minimum skeleton points, width range, interval step, and
over-threshold width. Preserve the binarized inputs, the exported workbook, and
the overlay previews used for quality control.

Do not compare datasets processed with different physical calibration or
materially different binary-segmentation rules without documenting those
differences.

## 11. Troubleshooting

### No binary images are found

Confirm that the selected directory contains a subfolder named exactly
`二值化图` and that the images use a supported extension.

### The overlay is blank or uses the wrong source image

Confirm that the corresponding file in `原图` has exactly the same file name as
the binary image. Measurements can still run without the source image, but the
overlay background will be blank.

### The crack/background class is reversed

Try automatic foreground detection first. If it fails, disable it and set the
manual dark-crack option according to the image polarity.

### Too many short segments are removed

Reduce `最小骨架点数`, then recalculate and inspect the quality metrics and
overlay. Avoid choosing the value only to maximize total length; it should
exclude segmentation noise without removing real cracks.

### Width values fall outside the selected range

Increase the upper bound or decrease the lower bound so that the selected range
covers the measured distribution. The out-of-range length remains reported for
quality control.

### The executable does not start

Re-download the current release, verify the SHA-256 checksum, and test from a
local writable folder. Security software may scan a newly downloaded one-file
executable during its first launch. The source version can be used as a fallback
with the provided Conda environment.
