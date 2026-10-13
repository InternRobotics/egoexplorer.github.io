"""Render the body and hand panels of one session.

  /Applications/Blender.app/Contents/MacOS/Blender -b -P streams_render.py -- session_X

Reads the bake from prep_streams.py and writes two PNG sequences. Both run on
the page's accelerated timeline, so the four streams stay on one playhead. The
body gets a damped follow camera, so locomotion reads as locomotion instead of
the subject sitting still while the room slides; the hands are held in a fixed
presentation frame — palm to the viewer, fingers up — so what moves on screen
is the articulation itself.
"""
import bpy, json, math, sys
import numpy as np
from pathlib import Path

ROOT = Path("/Volumes/NASStorage/Documents/code/.egoexplorer_build/streams")
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ALIAS = args[0]
FA = int(args[1]) if len(args) > 1 else 0
FB = int(args[2]) if len(args) > 2 else None

BW, BH = 984, 684          # body panel, 2x the page canvas
HW, HH = 696, 392          # hand panel, 2x the page canvas

D = ROOT / ALIAS
meta = json.loads((D / "meta.json").read_text())
V = np.load(D / "verts.npy", mmap_mode="r")
HV = np.load(D / "hands.npy", mmap_mode="r")
FACES = np.load(D / "faces.npy")
HFACES = np.load(D / "hfaces.npy")
NF = len(V)
FB = NF if FB is None else min(FB, NF)

