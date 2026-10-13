"""The capture section's figure: one continuous move over the wearing study.

  /Applications/Blender.app/Contents/MacOS/Blender -b -P rig_film.py -- [a b]

Geometry comes from camera_tracker_extrinsics/smplx_rig.html by way of
rig_extract.py — the same body, the same HTC tracker CAD, the same HERO13 and
Media Mod on their printed adapter, the same Wuji glove. Nothing is redrawn.
What this adds is a renderer: subdivision on the body, soft studio light, and
a camera that travels whole rig -> head -> wrist -> back, so the section plays
itself instead of waiting to be clicked.

The ankle is deliberately not a stop on the tour: the two devices worth a
close look are the ones that carry the camera and the hands.
"""
import bpy, json, math, sys
from mathutils import Matrix
import numpy as np
from pathlib import Path

HERE = Path(__file__).resolve().parent
GEO = np.load(HERE / "rig_geo.npz", allow_pickle=True)
META = json.loads(str(GEO["meta"]))
VIEWS = json.loads(str(GEO["views"]))
OUT = HERE / "rig_frames"
OUT.mkdir(exist_ok=True)

W, H, FPS = 900, 1125, 60
SECONDS = 15.0
NF = int(SECONDS * FPS)
SKIP = {"skeleton", "markers", "ground"}        # debug overlays, not hardware

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
FA = int(args[0]) if len(args) > 0 else 0
FB = int(args[1]) if len(args) > 1 else NF

# the asset is Y-up with +Z facing; Blender wants Z-up
Y2Z = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], dtype=np.float64)
conv = lambda p: np.asarray(p, np.float64) @ Y2Z.T

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE_NEXT'
sc.eevee.taa_render_samples = 32
for flag in ("use_shadows", "use_raytracing"):
    if hasattr(sc.eevee, flag):
        setattr(sc.eevee, flag, True)
sc.render.resolution_x, sc.render.resolution_y = W, H
sc.render.fps = FPS
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.compression = 25
sc.view_settings.view_transform = 'Standard'
sc.view_settings.exposure = -1.05
sc.world = bpy.data.worlds.new('w'); sc.world.use_nodes = True
next(n for n in sc.world.node_tree.nodes
     if n.type == 'BACKGROUND').inputs[0].default_value = (.80, .825, .855, 1)

