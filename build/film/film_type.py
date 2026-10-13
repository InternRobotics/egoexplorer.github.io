#!/usr/bin/env python3
"""Lay the typography over the pipeline film.

The picture underneath is now a full-bleed render of a real session inside a
mocked room (room_film.py), so the type sits on a scrim over the left 42%
rather than beside a boxed panel — which is also what fixes the old version
clipping the figure at the edge of its inset.

Six acts: the three C-cubed stages, its three constraint layers, and a last
one for the hands, where the glove's own finger articulation and seventeen
tactile regions come up on the same body. Each act's schematic is composed in
HTML/CSS and sampled across Chrome's virtual clock so it draws itself in.
"""
import html, json, math, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE / "base.mp4"
SIL = (HERE / "body_silhouette.png").as_uri()
MASK = (HERE / "body_sil_mask.png").as_uri()   # shadow-free, for CSS masks
# Next to the script, not in a session scratchpad: that path is wiped when
# the session restarts, and the film then renders for 25 minutes and fails at
# the last step with "No such file or directory".
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(parents=True, exist_ok=True)
FRAMES = HERE / "type_frames"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

FPS = 60
DRAW_MS, DRAW_N = 1500, 13          # entrance length and how many frames sample it
PALM = json.loads((HERE / "palm_map.json").read_text())

INK, DIM, FAINT = "#EDEFF3", "#9AA2AE", "#5A6372"
ACC, COOL, MINT = "#E2762A", "#5B8BD0", "#49B07A"


# ── diagram bodies ─────────────────────────────────────────────────────────
# the five device anchors, measured off the silhouette's own alpha so the pins
# sit on the head, the hands and the feet of this exact figure
ANCH = [("head", 46.4, 11.1), ("wristR", 30.1, 46.0), ("wristL", 65.1, 45.6),
        ("ankleR", 28.6, 92.4), ("ankleL", 68.4, 90.4)]


def figure(cls="", extra="", opacity=1.0, pins=False, delay=150):
    """The project's own SMPL-X silhouette, in a box of its exact aspect so
    percentage-positioned pins land on the body instead of the padding."""
    dots = "".join(
        f'<i class="pin" style="left:{x}%;top:{y}%;--d:{380+i*95}ms"></i>'
        for i, (_, x, y) in enumerate(ANCH)) if pins else ""
    return (f'<div class="figure {cls}" style="--fd:{delay}ms">'
            f'<img src="{SIL}" alt="" style="opacity:{opacity}">{extra}{dots}</div>')


def arrow(d=250):
    return (f'<div class="arrowline" style="--d:{d}ms">'
            f'<span class="dash"></span><span class="head"></span></div>')


def dia_calibrate():
    # a library of prescribed poses: one silhouette, shifted and skewed a little
    # per entry so the strip reads as five different references, not one stamp
    tw = ((-7, .96, .07), (-3, 1.0, -.05), (2, .94, .04), (0, 1.03, 0), (5, .97, -.06))
    poses = "".join(
        f'<i class="ghost{" live" if i == 3 else ""}" style="left:{i*55}px;'
        f'--d:{i*85}ms;opacity:{0.9 if i == 3 else 0.17 + i*0.05};'
        f'transform:rotate({r}deg) scaleY({sy}) skewX({sk}rad)"></i>'
        for i, (r, sy, sk) in enumerate(tw))
    rows = [("&#946;", "body shape", "10 dim"), ("s", "metric scale", "scalar"),
            ("A<sub>i</sub>", "device rotation", "5 &times; SO(3)"),
            ("a<sub>i</sub>", "device offset", "5 &times; R&#179;")]
    rr = "".join(
        f'<div class="row" style="--d:{520+i*90}ms"><span class="sym">{s}</span>'
        f'<span class="nm">{n}</span><span class="dm">{d}</span></div>'
        for i, (s, n, d) in enumerate(rows))
    return f'''
<div class="dia-wrap">
  <div class="stack">
    <div class="halo"></div>
    {poses}
    <div class="tag">reference library</div>
  </div>
  {arrow(300)}
  <div class="panel solve">
    <div class="phead"><span class="pdot"></span>SOLVE <em>&#934;</em></div>
    {rr}
    <div class="pfoot">once per mounting</div>
  </div>
</div>'''


