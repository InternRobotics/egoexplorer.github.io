"""Re-render the whole-body stream for every session.

  /Applications/Blender.app/Contents/MacOS/Blender -b -P body_streams.py

Replaces the dashboard's body panel, which shaded flat derivative normals under
one hard-coded light on a harsh blue grid. Here the real SMPL-X mesh gets smooth
normals, a three-point rig and a quiet ground, rendered per session onto the
accelerated video's own timeline:

    t_source = (t_clean + head_trim) * 5        head_trim = 14 s for F, else 2 s
    mesh_idx = t_source / source_duration * (NF - 1)

The camera is fixed per session, framed over the whole path, so locomotion still
reads as locomotion instead of the subject sitting still while the world slides.
"""
import bpy, csv, gzip, json, math, re, sys
import numpy as np
from pathlib import Path

SP = Path("/Volumes/NASStorage/Downloads/session_package")
OUT = Path(__file__).resolve().parent / "body_streams"
OUT.mkdir(exist_ok=True)

FPS = 12.5
W, H = 656, 456                 # matches the panel's 492x342
HEAD = {"session_F": 14.0}
SPEED = 5.0
KEEP = 0.98                     # the clean videos drop the last ~2 %

def load_session(sid):
    d = SP / sid
    html = (d / "viz" / "index.html").read_text(errors="replace")
    org = np.array(json.loads(re.search(r'"mesh_origin":(\[[^\]]+\])', html).group(1)))
    qs = float(re.search(r'"quant_scale":([0-9.eE+-]+)', html).group(1))
    nv = int(re.search(r'"vertex_count":(\d+)', html).group(1))
    raw = np.frombuffer(gzip.open(d / "mesh.i8c.gz").read(), dtype="<i2")
    nf = raw.size // (nv * 3)
    V = raw[:nf * nv * 3].reshape(nf, nv, 3).astype(np.float32) * qs + org   # Z up
    return V

FACES = np.fromfile(SP / "session_A" / "viz" / "smplx_faces.u32", dtype="<u4").reshape(-1, 3)

# ── scene built once, mesh swapped per session ─────────────────────────────
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE_NEXT'
sc.eevee.taa_render_samples = 16
sc.render.resolution_x, sc.render.resolution_y = W, H
sc.render.fps = 25
sc.render.image_settings.file_format = 'PNG'
sc.view_settings.view_transform = 'Filmic'
sc.view_settings.look = 'Medium High Contrast'
sc.world = bpy.data.worlds.new('w'); sc.world.use_nodes = True
next(n for n in sc.world.node_tree.nodes if n.type == 'BACKGROUND'
     ).inputs[0].default_value = (.020, .024, .031, 1)

def mat(name, rgba, rough=.5, emit=None, es=1.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    def s(k, v):
        if k in b.inputs: b.inputs[k].default_value = v
    s('Base Color', rgba); s('Roughness', rough)
    if emit:
        s('Emission Color', emit); s('Emission', emit); s('Emission Strength', es)
    return m

BODY = mat('body', (.337, .388, .470, 1), rough=.46)
GRID = mat('grid', (.090, .145, .215, 1), emit=(.090, .145, .215, 1), es=.8)

me = bpy.data.meshes.new('body')
me.from_pydata([(0, 0, 0)] * 10475, [], [tuple(t) for t in FACES])
me.update()
body = bpy.data.objects.new('body', me)
bpy.context.collection.objects.link(body)
body.data.materials.append(BODY)
for p in me.polygons:
    p.use_smooth = True

bpy.ops.mesh.primitive_grid_add(size=24, x_subdivisions=96, y_subdivisions=96)
grid = bpy.context.object
wf = grid.modifiers.new('wf', 'WIREFRAME'); wf.thickness = .007; wf.use_replace = True
grid.data.materials.append(GRID)

bpy.ops.object.camera_add(location=(0, -4, 1.4))
cam = bpy.context.object; cam.data.lens = 55; sc.camera = cam
bpy.ops.object.empty_add(location=(0, 0, .9))
tgt = bpy.context.object
c = cam.constraints.new('TRACK_TO'); c.target = tgt
c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'

def light(loc, e, col=(1, 1, 1), rot=(58, 0, -30)):
    bpy.ops.object.light_add(type='AREA', location=loc)
    L = bpy.context.object; L.data.energy = e; L.data.size = 5.0; L.data.color = col
    L.rotation_euler = tuple(math.radians(a) for a in rot)
    return L
KEY = light((-3.0, -3.2, 4.0), 900)
FILL = light((3.4, -1.8, 2.6), 380, (.78, .86, 1.0), (70, 0, 60))
RIM = light((0, 3.2, 3.0), 320, (1.0, .80, .62), (64, 0, 184))

rows = {r["alias"]: r for r in csv.DictReader(open(SP / "sessions.csv"))}
only = [a for a in sys.argv if a.startswith("session_")]
targets = only or list(rows)

for sid in targets:
    V = load_session(sid)
    NF = len(V)
    dur_src = float(rows[sid]["duration_s"])
    head = HEAD.get(sid, 2.0)
    dur_clean = (dur_src / SPEED - head) * KEEP
    n = max(int(round(dur_clean * FPS)), 1)

    # a damped follow beats a fixed wide shot: covering a 5 m walk from one
    # spot shrinks the figure to under half the frame. The world grid stays put,
    # so locomotion still reads as the ground sliding past.
    pelvis = V[:, ::40, :].mean(1)
    zmin = float(V[:, :, 2].min())
    body_h = float(V[:, :, 2].max() - zmin)
    sensor_h = 36.0 * H / W
    vfov = 2 * math.atan((sensor_h / 2) / cam.data.lens)
    dist = (body_h / 0.74 / 2) / math.tan(vfov / 2)
    grid.location = (0, 0, zmin + 0.002)

    d = OUT / sid
    d.mkdir(exist_ok=True)
    for f in d.glob("*.png"):
        f.unlink()
    # smooth the follow target so the camera glides instead of jittering
    idx = np.clip(((np.arange(n) / FPS + head) * SPEED / dur_src), 0, 1) * (NF - 1)
    idx = np.round(idx).astype(int)
    track = pelvis[idx][:, :2]
    win = max(int(FPS * 1.6) | 1, 3)
    pad = np.pad(track, ((win // 2, win // 2), (0, 0)), mode='edge')
    ker = np.ones(win) / win
    smooth = np.stack([np.convolve(pad[:, a], ker, 'valid')[:n] for a in (0, 1)], 1)

    for i in range(n):
        me.vertices.foreach_set('co', V[idx[i]].reshape(-1))
        me.update()
        tx, ty = float(smooth[i, 0]), float(smooth[i, 1])
        cam.location = (tx - dist * 0.38, ty - dist, zmin + body_h * 0.56)
        tgt.location = (tx, ty, zmin + body_h * 0.50)
        for L, off in ((KEY, (-3.0, -3.2, 4.0)), (FILL, (3.4, -1.8, 2.6)), (RIM, (0, 3.2, 3.0))):
            L.location = (tx + off[0], ty + off[1], zmin + off[2])
        sc.render.filepath = str(d / f"f_{i:05d}.png")
        bpy.ops.render.render(write_still=True)
    print(f"DONE {sid} {n} frames ({dur_clean:.1f}s)", flush=True)

print("ALL DONE")
