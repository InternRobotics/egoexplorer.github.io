#!/bin/zsh
# Two workers: measured 1.33x the throughput of one on this machine, and the
# memory headroom does not support a third.
HERE=${0:a:h}; cd "$HERE"
mkdir -p /Volumes/NASStorage/Documents/code/egoexplorer_website/assets/{body,hands}
( for s in session_I session_A session_C session_E session_J; do ./render_one.sh $s; done ) &
( for s in session_B session_G session_F session_D session_H; do ./render_one.sh $s; done ) &
wait
echo "ALL STREAMS DONE"
