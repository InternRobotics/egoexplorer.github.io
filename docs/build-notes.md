# EgoExplorer project page

Rebuilt from `egoexplorer_website.zip`. 138 MB, fully static — open it over HTTP
(the point-cloud previews and `sessions.json` are fetched, so `file://` will not
work):

```sh
python3 -m http.server 8799 --directory . && open http://127.0.0.1:8799/
```

## What changed

**Design.** Rebuilt in the register of the [Curr-0 blog](https://current-robotics.com/blog/curr-0),
with two full-bleed dark "chapters" (numbered eyebrow, serif headline, framed
media, stat row) carrying the showcase sections in the manner of the
`dinosaur_*` and `agile_*` demo reels:
a dark hero that fades into a light page, a serif display face (Source Serif 4)
over a sans body (Inter), one narrow 720 px measure for prose with figures
breaking out to 1180 px, and large section spacing. Nymeria's habit of giving
each hardware component its own framed panel with a caption is kept.

**Hero video — recut.** `assets/hero.mp4` is the reconstructed body replayed
inside the room's own point cloud, with the head-camera view inset and visible
again inside the camera frustum. Five chapters, cross-faded, drawn from the 4K
`wuji_four_sessions` and lab point-cloud reconstructions paired with the
matching session's egocentric view. Rebuild with `build/hero.py`.

**Statistics — removed.** The whole section and its ten figure/GIF assets are gone.

**Sample videos — replaced, and split into four streams.** The ten raw session
clips are gone. In their place is a dark chapter built on
`session_package/processed_10_videos/videos_clean/` (720p, 5×).

The four modalities are shown as **four separate labelled views** — egocentric
video, whole-body motion, finger articulation, tactile contact — rather than one
composite dashboard. All four are canvases drawing different crops of a *single*
hidden `<video>` on `requestAnimationFrame`, so they stay frame-exact in sync and
cost one download rather than four. Crop rectangles are in `CROP` in
`explorer.js`; fingers and tactile each composite the left and right hand panels
side by side.

Under them, a custom transport: a segment-partitioned timeline you can click to
seek, the live subtask label and description, and the full subtask list from
`assets/sessions.json`.

**Hardware — redrawn, not cropped.** Nothing is taken from the paper figure.
`build/rig_render.py` decodes the real SMPL-X mesh out of a session
(`mesh.i8c.gz` + `smplx_faces.u32`), turns the figure to camera using the nose
direction, and renders it in Blender (Cycles, transparent film, shadow catcher).
A post pass flattens it to a slate diagram silhouette, and the five tracked
anchors are marked in the page itself from `assets/rig-anchors.json` so the dots
scale with the image. Prose carries the reasoning — the design constraint, the
trade of five anchors against a mocap suit, and the one-calibration-per-mounting
property — with the spec table last for people who just want part numbers.

**Prose.** Rewritten throughout in the Curr-0 voice: broad opening claim narrowed
to a concrete scene, short declaratives, the gap stated before the fix, and
requirement lists with bolded one-word leads.

## Sessions index

`assets/sessions.json` maps each source caption onto the accelerated video
timeline: `video_time = caption_time / 5 − head_trim`, where `head_trim` is 14 s
for session F and 2 s for the other nine (the trims were applied in accelerated
seconds), then the last ~2 % is cut. Predicted and measured durations agree to
within 0.3 s on all ten, which is what validates the mapping. Segments falling
outside the trimmed window are dropped — F keeps 13 of 19, E 8 of 10, B 33 of 35,
C 21 of 22, the rest are complete.

Regenerate it from `/Volumes/NASStorage/Downloads/session_package` if the videos
are re-cut.

## Point clouds

The viewer reads the precomputed previews in `assets/point-clouds/*.js`; it never
touches the raw `.ply` files, so the 1.1 GB `gaussion/` directory from the
original zip is **not** shipped here. It is still needed to regenerate previews —
put it back beside this directory and run `build/build_pointcloud_previews.py`.

## Checked

Layout measured in-browser: 8,754 px tall, eight sections stacked correctly, no
horizontal overflow. All five rig markers land inside the figure box at their
intended fractions. Ten sessions, four canvases, and the 15 segments of session A
appear in both the timeline and the list. Point-cloud previews load with no
console errors.

The four crop rectangles were checked by cutting the same frame with ffmpeg and
eyeballing all six regions (ego, body, left/right skeleton, left/right tactile) —
each lands exactly on its panel.

Media could not be play-tested in the automation tab: Chrome keeps that tab
hidden (`document.hidden === true`), and a `<video>` there never gets past
`readyState 0`. Videos need a foreground window to verify.

---

# Revision 4

**The page no longer creeps upward.** `explorer.js` highlighted the live subtask
with `element.scrollIntoView({block:'nearest'})`, which walks up to *every*
ancestor scroll container — including the document — so the window drifted on
each segment change. It now sets the list's own `scrollTop` and touches nothing
else; verified by advancing the list and watching `scrollY` hold.

**Finger panel: both hands palm-out, fingers up.** The measured wrist rotation
is now divided out (`v @ R0` after the solve) and a presentation rotation is
derived from the MANO rest hand — finger axis onto +Z, palm normal onto −Y — so
the panel isolates articulation from global hand pose, which is panel B's job
anyway.

Two bugs were found getting there, both worth recording:

- The camera used `TRACK_TO` with `up_axis='UP_Y'` while looking *along* +Y. The
  up vector was degenerate, so Blender resolved it to an arbitrary roll — which
  is why the hands first came out sideways. Switching to `UP_Z` made the render
  come back black instead. The constraint is gone; the camera now takes an
  explicit `rotation_euler=(90°,0,0)`, which is exact for a −Y→+Y view.
- A diagnostic used `obj.data.vertices[::300]`; Blender's `bpy_prop_collection`
  has no step slicing and raised `TypeError`. Indexed `range()` instead.

**The pipeline film no longer screenshots the paper.** `build/pipeline_recut.py`
draws its own schematics as inline SVG — device+anchor into a reference library
into a fit; five dots through a temporal prior into a proposal; and one diagram
per constraint layer. The `figpanels/` crops of the paper PDF are gone.

**Left and right now agree.** A stage rail (01 CALIBRATE / 02 COMPLETE /
03 CONSTRAIN) sits across the top with the current stage lit, and a caption at
the lower right names exactly what the 3D is showing at that instant — "the five
measured anchors, alone", "the completed body appears around them", and so on.
Before, the two halves were simply adjacent; now they point at the same thing.

**Point clouds orbit by themselves.** A slow 0.075 rad/s spin, throttled to
24 fps, that yields to the pointer and resumes 2.5 s after you let go. It stops
when the canvas scrolls out of view (an `IntersectionObserver`), when the tab is
hidden, and when the visitor asks for reduced motion — `draw()` is a CPU
rasteriser over ~180k points and should not run against something nobody is
looking at.

**Design moved toward Curr-0.** Plain white rather than warm paper, body at
18.5 px / 1.76 on a 780 px measure, larger serif headings, roomier sections,
centred nav links, and the orange pulled back to eyebrows and markers only.

## Still open


- Fonts load from Google Fonts over the network; self-host them before any
  deployment that has to work offline or behind a firewall.
- `hero.mp4` is 23 MB and autoplays. Consider a shorter loop or a lower bitrate
  for mobile.
- The rig figure is an unclothed SMPL-X mesh flattened to a silhouette. It reads
  as a diagram, but swap in a clothed or more abstract body if that matters for
  the audience.
- The hardware section describes the glove and camera in prose only; the figure
  marks anchors, not the devices themselves. Device callout insets would be the
  next thing to draw.
- The citation block is still the anonymous placeholder.


---

# Revision 2

**Source video was leaking.** The four-stream chapter drives its canvases from a
`hidden` `<video>`, but the base rule `img, video, canvas { display: block }`
outranks the UA sheet's `[hidden] { display: none }`, so the whole composite
dashboard was rendering under the four panels. Fixed with an explicit
`[hidden] { display: none !important }`, an inline `style="display:none"` on
that element, and `?v=` on the stylesheet and script so a stale cache cannot
bring it back.

**Montage is now a dense seamless wall.** `build/montage.py` tiles the ten
egocentric panels 5 × 2 at 1920 × 432 with no gaps, no captions and no stat
cells — the "10 tasks / 100 / 2,715 / 5" text that used to be baked into the
video duplicated the page copy. Task names moved into an HTML key under the
strip, numbered in reading order.

**The pipeline section animates now.** The paper figure is replaced by
`assets/pipeline_anim.mp4` (11.6 s), built in two steps:

- `build/pipeline_anim.py` renders 290 EEVEE frames driven by the **real SMPL-X
  mesh sequence** of a session, in three acts — the five anchors alone, the body
  completed around them, the ground resolving under it — with material alpha
  fades and a slow eased orbit.
- `build/pipeline_mux.py` muxes those frames and overlays the stage typography
  (numbered eyebrow, serif headline, rule) as transparent Chrome-rendered plates,
  cross-faded on cue.

---

# Revision 3

**Stream B — the body is re-rendered, not re-cropped.** `build/body_streams.py`
decodes each session's own `mesh.i8c.gz` and renders it in Blender/EEVEE with
smooth normals, a three-point rig and a quiet wireframe ground, onto the
accelerated video's timeline:

    t_source = (t_clean + head_trim) * 5        head_trim = 14 s for F, else 2 s
    mesh_idx = t_source / source_duration * (NF - 1)

The camera distance is solved from the vertical FOV so the figure always fills
~74 % of the frame, and it follows the subject with a 1.6 s moving average while
the world grid stays put — a fixed wide shot had to cover a 5 m walk in session
E and shrank the figure to under half the frame. Ten clips, ~11.5 MB total.

**Stream C — a MANO hand, posed from the glove.** `build/hand_streams.py` loads
the MANO right hand from `fivetrackerlocal/tmp/hand_tactile_figure/mano_pinch.npz`
(778 vertices, 1,538 faces, LBS weights over 16 joints) and drives it from the
glove's 21 MediaPipe-style keypoints:

- the wrist frame comes from a Kabsch fit on the palm (wrist + four MCPs);
- every finger bone takes the minimal rotation carrying its rest direction onto
  the measured one, composed down the chain;
- the mesh keeps MANO's own bone lengths — only rotation comes from the glove;
- the left hand is solved by mirroring in X and mirroring the result back.

Twist about a bone is unobservable from three collinear-ish points, so it is
left at zero. The solve was checked over 82 sampled frames on both hands: all
finite, posed spans 0.10–0.14 m against a 0.19 m rest hand, i.e. curled as
expected for someone holding glassware.

**Tactile (D) is unchanged**, as asked — still the 17-region panel from the
dashboard.

**How the four panels are fed now.** A and D stay crops of the dashboard clip,
which also remains the master clock; B and C each get their own hidden `<video>`
that the paint loop nudges back whenever it drifts more than 0.22 s. Crops and
folders are at the top of `explorer.js`.

**The pipeline film is recut against the paper figure.** `build/pipeline_recut.py`
slows the Blender pass to 19.8 s, seats it in the right half, and builds the
paper's own pipeline panels up the left — ① Calibrate, ② Complete, then L1, L2,
L3 stacking one at a time — each with its own eyebrow, headline and rule. Panels
are cropped from `main_03_dataset_pipeline.pdf` by `build/figpanels`. The
previous cut was pure 3D and read as a diagram; this one is anchored to the
figure the paper actually uses.

## Driving 剪映 (jianying-headless) on this machine

The tool is still unused, and there is exactly one reason: **剪映 is not
installed here.** Everything else it wants is already in place — macOS 26.5.2 on
Apple Silicon, Xcode command line tools, ffmpeg/ffprobe, Python 3.11.

To enable it:

1. Install **剪映专业版 11.5.0** (11.4.2 also works) from
   <https://www.capcut.cn/>. The tool drives the installed app's own engine, so
   the version matters.
2. Then:

   ```sh
   git clone https://github.com/mcncarl/jianying-headless.git
   cd jianying-headless
   python3 tools/build_native_codec.py
   python3 skills/yichen-jianying-edit/scripts/headless_draft.py doctor
   ```

   `doctor` reports whether the environment and 剪映 version line up.
3. Editing is driven by a JSON plan (`examples/basic.plan.json` is the template):
   `build` turns a plan into an editable draft, `verify-build` checks it,
   `publish` registers it on 剪映's home screen, and export renders headlessly:

   ```sh
   python3 skills/yichen-jianying-edit/scripts/headless_draft.py export \
     --build "$PWD/work/new-build" --out "$PWD/work/new-export"
   ```

   The result is `render.mp4` in the `--out` directory.

Once it is installed, tell me and I will write the plan JSON for these cuts so
the timeline is editable in 剪映 rather than baked by ffmpeg. Until then every
video here is cut with ffmpeg plus Blender, which is why the edits are
reproducible scripts rather than a draft you can open.

## Still open

- Fonts load from Google Fonts over the network; self-host them before any
  deployment that has to work offline or behind a firewall.
- `hero.mp4` is 23 MB and autoplays. Consider a shorter loop or a lower bitrate
  for mobile.
- The rig figure is an unclothed SMPL-X mesh flattened to a silhouette. It reads
  as a diagram, but swap in a clothed or more abstract body if that matters.
- The citation block is still the anonymous placeholder.

---

## 2026-10-12 pass

**The pipeline film is now a real session in a mocked room** (`build/film/`).
The old version put a boxed 3D inset beside the typography, and the inset
clipped the figure at its edges. The picture is now full-bleed, with the type
on a scrim down the left third.

Everything in it is measured except the room:

* The body is SMPL-X solved from the session at **30 Hz**, read from
  `/Volumes/NASStorage/Downloads/smplx/*.npz` — the `unified_30hz` exports —
  and interpolated to 60 fps. The copies in
  `session_package/*/mesh.i8c.gz` are capped at 300 frames per session, which
  for `session_A` is 1.4 Hz; at 5× playback that was about seven distinct poses
  per second of video. **That cap, not the encode, was the stutter.**
* The five gizmos sit on the actual `tracker_position`, each trailing 1.35 s of
  where it has been. Vision is pale, manipulation warm, locomotion cool.
* The heat that comes up on the hands in the last act is the Wuji glove's own
  per-region pressure (`tactile_*_L2_score`), spread onto the SMPL-X hand
  vertices by `hand_regions.py`, which ports the paper's 17-region assignment
  onto SMPL-X (its hand rig is MANO's, joint for joint).
* The kitchen is invented, but fitted to the motion: its two work surfaces sit
  where the hands actually dwell.

**Dialling the room.** `SCENE_LEVEL` at the top of `build/film/room_film.py`
runs 0 (black void) to 1 (fully lit) and changes nothing about the body or the
measurements. `build/film/scene_levels_reference.jpg` shows the same frame at
0.25 / 0.45 / 0.70 / 0.95. The film ships at **0.70**. To change it, edit the
constant and re-run:

```sh
cd build/film
blender -b -P room_film.py -- 0 1620           # ~30 min, writes frames/
ffmpeg -framerate 60 -i frames/f_%04d.png -crf 19 -pix_fmt yuv420p base.mp4
python3 film_type.py                           # lays the typography over it
```

**Camera.** Placement is solved, not hand-tuned: `place()` searches outward
from the intended shot for the nearest angle that is neither inside furniture
nor looking through it, and the whole track is smoothed before rendering.
Angles are relative to the direction the subject faces, so a three-quarter shot
stays one when they turn from the counter to the island. In the last act the
camera flies the right hand's palm bearing, so the close-up lands on the palm
however the wrist rolls.

**The figure is clothed.** SMPL-X is unclothed and the film pushes close; a
baked garment mask (`bake/garment.npy`) shades the trunk and thighs as cloth.
The hands stay bare, because the tactile heat has to read against skin.

**Stream panels, rebuilt.** `build/film/build_streams.sh` re-renders the body
and hand panels for all ten sessions from the same 30 Hz source at 60 fps, and
the hand panel now comes from the SMPL-X hands (which the glove drives) rather
than a separate MANO fit, so panels B and C are the same body.

**Page.** The title gives `EgoExplorer` its own line and sizes the subtitle off
the viewport so it holds one line down to phone width; `<br>`-broken headings
are gone; the hero and nav carry Paper / Hugging Face / toolkit buttons (hrefs
are still placeholders — see the TODO in `index.html`); the four-stream section
plays itself and advances to the next session when one ends; `<cite data-r>`
markers show the entry on hover from `refs.json`, generated from the paper's
own `.bib`; the prose measure is 700 px; every section carries a number.

**Motion** lives in `motion.js`, gated on `<html data-motion>` — delete that
attribute to revert the whole layer. It never waits on `requestAnimationFrame`
(a background tab starves it) and reveals everything above the fold rather than
only what is on screen, so a jump scroll cannot strand content invisible.

**Fonts are self-hosted** — `fonts.css` plus 390 KB of woff2 under `fonts/`,
latin and latin-ext only. The page no longer touches fonts.googleapis.com.

### Testing note

Headless Chrome will not reproduce scroll- or animation-driven behaviour: it
clamps the viewport to 500 CSS px, starves `requestAnimationFrame`, never
advances CSS transitions, fires `scroll` only sporadically under
`--virtual-time-budget`, and never completes a `scroll-behavior: smooth`
scroll. Test through a same-origin iframe harness that sets
`scrollBehavior = 'auto'`, dispatches its own `scroll` events, and prints
results into a `<pre>` the screenshot can capture.

### Still open

* The four link buttons point at `#`. Fill them in when the URLs exist.
* The citation block is still anonymous, for double-blind review.
* `hero.mp4` is 13 MB and autoplays. Its source only exists at 10 fps, so it is
  motion-interpolated to 30.

## 2026-10-12, second pass

Review notes, and what each one turned into.

**"The body has colour patches on it — there is no tactile on the body, only
on the hands."** Correct, and the patches were mine: a garment mask shading the
trunk and thighs, added to avoid a bare mannequin. Soft-edged patches on a
figure whose hands carry a heat map read as tactile data on the torso, which
is exactly the wrong thing to suggest. The body is one uniform material now,
in the film and in the stream panels.

**"Some fingers bend backwards"**, and later **"the fingers are twisted and
dislocated."** Both real, both in the source, and the second is the bigger
fault.

The backward bend: measured against the model's own flat rest pose, session_J
puts the fingertips behind the knuckle plane on about 60% of frames, by up to
40 mm. It varies a lot by session — session_A's right hand barely does it at
7%, session_H's both hands at ~75%.

The twist is worse. The glove fit returns a free 3-DOF rotation at every
finger joint, and on session_A it puts **50-72 degrees of twist into the index
and middle PIP and DIP joints**. Those joints are hinges. No amount of
clamping flexion fixes that, and indeed the first attempt did not: raw and
clamped measured identical.

`Session.clean_hand()` decomposes each joint into twist about its own bone and
the remaining swing, drops the twist, and projects the swing onto the axes the
joint actually has — flexion plus limited abduction at the knuckle, flexion
only below it. The axes are derived from the model's rest pose per joint and
per side: the bone runs to the child joint, the hinge axis is perpendicular to
it in the plane of the palm. Because the swing axis is perpendicular to the
bone by construction, that projection is exact rather than an approximation.
Verified: twist goes to **exactly 0 at all fifteen joints** while flexion is
preserved to within about a degree.

The thumb keeps both swing axes under a generous limit — it is not a hinge at
any joint and its flexion plane is rotated away from the fingers', so for the
thumb this pass is a twist removal and nothing more.

Watch the signs: MANO's left hand is a **mirror** of its right, so the flexion
axis is positive toward the palm on the right and negative on the left, and
`cross(fwd, lat)` is palmar on the left and dorsal on the right. A sign shared
between the hands silently breaks one of them.

It is a presentational correction and the figure caption says so.

**"The SMPL-X suddenly scales and translates in."** The body used to arrive by
scaling from zero, and because the mesh lives in world coordinates, scaling
about the object origin also slid it across the room. It fades in on alpha now.

**"Lay the room out so the body does not pass through things."** The furniture
is placed from the body's own occupancy over all 1620 frames: with its front
face at y = 2.40 the body never drops below z = 0.788 over the counter run,
and with its back face at y = −0.70 it never drops below z = 0.854 over the
island, so the tops sit just under those ceilings. Props sit in the x-ranges
the hands never visit. The probe in the commit message reports zero
intersections across every box; before it, the island was 16 cm deep.

**"Show more of the tactile."** The bake smooths the 17 discrete regions over
the hand mesh with three Laplacian passes — a hard region assignment shows as
sawtooth stripes once it is lit — and the shader lifts the signal before the
ramp, which now runs cool → warm → white instead of dark → orange.

**"The hand geometry is not fine enough close up."** Catmull-Clark subdivision
at render level 2 on the body, and on the hands in the stream panels.

**Capture section** is now four views of `camera_tracker_extrinsics/
smplx_rig.html`, the project's own wearing study — see `build/rig/README.md`.


## On the cluster

Blender 4.5.3 installs on it in 14 s (its own link runs at ~26 MB/s), and
headless EEVEE renders. It is still not useful for this work: `nvidia-smi`
reports **0 MiB used** during a render, because the container ships CUDA but
not the NVIDIA EGL/GL userspace, so EGL resolves to Mesa and Blender falls
back to software. The Vulkan backend behaves the same. Steady state is
0.162 s/frame against ~0.21 s on the Mac — about 1.3x, which does not repay a
19-minute upload at the 1.6 MB/s uplink, nor the risk of the panels no longer
matching the film's look.

It would pay off for something transfer-light and CPU-heavy, or for a Cycles
render whose look is defined from scratch rather than matched.

## Two render-pipeline traps

* **Frame counts do not tell you the content is current.** Nine of ten panels
  had the right number of frames while six were from a build two pipelines
  old. Check write times against when the fix landed.
* **Do not resume a render from whatever frames are on disk, and do not
  delete frames until the encode is verified.** A worker script outlived a
  `pkill` of its parent, saw Blender exit, encoded a partial clip and removed
  its frames. `render_all.sh` renders from 0 and only cleans up once `ffprobe`
  agrees the clip is the right length.

## Chapter 06 — humanoid (added 2026-10-12)

A dark chapter between Environments and Citation (nav: "Humanoid"; Citation is now 07). Two
5×-speed takes of the G1 + Wuji Hand 2 physics rollouts side by side, in the same card style as the
four streams: `assets/humanoid/g1_weighing.mp4` (37.9 s) and `g1_reaction.mp4` (26.4 s), 1440×1080
(4:3 centre crop of the 1080p render — the robot never leaves x = 583…1269), with posters.
Made from `robotics/g1_smplx_retarget/outputs/<task>/wbc_wuji_1080p.mp4`:

```sh
ffmpeg -i wbc_wuji_1080p.mp4 -vf "select='not(mod(n\,5))',setpts=N/30/TB,crop=1440:1080:240:0" \
  -r 30 -an -c:v libx264 -preset slow -crf 21 -pix_fmt yuv420p -movflags +faststart g1_weighing.mp4
```

The BibTeX block has a Copy button (`copy.js`): Clipboard API in a secure context (https or
localhost), textarea fallback elsewhere; the button turns green with a check for 1.8 s on success,
and on failure selects the text and says "Press ⌘C".

## "Still growing" (added 2026-10-12)

The hero eyebrow reads "100+ hours, growing" behind a pulsing live dot, and the 100-hour stat in
chapter 01 counts up to "100+" with a rising "+", a light streak running along a hairline under the
number and a live dot on its label (`.stat-live`, `.live-dot` in styles.css; motion.js keeps the
trailing `<i>` through the count-up). Qualitative on purpose — swap in a real cumulative-hours curve
when the capture log is to hand. All of it stops under prefers-reduced-motion.
