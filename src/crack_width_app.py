# -*- coding: utf-8 -*-
from __future__ import annotations

import math
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageOps, ImageTk
from scipy import ndimage as ndi
from skimage import measure, morphology

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError as exc:
    raise SystemExit("当前 Python 环境缺少 tkinter，请安装带 tkinter 的 Python。") from exc


APP_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = APP_DIR.parent / "SiCnw-bu" / "crop_20260219_194515"
IMAGE_SUFFIXES = {".tif", ".tiff", ".png", ".jpg", ".jpeg", ".bmp"}


@dataclass
class SegmentStat:
    segment_id: int
    length_px: float
    width_px: float
    length_unit: float
    width_unit: float
    skeleton_points: int
    centroid_x: float
    centroid_y: float
    bbox_x: int
    bbox_y: int
    bbox_w: int
    bbox_h: int


@dataclass
class AnalysisResult:
    name: str
    mask: np.ndarray
    skeleton: np.ndarray
    widths_px: np.ndarray
    pixel_length_share: np.ndarray
    component_labels: np.ndarray
    segments: List[SegmentStat]
    bin_table: pd.DataFrame
    total_length_px: float
    total_length_unit: float


def natural_key(text: str) -> List[object]:
    parts = re.split(r"(\d+)", text)
    return [int(p) if p.isdigit() else p.lower() for p in parts]


def read_scale_info(data_dir: Path) -> Tuple[float, float, str]:
    pixel_value = 100.0
    real_value = 1.0
    unit = "mm"
    info_path = data_dir / "scale_info.txt"
    if not info_path.exists():
        return pixel_value, real_value, unit

    text = info_path.read_text(encoding="utf-8", errors="ignore")
    unit_match = re.search(r"Unit:\s*(.+)", text)
    ppu_match = re.search(r"Pixels Per Unit:\s*([0-9.]+)", text)
    if unit_match:
        unit = unit_match.group(1).strip()
    if ppu_match:
        pixel_value = float(ppu_match.group(1))
        real_value = 1.0
    return pixel_value, real_value, unit


def list_images(folder: Path) -> List[Path]:
    if not folder.exists():
        return []
    return sorted(
        [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES],
        key=lambda p: natural_key(p.name),
    )


def image_to_gray(path: Path) -> np.ndarray:
    with Image.open(path) as img:
        return np.asarray(ImageOps.grayscale(img), dtype=np.uint8)


def read_display_image(path: Optional[Path], fallback_shape: Tuple[int, int]) -> Image.Image:
    if path and path.exists():
        with Image.open(path) as img:
            return ImageOps.grayscale(img).convert("RGB")
    h, w = fallback_shape
    return Image.new("RGB", (w, h), "white")


def binary_mask_from_image(
    gray: np.ndarray,
    threshold: int,
    auto_foreground: bool,
    crack_is_dark: bool,
) -> np.ndarray:
    bright = gray >= threshold
    if auto_foreground:
        foreground = bright if bright.mean() <= 0.5 else ~bright
    else:
        foreground = ~bright if crack_is_dark else bright
    try:
        foreground = morphology.remove_small_objects(foreground.astype(bool), max_size=2)
    except TypeError:
        foreground = morphology.remove_small_objects(foreground.astype(bool), min_size=3)
    return ndi.binary_fill_holes(foreground).astype(bool)


def build_width_bins(range_min: float, range_max: float, step: float) -> List[Tuple[float, float]]:
    if range_max <= range_min:
        raise ValueError("宽度上限必须大于宽度下限。")
    if step <= 0:
        raise ValueError("区间步长必须大于 0。")

    bins: List[Tuple[float, float]] = []
    low = range_min
    guard = 0
    while low < range_max - 1e-12:
        high = min(range_max, low + step)
        bins.append((round(low, 10), round(high, 10)))
        low = high
        guard += 1
        if guard > 10000:
            raise ValueError("区间数量过多，请增大步长或缩小取值范围。")
    return bins


