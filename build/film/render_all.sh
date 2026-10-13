#!/bin/zsh
# One worker, every session from frame 0, and frames are only deleted once the
# encode is verified.
#
# Learned the hard way: a previous driver resumed from whatever frames were on
# disk, and a worker script that outlived a pkill of its parent encoded a
# partial clip and then deleted the frames. No resuming, and nothing is
# removed until ffprobe agrees the clip is the right length.
HERE=${0:a:h}; cd "$HERE"
B=/Volumes/NASStorage/Documents/code/.egoexplorer_build/streams
DST=/Volumes/NASStorage/Documents/code/egoexplorer_website/assets
BL=/Applications/Blender.app/Contents/MacOS/Blender
PY=/Users/zhouyunsong/miniconda3/bin/python3
mkdir -p "$DST/body" "$DST/hands"
for sid in "$@"; do
  exp=$("$PY" -c "import json;print(json.load(open('$B/$sid/meta.json'))['frames'])")
  echo "=== $sid ($exp frames)"
  rm -rf "$B/$sid/body" "$B/$sid/hand"
  "$BL" -b -P "$HERE/streams_render.py" -- "$sid" 2>&1 \
    | grep -Ei "frames, body|error|Traceback" || true
  got=$(ls "$B/$sid/body" | wc -l | tr -d ' ')
  if [ "$got" -ne "$exp" ]; then
    echo "ABORT $sid: rendered $got of $exp frames, leaving them in place"
    continue
  fi
  ffmpeg -v error -y -framerate 60 -i "$B/$sid/body/f_%05d.png" \
    -c:v libx264 -preset slow -crf 26 -pix_fmt yuv420p -r 60 -an \
    -movflags +faststart "$DST/body/$sid.mp4"
  ffmpeg -v error -y -framerate 60 -i "$B/$sid/hand/f_%05d.png" \
    -c:v libx264 -preset slow -crf 27 -pix_fmt yuv420p -r 60 -an \
    -movflags +faststart "$DST/hands/$sid.mp4"
  nb=$(ffprobe -v error -show_entries stream=nb_frames -of csv=p=0 "$DST/body/$sid.mp4" | tr -d ',')
  nh=$(ffprobe -v error -show_entries stream=nb_frames -of csv=p=0 "$DST/hands/$sid.mp4" | tr -d ',')
  if [ "$nb" -eq "$exp" ] && [ "$nh" -eq "$exp" ]; then
    rm -rf "$B/$sid/body" "$B/$sid/hand"
    printf "DONE %s  %s frames  body %s  hands %s\n" "$sid" "$exp" \
      "$(du -h "$DST/body/$sid.mp4" | cut -f1)" "$(du -h "$DST/hands/$sid.mp4" | cut -f1)"
  else
    echo "ABORT $sid: encoded $nb/$nh of $exp, keeping frames"
  fi
done
echo "ALL STREAMS DONE"
