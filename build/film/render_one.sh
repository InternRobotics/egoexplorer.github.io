#!/bin/zsh
# Render and encode one session's two panels, then drop its PNGs.
set -e
HERE=${0:a:h}
B=/Volumes/NASStorage/Documents/code/.egoexplorer_build/streams
DST=/Volumes/NASStorage/Documents/code/egoexplorer_website/assets
BL=/Applications/Blender.app/Contents/MacOS/Blender
sid=$1
"$BL" -b -P "$HERE/streams_render.py" -- "$sid" 2>&1 | grep -Ei "frames, body|error|Traceback" || true
ffmpeg -v error -y -framerate 60 -i "$B/$sid/body/f_%05d.png" \
  -c:v libx264 -preset slow -crf 26 -pix_fmt yuv420p -r 60 -an \
  -movflags +faststart "$DST/body/$sid.mp4"
ffmpeg -v error -y -framerate 60 -i "$B/$sid/hand/f_%05d.png" \
  -c:v libx264 -preset slow -crf 27 -pix_fmt yuv420p -r 60 -an \
  -movflags +faststart "$DST/hands/$sid.mp4"
rm -rf "$B/$sid/body" "$B/$sid/hand"
printf "DONE %s  body %s  hands %s\n" "$sid" \
  "$(du -h "$DST/body/$sid.mp4" | cut -f1)" "$(du -h "$DST/hands/$sid.mp4" | cut -f1)"
