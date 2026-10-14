#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Blender Authors
#
# SPDX-License-Identifier: Apache-2.0

"""ISS-34: compare two *built* Cycles kernels, without changing production code.

Run with system Python (stdlib only), passing separate baseline and candidate Blender
builds. The candidate must actually contain the proposed kernel change; a .blend file
or an unbuilt source edit cannot test it. See --help for options. Results are linear
RGB EXR-derived RMSE against an independent high-SPP baseline render, per-seed
variance (averaged across pixels/channels), and in-process render time. This is a
screening experiment, not a guarantee of improved convergence or unbiasedness.
"""

import argparse
from array import array
import json
import math
from pathlib import Path
import statistics
import struct
import subprocess
import sys
import time


CASES = {
    "dof": "camera/camera_depth_of_field.blend",
    "motion": "motion_blur/camera_zoom_blur_perspective.blend",
    "combined": "denoise/denoise_dof_mblur.blend",
}
PATTERNS = ("SOBOL_BURLEY", "TABULATED_SOBOL")


def pixels(path):
    with path.open("rb") as file:
        width, height = struct.unpack("<II", file.read(8))
        data = array("f")
        data.frombytes(file.read())
    if sys.byteorder != "little":
        data.byteswap()
    if len(data) != width * height * 3:
        raise ValueError(f"Invalid RGB buffer: {path}")
    return (width, height), data


def worker(args):
    import bpy

    bpy.ops.wm.open_mainfile(filepath=str(args.scene))
    scene = bpy.context.scene
    if scene.camera is None:
        raise RuntimeError(f"No active camera in {args.scene}")
    scene.render.engine = "CYCLES"
    bpy.context.preferences.experimental.use_cycles_debug = True
    bpy.context.preferences.view.show_developer_ui = True
    scene.cycles.device = "CPU"
    scene.cycles.sampling_pattern = args.pattern
    scene.cycles.scrambling_distance = 1.0
    scene.cycles.use_adaptive_sampling = False
    scene.cycles.use_denoising = False
    for layer in scene.view_layers:
        layer.cycles.use_denoising = False
        layer.samples = 0
    scene.cycles.samples = args.samples
    scene.cycles.seed = args.seed
    scene.render.use_compositing = False
    scene.render.use_sequencer = False
    scene.render.resolution_x = args.resolution
    scene.render.resolution_y = args.resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "OPEN_EXR"
    scene.render.image_settings.color_depth = "32"
    scene.render.image_settings.color_mode = "RGBA"
    # Disable the unused effect, but reject assets without the effect under test.
    dof = scene.camera.data.dof
    if args.case == "dof":
        if not dof.use_dof or dof.aperture_fstop <= 0:
            raise RuntimeError("DOF control needs an active aperture in its asset")
        scene.render.use_motion_blur = False
    elif args.case == "motion":
        if not scene.render.use_motion_blur:
            raise RuntimeError("Motion control needs motion blur enabled in its asset")
        dof.use_dof = False
    elif args.case == "combined":
        if not scene.render.use_motion_blur or not dof.use_dof:
            raise RuntimeError("Combined control needs both effects enabled in its asset")

    scene.render.filepath = str(args.exr)
    start = time.perf_counter()
    bpy.ops.render.render(write_still=True)
    elapsed = time.perf_counter() - start
    # Read saved EXR as scene-linear float pixels, not a display-transformed PNG.
    image = bpy.data.images.load(str(args.exr), check_existing=False)
    if image.channels != 4:
        raise RuntimeError(f"Expected RGBA EXR, got {image.channels} channels")
    rgba = array("f", [0.0]) * (image.size[0] * image.size[1] * 4)
    image.pixels.foreach_get(rgba)
    rgb = array("f", (rgba[i] for i in range(0, len(rgba)) if i % 4 != 3))
    if sys.byteorder != "little":
        rgb.byteswap()
    with args.raw.open("wb") as file:
        file.write(struct.pack("<II", *image.size))
        file.write(rgb.tobytes())
    args.meta.write_text(json.dumps({
        "seconds": elapsed, "size": list(image.size), "pattern": scene.cycles.sampling_pattern,
        "samples": scene.cycles.samples, "seed": scene.cycles.seed,
        "dof": dof.use_dof, "motion_blur": scene.render.use_motion_blur,
        "device": scene.cycles.device,
    }, indent=2))


