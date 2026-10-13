#!/bin/zsh
# Re-bake and re-render every session's panels: the finger clamp lives in the
# bake, the uniform body and the subdivided hands in the render.
set -e
HERE=${0:a:h}
cd "$HERE"
PY=/Users/zhouyunsong/miniconda3/bin/python3
for sid in session_A session_B session_C session_D session_E \
           session_F session_G session_H session_I session_J; do
  echo "=== bake $sid"
  "$PY" prep_streams.py "$sid"
done
echo "=== all baked"
./build_streams.sh