def unit_factor(pixel_value: float, real_value: float) -> float:
    if pixel_value <= 0:
        raise ValueError("像素值必须大于 0。")
    return real_value / pixel_value


def skeleton_edge_lengths(skeleton: np.ndarray) -> Tuple[float, np.ndarray]:
    coords = np.argwhere(skeleton)
    share = np.zeros(skeleton.shape, dtype=float)
    total = 0.0
    skel = skeleton.astype(bool)
    offsets = [(0, 1, 1.0), (1, 0, 1.0), (1, 1, math.sqrt(2.0)), (1, -1, math.sqrt(2.0))]
    h, w = skeleton.shape
    for y, x in coords:
        for dy, dx, weight in offsets:
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and skel[ny, nx]:
                total += weight
                share[y, x] += weight / 2.0
                share[ny, nx] += weight / 2.0
    lonely = skel & (share == 0)
    share[lonely] = 1.0
    total += float(lonely.sum())
    return total, share


def analyze_binary_image(
    image_path: Path,
    pixel_value: float,
    real_value: float,
    unit_name: str,
    bins: List[Tuple[float, float]],
    threshold: int,
    auto_foreground: bool,
    crack_is_dark: bool,
    min_skeleton_points: int,
) -> AnalysisResult:
    gray = image_to_gray(image_path)
    mask = binary_mask_from_image(gray, threshold, auto_foreground, crack_is_dark)
    skeleton = morphology.skeletonize(mask)
    distances = ndi.distance_transform_edt(mask)
    widths_px = distances * 2.0
    total_length_px, share = skeleton_edge_lengths(skeleton)
    px_to_unit = unit_factor(pixel_value, real_value)

    labels = measure.label(skeleton, connectivity=2)
    props = measure.regionprops(labels)
    segments: List[SegmentStat] = []
    kept = np.zeros_like(skeleton, dtype=bool)
    segment_id = 1

    for prop in props:
        component = labels == prop.label
        points = int(component.sum())
        if points < min_skeleton_points:
            continue
        component_share = share * component
        length_px = float(component_share.sum())
        if length_px <= 0:
            continue
        width_px = float((widths_px * component_share).sum() / length_px)
        minr, minc, maxr, maxc = prop.bbox
        cy, cx = prop.centroid
        segments.append(
            SegmentStat(
                segment_id=segment_id,
                length_px=length_px,
                width_px=width_px,
                length_unit=length_px * px_to_unit,
                width_unit=width_px * px_to_unit,
                skeleton_points=points,
                centroid_x=float(cx),
                centroid_y=float(cy),
                bbox_x=int(minc),
                bbox_y=int(minr),
                bbox_w=int(maxc - minc),
                bbox_h=int(maxr - minr),
            )
        )
        kept |= component
        segment_id += 1

    skeleton = kept
    share = share * kept
    total_length_px = float(share.sum())
    total_length_unit = total_length_px * px_to_unit

    bin_rows = []
    width_units = widths_px * px_to_unit
    for idx, (low, high) in enumerate(bins):
        if idx == len(bins) - 1:
            in_bin = skeleton & (width_units >= low) & (width_units <= high)
        else:
            in_bin = skeleton & (width_units >= low) & (width_units < high)
        length_px = float(share[in_bin].sum())
        bin_rows.append(
            {
                f"区间下限({unit_name})": low,
                f"区间上限({unit_name})": high,
                "累计长度(px)": length_px,
                f"累计长度({unit_name})": length_px * px_to_unit,
                "骨架点数": int(in_bin.sum()),
            }
        )

    return AnalysisResult(
        name=image_path.stem,
        mask=mask,
        skeleton=skeleton,
        widths_px=widths_px,
        pixel_length_share=share,
        component_labels=labels,
        segments=segments,
        bin_table=pd.DataFrame(bin_rows),
        total_length_px=total_length_px,
        total_length_unit=total_length_unit,
    )


