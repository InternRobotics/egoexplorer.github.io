#!/bin/zsh
# Re-bake every session and the film in float32, then re-render.
#
# float16 world coordinates were the bug: session_A reaches -5.5 m, where the
# float16 step is 3.9 mm, so every vertex of every frame carried ~1 mm of
# noise. The hand frame also now uses the real per-frame joints instead of
# vertex centroids, so it no longer wobbles.
set -e
HERE=${0:a:h}; cd "$HERE"
PY=/Users/zhouyunsong/miniconda3/bin/python3
for s in session_B session_C session_D session_E session_F session_G \
         session_H session_I session_J; do
  echo "=== bake $s"
  "$PY" prep_streams.py "$s"
done
echo "=== bake the film"
"$PY" -c "import sys; sys.path.insert(0,'.')
import prep_session as P; P.main(); P.bake_palm(); P.bake_facing(smooth_s=2.6)"
echo "=== all baked, rendering panels"
./render_all.sh session_E session_J session_D session_H session_C session_F \
                session_G session_A session_B session_I
echo "=== rendering the film"
./film_only.sh
echo "EVERYTHING DONE"
