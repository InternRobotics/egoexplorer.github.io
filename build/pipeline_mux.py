#!/usr/bin/env python3
"""Mux the pipeline frames and lay the stage typography over them."""
import html, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FRAMES = HERE / "pipeline_frames"
OUT = Path("/private/tmp/claude-501/-Volumes-NASStorage-Documents-code/"
           "9055ee78-31fb-4a18-963a-1b1f1bd46787/scratchpad/web/assets")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
FPS = 25

# (in, out) seconds, eyebrow, title, sub
ACTS = [
    (0.3, 3.5, "01 / CALIBRATE",
     "Five anchors, fixed first",
     "Body shape, metric scale and every sensor-to-anchor transform are solved once, before any motion is inferred."),
    (3.6, 7.3, "02 / COMPLETE",
     "The joints nothing measures",
     "A temporal prior turns the five calibrated anchors into a first whole-body trajectory."),
    (7.4, 11.5, "03 / CONSTRAIN",
     "Measurements, surface, ground",
     "Three layers refine that trajectory against the trackers, the body's own surface and the floor — one shared objective, not three passes."),
]

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,700&family=Inter:wght@400;500&family=JetBrains+Mono:wght@500&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1920px;height:1080px;background:transparent}
body{font-family:'Inter',Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}
.wrap{position:absolute;left:104px;top:92px;max-width:980px}
.eb{font-family:'JetBrains Mono',monospace;font-size:17px;letter-spacing:.26em;color:#e2762a;margin-bottom:20px}
h1{font-family:'Source Serif 4',Georgia,serif;font-weight:700;font-size:56px;line-height:1.08;
   letter-spacing:-.02em;color:#f2f4f7;text-shadow:0 2px 28px rgba(0,0,0,.6)}
p{margin-top:20px;font-size:23px;line-height:1.56;color:#aeb6c2;max-width:830px;
  text-shadow:0 1px 18px rgba(0,0,0,.6)}
.rule{width:62px;height:2px;background:#e2762a;margin:26px 0 0}
"""

def plate(i, eb, title, sub):
    p = HERE / f"lab_{i}.html"
    png = HERE / f"lab_{i}.png"
    p.write_text(f"""<!doctype html><meta charset="utf-8"><style>{CSS}</style>
<div class="wrap"><div class="eb">{html.escape(eb)}</div>
<h1>{html.escape(title)}</h1><p>{html.escape(sub)}</p><div class="rule"></div></div>""")
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    "--force-device-scale-factor=1", "--virtual-time-budget=3500",
                    "--default-background-color=00000000",
                    f"--screenshot={png}", "--window-size=1920,1080", p.as_uri()],
                   check=True, capture_output=True)
    return png

def main():
    n = len(list(FRAMES.glob("*.png")))
    if not n:
        sys.exit("no frames")
    base = HERE / "pipeline_base.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS),
                    "-pattern_type", "glob", "-i", str(FRAMES / "*.png"),
                    "-c:v", "libx264", "-preset", "slow", "-crf", "20",
                    "-pix_fmt", "yuv420p", str(base)], check=True)

    inputs = ["-i", str(base)]
    chain, last = [], "0:v"
    for i, (t0, t1, eb, title, sub) in enumerate(ACTS):
        png = plate(i, eb, title, sub)
        inputs += ["-loop", "1", "-i", str(png)]
        f = 0.45
        chain.append(
            f"[{i+1}:v]format=rgba,"
            f"fade=t=in:st={t0}:d={f}:alpha=1,fade=t=out:st={t1-f}:d={f}:alpha=1,"
            f"setpts=PTS-STARTPTS[L{i}]")
        out = "vo" if i == len(ACTS) - 1 else f"s{i}"
        chain.append(f"[{last}][L{i}]overlay=0:0:enable='between(t,{t0-f},{t1})'[{out}]")
        last = out

    out = OUT / "pipeline_anim.mp4"
    r = subprocess.run(["ffmpeg", "-v", "error", "-y"] + inputs +
                       ["-filter_complex", ";".join(chain), "-map", "[vo]",
                        "-t", f"{n/FPS:.2f}", "-c:v", "libx264", "-preset", "slow",
                        "-crf", "21", "-pix_fmt", "yuv420p", "-r", str(FPS), "-an",
                        "-movflags", "+faststart", str(out)], capture_output=True, text=True)
    if r.returncode:
        print(r.stderr[-2500:]); sys.exit(1)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "1.6", "-i", str(out),
                    "-frames:v", "1", "-q:v", "4", str(OUT / "pipeline-poster.jpg")], check=True)
    print(f"-> {out} ({out.stat().st_size/1e6:.1f} MB, {n/FPS:.1f}s)")

if __name__ == "__main__":
    main()
