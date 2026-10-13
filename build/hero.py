#!/usr/bin/env python3
"""Hero video: the reconstructed body replayed inside the room's point cloud,
with the matching head-camera view inset.

Five chapters, cross-faded. The point cloud carries the scene and the metric
body; the inset says where the view came from. Dark throughout so the page's
hero gradient can sit on top of it.
"""
import os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# HERO_OUT / HERO_W / HERO_H let the same cut be rendered at other sizes (the
# promo film uses a 2560x1440 copy); the page itself takes the 1920x1080 default.
OUT = Path(os.environ.get("HERO_OUT", ROOT / "assets"))
OUT.mkdir(parents=True, exist_ok=True)

# Every chapter now comes from a 3840x2160 render. 过柱 and 萃取 used to be cut
# from the 1280x720 batch (pointcloud_smplx_wuji_existing), which is what made
# the hero look soft; the 4K batch has the same two tasks from other sessions.
W4 = Path("/Volumes/NASStorage/Downloads/wuji_four_sessions_4k_20260923_104615/pointcloud")
R14 = Path("/Volumes/NASStorage/Downloads/wuji_remaining_14videos_4k_20260925_161123/pointcloud")

W, H, FPS = int(os.environ.get("HERO_W", 1920)), int(os.environ.get("HERO_H", 1080)), 60
CRF = os.environ.get("HERO_CRF", "27")   # ~19 MB at 1080p: sharp, still light enough for the page
# The third-view point-cloud renders only exist at 10 fps, which judders badly
# under the hero's slow orbit. Motion-compensated interpolation is clean on
# this material — it is a smooth camera move over a static cloud — but it is
# slow, so the scale happens first. 60 rather than 30: the orbit is slow
# enough that every real frame is already being interpolated, so the extra
# ones cost nothing in fidelity and the pan stops stepping on a 120 Hz panel.
MI = (f"minterpolate=fps={FPS}:mi_mode=mci:me_mode=bidir:"
      "mc_mode=aobmc:vsbmc=1")
SEG, FADE = 5.4, 0.7                       # chapter length and cross-fade

# No ego inset. The head camera's view is already in the picture, projected on
# the far plane of its own frustum, so a second copy in the corner was just
# clutter over the hero copy.

# (point-cloud clip, start)
CHAPTERS = [
    (W4 / "session_20260918_103359_制作三明治/third_view_full_10fps.mp4", 34),
    (R14 / "session_20260914_112419_过柱/third_view_full_10fps.mp4",     24),
    (W4 / "session_20260917_180639_书架整理/third_view_full_10fps.mp4",    22),
    (R14 / "session_20260901_165217_萃取/third_view_full_10fps.mp4",     66),
    (W4 / "session_20260918_180008_折大纸箱/third_view_full_10fps.mp4",    40),
]

def main():
    inputs, f = [], []
    for i, (pc, pcs) in enumerate(CHAPTERS):
        if not pc.exists():
            sys.exit(f"missing {pc}")
        inputs += ["-ss", str(pcs), "-i", str(pc)]
        f.append(f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,"
                 f"crop={W}:{H},{MI},trim=duration={SEG},setpts=PTS-STARTPTS[ch{i}]")

    last, t = "ch0", SEG - FADE
    for i in range(1, len(CHAPTERS)):
        out = f"x{i}" if i < len(CHAPTERS) - 1 else "vo"
        f.append(f"[{last}][ch{i}]xfade=transition=fade:duration={FADE}:offset={t:.2f}[{out}]")
        last, t = out, t + SEG - FADE

    total = len(CHAPTERS) * SEG - (len(CHAPTERS) - 1) * FADE
    out = OUT / "hero.mp4"
    cmd = (["ffmpeg", "-v", "error", "-y"] + inputs +
           ["-filter_complex", ";".join(f), "-map", "[vo]", "-t", f"{total:.2f}",
            "-c:v", "libx264", "-preset", "slow", "-crf", CRF,
            "-pix_fmt", "yuv420p", "-r", str(FPS), "-an",
            "-movflags", "+faststart", str(out)])
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        print(r.stderr[-3000:]); sys.exit(1)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "2", "-i", str(out),
                    "-frames:v", "1", "-q:v", "4", str(OUT / "hero-poster.jpg")], check=True)
    print(f"-> {out}  ({out.stat().st_size/1e6:.1f} MB, {total:.1f}s)")

if __name__ == "__main__":
    main()
