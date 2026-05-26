# CARLA Conda Environments

This folder contains Conda environment files for the CARLA demo scripts in this
repository.

- `carla0916_environment.yml` is the default environment for CARLA 0.9.16.
- `carla0915_environment.yml` is kept for CARLA 0.9.15 compatibility.

## Recommended Restore

On another computer with Anaconda or Miniconda installed:

```bash
cd /path/to/carla-lidar-exam
conda env create -f conda_env/carla0916_environment.yml
conda activate carla0916
python --version
```

Expected Python version:

```text
Python 3.10.x
```

The CARLA Python API is installed as `carla==0.9.16` from pip by the YAML file.
The demo scripts can also add a simulator wheel from:

```text
PythonAPI/carla/dist/carla-0.9.16-*.whl
```

If you use a manually installed simulator API instead of the pip package, keep
that layout intact or set `CARLA_ROOT` to the CARLA 0.9.16 simulator folder.

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
conda run -n carla0916 python -m py_compile exam_lidar_minimal.py
./CarlaUE4.sh
```

Then in another terminal:

```bash
./run_exam_lidar_minimal.sh
```

The Python API and simulator server must be the same CARLA version. This
default environment is for CARLA 0.9.16. To run against CARLA 0.9.15, use
`CARLA_CONDA_ENV=carla0915 ./run_exam_lidar_minimal.sh` with a 0.9.15 server.