def dia_complete():
    bars = "".join(f'<i style="--d:{620+i*70}ms;--h:{h}%"></i>'
                   for i, h in enumerate((38, 62, 86, 62, 44, 70, 52)))
    return f'''
<div class="dia-wrap">
  <div class="col-fig">
    <div class="halo soft"></div>
    {figure("lit", opacity=0.2, pins=True, delay=120)}
    <div class="tag">5 measured</div>
  </div>
  {arrow(330)}
  <div class="panel prior">
    <div class="phead"><span class="pdot cool"></span>TEMPORAL PRIOR</div>
    <div class="bars">{bars}</div>
    <div class="pfoot">5 anchors &#8594; 22 joints</div>
  </div>
  {arrow(700)}
  <div class="col-fig">
    {figure(opacity=0.94, delay=800)}
    <div class="tag">proposal</div>
  </div>
</div>'''


def panel(head, dot, rows, foot, width=272, delay=420):
    rr = "".join(
        f'<div class="lrow" style="--d:{delay+i*95}ms"><i class="sw {c}"></i>'
        f'<span>{a}</span><b>{b}</b></div>' for i, (c, a, b) in enumerate(rows))
    return (f'<div class="panel lay" style="width:{width}px">'
            f'<div class="phead"><span class="pdot {dot}"></span>{head}</div>'
            f'{rr}<div class="pfoot">{foot}</div></div>')


def dia_layer(n):
    if n == 1:
        return f'''
<div class="dia-wrap single">
  <div class="col-fig">
    <div class="halo soft"></div>
    {figure("tall", pins=True)}
  </div>
  {panel("RESIDUALS", "", [
      ("acc", "tracker residual", "pos + rot"),
      ("cool", "temporal change", "frame to frame"),
      ("dim", "joint limits", "soft hinge")],
      "five anchors, one skeleton", width=352)}
</div>'''
    if n == 2:
        ex = '<span class="clash"></span><span class="clashring"></span>'
        return f'''
<div class="dia-wrap single">
  <div class="col-fig">
    <div class="halo soft"></div>
    {figure("tall", extra=ex)}
  </div>
  {panel("CLEARANCE", "", [
      ("acc", "oriented clearance", "on the posed surface"),
      ("dim", "worst pairs first", "per body part")],
      "a matched wrist says nothing about the arm on the way", width=370)}
</div>'''
    ex = '<span class="plane"></span><span class="dip"></span>'
    return f'''
<div class="dia-wrap single">
  <div class="col-fig">
    <div class="halo soft"></div>
    {figure("tall floor", extra=ex)}
  </div>
  {panel("FLOOR", "", [
      ("acc", "every posed vertex", "not just the ankle"),
      ("dim", "penetration depth", "below the plane")],
      "heel, sole and knee all have to clear it", width=356)}
</div>'''


def dia_touch():
    """The hand the film is looking at, with its seventeen measured regions."""
    order = ["thumb_distal", "index_distal", "middle_distal", "ring_distal",
             "pinky_distal", "thumb_proximal", "index_middle", "middle_middle",
             "ring_middle", "pinky_middle", "index_proximal", "middle_proximal",
             "ring_proximal", "pinky_proximal", "palm_radial", "palm_central",
             "palm_ulnar"]
    dots = "".join(
        f'<i class="tz" style="left:{PALM["regions"][k][0]*100:.2f}%;'
        f'top:{PALM["regions"][k][1]*100:.2f}%;--d:{300+i*52}ms"></i>'
        for i, k in enumerate(order) if k in PALM["regions"])
    return f'''
<div class="dia-wrap single">
  <div class="col-fig">
    <div class="halo warm"></div>
    <div class="palm">
      <svg viewBox="0 0 1 1" preserveAspectRatio="xMidYMid meet">
        <path d="{PALM["path"]}"/>
      </svg>
      {dots}
    </div>
    <div class="tag">17 regions &times; 2 hands</div>
  </div>
  {panel("MEASURED, NOT INFERRED", "", [
      ("acc", "finger articulation", "21 points, 120 Hz"),
      ("cool", "contact pressure", "17 regions, 120 Hz"),
      ("dim", "one clock", "with body and view")],
      "the glove reports it; nothing here is estimated from pixels", width=370)}
</div>'''