def render(binary, scene, case, pattern, samples, seed, resolution, output):
    output = output.resolve()
    exr, raw, meta_path = (output.with_suffix(ext) for ext in (".exr", ".rgb", ".json"))
    for path in (exr, raw, meta_path, output.with_suffix(".log")):
        if path.exists():
            raise FileExistsError(f"Refusing stale render artifact: {path}")
    args = [str(binary), "-b", "--factory-startup", "--disable-autoexec",
            "--python-exit-code", "1", "--python", str(Path(__file__).resolve()),
            "--", "--worker", "--scene", str(scene), "--case", case, "--pattern", pattern,
            "--samples", str(samples), "--seed", str(seed), "--resolution", str(resolution),
            "--exr", str(exr), "--raw", str(raw), "--meta", str(meta_path)]
    with output.with_suffix(".log").open("w") as log:
        subprocess.run(args, check=True, stdout=log, stderr=subprocess.STDOUT)
    for path in (exr, raw, meta_path):
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(f"Render did not produce {path}; inspect {output.with_suffix('.log')}")
    metadata = json.loads(meta_path.read_text())
    expected = {"pattern": pattern, "samples": samples, "seed": seed, "device": "CPU",
                "dof": case != "motion", "motion_blur": case != "dof"}
    for key, value in expected.items():
        if metadata.get(key) != value:
            raise ValueError(f"Unexpected {key} in {meta_path}: {metadata.get(key)!r}, expected {value!r}")
    size, values = pixels(raw)
    if list(size) != metadata.get("size") or not all(math.isfinite(v) for v in values):
        raise ValueError(f"Invalid RGB buffer or size in {raw}")
    if not isinstance(metadata.get("seconds"), (int, float)) or not math.isfinite(metadata["seconds"]) or metadata["seconds"] < 0:
        raise ValueError(f"Invalid render time in {meta_path}")
    return metadata


def evaluate(reference, images):
    size, ref = pixels(reference)
    data = []
    for path in images:
        image_size, values = pixels(path)
        if image_size != size:
            raise ValueError(f"Image size mismatch: {path}")
        data.append(values)
    n = len(ref)
    errors = [math.sqrt(sum((a - b) ** 2 for a, b in zip(img, ref)) / n)
              for img in data]
    # Variance across independent seeds, averaged across linear RGB pixels.
    variance = sum(max(0.0, sum(v * v for v in img) / len(img) -
                       (sum(img) / len(img)) ** 2)
                   for img in zip(*data)) / n
    return {"rmse_by_seed": errors, "mean_rmse": statistics.mean(errors),
            "seed_variance": variance}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, help="built Blender with original mapping")
    parser.add_argument("--candidate", type=Path, help="built Blender with proposed mapping")
    parser.add_argument("--assets", type=Path, help="directory containing render/camera etc.; e.g. tests/files/render")
    parser.add_argument("--output", type=Path, help="new output directory (never overwrite)")
    parser.add_argument("--samples", type=int, nargs="+", default=[1, 16, 64])
    parser.add_argument("--reference-samples", type=int, default=4096)
    parser.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3, 4])
    parser.add_argument("--reference-seed", type=int, default=123456)
    parser.add_argument("--resolution", type=int, default=96)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--scene", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--case", choices=CASES, help=argparse.SUPPRESS)
    parser.add_argument("--pattern", choices=PATTERNS, help=argparse.SUPPRESS)
    parser.add_argument("--seed", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--exr", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--raw", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--meta", type=Path, help=argparse.SUPPRESS)
    # Blender passes its own command line in sys.argv; only arguments after --
    # belong to this script. Normal Python invocations have no separator.
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    args = parser.parse_args(argv)
    if args.worker:
        worker(args)
        return
    if not all((args.baseline, args.candidate, args.assets, args.output)):
        parser.error("--baseline, --candidate, --assets and --output are required")
    if (min(args.samples + args.seeds + [args.reference_samples, args.reference_seed,
                                         args.resolution]) < 1 or
            args.reference_seed in args.seeds or len(set(args.seeds)) != len(args.seeds)):
        parser.error("samples, seeds and resolution must be positive; seeds must be unique and distinct from reference")
    for binary in (args.baseline, args.candidate):
        if not binary.is_file():
            parser.error(f"Missing Blender build: {binary}")
    if args.baseline.resolve() == args.candidate.resolve():
        parser.error("Baseline and candidate must be distinct builds")
    for asset in CASES.values():
        if not (args.assets / asset).is_file():
            parser.error(f"Missing scene: {args.assets / asset}")
    args.output.mkdir(parents=True, exist_ok=False)
    results = {}
    try:
        for case, asset in CASES.items():
            scene = (args.assets / asset).resolve()
            for pattern in PATTERNS:
                prefix = f"{case}_{pattern}"
                reference = args.output / f"{prefix}_reference"
                render(args.baseline.resolve(), scene, case, pattern, args.reference_samples,
                       args.reference_seed, args.resolution, reference)
                row = {}
                for samples in args.samples:
                    groups = {}
                    for label, binary in (("baseline", args.baseline), ("candidate", args.candidate)):
                        paths, times = [], []
                        for seed in args.seeds:
                            output = args.output / f"{prefix}_{samples}_{label}_{seed}"
                            meta = render(binary.resolve(), scene, case, pattern, samples, seed,
                                          args.resolution, output)
                            times.append(meta["seconds"])
                            paths.append(output.with_suffix(".rgb"))
                        groups[label] = {**evaluate(reference.with_suffix(".rgb"), paths),
                                         "render_seconds_by_seed": times,
                                         "mean_render_seconds": statistics.mean(times)}
                    row[str(samples)] = groups
                    print(json.dumps({"case": case, "pattern": pattern,
                                      "samples": samples, "results": groups}), flush=True)
                results[prefix] = row
        (args.output / "summary.json").write_text(json.dumps(results, indent=2))
    except Exception:
        print(f"Render/analysis failed; inspect *.log and *.json in {args.output}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
