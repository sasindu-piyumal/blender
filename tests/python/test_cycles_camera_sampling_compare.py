# SPDX-FileCopyrightText: 2026 Blender Authors
#
# SPDX-License-Identifier: Apache-2.0

"""Run: python3 -m unittest discover -s tests/python -p test_cycles_camera_sampling_compare.py"""

from array import array
from pathlib import Path
import json
import os
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import cycles_camera_sampling_compare as comparator
from cycles_camera_sampling_compare import evaluate


class CameraSamplingCompareTest(unittest.TestCase):
    def test_rmse_and_seed_variance(self):
        with tempfile.TemporaryDirectory() as directory:
            def write(name, values):
                path = Path(directory) / name
                with path.open("wb") as file:
                    file.write(struct.pack("<II", 1, 1))
                    file.write(array("f", values).tobytes())
                return path

            ref = write("reference.rgb", [0.0, 0.0, 0.0])
            first = write("first.rgb", [1.0, 1.0, 1.0])
            second = write("second.rgb", [-1.0, -1.0, -1.0])
            result = evaluate(ref, [first, second])
            self.assertEqual(result["rmse_by_seed"], [1.0, 1.0])
            self.assertEqual(result["mean_rmse"], 1.0)
            self.assertEqual(result["seed_variance"], 1.0)

            wrong_size = Path(directory) / "wrong.rgb"
            with wrong_size.open("wb") as file:
                file.write(struct.pack("<II", 2, 1))
                file.write(array("f", [1.0] * 6).tobytes())
            with self.assertRaises(ValueError):
                evaluate(ref, [wrong_size])

    def test_blender_argv_dispatch(self):
        argv = ["blender", "-b", "--factory-startup", "--python", "script.py", "--",
                "--worker", "--scene", "scene.blend", "--case", "dof", "--pattern",
                "SOBOL_BURLEY", "--samples", "1", "--seed", "7"]
        with mock.patch.object(sys, "argv", argv), mock.patch.object(comparator, "worker") as worker:
            comparator.main()
        worker.assert_called_once()
        self.assertEqual(worker.call_args.args[0].seed, 7)
        self.assertEqual(worker.call_args.args[0].scene, Path("scene.blend"))

    def test_relative_output_and_worker_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            assets = root / "assets"
            scene = assets / "camera" / "camera_depth_of_field.blend"
            scene.parent.mkdir(parents=True)
            scene.touch()
            baseline, candidate = root / "baseline", root / "candidate"
            baseline.touch()
            candidate.touch()
            observed = []

            def fake_blender(command, **kwargs):
                self.assertIn("--python-exit-code", command)
                self.assertEqual(command[command.index("--python-exit-code") + 1], "1")
                self.assertIn("--disable-autoexec", command)
                self.assertEqual(command[command.index("--") + 1], "--worker")
                def fake_worker(args):
                    self.assertTrue(args.exr.is_absolute())
                    self.assertTrue(args.raw.is_absolute())
                    self.assertTrue(args.meta.is_absolute())
                    observed.append((args.samples, args.seed, args.exr))
                    args.exr.write_bytes(b"EXR fixture")
                    with args.raw.open("wb") as file:
                        file.write(struct.pack("<II", args.resolution, args.resolution))
                        file.write(array("f", [float(args.samples)] * (args.resolution ** 2 * 3)).tobytes())
                    args.meta.write_text(json.dumps({
                        "pattern": args.pattern, "samples": args.samples, "seed": args.seed,
                        "device": "CPU", "scene": str(args.scene.resolve()), "case": args.case,
                        "dof": True, "motion_blur": False,
                        "size": [args.resolution, args.resolution], "seconds": 0.25,
                    }))
                with mock.patch.object(sys, "argv", command), mock.patch.object(comparator, "worker", fake_worker):
                    comparator.main()

            argv = ["script.py", "--baseline", str(baseline), "--candidate", str(candidate),
                    "--assets", str(assets), "--output", "relative-results", "--samples", "1",
                    "--seeds", "2", "--reference-samples", "4"]
            with mock.patch.dict(comparator.CASES, {"dof": "camera/camera_depth_of_field.blend"}, clear=True), \
                 mock.patch.object(comparator, "PATTERNS", ("SOBOL_BURLEY",)), \
                 mock.patch.object(comparator.subprocess, "run", side_effect=fake_blender), \
                 mock.patch.object(sys, "argv", argv):
                previous = Path.cwd()
                try:
                    os.chdir(root)
                    comparator.main()
                finally:
                    os.chdir(previous)
            self.assertEqual(len(observed), 3)  # reference, baseline, candidate
            self.assertTrue((root / "relative-results" / "summary.json").is_file())

    def test_reject_stale_and_missing_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            output.with_suffix(".exr").write_bytes(b"old")
            with self.assertRaises(FileExistsError), mock.patch.object(comparator.subprocess, "run") as run:
                comparator.render(Path("blender"), Path("scene.blend"), "dof", "SOBOL_BURLEY",
                                  1, 1, 32, output)
            run.assert_not_called()
            output.with_suffix(".exr").unlink()
            with mock.patch.object(comparator.subprocess, "run"):
                with self.assertRaisesRegex(RuntimeError, "did not produce"):
                    comparator.render(Path("blender"), Path("scene.blend"), "dof", "SOBOL_BURLEY",
                                      1, 1, 32, output)
            output.with_suffix(".log").unlink()

            def wrong_run(command, **kwargs):
                for extension in (".exr", ".rgb"):
                    output.with_suffix(extension).write_bytes(b"not empty")
                output.with_suffix(".json").write_text(json.dumps({
                    "pattern": "TABULATED_SOBOL", "samples": 1, "seed": 1,
                    "scene": str(Path("scene.blend").resolve()), "case": "dof",
                    "device": "CPU", "dof": True, "motion_blur": False,
                }))
            with mock.patch.object(comparator.subprocess, "run", side_effect=wrong_run):
                with self.assertRaisesRegex(ValueError, "Unexpected pattern"):
                    comparator.render(Path("blender"), Path("scene.blend"), "dof", "SOBOL_BURLEY",
                                      1, 1, 32, output)


if __name__ == "__main__":
    unittest.main()
