#!/bin/zsh
# Render and encode every session's body and hand panel at 60 fps, one session
# at a time so the PNG sequences never pile up on the small system disk.
set -e
HERE=${0:a:h}
B=/Volumes/NASStorage/Documents/code/.egoexplorer_build/streams
DST=/Volumes/NASStorage/Documents/code/egoexplorer_website/assets
BL=/Applications/Blender.app/Contents/MacOS/Blender
mkdir -p "$DST/body" "$DST/hands"
for sid in session_A session_B session_C session_D session_E \
           session_F session_G session_H session_I session_J; do
  [ -d "$B/$sid" ] || { echo "skip $sid (no bake)"; continue; }
  echo "=== $sid"
  "$BL" -b -P "$HERE/streams_render.py" -- "$sid" 2>&1 | grep -Ei "frames, body|error|Traceback" || true
  ffmpeg -v error -y -framerate 60 -i "$B/$sid/body/f_%05d.png" \
    -c:v libx264 -preset slow -crf 26 -pix_fmt yuv420p -r 60 -an \
    -movflags +faststart "$DST/body/$sid.mp4"
  ffmpeg -v error -y -framerate 60 -i "$B/$sid/hand/f_%05d.png" \
    -c:v libx264 -preset slow -crf 27 -pix_fmt yuv420p -r 60 -an \
    -movflags +faststart "$DST/hands/$sid.mp4"
  printf "    body %s  hands %s\n" "$(du -h "$DST/body/$sid.mp4" | cut -f1)" \
         "$(du -h "$DST/hands/$sid.mp4" | cut -f1)"
  rm -rf "$B/$sid/body" "$B/$sid/hand"
done
echo "ALL STREAMS DONE"
