#!/bin/zsh
# The pipeline film's bake predates clean_hand, and its hand act is the most
# zoomed-in view of a hand on the page — so it needs the same treatment.
# Waits for the panel render to free the GPU first.
set -e
HERE=${0:a:h}; cd "$HERE"
PY=/Users/zhouyunsong/miniconda3/bin/python3
BL=/Applications/Blender.app/Contents/MacOS/Blender
WEB=/Volumes/NASStorage/Documents/code/egoexplorer_website
until grep -q "ALL STREAMS DONE" /tmp/streams9.log; do sleep 30; done
echo "=== panels done, rebaking the film"
"$PY" -c "import sys; sys.path.insert(0,'.')
import prep_session as P; P.main(); P.bake_palm(); P.bake_facing(smooth_s=2.6)"
echo "=== rendering the film"
rm -f frames/*.png
"$BL" -b -P room_film.py -- 0 1620 2>&1 | grep -Ei "^Error|Traceback|camera z" || true
n=$(ls frames | wc -l | tr -d ' ')
[ "$n" -eq 1620 ] || { echo "ABORT: only $n frames"; exit 1; }
ffmpeg -v error -y -framerate 60 -i frames/f_%04d.png -c:v libx264 -preset slow \
  -crf 19 -pix_fmt yuv420p -movflags +faststart base.mp4
"$PY" film_type.py
cp ../web/assets/pipeline_anim.mp4 ../web/assets/pipeline-poster.jpg "$WEB/assets/"
rm -f frames/*.png
echo "FILM DONE $(du -h "$WEB/assets/pipeline_anim.mp4" | cut -f1)"
