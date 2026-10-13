"""C-cubed pipeline animation: five poses becoming a whole body.

  /Applications/Blender.app/Contents/MacOS/Blender -b -P pipeline_anim.py

Driven by the real SMPL-X mesh sequence from a session, so the motion is the
dataset's own. Three acts, cross-faded by material alpha:

  act 1  the five tracked anchors alone, which is all the rig measures
  act 2  the completed body fades in around them
  act 3  the ground resolves and the body settles onto it

Writes PNG frames; the caller muxes them and overlays the typography.
"""
import bpy, gzip, json, math, re, sys
import numpy as np
from pathlib import Path
from mathutils import Matrix

HERE = Path(__file__).resolve().parent
VIZ = Path("/Volumes/NASStorage/Downloads/session_package/session_A/viz")
OUTDIR = HERE / "pipeline_frames"
OUTDIR.mkdir(exist_ok=True)
for f in OUTDIR.glob("*.png"):
    f.unlink()

W, H, FPS = 1920, 1080, 25
A1, A2, A3 = 72, 100, 118          # act lengths (frames)
TOTAL = A1 + A2 + A3

# ── decode the mesh sequence ───────────────────────────────────────────────
html = (VIZ / "index.html").read_text(errors="replace")
org = np.array(json.loads(re.search(r'"mesh_origin":(\[[^\]]+\])', html).group(1)))
qs = float(re.search(r'"quant_scale":([0-9.eE+-]+)', html).group(1))
NV = int(re.search(r'"vertex_count":(\d+)', html).group(1))
raw = np.frombuffer(gzip.open(VIZ / "session_20260902_135055.mesh.i8c.gz").read(), dtype="<i2")
NF = raw.size // (NV * 3)
V = raw[:NF * NV * 3].reshape(NF, NV, 3).astype(np.float32) * qs + org   # Z up
FACES = np.fromfile(VIZ / "smplx_faces.u32", dtype="<u4").reshape(-1, 3)

