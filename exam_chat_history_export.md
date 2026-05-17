# Exam Development Chat History Export

This is a compact English export of the development history for the CARLA LiDAR exam task.

## Original Exam Task

The exam PDF described this setup:

- run a CARLA server;
- create one ego vehicle;
- create 20 static NPCs around the ego vehicle at different distances;
- attach a LiDAR sensor to the ego vehicle;
- visualize the point cloud and Ground Truth 3D Bounding Boxes with Open3D;
- optionally store a dataset with `.pcd` files and `.json` labels in SUSTechPOINTS format.

## Repository Analysis

The repository already contained CARLA 0.9.15, PythonAPI examples, maps, LiDAR examples, and custom scripts:

- `manual_control_lidar_demo.py`
- `run_manual_lidar.sh`
- `manual_camera_lidar_minimap.py`
- CARLA examples such as `PythonAPI/examples/open3d_lidar.py`

The first conclusion was that the repository had a strong base, but it missed stable GT 3D boxes and dataset export.

## Backup And First Cleanup

A backup was created:

```text
manual_control_lidar_demo.py.bak_2026-05-17
```

The original script was reviewed. Main risks:

- it cleared all existing vehicles and walkers by default;
- it depended on a specific Python/CARLA environment;
- pygame camera output was unreliable on this machine;
- Open3D point cloud existed, but GT boxes were not implemented;
- dataset export was missing.

Some safety changes were added to the old script, but the black pygame window problem remained.

## New Minimal Script

A new script was created from scratch:

```text
exam_lidar_minimal.py
```

The first goal was to remove complexity and keep only the exam pipeline:

- connect to CARLA;
- spawn ego vehicle;
- spawn 20 static pedestrians;
- attach RGB camera;
- attach semantic LiDAR;
- show Open3D point cloud;
- support manual driving.

## Pygame Problem

The pygame vehicle window stayed black. Debugging showed:

- CARLA camera frames were valid;
- `debug_exam_camera_first_frame.png` contained a real image;
- pygame could save a drawn surface to `debug_pygame_display.png`;
- the real pygame window still showed black.

This suggested that the issue was not CARLA camera settings. It was probably an SDL/pygame window display problem on this desktop session.

## Tk Viewer Workaround

The camera viewer was moved from pygame to:

```text
tkinter + PIL.ImageTk
```

This fixed the visible camera window. Keyboard handling was then improved with:

- `bind_all`;
- physical key codes for `WASD`, arrows, `Space`, `Esc`, and `L`;
- a status line showing active keys.

Reverse driving was also fixed. `S` or `Arrow Down` now brakes first, then sets reverse gear and applies throttle.

## Performance Improvements

The scene was lagging at first. The following changes were made:

- reduced camera window resolution to `800x450`;
- reduced Tk viewer update rate to `10 FPS`;
- reduced Open3D update rate to `5 Hz`;
- limited Open3D points to `30000`;
- reduced LiDAR points per second to `100000`;
- avoided unnecessary full point cloud copies;
- added `--no-open3d` for a stable driving and dataset mode.

## GT 3D Bounding Boxes

Ground Truth boxes were added using CARLA actor bounding boxes.

The pipeline for boxes:

1. Read each pedestrian actor bounding box.
2. Build 8 local box vertices.
3. Transform vertices from actor space to world space.
4. Transform from world space to LiDAR space.
5. Convert coordinates for Open3D.
6. Draw 12 box edges as Open3D `LineSet`.

Open3D sometimes rejected the line set with a native `RuntimeError`. The code was made safer:

- skip invalid bbox extents;
- check finite vertices;
- use contiguous numpy arrays;
- continue with point cloud only if Open3D rejects boxes.

## Dataset Export

Dataset export was added with:

```text
run_exam_lidar_dataset.sh
```

This launcher runs with:

```text
--no-open3d --save-dataset --save-once
```

This avoids Open3D segmentation faults during dataset writing.

Output:

```text
exam_dataset/lidar/000000.pcd
exam_dataset/label/000000.json
```

The first dataset attempt produced a non-empty PCD but an empty JSON. This was fixed by removing the distance filter for dataset labels. After the fix, the JSON contained all spawned pedestrians.

Final verified result:

```text
labels: 20
types: ['Pedestrian']
```

## Final Current State

Working scripts:

- `run_exam_lidar_minimal.sh`: interactive scene and visualization;
- `run_exam_lidar_dataset.sh`: stable dataset export;
- `exam_lidar_minimal.py`: main implementation.

Verified features:

- one ego vehicle;
- 20 static pedestrians;
- RGB camera viewer;
- manual control;
- reverse gear;
- semantic LiDAR;
- Open3D point cloud;
- GT 3D boxes;
- dataset export with PCD and SUSTechPOINTS-like JSON labels.

## Useful Commands

Run CARLA:

```bash
./CarlaUE4.sh
```

Run interactive scene:

```bash
./run_exam_lidar_minimal.sh
```

Run without Open3D:

```bash
./run_exam_lidar_minimal.sh --no-open3d
```

Run without GT boxes:

```bash
./run_exam_lidar_minimal.sh --hide-gt-boxes
```

Export dataset:

```bash
./run_exam_lidar_dataset.sh
```

Check dataset:

```bash
ls -lh exam_dataset/lidar exam_dataset/label
head -20 exam_dataset/lidar/000000.pcd
python -m json.tool exam_dataset/label/000000.json | head -80
```

Count labels:

```bash
python - <<'PY'
import json
with open("exam_dataset/label/000000.json") as f:
    labels = json.load(f)
print("labels:", len(labels))
print("types:", sorted(set(x["obj_type"] for x in labels)))
PY
```

