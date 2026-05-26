#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

export SDL_VIDEO_X11_NET_WM_BYPASS_COMPOSITOR="${SDL_VIDEO_X11_NET_WM_BYPASS_COMPOSITOR:-0}"
export SDL_RENDER_DRIVER="${SDL_RENDER_DRIVER:-software}"
if [[ -n "${DISPLAY:-}" && -z "${SDL_VIDEODRIVER:-}" ]]; then
  export SDL_VIDEODRIVER=x11
fi

CARLA_CONDA_ENV="${CARLA_CONDA_ENV:-carla0916}"

exec conda run --no-capture-output -n "$CARLA_CONDA_ENV" python exam_lidar_minimal.py \
  --viewer tk \
  --width 800 \
  --height 450 \
  --viewer-fps 10 \
  --open3d-update-hz 5 \
  --open3d-max-points 30000 \
  --lidar-points-per-second 100000 \
  --lidar-rotation-frequency 10 \
  --fixed-delta-seconds 0.1 \
  --clear-existing-npcs \
  --static-people 20 \
  --people-radius 10 \
  --people-min-distance 2 \
  "$@"
