#!/usr/bin/env python3
"""Ten-task egocentric montage: a seamless 5 x 2 wall, nothing else.

Only panel 01 of each submitted dashboard is used — the egocentric camera — so
no body, hand or tactile panel leaks in. That panel sits at exactly the same
place in all ten (x=62, y=80, 654x330 in a 1280x720 frame, verified per
session). No captions and no stat cells: the page already carries that text.
"""
import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUPP = ROOT / "assets" / "sessions"   # the per-session dashboards; panel 01 is the ego camera
OUT = ROOT / "montage"
OUT.mkdir(parents=True, exist_ok=True)

COLS, ROWS = 5, 2
TW, TH = 384, 216                   # 16:9 cells -> 1920 x 432, seamless
DUR, FPS = 22, 30                   # the dashboards are 30 fps; do not resample down
CROP = (96, 80, 586, 330)           # 16:9 centre of the ego panel

# ordered so the two rows read lab-first, then household
SESSIONS = [("session_A", 1), ("session_B", 7), ("session_C", 3), ("session_D", 5),
            ("session_E", 0), ("session_F", 9), ("session_G", 4), ("session_H", 2),
            ("session_I", 14), ("session_J", 6)]

def main():
    inputs, f = [], []
    for i, (sid, off) in enumerate(SESSIONS):
        src = SUPP / f"{sid}.mp4"
        if not src.exists():
            sys.exit(f"missing {src}")
        inputs += ["-stream_loop", "-1", "-ss", str(off), "-i", str(src)]
        f.append(f"[{i}:v]crop={CROP[2]}:{CROP[3]}:{CROP[0]}:{CROP[1]},"
                 f"scale={TW}:{TH},fps={FPS},setpts=PTS-STARTPTS[t{i}]")
    layout = "|".join(f"{(i % COLS) * TW}_{(i // COLS) * TH}" for i in range(len(SESSIONS)))
    f.append("".join(f"[t{i}]" for i in range(len(SESSIONS)))
             + f"xstack=inputs={len(SESSIONS)}:layout={layout}:fill=black[vo]")
    out = OUT / "montage_tasks.mp4"
    r = subprocess.run(["ffmpeg", "-v", "error", "-y"] + inputs +
                       ["-filter_complex", ";".join(f), "-map", "[vo]", "-t", str(DUR),
                        "-c:v", "libx264", "-preset", "slow", "-crf", "24",
                        "-pix_fmt", "yuv420p", "-r", str(FPS), "-an",
                        "-movflags", "+faststart", str(out)], capture_output=True, text=True)
    if r.returncode:
        print(r.stderr[-2500:]); sys.exit(1)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "6", "-i", str(out),
                    "-frames:v", "1", str(OUT / "montage_tasks.png")], check=True)
    print(f"-> {out} ({out.stat().st_size/1e6:.1f} MB, {COLS}x{ROWS}, {TW*COLS}x{TH*ROWS})")

if __name__ == "__main__":
    main()
