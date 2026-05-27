from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def existing_option(flag: str, path: Path, target: str) -> list[str]:
    if path.exists():
        return [flag, f"{path};{target}"]
    return []


def main() -> None:
    base_prefix = Path(sys.base_prefix)
    conda_library = base_prefix / "Library"
    conda_bin = conda_library / "bin"
    conda_lib = conda_library / "lib"

    args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        "--windowed",
        "--onefile",
        "--name",
        "SiCnwCrackWidthStats",
    ]

    for dll in ["tk86t.dll", "tcl86t.dll", "zlib.dll", "ffi.dll", "LIBBZ2.dll"]:
        args.extend(existing_option("--add-binary", conda_bin / dll, "."))
    args.extend(existing_option("--add-data", conda_lib / "tcl8.6", r"tcl\tcl8.6"))
    args.extend(existing_option("--add-data", conda_lib / "tk8.6", r"tcl\tk8.6"))

    for module in [
        "pandas",
        "matplotlib",
        "jinja2",
        "IPython",
        "pytest",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "cv2",
        "skimage.data",
        "skimage.io",
        "skimage.viewer",
        "skimage.filters",
        "skimage.transform",
        "skimage.feature",
        "skimage.restoration",
        "skimage.metrics",
        "skimage.segmentation",
        "skimage.registration",
        "skimage.graph",
        "skimage.measure",
    ]:
        args.extend(["--exclude-module", module])

    args.append(str(ROOT / "src" / "crack_width_app.py"))
    subprocess.check_call(args, cwd=ROOT)


if __name__ == "__main__":
    main()
