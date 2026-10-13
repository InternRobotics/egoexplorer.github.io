#!/bin/zsh
# Every panel must be the right length, at 60 fps, and newer than the fix that
# produced it. Frame counts alone do not prove the content is current — six
# panels once passed a count check while being two pipelines old.
B=/Volumes/NASStorage/Documents/code/.egoexplorer_build/streams
A=/Volumes/NASStorage/Documents/code/egoexplorer_website/assets
PY=/Users/zhouyunsong/miniconda3/bin/python3
# The reference is the pipeline source in this repo, not a session scratchpad:
# a scratchpad path is wiped on restart, CUT comes back empty, every -lt test
# errors AND evaluates false, and the staleness check silently passes
# everything -- which is the exact failure this audit exists to catch.
HERE=$(cd "$(dirname "$0")" && pwd)   # works under bash too, not just zsh
CUT=$(stat -f '%m' "$HERE/egodata.py")
[ -n "$CUT" ] || { echo "cannot stat egodata.py; refusing to report"; exit 2; }
printf "%-11s %7s %7s %7s %5s %5s  %s\n" session expect body hands bfps hfps status
bad=0
for s in A B C D E F G H I J; do
  exp=$($PY -c "import json;print(json.load(open('$B/session_$s/meta.json'))['frames'])" 2>/dev/null)
  nb=$(ffprobe -v error -show_entries stream=nb_frames -of csv=p=0 "$A/body/session_$s.mp4" 2>/dev/null | tr -d ',')
  nh=$(ffprobe -v error -show_entries stream=nb_frames -of csv=p=0 "$A/hands/session_$s.mp4" 2>/dev/null | tr -d ',')
  fb=$(ffprobe -v error -show_entries stream=r_frame_rate -of csv=p=0 "$A/body/session_$s.mp4" 2>/dev/null | cut -d/ -f1)
  fh=$(ffprobe -v error -show_entries stream=r_frame_rate -of csv=p=0 "$A/hands/session_$s.mp4" 2>/dev/null | cut -d/ -f1)
  tb=$(stat -f '%m' "$A/body/session_$s.mp4" 2>/dev/null || echo 0)
  th=$(stat -f '%m' "$A/hands/session_$s.mp4" 2>/dev/null || echo 0)
  st="ok"
  [ "$nb" != "$exp" ] || [ "$nh" != "$exp" ] && { st="WRONG LENGTH"; bad=1; }
  [ "$fb" != "60" ] || [ "$fh" != "60" ] && { st="NOT 60 fps"; bad=1; }
  [ "$tb" -lt "$CUT" ] || [ "$th" -lt "$CUT" ] && { st="STALE (predates the fix)"; bad=1; }
  printf "%-11s %7s %7s %7s %5s %5s  %s\n" "session_$s" "$exp" "${nb:-none}" "${nh:-none}" "${fb:-?}" "${fh:-?}" "$st"
done
echo
f="$A/pipeline_anim.mp4"
printf "film        %s frames  %s fps  %s  %s\n" \
  "$(ffprobe -v error -show_entries stream=nb_frames -of csv=p=0 "$f" | tr -d ',')" \
  "$(ffprobe -v error -show_entries stream=r_frame_rate -of csv=p=0 "$f" | cut -d/ -f1)" \
  "$(du -h "$f" | cut -f1)" \
  "$([ "$(stat -f '%m' "$f")" -ge "$CUT" ] && echo ok || echo 'STALE (predates the fix)')"
[ $bad -eq 0 ] && echo "ALL PANELS CURRENT" || echo "SOME PANELS NEED REDOING"