ACTS = [
    (0.35, 5.35, 0, None, "Fix the geometry first",
     "A prescribed sequence is matched by phase to a reference library, solving "
     "body shape, metric scale and every sensor-to-anchor transform \u2014 once "
     "per mounting, before any motion is inferred.",
     dia_calibrate(), "the five measured anchors, alone in the room"),
    (5.55, 11.45, 1, None, "Fill what nothing measures",
     "A temporal prior carries those five calibrated anchors into a first "
     "whole-body trajectory.",
     dia_complete(), "the completed body appears around them"),
    (11.65, 14.95, 2, "LAYER 1", "Skeletal motion",
     "Fit this recording's trackers, stay near the proposal, keep joints inside "
     "soft limits.", dia_layer(1),
     "the body settles onto its measurements"),
    (15.1, 17.65, 2, "LAYER 2", "Surface clearance",
     "Oriented clearance on the participant's own posed surface, so an arm "
     "cannot pass through the chest.", dia_layer(2),
     "no part of the body passes through another"),
    (17.8, 20.55, 2, "LAYER 3", "Ground consistency",
     "Every posed vertex is penalised below the floor, not just the ankle "
     "anchors.", dia_layer(3),
     "the floor resolves and the body stands on it"),
    (20.8, 26.9, 3, "SAME RECORDING", "And the hands were never inferred",
     "Finger articulation and seventeen regions of contact pressure per hand "
     "arrive from the glove on the same clock as the body and the view.",
     dia_touch(), "measured pressure, on the solved hand"),
]
STAGES = [("01", "CALIBRATE"), ("02", "COMPLETE"), ("03", "CONSTRAIN")]

FONTS = (HERE / "fonts_local.css").read_text()