def segments_to_dataframe(segments: List[SegmentStat], unit_name: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "裂纹段编号": s.segment_id,
                "长度(px)": s.length_px,
                "宽度(px)": s.width_px,
                f"长度({unit_name})": s.length_unit,
                f"宽度({unit_name})": s.width_unit,
                "骨架点数": s.skeleton_points,
                "质心X": s.centroid_x,
                "质心Y": s.centroid_y,
                "边界框X": s.bbox_x,
                "边界框Y": s.bbox_y,
                "边界框宽": s.bbox_w,
                "边界框高": s.bbox_h,
            }
            for s in segments
        ]
    )


def colors_for_bins(count: int) -> List[Tuple[int, int, int]]:
    base = [
        (61, 90, 254),
        (0, 172, 193),
        (67, 160, 71),
        (251, 192, 45),
        (245, 124, 0),
        (229, 57, 53),
        (142, 36, 170),
        (93, 64, 55),
    ]
    if count <= len(base):
        return base[:count]
    colors = []
    for i in range(count):
        hue = i / max(count, 1)
        r = int(127 + 100 * math.sin(2 * math.pi * hue))
        g = int(127 + 100 * math.sin(2 * math.pi * (hue + 0.33)))
        b = int(127 + 100 * math.sin(2 * math.pi * (hue + 0.66)))
        colors.append((r, g, b))
    return colors


def draw_skeleton_pixels(
    image: Image.Image,
    result: AnalysisResult,
    bins: List[Tuple[float, float]],
    pixel_value: float,
    real_value: float,
    mode: str,
    show_labels: bool,
) -> Image.Image:
    out = image.convert("RGB")
    arr = np.asarray(out).copy()
    px_to_unit = unit_factor(pixel_value, real_value)
    yx = np.argwhere(result.skeleton)
    if mode == "blue":
        color_lookup = np.tile(np.array([[20, 35, 240]], dtype=np.uint8), (len(yx), 1))
    else:
        bin_colors = np.array(colors_for_bins(len(bins)), dtype=np.uint8)
        widths_unit = result.widths_px[result.skeleton] * px_to_unit
        color_lookup = np.tile(np.array([[170, 170, 170]], dtype=np.uint8), (len(yx), 1))
        for idx, (low, high) in enumerate(bins):
            if idx == len(bins) - 1:
                in_bin = (widths_unit >= low) & (widths_unit <= high)
            else:
                in_bin = (widths_unit >= low) & (widths_unit < high)
            color_lookup[in_bin] = bin_colors[idx]

    h, w = result.skeleton.shape
    for (y, x), color in zip(yx, color_lookup):
        y0, y1 = max(0, y - 1), min(h, y + 2)
        x0, x1 = max(0, x - 1), min(w, x + 2)
        arr[y0:y1, x0:x1] = color

    out = Image.fromarray(arr)
    if show_labels:
        draw = ImageDraw.Draw(out)
        for seg in result.segments:
            draw.text((seg.centroid_x + 4, seg.centroid_y + 4), str(seg.segment_id), fill=(255, 0, 0))
    return out


def mask_to_display(mask: np.ndarray, white_background: bool) -> Image.Image:
    if white_background:
        arr = np.where(mask, 0, 255).astype(np.uint8)
    else:
        arr = np.where(mask, 255, 0).astype(np.uint8)
    return Image.fromarray(arr, mode="L").convert("RGB")