BODY_DIR = D / "body"; HAND_DIR = D / "hand"
BODY_DIR.mkdir(exist_ok=True); HAND_DIR.mkdir(exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE_NEXT'
sc.eevee.taa_render_samples = 16
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.compression = 25
sc.view_settings.view_transform = 'Filmic'
sc.view_settings.look = 'Medium High Contrast'
sc.view_settings.exposure = -2.1
sc.world = bpy.data.worlds.new('w'); sc.world.use_nodes = True
next(n for n in sc.world.node_tree.nodes
     if n.type == 'BACKGROUND').inputs[0].default_value = (.020, .024, .031, 1)


def principled(m):
    return next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')


def mat(name, rgba, rough=.5, emit=None, es=1.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = principled(m)
    for k, v in (('Base Color', rgba), ('Roughness', rough)):
        if k in b.inputs:
            b.inputs[k].default_value = v
    if emit:
        b.inputs['Emission Color'].default_value = emit
        b.inputs['Emission Strength'].default_value = es
    return m

SKIN = mat('skin', (.455, .487, .553, 1), rough=.52)
GRID = mat('grid', (.075, .120, .180, 1), emit=(.075, .120, .180, 1), es=1.5)
HSKIN = mat('hskin', (.560, .540, .522, 1), rough=.46)

# ── body ───────────────────────────────────────────────────────────────────
me = bpy.data.meshes.new('body')
me.from_pydata([tuple(p) for p in np.asarray(V[0], np.float64)], [],
               [tuple(t) for t in FACES])
me.update()
body = bpy.data.objects.new('body', me)
bpy.context.collection.objects.link(body)
# one uniform body: shading the trunk as cloth reads as tactile data on the
# torso, and only the hands are instrumented
body.data.materials.append(SKIN)
for p in me.polygons:
    p.use_smooth = True

bpy.ops.mesh.primitive_grid_add(size=26, x_subdivisions=104, y_subdivisions=104)
grid = bpy.context.object
wf = grid.modifiers.new('wf', 'WIREFRAME'); wf.thickness = .007; wf.use_replace = True
grid.data.materials.append(GRID)

bpy.ops.object.camera_add(location=(0, -4, 1.4))
bcam = bpy.context.object; bcam.data.lens = 55
bpy.ops.object.empty_add(location=(0, 0, .9))
btgt = bpy.context.object
c = bcam.constraints.new('TRACK_TO')
c.target = btgt; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'


def light(loc, e, size, col=(1, 1, 1), rot=(58, 0, -30)):
    bpy.ops.object.light_add(type='AREA', location=loc)
    L = bpy.context.object
    L.data.energy = e; L.data.size = size; L.data.color = col
    L.rotation_euler = tuple(math.radians(a) for a in rot)
    return L

BL = [light((-3.0, -3.2, 4.0), 380, 5.0),
      light((3.4, -1.8, 2.6), 150, 5.0, (.78, .86, 1.0), (70, 0, 60)),
      light((0, 3.2, 3.0), 130, 5.0, (1.0, .80, .62), (64, 0, 184))]
BOFF = [(-3.0, -3.2, 4.0), (3.4, -1.8, 2.6), (0, 3.2, 3.0)]

# ── hands, in their own little studio off to one side ──────────────────────
HX = 100.0                      # parked far from the body so one scene serves both
hobjs = []
for si, dx in ((0, -0.105), (1, 0.105)):
    hm = bpy.data.meshes.new(f'hand{si}')
    hm.from_pydata([tuple(p) for p in np.asarray(HV[0, si], np.float64)], [],
                   [tuple(t) for t in HFACES[si]])
    hm.update()
    o = bpy.data.objects.new(f'hand{si}', hm)
    bpy.context.collection.objects.link(o)
    o.location = (HX + dx, 0, 0)
    o.data.materials.append(HSKIN)
    for p in hm.polygons:
        p.use_smooth = True
    # No subdivision here. Measured: a subsurf on a mesh whose vertices change
    # every frame costs 3.4x the render time (16 s -> 53 s per 40 frame-pairs),
    # and the cost is in having the modifier at all, not in its level. This
    # panel shows the hands at 348x196 CSS, where SMPL-X's own tessellation is
    # fine; the pipeline film, which pushes to within 0.6 m of a hand, keeps
    # its level 2.
    hobjs.append((o, hm))

bpy.ops.object.camera_add(location=(HX, -0.40, 0.03),
                          rotation=(math.radians(90), 0, 0))
hcam = bpy.context.object; hcam.data.lens = 46
for loc, e, col, rot in (((-.38, -.36, .42), 3.2, (1, 1, 1), (62, 0, -28)),
                         ((.42, -.22, .26), 2.2, (.78, .86, 1.0), (72, 0, 56)),
                         ((0, .38, .30), 1.9, (1.0, .80, .62), (64, 0, 182))):
    light((HX + loc[0], loc[1], loc[2]), e, .9, col, rot)

# ── framing ────────────────────────────────────────────────────────────────
# The floor is z = 0 by construction (egodata subtracts ground_y_m), so the
# grid belongs there. Height comes from a robust percentile, not the extremes:
# session_A's solve dips 0.69 m through the floor on a few frames, which with
# min/max framing pushed the camera 46% too far back and dropped the grid
# below the feet.
zs = np.concatenate([np.asarray(V[i][::7, 2], np.float32)
                     for i in range(0, len(V), max(len(V) // 150, 1))])
zmin = 0.0
body_h = float(np.percentile(zs, 99.8))
grid.location = (0, 0, 0.002)
sensor_h = 36.0 * BH / BW
vfov = 2 * math.atan((sensor_h / 2) / bcam.data.lens)
bdist = (body_h / 0.74 / 2) / math.tan(vfov / 2)

pelvis = np.asarray(V[:, ::40, :2]).mean(1)
w = max(int(meta["fps"] * 1.4) | 1, 3)
ker = np.ones(w) / w
pad = np.pad(pelvis, ((w // 2, w // 2), (0, 0)), mode='edge')
track = np.stack([np.convolve(pad[:, a], ker, 'valid')[:NF] for a in (0, 1)], 1)

P = np.asarray(HV, np.float64).reshape(-1, 3)
hctr = (P.max(0) + P.min(0)) / 2
hext = P.max(0) - P.min(0)
hhf = 2 * math.atan(18.0 / hcam.data.lens)
hvf = 2 * math.atan((36.0 * HH / HW / 2) / hcam.data.lens)
hdist = max((hext[0] + 0.21) / 0.86 / 2 / math.tan(hhf / 2),
            hext[2] / 0.80 / 2 / math.tan(hvf / 2)) + hext[1] * 0.6
hcam.location = (HX + hctr[0], hctr[1] - hdist, hctr[2])

print(f"{ALIAS}: {FB-FA} frames, body dist {bdist:.2f}, hand dist {hdist:.2f}",
      flush=True)

for i in range(FA, FB):
    me.vertices.foreach_set('co', np.asarray(V[i], np.float32).reshape(-1))
    me.update()
    tx, ty = float(track[i, 0]), float(track[i, 1])
    bcam.location = (tx - bdist * 0.38, ty - bdist, zmin + body_h * 0.56)
    btgt.location = (tx, ty, zmin + body_h * 0.50)
    for L, off in zip(BL, BOFF):
        L.location = (tx + off[0], ty + off[1], zmin + off[2])
    sc.camera = bcam
    sc.render.resolution_x, sc.render.resolution_y = BW, BH
    sc.render.filepath = str(BODY_DIR / f"f_{i:05d}.png")
    bpy.ops.render.render(write_still=True)

    for si, (o, hm) in enumerate(hobjs):
        hm.vertices.foreach_set('co', np.asarray(HV[i, si], np.float32).reshape(-1))
        hm.update()
    sc.camera = hcam
    sc.render.resolution_x, sc.render.resolution_y = HW, HH
    sc.render.filepath = str(HAND_DIR / f"f_{i:05d}.png")
    bpy.ops.render.render(write_still=True)

print("DONE", ALIAS, flush=True)
