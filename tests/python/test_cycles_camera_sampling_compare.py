# SPDX-FileCopyrightText: 2026 Blender Authors
#
# SPDX-License-Identifier: Apache-2.0

"""Run: python3 -m unittest discover -s tests/python -p test_cycles_camera_sampling_compare.py"""

from array import array
from pathlib import Path
import struct
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
