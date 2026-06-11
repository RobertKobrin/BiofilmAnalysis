#!/usr/bin/env python3
"""Generate a labeled synthetic AO/PI PNG stack for GUI visualization."""

from __future__ import annotations

import argparse
from pathlib import Path

from biofilm_analyzer.demo import write_demo_png_stack


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default="demo_data/png_stack",
        help="Directory where PNG slices will be written.",
    )
    parser.add_argument("--z-slices", type=int, default=28)
    parser.add_argument("--height", type=int, default=96)
    parser.add_argument("--width", type=int, default=96)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    written = write_demo_png_stack(
        Path(args.output_dir),
        z_slices=args.z_slices,
        height=args.height,
        width=args.width,
        seed=args.seed,
    )
    print(f"Wrote {len(written)} PNG slices to {args.output_dir}")


if __name__ == "__main__":
    main()
