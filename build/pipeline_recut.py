#!/usr/bin/env python3
"""Recut the pipeline film.

Left: a stage rail that stays put so you always know where you are, plus a
schematic drawn here for the current stage. Right: the Blender pass, captioned
with exactly what is on screen. The two halves name the same thing at the same
moment, which the earlier cut did not.

Nothing is screenshotted from the paper -- the schematics are inline SVG
authored in this file.
"""
import html, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE / "pipeline_base.mp4"
OUT = Path("/private/tmp/claude-501/-Volumes-NASStorage-Documents-code/"
           "9055ee78-31fb-4a18-963a-1b1f1bd46787/scratchpad/web/assets")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
FPS, SLOW = 25, 1.72

INK, DIM, FAINT, ACC, BLUE = "#EDEFF3", "#9AA2AE", "#39414E", "#E2762A", "#5B8BD0"


def svg_calibrate():
    return f'''<svg viewBox="0 0 520 250" fill="none">
  <circle cx="92" cy="118" r="44" stroke="{DIM}" stroke-width="2"/>
  <path d="M92 74v-16" stroke="{FAINT}" stroke-width="2"/>
  <rect x="72" y="40" width="40" height="19" rx="5" fill="{ACC}"/>
  <circle cx="92" cy="118" r="5" fill="{ACC}"/>
  <text x="92" y="196" fill="{DIM}" font-size="15" text-anchor="middle">device + anchor</text>
  <path d="M152 118h54" stroke="{FAINT}" stroke-width="2"/>
  <path d="M200 112l10 6-10 6z" fill="{FAINT}"/>
  <g stroke="{DIM}" stroke-width="2">
    <rect x="224" y="70" width="34" height="96" rx="5"/>
    <rect x="266" y="70" width="34" height="96" rx="5"/>
    <rect x="308" y="70" width="34" height="96" rx="5"/>
  </g>
  <text x="283" y="196" fill="{DIM}" font-size="15" text-anchor="middle">reference library</text>
  <path d="M356 118h40" stroke="{FAINT}" stroke-width="2"/>
  <path d="M390 112l10 6-10 6z" fill="{FAINT}"/>
  <rect x="408" y="92" width="100" height="52" rx="9" stroke="{ACC}" stroke-width="2"/>
  <text x="458" y="125" fill="{ACC}" font-size="17" text-anchor="middle"
        font-family="ui-monospace,monospace">fit &#934;</text>
</svg>'''


def svg_complete():
    dots = "".join(f'<circle cx="54" cy="{y}" r="8" fill="{ACC}"/>'
                   for y in (46, 92, 118, 166, 198))
    return f'''<svg viewBox="0 0 520 250" fill="none">
  {dots}
  <text x="54" y="232" fill="{DIM}" font-size="15" text-anchor="middle">5 anchors</text>
  <path d="M78 118h52" stroke="{FAINT}" stroke-width="2"/>
  <path d="M124 112l10 6-10 6z" fill="{FAINT}"/>
  <rect x="146" y="78" width="158" height="80" rx="10" stroke="{BLUE}" stroke-width="2"/>
  <text x="225" y="112" fill="{BLUE}" font-size="16" text-anchor="middle">temporal prior</text>
  <text x="225" y="136" fill="{DIM}" font-size="13.5" text-anchor="middle">5 anchors &#8594; 22 joints</text>
  <path d="M318 118h44" stroke="{FAINT}" stroke-width="2"/>
  <path d="M356 112l10 6-10 6z" fill="{FAINT}"/>
  <g stroke="{DIM}" stroke-width="2" stroke-linecap="round">
    <circle cx="438" cy="54" r="13"/>
    <path d="M438 68v52M438 84l-30 24M438 84l30 24M438 120l-22 48M438 120l22 48"/>
  </g>
  <text x="438" y="232" fill="{DIM}" font-size="15" text-anchor="middle">proposal</text>
</svg>'''


