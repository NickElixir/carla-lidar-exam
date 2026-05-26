# Manual Setup On Another Computer

This guide explains how to run the CARLA LiDAR exam demo without any agents.

The repository contains the Python client code and Conda environment exports.
It does not contain the full CARLA simulator binaries, maps, or Unreal assets.

## 1. Install CARLA 0.9.16

On the target computer, install or copy CARLA 0.9.16 for Linux.

The Conda YAML installs the CARLA Python API as `carla==0.9.16` from pip.
Alternatively, the Python scripts can load the CARLA Python API egg from a
simulator-style folder:

```text
PythonAPI/carla/dist/carla-0.9.16-*.whl
```

If this repository is placed inside a full CARLA simulator folder, this path is
already correct. If CARLA is installed elsewhere, set `CARLA_ROOT` to that full
CARLA folder before running the scripts.

## 2. Create The Conda Environment

Install Anaconda or Miniconda first. Then run:

```bash
cd /path/to/carla-lidar-exam
conda env create -f conda_env/carla0916_environment.yml
conda activate carla0916
python --version
```

Expected output:

```text
Python 3.10.x
```

The older CARLA 0.9.15 environment is still available as
`conda_env/carla0915_environment.yml`, but the default launcher uses
`carla0916`.

To force another environment for experiments, set `CARLA_CONDA_ENV`.

## 3. Check Python Dependencies

From the repository or CARLA folder:

```bash
conda run -n carla0916 python -m py_compile exam_lidar_minimal.py
```

If this passes, Python dependencies are available.

## 4. Start CARLA

In the full CARLA simulator folder:

```bash
./CarlaUE4.sh
```

Wait until the simulator window is open and the map is loaded.

## 5. Run The Demo

In a second terminal:

```bash
conda activate carla0916
cd /path/to/full/CARLA_simulator_or_repo
./run_exam_lidar_minimal.sh
```

This starts:

- a camera viewer for manual driving;
- a semantic LiDAR visualization;
- static pedestrians around the ego vehicle;
- optional ground-truth 3D boxes in the LiDAR viewer.

Controls:

```text
W / Up Arrow      drive forward
S / Down Arrow    brake / reverse
A / Left Arrow    steer left
D / Right Arrow   steer right
Space             hand brake
Esc               quit
L                 save dataset frame when dataset mode is enabled
```

## 6. Export A Dataset Frame

Run:

```bash
./run_exam_lidar_dataset.sh
```

Output:

```text
exam_dataset/
  lidar/
    000000.pcd
  label/
    000000.json
```

Check the result:

```bash
ls -lh exam_dataset/lidar exam_dataset/label
head -20 exam_dataset/lidar/000000.pcd
python -m json.tool exam_dataset/label/000000.json | head -80
```

## Common Issues

If Python cannot import `carla`, make sure the package is installed:

```bash
python -m pip install carla==0.9.16
```

Or point `CARLA_ROOT` to a simulator folder containing the matching Python API:

```bash
export CARLA_ROOT=/path/to/CARLA_0.9.16
```

If the script reports a client/server mismatch, the running simulator version
does not match this environment. For this repository's default `carla0916`
environment, start CARLA 0.9.16.

If Open3D is slow or unstable:

```bash
./run_exam_lidar_minimal.sh --no-open3d
```

The default launcher uses dense LiDAR settings:

```bash
--lidar-points-per-second 500000 --open3d-max-points 500000
```

For less noisy/smeared demo visuals, the script disables camera post-processing
and sets LiDAR noise/dropoff attributes to zero when the active CARLA blueprint
supports those attributes.

Manual driving uses throttle ramping instead of a hard speed limit. The default
forward throttle is `0.55`, reached gradually via `--throttle-ramp-rate 0.9`.

If the LiDAR scan looks split or incomplete, keep the LiDAR rotation frequency
aligned with the synchronous timestep. For example:

```bash
--fixed-delta-seconds 0.05 --lidar-rotation-frequency 20
```

because `1 / 0.05 = 20 Hz`.
