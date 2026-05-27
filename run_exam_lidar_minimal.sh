#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

export SDL_VIDEO_X11_NET_WM_BYPASS_COMPOSITOR="${SDL_VIDEO_X11_NET_WM_BYPASS_COMPOSITOR:-0}"
export SDL_RENDER_DRIVER="${SDL_RENDER_DRIVER:-software}"
if [[ -n "${DISPLAY:-}" && -z "${SDL_VIDEODRIVER:-}" ]]; then
  export SDL_VIDEODRIVER=x11
fi

exec "/media/hyperdog/Новый том1/conda_envs/carla0916/bin/python" exam_lidar_minimal.py \
  --viewer tk \
  --width 800 \
  --height 450 \
  --viewer-fps 10 \
  --open3d-update-hz 5 \
  --open3d-max-points 30000 \
  --lidar-points-per-second 500000 \
  --lidar-rotation-frequency 20 \
  --fixed-delta-seconds 0.05 \
  --clear-existing-npcs \
  --static-people 20 \
  --people-radius 10 \
  --people-min-distance 2 \
  "$@"