def svg_layer(n):
    if n == 1:
        return f'''<svg viewBox="0 0 520 250" fill="none">
  <g stroke="{DIM}" stroke-width="2" stroke-linecap="round">
    <circle cx="206" cy="48" r="14"/>
    <path d="M206 62v56M206 80l-42 30M206 80l42 30M206 118l-30 62M206 118l30 62"/>
  </g>
  <g stroke="{ACC}" stroke-width="2.4">
    <path d="M198 30h16M206 22v16"/><path d="M156 102h16M164 94v16"/>
    <path d="M240 102h16M248 94v16"/><path d="M168 172h16M176 164v16"/>
    <path d="M228 172h16M236 164v16"/>
  </g>
  <g stroke="{BLUE}" stroke-width="2" stroke-linecap="round">
    <path d="M300 92h44"/><path d="M338 86l8 6-8 6"/>
    <path d="M300 128h30"/><path d="M324 122l8 6-8 6"/>
    <path d="M300 164h52"/><path d="M346 158l8 6-8 6"/>
  </g>
  <text x="372" y="98" fill="{DIM}" font-size="14">tracker residual</text>
  <text x="372" y="134" fill="{DIM}" font-size="14">temporal change</text>
  <text x="372" y="170" fill="{DIM}" font-size="14">joint limits</text>
</svg>'''
    if n == 2:
        return f'''<svg viewBox="0 0 520 250" fill="none">
  <rect x="150" y="38" width="86" height="176" rx="42" stroke="{DIM}" stroke-width="2"/>
  <rect x="206" y="92" width="150" height="46" rx="23" stroke="{DIM}" stroke-width="2"/>
  <path d="M206 92a23 23 0 0 0 0 46" stroke="{ACC}" stroke-width="3"/>
  <circle cx="222" cy="115" r="30" stroke="{ACC}" stroke-width="2" stroke-dasharray="5 5"/>
  <text x="300" y="186" fill="{DIM}" font-size="15" text-anchor="middle">arm through torso</text>
  <text x="300" y="70" fill="{ACC}" font-size="15" text-anchor="middle">oriented clearance</text>
</svg>'''
    return f'''<svg viewBox="0 0 520 250" fill="none">
  <path d="M96 176h330" stroke="{DIM}" stroke-width="2"/>
  <g stroke="{DIM}" stroke-width="2" stroke-linecap="round">
    <path d="M214 60v62M214 122l-26 54M214 122l26 54"/>
    <circle cx="214" cy="44" r="13"/>
  </g>
  <path d="M188 176c-6 12-2 20 10 20h26" stroke="{ACC}" stroke-width="3"/>
  <circle cx="202" cy="188" r="25" stroke="{ACC}" stroke-width="2" stroke-dasharray="5 5"/>
  <text x="300" y="228" fill="{DIM}" font-size="15" text-anchor="middle">every posed vertex, not just the ankle</text>
</svg>'''


# (t_in, t_out, stage index, sub label, headline, copy, svg, right-hand chip)
ACTS = [
    (0.4, 5.6, 0, None, "Fix the geometry first",
     "A prescribed sequence is matched by phase to a reference library, solving "
     "body shape, metric scale and every sensor-to-anchor transform — once "
     "per mounting, before any motion is inferred.",
     svg_calibrate(), "right — <b>the five measured anchors, alone</b>"),
    (5.9, 11.8, 1, None, "Fill what nothing measures",
     "A temporal prior carries those five calibrated anchors into a first "
     "whole-body trajectory.",
     svg_complete(), "right — <b>the completed body appears around them</b>"),
    (12.1, 15.0, 2, "L1", "Skeletal motion",
     "Fit this recording's trackers, stay near the proposal, keep joints inside "
     "soft limits.", svg_layer(1),
     "right — <b>the body settles onto its measurements</b>"),
    (15.2, 17.6, 2, "L2", "Surface clearance",
     "Oriented clearance on the participant's own posed surface, so an arm "
     "cannot pass through the chest.", svg_layer(2),
     "right — <b>no part of the body passes through another</b>"),
    (17.8, 20.4, 2, "L3", "Ground consistency",
     "Every posed vertex is penalised below the floor, not just the ankle "
     "anchors.", svg_layer(3),
     "right — <b>the floor resolves and the body stands on it</b>"),
]
STAGES = [("01", "CALIBRATE"), ("02", "COMPLETE"), ("03", "CONSTRAIN")]

