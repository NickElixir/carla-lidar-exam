#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

export SDL_VIDEO_X11_NET_WM_BYPASS_COMPOSITOR="${SDL_VIDEO_X11_NET_WM_BYPASS_COMPOSITOR:-0}"
export SDL_RENDER_DRIVER="${SDL_RENDER_DRIVER:-software}"
if [[ -n "${DISPLAY:-}" && -z "${SDL_VIDEODRIVER:-}" ]]; then
  export SDL_VIDEODRIVER=x11
fi

PYTHON="${PYTHON:-$SCRIPT_DIR/.venv/bin/python}"

if [[ ! -x "$PYTHON" ]]; then
  echo "Python environment not found: $PYTHON" >&2
  echo "Create it first, for example: /home/isr-lab3/miniconda3/envs/carla0916/bin/python -m venv .venv" >&2
  exit 1
fi

exec "$PYTHON" exam_lidar_minimal.py \
  --viewer tk \
  --width 800 \
  --height 450 \
  --viewer-fps 10 \
  --open3d-update-hz 5 \
  --open3d-max-points 500000\
  --lidar-points-per-second 500000 \
  --lidar-rotation-frequency 20 \
  --lidar-noise-stddev 0.02 \
  --fixed-delta-seconds 0.05 \
  --clear-existing-npcs \
  --static-people 20 \
  --people-min-distance 2.0 \
  --people-radius 12.0 \
  --lidar-range 150 \
  "$@"
