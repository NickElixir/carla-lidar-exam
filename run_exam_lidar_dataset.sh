#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

exec ./run_exam_lidar_minimal.sh \
  --no-open3d \
  --save-dataset \
  --save-once \
  --dataset-dir exam_dataset \
  "$@"