class ImagePanel(ttk.Frame):
    def __init__(self, master: tk.Misc, title: str) -> None:
        super().__init__(master)
        self.title_var = tk.StringVar(value=title)
        ttk.Label(self, textvariable=self.title_var, anchor="center").pack(fill="x", pady=(6, 4))
        self.canvas = tk.Canvas(self, bg="white", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._photo: Optional[ImageTk.PhotoImage] = None
        self._image: Optional[Image.Image] = None
        self.canvas.bind("<Configure>", lambda _event: self.redraw())

    def set_image(self, image: Image.Image) -> None:
        self._image = image
        self.redraw()

    def redraw(self) -> None:
        self.canvas.delete("all")
        if self._image is None:
            return
        cw = max(self.canvas.winfo_width(), 10)
        ch = max(self.canvas.winfo_height(), 10)
        iw, ih = self._image.size
        scale = min(cw / iw, ch / ih)
        nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
        resized = self._image.resize((nw, nh), Image.Resampling.LANCZOS)
        self._photo = ImageTk.PhotoImage(resized)
        self.canvas.create_image(cw // 2, ch // 2, image=self._photo, anchor="center")


class CrackStatsApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("裂纹宽度分段统计")
        self.geometry("1580x860")
        self.minsize(1180, 680)

        self.data_dir = DEFAULT_DATA_DIR
        self.original_dir = self.data_dir / "原图"
        self.binary_dir = self.data_dir / "二值化图"
        self.binary_images: List[Path] = []
        self.original_map: Dict[str, Path] = {}
        self.index = 0
        self.current_result: Optional[AnalysisResult] = None
        self.result_cache: Dict[Tuple[str, str], AnalysisResult] = {}

        pixel_value, real_value, unit_name = read_scale_info(self.data_dir)
        self.pixel_value_var = tk.StringVar(value=f"{pixel_value:g}")
        self.real_value_var = tk.StringVar(value=f"{real_value:g}")
        self.unit_var = tk.StringVar(value=unit_name)
        self.threshold_var = tk.StringVar(value="128")
        self.width_min_var = tk.StringVar(value="0")
        self.width_max_var = tk.StringVar(value="3")
        self.width_step_var = tk.StringVar(value="0.5")
        self.min_points_var = tk.StringVar(value="5")
        self.white_bg_var = tk.BooleanVar(value=True)
        self.show_labels_var = tk.BooleanVar(value=False)
        self.auto_foreground_var = tk.BooleanVar(value=True)
        self.crack_dark_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="")

        self._build_ui()
        self.reload_images()
        self.analyze_current()

    def _build_ui(self) -> None:
        root = ttk.Frame(self)
        root.pack(fill="both", expand=True, padx=12, pady=12)
        root.columnconfigure(0, weight=0, minsize=330)
        root.columnconfigure(1, weight=1)
        root.columnconfigure(2, weight=1)
        root.rowconfigure(0, weight=1)

        controls = ttk.Frame(root)
        controls.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        controls.columnconfigure(1, weight=1)

        ttk.Button(controls, text="选择数据目录", command=self.choose_data_dir).grid(row=0, column=0, columnspan=2, sticky="ew")
        self.path_label = ttk.Label(controls, text=str(self.data_dir), wraplength=310)
        self.path_label.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 10))

        row = 2
        for label, var in [
            ("像素值(px)", self.pixel_value_var),
            ("对应实际尺度", self.real_value_var),
            ("单位名", self.unit_var),
            ("二值阈值", self.threshold_var),
            ("最小骨架点数", self.min_points_var),
            ("宽度下限", self.width_min_var),
            ("宽度上限", self.width_max_var),
            ("区间步长", self.width_step_var),
        ]:
            ttk.Label(controls, text=label).grid(row=row, column=0, sticky="w", pady=3)
            ttk.Entry(controls, textvariable=var).grid(row=row, column=1, sticky="ew", pady=3)
            row += 1

        ttk.Checkbutton(controls, text="二值视图白底", variable=self.white_bg_var, command=self.refresh_views).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(8, 2)
        )
        row += 1
        ttk.Checkbutton(controls, text="显示编号", variable=self.show_labels_var, command=self.refresh_views).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=2
        )
        row += 1
        ttk.Checkbutton(controls, text="自动识别裂纹颜色", variable=self.auto_foreground_var, command=self.analyze_current).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=2
        )
        row += 1
        ttk.Checkbutton(controls, text="手动模式下裂纹为深色", variable=self.crack_dark_var, command=self.analyze_current).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=2
        )
        row += 1

        ttk.Button(controls, text="重新统计当前图", command=self.analyze_current).grid(row=row, column=0, columnspan=2, sticky="ew", pady=(10, 4))
        row += 1
        ttk.Button(controls, text="一键输出全部", command=self.export_all).grid(row=row, column=0, columnspan=2, sticky="ew")
        row += 1

        nav = ttk.Frame(controls)
        nav.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(12, 4))
        nav.columnconfigure((0, 1), weight=1)
        ttk.Button(nav, text="← 上一张", command=self.prev_image).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(nav, text="下一张 →", command=self.next_image).grid(row=0, column=1, sticky="ew", padx=(4, 0))
        row += 1

        self.counter_var = tk.StringVar(value="")
        ttk.Label(controls, textvariable=self.counter_var, anchor="center").grid(row=row, column=0, columnspan=2, sticky="ew")
        row += 1

        ttk.Label(controls, textvariable=self.status_var, wraplength=310, foreground="#555").grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=(10, 0)
        )

        center = ttk.Frame(root)
        center.grid(row=0, column=1, sticky="nsew", padx=(0, 10))
        center.rowconfigure(0, weight=1)
        center.columnconfigure(0, weight=1)
        self.overlay_panel = ImagePanel(center, "叠加图")
        self.overlay_panel.grid(row=0, column=0, sticky="nsew")

        right = ttk.Frame(root)
        right.grid(row=0, column=2, sticky="nsew")
        right.rowconfigure(0, weight=3)
        right.rowconfigure(1, weight=2)
        right.columnconfigure(0, weight=1)
        self.binary_panel = ImagePanel(right, "二值视图（分段着色）")
        self.binary_panel.grid(row=0, column=0, sticky="nsew")

        table_frame = ttk.Frame(right)
        table_frame.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        table_frame.rowconfigure(1, weight=1)
        table_frame.columnconfigure(0, weight=1)
        ttk.Label(table_frame, text="右下角：裂纹段统计（当前图片）").grid(row=0, column=0, sticky="w")
        columns = ("id", "length_px", "width_px", "length_unit", "width_unit", "points")
        self.table = ttk.Treeview(table_frame, columns=columns, show="headings", height=8)
        for col, text, width in [
            ("id", "段ID", 70),
            ("length_px", "长度(px)", 95),
            ("width_px", "宽度(px)", 95),
            ("length_unit", "长度", 95),
            ("width_unit", "宽度", 95),
            ("points", "骨架点数", 85),
        ]:
            self.table.heading(col, text=text)
            self.table.column(col, width=width, anchor="center")
        self.table.grid(row=1, column=0, sticky="nsew")
        ybar = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        ybar.grid(row=1, column=1, sticky="ns")
        self.table.configure(yscrollcommand=ybar.set)

    def choose_data_dir(self) -> None:
        selected = filedialog.askdirectory(initialdir=str(self.data_dir), title="选择包含原图和二值化图的目录")
        if not selected:
            return
        self.data_dir = Path(selected)
        self.original_dir = self.data_dir / "原图"
        self.binary_dir = self.data_dir / "二值化图"
        pixel_value, real_value, unit_name = read_scale_info(self.data_dir)
        self.pixel_value_var.set(f"{pixel_value:g}")
        self.real_value_var.set(f"{real_value:g}")
        self.unit_var.set(unit_name)
        self.reload_images()
        self.analyze_current()

    def reload_images(self) -> None:
        self.binary_images = list_images(self.binary_dir)
        originals = list_images(self.original_dir)
        self.original_map = {p.name: p for p in originals}
        self.index = min(self.index, max(0, len(self.binary_images) - 1))
        self.path_label.configure(text=str(self.data_dir))
        self.result_cache.clear()
        self.update_counter()

    def update_counter(self) -> None:
        if not self.binary_images:
            self.counter_var.set("未找到二值化图")
            return
        self.counter_var.set(f"{self.binary_images[self.index].stem}  ({self.index + 1}/{len(self.binary_images)})")

    def current_parameters(self) -> Tuple[float, float, str, List[Tuple[float, float]], int, int]:
        pixel_value = float(self.pixel_value_var.get())
        real_value = float(self.real_value_var.get())
        unit_name = self.unit_var.get().strip() or "unit"
        width_min = float(self.width_min_var.get())
        width_max = float(self.width_max_var.get())
        width_step = float(self.width_step_var.get())
        bins = build_width_bins(width_min, width_max, width_step)
        threshold = int(float(self.threshold_var.get()))
        min_points = max(1, int(float(self.min_points_var.get())))
        return pixel_value, real_value, unit_name, bins, threshold, min_points

    def cache_key(self, image_path: Path) -> Tuple[str, str]:
        values = [
            self.pixel_value_var.get(),
            self.real_value_var.get(),
            self.unit_var.get(),
            self.width_min_var.get(),
            self.width_max_var.get(),
            self.width_step_var.get(),
            self.threshold_var.get(),
            self.min_points_var.get(),
            str(self.auto_foreground_var.get()),
            str(self.crack_dark_var.get()),
        ]
        return (str(image_path), "|".join(values))

    def analyze_current(self) -> None:
        if not self.binary_images:
            self.status_var.set(f"未在 {self.binary_dir} 中找到二值化图。")
            return
        image_path = self.binary_images[self.index]
        try:
            pixel_value, real_value, unit_name, bins, threshold, min_points = self.current_parameters()
            key = self.cache_key(image_path)
            if key not in self.result_cache:
                self.result_cache[key] = analyze_binary_image(
                    image_path=image_path,
                    pixel_value=pixel_value,
                    real_value=real_value,
                    unit_name=unit_name,
                    bins=bins,
                    threshold=threshold,
                    auto_foreground=self.auto_foreground_var.get(),
                    crack_is_dark=self.crack_dark_var.get(),
                    min_skeleton_points=min_points,
                )
            self.current_result = self.result_cache[key]
            self.update_counter()
            self.refresh_views()
            self.refresh_table()
            self.status_var.set(
                f"当前图：{len(self.current_result.segments)} 段，"
                f"总长度 {self.current_result.total_length_unit:.4f} {unit_name}。"
            )
        except Exception as exc:
            messagebox.showerror("统计失败", str(exc))

    def refresh_views(self) -> None:
        if self.current_result is None:
            return
        try:
            pixel_value, real_value, _unit_name, bins, _threshold, _min_points = self.current_parameters()
        except Exception:
            return
        binary_path = self.binary_images[self.index]
        original = read_display_image(self.original_map.get(binary_path.name), self.current_result.mask.shape)
        overlay = draw_skeleton_pixels(
            original,
            self.current_result,
            bins,
            pixel_value,
            real_value,
            mode="blue",
            show_labels=self.show_labels_var.get(),
        )
        binary_view = mask_to_display(self.current_result.mask, self.white_bg_var.get())
        colored = draw_skeleton_pixels(
            binary_view,
            self.current_result,
            bins,
            pixel_value,
            real_value,
            mode="bins",
            show_labels=self.show_labels_var.get(),
        )
        self.overlay_panel.title_var.set(f"叠加图：{self.current_result.name}")
        self.binary_panel.title_var.set(f"二值视图（分段着色）：{self.current_result.name}")
        self.overlay_panel.set_image(overlay)
        self.binary_panel.set_image(colored)

    def refresh_table(self) -> None:
        for item in self.table.get_children():
            self.table.delete(item)
        if self.current_result is None:
            return
        unit_name = self.unit_var.get().strip() or "unit"
        self.table.heading("length_unit", text=f"长度({unit_name})")
        self.table.heading("width_unit", text=f"宽度({unit_name})")
        for seg in self.current_result.segments:
            self.table.insert(
                "",
                "end",
                values=(
                    seg.segment_id,
                    f"{seg.length_px:.2f}",
                    f"{seg.width_px:.2f}",
                    f"{seg.length_unit:.4f}",
                    f"{seg.width_unit:.4f}",
                    seg.skeleton_points,
                ),
            )

    def prev_image(self) -> None:
        if not self.binary_images:
            return
        self.index = (self.index - 1) % len(self.binary_images)
        self.analyze_current()

    def next_image(self) -> None:
        if not self.binary_images:
            return
        self.index = (self.index + 1) % len(self.binary_images)
        self.analyze_current()

    def export_all(self) -> None:
        if not self.binary_images:
            messagebox.showwarning("无法导出", "没有找到二值化图。")
            return
        try:
            pixel_value, real_value, unit_name, bins, threshold, min_points = self.current_parameters()
        except Exception as exc:
            messagebox.showerror("参数错误", str(exc))
            return

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = self.data_dir / f"裂纹统计输出_{stamp}"
        preview_dir = out_dir / "预览图"
        preview_dir.mkdir(parents=True, exist_ok=True)
        excel_path = out_dir / "crack_width_statistics.xlsx"

        all_segment_frames = []
        all_bin_frames = []
        summary_rows = []

        try:
            with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
                for idx, binary_path in enumerate(self.binary_images, start=1):
                    result = analyze_binary_image(
                        image_path=binary_path,
                        pixel_value=pixel_value,
                        real_value=real_value,
                        unit_name=unit_name,
                        bins=bins,
                        threshold=threshold,
                        auto_foreground=self.auto_foreground_var.get(),
                        crack_is_dark=self.crack_dark_var.get(),
                        min_skeleton_points=min_points,
                    )
                    seg_df = segments_to_dataframe(result.segments, unit_name)
                    bin_df = result.bin_table.copy()
                    seg_df.to_excel(writer, sheet_name=self.safe_sheet_name(result.name), index=False, startrow=0)
                    bin_df.to_excel(writer, sheet_name=self.safe_sheet_name(result.name), index=False, startrow=len(seg_df) + 3)

                    named_seg_df = seg_df.copy()
                    named_seg_df.insert(0, "图片名", result.name)
                    all_segment_frames.append(named_seg_df)

                    named_bin_df = bin_df.copy()
                    named_bin_df.insert(0, "图片名", result.name)
                    all_bin_frames.append(named_bin_df)

                    summary_rows.append(
                        {
                            "图片名": result.name,
                            "裂纹段数": len(result.segments),
                            "总长度(px)": result.total_length_px,
                            f"总长度({unit_name})": result.total_length_unit,
                        }
                    )

                    original = read_display_image(self.original_map.get(binary_path.name), result.mask.shape)
                    overlay = draw_skeleton_pixels(
                        original,
                        result,
                        bins,
                        pixel_value,
                        real_value,
                        mode="blue",
                        show_labels=self.show_labels_var.get(),
                    )
                    overlay.save(preview_dir / f"{result.name}_overlay.png")
                    self.status_var.set(f"正在导出 {idx}/{len(self.binary_images)}：{result.name}")
                    self.update_idletasks()

                if all_segment_frames:
                    pd.concat(all_segment_frames, ignore_index=True).to_excel(writer, sheet_name="总汇总表", index=False)
                if all_bin_frames:
                    pd.concat(all_bin_frames, ignore_index=True).to_excel(writer, sheet_name="各图宽度区间统计", index=False)
                    total_bin = pd.concat(all_bin_frames, ignore_index=True)
                    lower_col = f"区间下限({unit_name})"
                    upper_col = f"区间上限({unit_name})"
                    length_col = f"累计长度({unit_name})"
                    grouped = (
                        total_bin.groupby([lower_col, upper_col], dropna=False)[["累计长度(px)", length_col, "骨架点数"]]
                        .sum()
                        .reset_index()
                    )
                    grouped.to_excel(writer, sheet_name="宽度区间总统计", index=False)
                pd.DataFrame(summary_rows).to_excel(writer, sheet_name="图片总览", index=False)

            self.status_var.set(f"导出完成：{excel_path}")
            messagebox.showinfo("导出完成", f"已导出：\n{excel_path}\n\n预览图目录：\n{preview_dir}")
        except Exception as exc:
            messagebox.showerror("导出失败", str(exc))

    @staticmethod
    def safe_sheet_name(name: str) -> str:
        cleaned = re.sub(r"[\[\]:*?/\\]", "_", name)
        return cleaned[:31] or "Sheet"


def main() -> None:
    app = CrackStatsApp()
    app.mainloop()


if __name__ == "__main__":
    main()
