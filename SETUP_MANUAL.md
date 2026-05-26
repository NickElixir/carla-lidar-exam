# Manual Setup On Another Computer

This guide explains how to run the CARLA LiDAR exam demo without any agents.

The repository contains the Python client code and Conda environment exports.
It does not contain the full CARLA simulator binaries, maps, or Unreal assets.

## 1. Install CARLA 0.9.15

On the target computer, install or copy CARLA 0.9.15 for Linux.

The Python scripts expect the CARLA Python API egg to exist inside a CARLA
simulator-style folder:

```text
PythonAPI/carla/dist/carla-0.9.15-py3.7-linux-x86_64.egg
```

If this repository is placed inside a full CARLA simulator folder, this path is
already correct. If CARLA is installed elsewhere, either run the scripts from
that full CARLA folder or copy this repository's client files into it.

## 2. Create The Conda Environment

Install Anaconda or Miniconda first. Then run:

```bash
cd /path/to/carla-lidar-exam
conda env create -f conda_env/carla0915_environment.yml
conda activate carla0915
python --version
```

Expected output:

```text
Python 3.7.16
```

For a stricter Linux x86_64 restore, use:

```bash
conda create -n carla0915 --file conda_env/carla0915_explicit_linux-64.txt
conda activate carla0915
python -m pip install -r conda_env/carla0915_pip_freeze.txt
```

The YAML restore is usually easier. The explicit restore is more exact but less
portable.

## 3. Check Python Dependencies

From the repository or CARLA folder:

```bash
conda run -n carla0915 python -m py_compile exam_lidar_minimal.py
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
conda activate carla0915
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

If Python cannot import `carla`, make sure the CARLA Python egg path exists:

```bash
ls PythonAPI/carla/dist/carla-0.9.15-py3.7-linux-x86_64.egg
```

If Open3D is slow or unstable:

```bash
./run_exam_lidar_minimal.sh --no-open3d
```

If the LiDAR scan looks split or incomplete, keep the LiDAR rotation frequency
aligned with the synchronous timestep. For example:

```bash
--fixed-delta-seconds 0.05 --lidar-rotation-frequency 20
```

because `1 / 0.05 = 20 Hz`.