CSS = FONTS + f"""
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:1920px;height:1080px;background:transparent}}
.scrim{{position:absolute;inset:0;pointer-events:none;
  /* The scrim has to cover the type and then get out of the way. It used to
     run to 80% of the width and was still 62% opaque at the midpoint, which
     put a wash over 65% of the right half -- where the render is -- and read
     as part of the picture being covered. The type ends at about 42%, so the
     stops now hold full strength under it and are gone by 60%. */
  background:linear-gradient(90deg,rgba(14,16,20,.94) 0%,rgba(14,16,20,.90) 34%,
    rgba(14,16,20,.72) 44%,rgba(14,16,20,.18) 54%,rgba(14,16,20,0) 60%),
    linear-gradient(0deg,rgba(14,16,20,.55) 0%,rgba(14,16,20,0) 26%)}}
body{{font-family:'Inter',Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}}

@keyframes rise{{from{{opacity:0;transform:translateY(14px)}}to{{opacity:1;transform:none}}}}
@keyframes grow{{from{{transform:scaleX(0)}}to{{transform:scaleX(1)}}}}
@keyframes pop{{0%{{opacity:0;transform:scale(.4)}}70%{{transform:scale(1.18)}}
                100%{{opacity:1;transform:scale(1)}}}}
@keyframes bar{{from{{height:0}}to{{height:var(--h)}}}}
@keyframes ring{{from{{opacity:0;transform:scale(.6)}}to{{opacity:1;transform:scale(1)}}}}

.rail{{position:absolute;left:104px;top:92px;display:flex;gap:34px}}
.rail div{{font-family:'JetBrains Mono',monospace;font-size:19px;letter-spacing:.2em;
          color:#5A6372;min-width:178px}}
.rail div.on{{color:{ACC}}}
.rail div span{{display:block;height:2px;margin-top:12px;background:#333B46}}
.rail div.on span{{background:{ACC};transform-origin:left;animation:grow .5s ease both}}

.col{{position:absolute;left:104px;top:200px;width:860px}}
.sub-lab{{font-family:'JetBrains Mono',monospace;font-size:19px;letter-spacing:.2em;
         color:{ACC};margin-bottom:16px}}
h1{{font-family:'Source Serif 4',Georgia,serif;font-weight:700;font-size:64px;
   line-height:1.06;letter-spacing:-.022em;color:{INK};animation:rise .5s ease both}}
p.sub{{margin-top:22px;font-size:27px;line-height:1.5;color:#B4BAC4;max-width:730px;
      animation:rise .5s .08s ease both}}

/* ── diagram shell ─────────────────────────────────────────────── */
.dia{{margin-top:44px;width:830px;padding-top:34px;position:relative}}
.dia::before{{content:'';position:absolute;top:0;left:0;width:100%;height:1px;
  background:linear-gradient(90deg,#39414E,rgba(57,65,78,0));
  transform-origin:left;animation:grow .6s ease both}}
.dia-wrap{{display:flex;align-items:center;gap:26px;height:360px}}
.dia-wrap.single{{gap:42px}}

.panel{{position:relative;border-radius:15px;padding:17px 19px 15px;
  background:linear-gradient(160deg,rgba(255,255,255,.058),rgba(255,255,255,.016));
  box-shadow:inset 0 1px 0 rgba(255,255,255,.075),0 20px 44px rgba(0,0,0,.48);
  animation:rise .5s .2s ease both}}
.panel::after{{content:'';position:absolute;inset:0;border-radius:15px;
  border:1px solid rgba(255,255,255,.045);pointer-events:none}}
.phead{{display:flex;align-items:center;gap:9px;font-family:'JetBrains Mono',monospace;
  font-size:15.5px;letter-spacing:.17em;color:{DIM};margin-bottom:16px}}
.phead em{{font-family:'Source Serif 4',Georgia,serif;font-style:normal;font-size:15px;
  letter-spacing:0;color:{ACC};margin-left:1px}}
.pdot{{width:7px;height:7px;border-radius:9px;background:{ACC};
  box-shadow:0 0 0 4px rgba(226,118,42,.16)}}
.pdot.cool{{background:{COOL};box-shadow:0 0 0 4px rgba(91,139,208,.16)}}
.pfoot{{margin-top:15px;padding-top:13px;border-top:1px solid rgba(255,255,255,.055);
  font-size:17px;color:#767F8D;letter-spacing:.01em;line-height:1.45}}

.solve{{width:384px}}
.row{{display:grid;grid-template-columns:34px 1fr auto;align-items:baseline;gap:10px;
  padding:6px 0;border-top:1px solid rgba(255,255,255,.05);animation:rise .4s ease both;
  animation-delay:var(--d)}}
.row:first-of-type{{border-top:0}}
.sym{{font-family:'Source Serif 4',Georgia,serif;font-size:26px;color:{ACC}}}
.nm{{font-size:19.5px;color:{INK}}}
.dm{{font-family:'JetBrains Mono',monospace;font-size:15px;color:#767F8D}}

/* reference-pose stack */
.stack{{position:relative;width:286px;height:300px;flex:none}}
.halo{{position:absolute;inset:-18px -4px 10px;border-radius:50%;filter:blur(16px);
  background:radial-gradient(closest-side,rgba(226,118,42,.20),transparent 76%)}}
.halo.soft{{background:radial-gradient(closest-side,rgba(91,139,208,.17),transparent 74%)}}
.ghost{{position:absolute;bottom:34px;width:60px;height:214px;transform-origin:bottom;
  background:#C3CAD6;-webkit-mask:url({MASK}) no-repeat center bottom/contain;
  mask:url({MASK}) no-repeat center bottom/contain;
  animation:rise .45s ease both;animation-delay:var(--d)}}
.ghost.live{{background:{ACC};filter:drop-shadow(0 0 16px rgba(226,118,42,.45));
  animation-delay:430ms}}
.tag{{position:absolute;bottom:0;left:0;right:0;text-align:center;
  font-family:'JetBrains Mono',monospace;font-size:15px;letter-spacing:.16em;
  color:#767F8D}}
.stack .tag{{text-align:left}}

.arrowline{{position:relative;width:52px;height:2px;flex:none}}
.arrowline .dash{{position:absolute;inset:0;
  background:repeating-linear-gradient(90deg,{FAINT} 0 6px,transparent 6px 12px);
  transform-origin:left;animation:grow .5s ease both;animation-delay:var(--d)}}
.arrowline .head{{position:absolute;right:-2px;top:-4px;width:0;height:0;
  border-left:9px solid {FAINT};border-top:5px solid transparent;
  border-bottom:5px solid transparent;animation:rise .3s ease both;
  animation-delay:calc(var(--d) + 350ms)}}

/* a figure column: the silhouette in a box of its own aspect, plus a caption */
.col-fig{{position:relative;height:340px;display:flex;flex-direction:column;
  align-items:center;justify-content:flex-end;padding-bottom:26px;flex:none}}
.figure{{position:relative;height:276px;aspect-ratio:751/1500;
  animation:rise .5s ease both;animation-delay:var(--fd)}}
.figure.tall{{height:300px}}
.figure img{{height:100%;width:100%;object-fit:contain;display:block;
  filter:drop-shadow(0 16px 30px rgba(0,0,0,.5))}}
.figure.lit img{{filter:none}}
.pin{{position:absolute;width:13px;height:13px;border-radius:50%;background:{ACC};
  transform:translate(-50%,-50%);
  box-shadow:0 0 0 4px rgba(226,118,42,.17),0 0 16px rgba(226,118,42,.5);
  animation:pop .4s ease both;animation-delay:var(--d)}}
.clash{{position:absolute;left:34%;top:40%;width:66px;height:66px;margin:-33px 0 0 -33px;
  border-radius:50%;
  background:radial-gradient(closest-side,rgba(226,118,42,.55),transparent 70%);
  animation:ring .5s .45s ease both}}
.clashring{{position:absolute;left:34%;top:40%;width:98px;height:98px;
  margin:-49px 0 0 -49px;border-radius:50%;border:1.5px dashed rgba(226,118,42,.7);
  animation:ring .55s .55s ease both}}
.plane{{position:absolute;left:-62px;right:-62px;bottom:6px;height:1px;
  background:linear-gradient(90deg,transparent,rgba(154,162,174,.55) 22%,
    rgba(154,162,174,.55) 78%,transparent);
  transform-origin:center;animation:grow .55s .4s ease both}}
.dip{{position:absolute;left:18%;bottom:-7px;width:74px;height:16px;
  border-radius:50%;filter:blur(5px);
  background:radial-gradient(closest-side,rgba(226,118,42,.75),transparent 80%);
  animation:rise .45s .6s ease both}}
.dip::after{{content:'';position:absolute;left:50%;top:-1px;width:1px;height:13px;
  background:repeating-linear-gradient(180deg,{ACC} 0 3px,transparent 3px 6px)}}

/* prior */
.prior{{width:214px}}
.bars{{display:flex;align-items:flex-end;gap:7px;height:78px}}
.bars i{{display:block;width:17px;border-radius:3px;
  background:linear-gradient(180deg,{COOL},rgba(91,139,208,.22));
  animation:bar .5s ease both;animation-delay:var(--d)}}

.lay .lrow{{display:flex;align-items:baseline;gap:11px;padding:7px 0;
  border-top:1px solid rgba(255,255,255,.05);font-size:18px;color:{DIM};
  animation:rise .4s ease both;animation-delay:var(--d)}}
.lay .lrow:first-of-type{{border-top:0}}
.lay .lrow span{{white-space:nowrap}}
.lay .lrow b{{color:{INK};font-weight:500;margin-left:auto;font-size:17.5px;
  white-space:nowrap}}
.sw{{width:9px;height:9px;border-radius:3px;flex:none;transform:translateY(-1px)}}
.sw.acc{{background:{ACC}}} .sw.cool{{background:{COOL}}} .sw.dim{{background:{FAINT}}}

.chip{{position:absolute;right:96px;bottom:74px;max-width:700px;text-align:right;
  font-size:23px;line-height:1.45;color:#C8CED8;letter-spacing:-.004em;
  text-shadow:0 2px 16px rgba(0,0,0,.75);animation:rise .5s .3s ease both}}
.chip::before{{content:'';display:block;width:46px;height:1px;margin:0 0 12px auto;
  background:{ACC};transform-origin:right;animation:grow .5s .35s ease both}}

/* the palm map: the same hand the picture is looking at */
.palm{{position:relative;height:300px;aspect-ratio:1/1;
  animation:rise .5s .15s ease both}}
.palm svg{{width:100%;height:100%;display:block;overflow:visible}}
.palm path{{fill:rgba(200,210,226,.085);stroke:rgba(190,201,218,.55);
  stroke-width:.0045;vector-effect:non-scaling-stroke;
  stroke-dasharray:4;stroke-dashoffset:4;animation:draw 1.1s .1s ease both}}
@keyframes draw{{to{{stroke-dashoffset:0}}}}
.tz{{position:absolute;width:15px;height:15px;border-radius:50%;
  transform:translate(-50%,-50%);background:{ACC};
  box-shadow:0 0 0 4px rgba(226,118,42,.17),0 0 15px rgba(226,118,42,.6);
  animation:pop .42s ease both;animation-delay:var(--d)}}
.halo.warm{{background:radial-gradient(closest-side,rgba(226,118,42,.17),transparent 74%)}}
"""


