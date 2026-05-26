# CARLA 0.9.15 Conda Environment

This folder contains exports of the `carla0915` Conda environment used by the
CARLA demo scripts in this repository.

## Recommended Restore

On another computer with Anaconda or Miniconda installed:

```bash
cd /path/to/carla-lidar-exam
conda env create -f conda_env/carla0915_environment.yml
conda activate carla0915
python --version
```

Expected Python version:

```text
Python 3.7.16
```

The CARLA Python API itself is not installed from pip. The demo scripts add the
bundled repository egg from:

```text
PythonAPI/carla/dist/carla-0.9.15-py3.7-linux-x86_64.egg
```

So keep this repository layout intact when copying it to the other machine.

## Exact Linux Restore

For a more exact restore on Linux x86_64:

```bash
conda create -n carla0915 --file conda_env/carla0915_explicit_linux-64.txt
conda activate carla0915
python -m pip install -r conda_env/carla0915_pip_freeze.txt
```

Use this only on a similar Linux platform. The YAML file is usually easier to
move between machines.

## Quick Test

After restoring:

```bash
conda run -n carla0915 python -m py_compile exam_lidar_minimal.py
./CarlaUE4.sh
```

Then in another terminal:

```bash
./run_exam_lidar_minimal.sh
```