MATS = {}
def material(rgb, metal, rough):
    key = (tuple(np.round(rgb, 3)), metal, rough)
    if key in MATS:
        return MATS[key]
    m = bpy.data.materials.new('m%d' % len(MATS)); m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    b.inputs['Base Color'].default_value = (*rgb, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    MATS[key] = m
    return m

# the devices are matte-ish plastic, not chrome: high metallic blew the
# tracker out to white against a light background, which read as a flat plate
FINISH = {                       # group -> (metallic, roughness)
    "body": (0.0, 0.54), "camera": (0.12, 0.42), "media": (0.10, 0.46),
    "adapter": (0.0, 0.62), "strap": (0.0, 0.86), "glove": (0.0, 0.80),
    "tracker_head": (0.10, 0.44),
}

body_obj = None
for m in META:
    if m["group"] in SKIP:
        continue
    k = m["i"]
    v = conv(GEO[f"v{k}"])
    f = GEO[f"f{k}"].astype(np.int32)
    me = bpy.data.meshes.new(m["name"])
    me.from_pydata([tuple(p) for p in v], [], [tuple(t) for t in f])
    me.update()
    for poly in me.polygons:
        poly.use_smooth = True
    mat = material(m["color"] or [.6, .6, .6], *FINISH.get(m["group"], (0.0, .55)))
    me.materials.append(mat)
    if m["ninst"]:
        R = GEO[f"m{k}"]; T = GEO[f"o{k}"]
        for a in range(m["ninst"]):
            o = bpy.data.objects.new(f'{m["name"]}_{a}', me)
            bpy.context.collection.objects.link(o)
            # the page stores the rotation transposed, in the Y-up frame
            Rm = np.array(R[a], np.float64).reshape(3, 3).T
            Rz = Y2Z @ Rm @ Y2Z.T
            M = np.eye(4); M[:3, :3] = Rz; M[:3, 3] = conv(T[a])
            # must be plain floats: assigning matrix_world from a nested list
            # of numpy scalars silently drops the translation column
            o.matrix_world = Matrix([[float(x) for x in r] for r in M])
    else:
        o = bpy.data.objects.new(m["name"], me)
        bpy.context.collection.objects.link(o)
    if m["group"] == "body":
        body_obj = o

# the figure is what the camera gets closest to, and SMPL-X is coarse up close
if body_obj is not None:
    sub = body_obj.modifiers.new('subsurf', 'SUBSURF')
    sub.subdivision_type = 'CATMULL_CLARK'
    sub.levels = 0
    sub.render_levels = 2

# a soft floor so the figure is not floating, as a shadow catcher only
bpy.ops.mesh.primitive_plane_add(size=14, location=(0, 0, 0))
floor = bpy.context.object
floor.is_shadow_catcher = True
floor.data.materials.append(material((.93, .945, .96), 0.0, .95))

def light(loc, energy, size, col=(1, 1, 1)):
    bpy.ops.object.light_add(type='AREA', location=loc)
    L = bpy.context.object
    L.data.energy = energy; L.data.size = size; L.data.color = col
    d = -np.array(loc, np.float64); d /= np.linalg.norm(d)
    L.rotation_euler = (math.acos(-d[2]), 0, math.atan2(-d[0], d[1]))
    return L

light((-1.9, -2.4, 2.8), 190, 3.4)
light((2.3, -1.5, 1.7), 85, 3.0, (.90, .94, 1.0))
light((0.2, 2.6, 2.2), 70, 3.0, (1.0, .95, .90))

bpy.ops.object.camera_add(location=(0, -3, 1))
cam = bpy.context.object; sc.camera = cam
bpy.ops.object.empty_add(location=(0, 0, 1))
tgt = bpy.context.object
c = cam.constraints.new('TRACK_TO')
c.target = tgt; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'

AT_BODY = conv([0.0, 0.95, 0.0])
AT_HEAD = conv(VIEWS["head"][3:])
# the wrist tracker sits a little above and behind the wrist joint the
# viewer aims at; nudge so the device, not the knuckles, is the subject
AT_HAND = conv(VIEWS["handR"][3:]) + np.array([0.012, 0.0, 0.028])

# t, aim, yaw(deg from the front), pitch(deg), distance, lens
KEYS = [
    (0.0,  AT_BODY,  30, 10, 3.45, 42),   # the whole rig
    (3.2,  AT_BODY,  12,  8, 3.25, 42),
    (5.4,  AT_HEAD,   8,  4, 0.62, 52),   # in to the camera on the head
    (8.0,  AT_HEAD, -16,  6, 0.56, 52),
    (10.0, AT_HAND, -34, 20, 0.36, 50),   # across to the glove and its tracker
    (12.4, AT_HAND,  -6, 13, 0.32, 50),
    (15.0, AT_BODY,  30, 10, 3.45, 42),   # back where it started, so it loops
]


def smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def at(t):
    for a, b in zip(KEYS, KEYS[1:]):
        if t <= b[0]:
            u = smooth((t - a[0]) / (b[0] - a[0]))
            aim = a[1] * (1 - u) + b[1] * u
            yaw, pit, dist, lens = [x + (y - x) * u
                                    for x, y in zip(a[2:], b[2:])]
            return aim, yaw, pit, dist, lens
    return KEYS[-1][1], *KEYS[-1][2:]


def on_frame(scene, _=None):
    i = min(max(scene.frame_current - 1, 0), NF - 1)
    aim, yaw, pit, dist, lens = at(i / FPS)
    az, el = math.radians(yaw), math.radians(pit)
    cam.location = (aim[0] + dist * math.sin(az) * math.cos(el),
                    aim[1] - dist * math.cos(az) * math.cos(el),
                    aim[2] + dist * math.sin(el))
    tgt.location = tuple(aim)
    cam.data.lens = lens


bpy.app.handlers.frame_change_pre.clear()
bpy.app.handlers.frame_change_pre.append(on_frame)
sc.frame_start, sc.frame_end = FA + 1, FB
sc.render.filepath = str(OUT / "f_")
print(f"rendering {FA+1}..{FB} of {NF} at {W}x{H}", flush=True)
bpy.ops.render.render(animation=True)
print("DONE")