def plate(i, frame, ms, stage, sub_lab, title, sub, dia, chip):
    rail = "".join(
        f'<div class="{"on" if k == stage else ""}">{n} {t}<span></span></div>'
        for k, (n, t) in enumerate(STAGES))
    lab = f'<div class="sub-lab">{html.escape(sub_lab)}</div>' if sub_lab else ""
    p = HERE / f"rc_{i}_{frame:03d}.html"
    png = FRAMES / f"a{i}_{frame:03d}.png"
    p.write_text(f"""<!doctype html><meta charset="utf-8"><style>{CSS}</style>
<div class="scrim"></div>
<div class="rail">{rail}</div>
<div class="col">{lab}<h1>{html.escape(title)}</h1>
<p class="sub">{html.escape(sub)}</p><div class="dia">{dia}</div></div>
<div class="chip">{chip}</div>""")
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    "--force-device-scale-factor=1",
                    f"--virtual-time-budget={ms}",
                    "--allow-file-access-from-files",
                    "--default-background-color=00000000",
                    f"--screenshot={png}", "--window-size=1920,1080", p.as_uri()],
                   check=True, capture_output=True)
    p.unlink()
    return png


def main():
    if not BASE.exists():
        sys.exit(f"missing {BASE}")
    FRAMES.mkdir(exist_ok=True)
    for f in FRAMES.glob("*.png"):
        f.unlink()

    total = ACTS[-1][1] + 0.5
    # the picture is now the bed, full frame; the type rides on top of it
    chain = [f"[0:v]fps={FPS},scale=1920:1080,"
             f"fade=t=in:st=0:d=0.7,fade=t=out:st={total-0.55:.2f}:d=0.55[b0]"]
    last, inputs, idx = "b0", ["-i", str(BASE)], 1

    for i, (t0, t1, stage, lab, title, sub, dia, chip) in enumerate(ACTS):
        seq_fps = DRAW_N / (DRAW_MS / 1000)
        for k in range(DRAW_N):
            ms = int(60 + k * (DRAW_MS / (DRAW_N - 1)))
            plate(i, k, ms, stage, lab, title, sub, dia, chip)
        hold = max(int(round((t1 - t0 - DRAW_MS / 1000) * seq_fps)), 1)
        for k in range(hold):                       # hold the finished diagram
            src = FRAMES / f"a{i}_{DRAW_N-1:03d}.png"
            (FRAMES / f"a{i}_{DRAW_N+k:03d}.png").write_bytes(src.read_bytes())
        inputs += ["-framerate", f"{seq_fps:.4f}",
                   "-i", str(FRAMES / f"a{i}_%03d.png")]
        f = 0.38
        chain.append(f"[{idx}:v]format=rgba,fps={FPS},"
                     f"fade=t=in:st=0:d={f}:alpha=1,"
                     f"fade=t=out:st={t1-t0-f:.2f}:d={f}:alpha=1,"
                     f"setpts=PTS-STARTPTS+{t0}/TB[L{i}]")
        out = "vo" if i == len(ACTS) - 1 else f"b{i+1}"
        chain.append(f"[{last}][L{i}]overlay=0:0:enable='between(t,{t0-f},{t1})'[{out}]")
        last = out
        idx += 1
        print(f"  act {i}: {DRAW_N} drawn + {hold} held @ {seq_fps:.1f} fps", flush=True)

    dst = OUT / "pipeline_anim.mp4"
    r = subprocess.run(["ffmpeg", "-v", "error", "-y"] + inputs +
                       ["-filter_complex", ";".join(chain), "-map", "[vo]",
                        "-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "slow",
                        "-crf", "21", "-pix_fmt", "yuv420p", "-r", str(FPS), "-an",
                        "-movflags", "+faststart", str(dst)], capture_output=True, text=True)
    if r.returncode:
        print(r.stderr[-2500:]); sys.exit(1)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "3.2", "-i", str(dst),
                    "-frames:v", "1", "-q:v", "4", str(OUT / "pipeline-poster.jpg")], check=True)
    print(f"-> {dst} ({dst.stat().st_size/1e6:.1f} MB, {total:.1f}s)")


if __name__ == "__main__":
    main()
