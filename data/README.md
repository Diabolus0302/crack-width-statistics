# Data Layout

Place microscopy images in this repository only when the data are cleared for
public release. The application expects the following folder layout:

```text
example-data-root/
`-- crop_20260219_194515/
    |-- 原图/
    |-- 二值化图/
    `-- scale_info.txt
```

The statistical workflow uses files in `二值化图` as the primary input and looks
for same-name source images in `原图` for visual overlays.