CSS = f"""
@import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,700&family=Inter:wght@400;500&family=JetBrains+Mono:wght@500&display=swap');
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:1920px;height:1080px;background:transparent}}
body{{font-family:'Inter',Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}}
.rail{{position:absolute;left:92px;top:88px;display:flex;gap:30px}}
.rail div{{font-family:'JetBrains Mono',monospace;font-size:13px;letter-spacing:.2em;color:#49515E;min-width:124px}}
.rail div.on{{color:{ACC}}}
.rail div span{{display:block;height:2px;margin-top:10px;background:#2B323C}}
.rail div.on span{{background:{ACC}}}
.col{{position:absolute;left:92px;top:168px;width:640px}}
.sub-lab{{font-family:'JetBrains Mono',monospace;font-size:13px;letter-spacing:.2em;color:{ACC};margin-bottom:12px}}
h1{{font-family:'Source Serif 4',Georgia,serif;font-weight:700;font-size:46px;line-height:1.08;
   letter-spacing:-.02em;color:{INK}}}
p.sub{{margin-top:16px;font-size:18.5px;line-height:1.56;color:{DIM};max-width:600px}}
.dia{{margin-top:32px;width:600px;border-top:1px solid #272E38;padding-top:24px}}
.dia svg{{width:520px;height:250px;display:block}}
.chip{{position:absolute;left:1120px;bottom:80px;width:660px;text-align:right;
      font-size:17px;color:{DIM}}}
.chip b{{color:{INK};font-weight:500}}
"""


def plate(i, stage, sub_lab, title, sub, svg, chip):
    rail = "".join(
        f'<div class="{"on" if k == stage else ""}">{n} {t}<span></span></div>'
        for k, (n, t) in enumerate(STAGES))
    lab = f'<div class="sub-lab">{html.escape(sub_lab)}</div>' if sub_lab else ""
    p = HERE / f"rc_{i}.html"
    png = HERE / f"rc_{i}.png"
    p.write_text(f"""<!doctype html><meta charset="utf-8"><style>{CSS}</style>
<div class="rail">{rail}</div>
<div class="col">{lab}<h1>{html.escape(title)}</h1>
<p class="sub">{html.escape(sub)}</p><div class="dia">{svg}</div></div>
<div class="chip">{chip}</div>""")
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    "--force-device-scale-factor=1", "--virtual-time-budget=4000",
                    "--allow-file-access-from-files",
                    "--default-background-color=00000000",
                    f"--screenshot={png}", "--window-size=1920,1080", p.as_uri()],
                   check=True, capture_output=True)
    return png


def main():
    if not BASE.exists():
        sys.exit(f"missing {BASE}")
    total = ACTS[-1][1] + 0.6
    chain = [f"color=c=0x1B1E26:s=1920x1080:r={FPS}[bed]",
             f"[0:v]setpts={SLOW}*PTS,fps={FPS},scale=1080:608[v3d]",
             "[bed][v3d]overlay=782:208[b0]"]
    last, inputs = "b0", ["-i", str(BASE)]
    for i, (t0, t1, stage, lab, title, sub, svg, chip) in enumerate(ACTS):
        png = plate(i, stage, lab, title, sub, svg, chip)
        inputs += ["-loop", "1", "-i", str(png)]
        f = 0.38
        chain.append(f"[{i+1}:v]format=rgba,fade=t=in:st={t0}:d={f}:alpha=1,"
                     f"fade=t=out:st={t1-f}:d={f}:alpha=1,setpts=PTS-STARTPTS[L{i}]")
        out = "vo" if i == len(ACTS) - 1 else f"b{i+1}"
        chain.append(f"[{last}][L{i}]overlay=0:0:enable='between(t,{t0-f},{t1})'[{out}]")
        last = out

    dst = OUT / "pipeline_anim.mp4"
    r = subprocess.run(["ffmpeg", "-v", "error", "-y"] + inputs +
                       ["-filter_complex", ";".join(chain), "-map", "[vo]",
                        "-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "slow",
                        "-crf", "21", "-pix_fmt", "yuv420p", "-r", str(FPS), "-an",
                        "-movflags", "+faststart", str(dst)], capture_output=True, text=True)
    if r.returncode:
        print(r.stderr[-2500:]); sys.exit(1)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "2.5", "-i", str(dst),
                    "-frames:v", "1", "-q:v", "4", str(OUT / "pipeline-poster.jpg")], check=True)
    print(f"-> {dst} ({dst.stat().st_size/1e6:.1f} MB, {total:.1f}s)")


if __name__ == "__main__":
    main()
