# Capture-section figures

Four views of the five-tracker wearing study, rendered from

    /Volumes/NASStorage/Documents/code/camera_tracker_extrinsics/smplx_rig.html

which is the project's own rig visualization: SMPL-X neutral body, HTC's VIVE
Ultimate Tracker CAD mesh ×5, GoPro HERO13 + Media Mod + printed adapter on a
head strap, and the Wuji glove description package. Nothing here is redrawn.

To regenerate:

```sh
cd /Volumes/NASStorage/Documents/code/camera_tracker_extrinsics
cp <this dir>/shot_rig.html _shot_rig.html
python3 -m http.server 8802 --directory . &
# view / zoom per image:
#   oblique 1.02   head 3.5   handR 8.5   ankleR 5.4
chrome --headless=new --enable-unsafe-swiftshader --use-gl=angle \
  --use-angle=swiftshader --virtual-time-budget=25000 \
  --screenshot=/tmp/rv_head.png --window-size=1200,1200 \
  "http://127.0.0.1:8802/_shot_rig.html?view=head&zoom=3.5"
```

The harness turns off the viewer's own annotation overlay — it is in Chinese
and points at internal files — and copies the WebGL canvas out, so only the
render is captured. The crop is then taken to 4:5 around the content by
luminance, so all four share one frame while each subject fills it.

WebGL does work in headless Chrome, but only with the ANGLE/SwiftShader flags
above; without them the canvas comes out blank.

## Update: it is a film now, rendered rather than screenshotted

Screenshotting the viewer had three problems: the crop distorted two of the
four images (the window was clamped at the image edge and stopped being 4:5),
it was static, and the viewer's own body mesh is coarse.

`rig_extract.py` decodes the geometry out of `smplx_rig.html` — each part is
gzipped base64 in `const payload`, either a triangle soup (n,3,6: position +
normal) or an indexed mesh, with a colour, a group and optional instance
transforms — and `rig_film.py` renders it in Blender: Catmull-Clark on the
body, matte finishes, soft studio light, and one continuous camera move,
whole rig → head → wrist → back to the start so it loops. 15 s, 900×1126, 60 fps.

The ankle is deliberately not a stop on the tour; it is visible in the wide
shot and the wrist note covers it in a line.

Two traps worth writing down:

* **`matrix_world` from numpy silently drops the translation.**
  `o.matrix_world = [list(r) for r in M]` applies the rotation and leaves the
  object at the origin. It has to be
  `Matrix([[float(x) for x in r] for r in M])`. Every instanced part — all
  five trackers, the adapter, the straps — was piled at the origin, and
  because the rotation *did* apply, the tracker read as a flat plate rather
  than as a misplaced one.
* **The instance matrix is column-major.** The page stores `R.T` flattened
  row-major and hands it to `uniformMatrix3fv(..., transpose=false)`, so the
  matrix GL sees is `R`. Reconstruct with `flat.reshape(3,3).T`.

Tone mapping is `Standard`, not Filmic: on a light background Filmic lifts the
blacks until the dark hardware reads as pale grey.