# centre on the subject's own path and drop to the floor
V[:, :, :2] -= V[:, :, :2].reshape(-1, 2).mean(0)
V[:, :, 2] -= V[:, :, 2].min()
STEP = max(1, NF // TOTAL)
SEQ = V[::STEP][:TOTAL]
while len(SEQ) < TOTAL:                      # hold the last pose if we run short
    SEQ = np.concatenate([SEQ, SEQ[-1:]], 0)
print("SEQ", SEQ.shape)

# anchors: head crown, both wrists, both ankles, tracked per frame
top = SEQ[:, :, 2].max(1, keepdims=True)
bot = SEQ[:, :, 2].min(1, keepdims=True)
hgt = (top - bot)
def anchor_idx(frame):
    p = SEQ[frame]; z = p[:, 2]; t, b = z.max(), z.min(); h = t - b
    cx = (p[:, 0].max() + p[:, 0].min()) / 2
    out = {}
    out['head'] = int(np.argmax(z))
    low = np.where(z < b + .10 * h)[0]
    lL = low[p[low, 0] < cx]; lR = low[p[low, 0] >= cx]
    out['ankleL'] = int(lL[np.argmin(p[lL, 2])]) if len(lL) else int(low[0])
    out['ankleR'] = int(lR[np.argmin(p[lR, 2])]) if len(lR) else int(low[-1])
    band = np.where((z > b + .35 * h) & (z < b + .80 * h))[0]
    trunk = p[band][:, :2].mean(0)
    d = np.linalg.norm(p[band][:, :2] - trunk, axis=1)
    left = band[p[band, 0] < cx]; right = band[p[band, 0] > cx]
    dl = np.linalg.norm(p[left][:, :2] - trunk, axis=1)
    dr = np.linalg.norm(p[right][:, :2] - trunk, axis=1)
    out['wristL'] = int(left[np.argmax(dl)]); out['wristR'] = int(right[np.argmax(dr)])
    return out
AIDX = anchor_idx(TOTAL // 2)
print("ANCHOR IDX", AIDX)

# ── scene ──────────────────────────────────────────────────────────────────
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE_NEXT'
sc.render.resolution_x, sc.render.resolution_y = W, H
sc.render.fps = FPS
sc.frame_start, sc.frame_end = 1, TOTAL
sc.render.image_settings.file_format = 'PNG'
sc.view_settings.view_transform = 'Filmic'
sc.view_settings.look = 'Medium High Contrast'
sc.world = bpy.data.worlds.new('w')
sc.world.use_nodes = True
next(n for n in sc.world.node_tree.nodes if n.type == 'BACKGROUND'
     ).inputs[0].default_value = (.016, .019, .025, 1)

def mat(name, rgba, rough=.5, emit=None, es=1.0, alpha=1.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    def s(k, v):
        if k in b.inputs: b.inputs[k].default_value = v
    s('Base Color', rgba); s('Roughness', rough); s('Alpha', alpha)
    if emit:
        s('Emission Color', emit); s('Emission', emit); s('Emission Strength', es)
    m.blend_method = 'BLEND'
    return m

BODY = mat('body', (.317, .360, .436, 1), rough=.52, alpha=0.0)
ANC = mat('anchor', (.886, .408, .133, 1), emit=(.886, .408, .133, 1), es=3.4)
GRID = mat('grid', (.106, .180, .263, 1), emit=(.106, .180, .263, 1), es=1.0, alpha=0.0)

# body mesh, vertices swapped in per frame
me = bpy.data.meshes.new('body')
me.from_pydata([tuple(p) for p in SEQ[0]], [], [tuple(t) for t in FACES])
me.update()
body = bpy.data.objects.new('body', me)
bpy.context.collection.objects.link(body)
body.data.materials.append(BODY)
for poly in me.polygons:
    poly.use_smooth = True

anchors = {}
for k in AIDX:
    bpy.ops.mesh.primitive_uv_sphere_add(radius=.044, segments=22, ring_count=12)
    o = bpy.context.object; o.name = 'anc_' + k
    o.data.materials.append(ANC)
    bpy.ops.object.shade_smooth()
    anchors[k] = o

bpy.ops.mesh.primitive_grid_add(size=6, x_subdivisions=24, y_subdivisions=24)
grid = bpy.context.object; grid.name = 'grid'
wf = grid.modifiers.new('wf', 'WIREFRAME')
wf.thickness = .006; wf.use_replace = True
grid.data.materials.append(GRID)

# ── per-frame update ───────────────────────────────────────────────────────
def on_frame(scene, _=None):
    i = min(max(scene.frame_current - 1, 0), TOTAL - 1)
    P = SEQ[i]
    me.vertices.foreach_set('co', P.reshape(-1))
    me.update()
    for k, idx in AIDX.items():
        anchors[k].location = tuple(P[idx])
    # act fades
    a_body = 0.0 if i < A1 - 16 else min((i - (A1 - 16)) / 26.0, 1.0)
    a_grid = 0.0 if i < A1 + A2 - 14 else min((i - (A1 + A2 - 14)) / 24.0, 1.0)
    a_anc = 1.0 if i < A1 + A2 else max(1.0 - (i - (A1 + A2)) / 40.0, .35)
    bb = next(n for n in BODY.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bb.inputs['Alpha'].default_value = a_body
    gb = next(n for n in GRID.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    gb.inputs['Alpha'].default_value = a_grid * .9
    ab = next(n for n in ANC.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    ab.inputs['Emission Strength'].default_value = 3.4 * a_anc
    for o in anchors.values():
        o.scale = (a_anc,) * 3
    # slow orbit, easing out
    t = i / max(TOTAL - 1, 1)
    az = math.radians(-52 + 86 * (1 - (1 - t) ** 2))
    r, zc = 4.0, 0.86
    cam.location = (r * math.sin(az), -r * math.cos(az), zc + 0.52)
    tgt.location = (0, 0, zc - 0.06)

bpy.ops.object.camera_add(location=(0, -4.3, 1.3))
cam = bpy.context.object; cam.data.lens = 50; sc.camera = cam
bpy.ops.object.empty_add(location=(0, 0, .95))
tgt = bpy.context.object
c = cam.constraints.new('TRACK_TO'); c.target = tgt
c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'

def light(loc, e, col=(1, 1, 1)):
    bpy.ops.object.light_add(type='AREA', location=loc)
    L = bpy.context.object; L.data.energy = e; L.data.size = 4.0
    L.data.color = col
    L.rotation_euler = (math.radians(58), 0, math.radians(-30))
    return L
light((-2.6, -2.8, 3.2), 420)
light((2.9, -1.4, 2.2), 180, (.78, .86, 1.0))
light((0, 2.8, 2.4), 150, (1.0, .80, .62))

bpy.app.handlers.frame_change_pre.clear()
bpy.app.handlers.frame_change_pre.append(on_frame)

sc.render.filepath = str(OUTDIR / "f_")
bpy.ops.render.render(animation=True)
print("WROTE", TOTAL, "frames to", OUTDIR)
