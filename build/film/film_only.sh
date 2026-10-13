#!/bin/zsh
set -e
HERE=${0:a:h}; cd "$HERE"
PY=/Users/zhouyunsong/miniconda3/bin/python3
BL=/Applications/Blender.app/Contents/MacOS/Blender
WEB=/Volumes/NASStorage/Documents/code/egoexplorer_website
rm -rf frames && mkdir -p frames
echo "=== rendering the film"
"$BL" -b -P room_film.py -- 0 1620 2>&1 | grep -Ei "^Error|Traceback|camera z" || true
n=$(ls frames | wc -l | tr -d ' ')
[ "$n" -eq 1620 ] || { echo "ABORT: only $n frames"; exit 1; }
ffmpeg -v error -y -framerate 60 -i frames/f_%04d.png -c:v libx264 -preset slow \
  -crf 19 -pix_fmt yuv420p -movflags +faststart base.mp4
"$PY" film_type.py
cp out/pipeline_anim.mp4 out/pipeline-poster.jpg "$WEB/assets/"
rm -rf frames && mkdir -p frames
echo "FILM DONE $(du -h "$WEB/assets/pipeline_anim.mp4" | cut -f1)"
