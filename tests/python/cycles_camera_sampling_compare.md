# ISS-34: camera Sobol dimension experiment

Production keeps time=x, lens=(y,z). The x,y lens-only alternative is **not**
validated by a 2D Sobol projection argument: it needs paired render evidence.

`cycles_camera_sampling_compare.py` uses the checked-in Cycles scenes
`camera/camera_depth_of_field.blend` (DOF only),
`motion_blur/camera_zoom_blur_perspective.blend` (MB only) and
`denoise/denoise_dof_mblur.blend` (both). It rejects scenes if the expected
camera effect is off. It compares the Sobol-Burley and tabulated Sobol patterns.
The MB-only control should give identical images for a lens-only change;
non-identical images point to a confounder. Other camera types and blue-noise
patterns require separate validation before changing their behavior.

Build **two separate** Blender executables from identical sources/configuration
except for the candidate dimension mapping. Do not use the packaged
`release/darwin/Blender.app/Contents/MacOS/blender` as evidence for either
source revision without verifying how it was built. On a machine that can run
both binaries, from the repository root:

```sh
python3 tests/python/cycles_camera_sampling_compare.py \
  --baseline /absolute/path/to/baseline/blender \
  --candidate /absolute/path/to/candidate/blender \
  --assets tests/files/render --output /tmp/iss34-camera
```

`python3 tests/python/cycles_camera_sampling_compare.py --help` lists optional
sample counts, independent seeds and resolution. The stdlib-only metrics smoke
check is `python3 -m unittest discover -s tests/python -p test_cycles_camera_sampling_compare.py`. Defaults: 1/16/64 SPP,
seeds 1-4, 4096-SPP reference seed 123456, 96x96, CPU. Each Blender worker
opens the scene, forces Cycles, explicit sampling pattern, seed, 32-bit float
EXR, no adaptive sampling, no denoising/compositing, and writes timing and
scene flags. Per-render logs, EXRs, linear RGB buffers and JSON metadata are
retained in a new output directory; a completed run writes `summary.json`.
Runs abort on missing assets, unsupported pattern or disabled effects. Expect
many renders (three scenes x two patterns x two variants x four seeds x three
sample counts, plus six references); reduce `--seeds`/`--samples` for a smoke
check. Use multiple seeds for a variance comparison.

`mean_rmse` is the average per-seed linear RGB RMSE versus an *independent*
high-SPP baseline image of the same scene/pattern; `seed_variance` is mean
per-channel, per-pixel population variance across the selected independent
seeds. `mean_render_seconds` measures the render call only (not startup,
image loading, EXR I/O or build time). Evaluate per-case deltas across seeds,
check reference noise with a higher reference SPP if effects are small, and
repeat with other scenes/seeds before changing production. Low RMSE alone
is not proof of unbiasedness; the same reference can favor the baseline, and
small samples/finite references have noise. Record source revisions, build
options, CPU, scene versions and full output alongside any reported numbers.
