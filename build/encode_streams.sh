#!/bin/zsh
# Encode the per-session body and hand frame folders into web clips.
set -e
HERE=${0:a:h}
DST=/private/tmp/claude-501/-Volumes-NASStorage-Documents-code/9055ee78-31fb-4a18-963a-1b1f1bd46787/scratchpad/web/site/assets
for pair in "body_streams:body" "hand_streams:hands"; do
  src="$HERE/${pair%%:*}"; out="$DST/${pair##*:}"
  mkdir -p "$out"
  for d in "$src"/session_*; do
    sid=$(basename "$d"); n=$(ls "$d" | wc -l | tr -d ' ')
    [ "$n" -lt 2 ] && { echo "skip ${pair##*:}/$sid ($n frames)"; continue; }
    ffmpeg -v error -y -framerate 12.5 -i "$d/f_%05d.png" \
      -c:v libx264 -preset slow -crf 26 -pix_fmt yuv420p -r 25 -an \
      -movflags +faststart "$out/$sid.mp4"
    printf "%-6s %-10s %4s frames  %s\n" "${pair##*:}" "$sid" "$n" "$(du -h "$out/$sid.mp4" | cut -f1)"
  done
done
