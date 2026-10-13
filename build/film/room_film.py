"""The pipeline film's picture: a real session replayed inside a mocked room.

  /Applications/Blender.app/Contents/MacOS/Blender -b -P room_film.py -- [a b]

Everything here is measured except the room. The body is SMPL-X solved from the
session (30 Hz, upsampled to 60), the five gizmos sit on the actual tracker
poses with a trail of where each has been, and the heat on the hands is the
Wuji glove's own per-region pressure. The kitchen is a stand-in, built to fit
the motion: its two work surfaces are placed where the hands actually dwell, so
the reaching reads correctly even though the geometry is invented.

Dial the room's presence with SCENE_LEVEL (0 = black void, 1 = fully lit); the
body and the measurements do not change with it.
"""
import bpy, json, math, sys
import numpy as np
from pathlib import Path
from mathutils import Vector

HERE = Path(__file__).resolve().parent
BAKE = HERE / "bake"
OUT = HERE / "frames"

# ── the dials ──────────────────────────────────────────────────────────────
SCENE_LEVEL = 0.70        # how present the mocked room is, 0..1
SCENE_EDGES = 0.70        # the thin accent lines on the room volumes, 0..1
SCENE_EXPOSURE = -1.00    # overall stop; the page is dark, the film matches it
TRAIL_SEC   = 1.35        # how much history each tracker carries
TOUCH_GAIN  = 1.0         # brightness of the measured pressure on the hands
RES_SCALE   = 1.0

W, H, FPS = 1920, 1080, 60
SKIN = (0.520, 0.545, 0.600, 1)
WARM = (0.886, 0.408, 0.133, 1)      # manipulation
COOL = (0.357, 0.545, 0.816, 1)      # locomotion
PALE = (0.86, 0.89, 0.95, 1)         # vision

meta = json.loads((BAKE / "meta.json").read_text())
VERT = np.load(BAKE / "verts.npy", mmap_mode="r")
FACE = np.load(BAKE / "faces.npy")
TRK  = np.load(BAKE / "track.npy")
PALM = np.load(BAKE / "palm.npy")   # (NF,2,3) right-hand centre and palm normal
FACING = np.load(BAKE / "facing.npy")  # (NF,) bearing the subject faces, rad
TOUCH = np.load(BAKE / "touch.npy", mmap_mode="r")
NF = len(VERT)
ROLES = meta["roles"]
ROLE_COL = {"camera": PALE, "left_wrist": WARM, "right_wrist": WARM,
            "left_ankle": COOL, "right_ankle": COOL}

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
FA = int(args[0]) if len(args) > 0 else 0
FB = int(args[1]) if len(args) > 1 else NF


# ── acts ───────────────────────────────────────────────────────────────────
# t, yaw(deg, 0 = looking along -y), pitch(deg), distance, lens, aim, aim-height
# yaw is relative to the direction the subject faces: 0 is straight in front of
# them, 90 is directly to their right, 180 is behind. Working at a counter
# leaves no room in front, so the film holds a three-quarter follow and only
# goes frontal for the hands, where the palm normal drives the camera anyway.
KEYS = [
    (0.0,  132, 16, 5.4, 30, "pelvis", 1.00),  # the room, and five dots in it
    (5.4,  126, 14, 4.8, 32, "pelvis", 1.00),
    (11.6, 112, 12, 4.2, 36, "pelvis", 1.02),  # the body, whole
    (14.9,  98, 11, 3.6, 38, "pelvis", 1.00),
    # a profile is the shot for both of these: it is the reach across the body
    # that layer 2 is about, and the lean over the feet that layer 3 is about
    (15.4,  88,  9, 2.5, 42, "arms", 1.16),
    (17.6,  84,  8, 2.4, 42, "arms", 1.14),
    (18.1,  92,  9, 2.8, 40, "feet", 0.42),
    (20.4,  96, 11, 2.7, 40, "feet", 0.46),
    (22.6, 100, 14, 0.74, 46, "hands", 0.02),  # into the hands
    (27.0, 100,  9, 0.56, 48, "hands", 0.01),
]
BODY_IN = (4.3, 5.7)          # the body fades in across these seconds
TOUCH_IN = (20.6, 22.2)       # the measured pressure comes up here
RIG_OUT = (21.2, 23.0)        # the gizmos dim so the hands carry the close-up

# anything the camera must not end up inside
FURNITURE = [(-2.58, 1.40, 2.40, 3.12, 0.00, 0.78),
             (-2.55, 0.35, 2.62, 3.05, 1.55, 2.18),
             (1.42, 1.98, 2.42, 3.05, 0.00, 1.62),
             (-0.08, 1.48, -1.58, -0.70, 0.00, 0.845),
             (1.62, 2.00, -0.96, -0.58, 0.00, 0.62),
             # the two walls, widened past the set so the camera can never end
             # up outside the room looking at the back of one
             (-9.0, 9.0, 3.04, 4.00, 0.00, 3.40),
             (-3.10, -2.56, -9.0, 3.12, 0.00, 3.40)]


def inside_any(p, pad=0.30):
    return any(x0 - pad < p[0] < x1 + pad and y0 - pad < p[1] < y1 + pad
               and z0 - pad < p[2] < z1 + pad
               for x0, x1, y0, y1, z0, z1 in FURNITURE)


def seg_blocked(p, q, pad=0.04):
    """Does the segment p->q pass through any furniture? (slab method)"""
    d = q - p
    for x0, x1, y0, y1, z0, z1 in FURNITURE:
        lo = np.array([x0 - pad, y0 - pad, z0 - pad])
        hi = np.array([x1 + pad, y1 + pad, z1 + pad])
        t0, t1 = 0.0, 1.0
        ok = True
        for k in range(3):
            if abs(d[k]) < 1e-9:
                if not (lo[k] <= p[k] <= hi[k]):
                    ok = False
                    break
                continue
            a = (lo[k] - p[k]) / d[k]
            b = (hi[k] - p[k]) / d[k]
            if a > b:
                a, b = b, a
            t0, t1 = max(t0, a), min(t1, b)
            if t0 > t1:
                ok = False
                break
        if ok:
            return True
    return False


def place(look, bearing, yaw, pitch, dist):
    """Put the camera where the subject is actually visible.

    A kitchen gives the camera almost nowhere to stand: work happens facing a
    wall of cabinets, and the ideal three-quarter angle regularly lands inside
    the fridge. Rather than hand-tuning angles per act, search outward from the
    intended shot for the nearest one that is neither inside furniture nor
    looking through it.
    """
    def at(y, pi, ds):
        az, el = math.pi - bearing - math.radians(y), math.radians(pi)
        return np.array([look[0] + ds * math.sin(az) * math.cos(el),
                         look[1] - ds * math.cos(az) * math.cos(el),
                         max(look[2] + ds * math.sin(el), 0.34)])
    best = at(yaw, pitch, dist)
    for dy in (0, 10, -10, 20, -20, 32, -32, 46, -46, 62, -62, 80, -80, 100, -100,
               124, -124, 150, -150, 180):
        # try backing off or stepping sideways before craning upward: a high
        # camera reads as a security feed
        for ds in (1.0, 1.12, 0.9, 1.26, 1.45):
            for dp in (0, 5, 11, 20):
                c = at(yaw + dy, pitch + dp, dist * ds)
                if c[2] > 2.45:
                    continue
                if not inside_any(c) and not seg_blocked(c, look):
                    return c
    return best


def smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def lerp_keys(t):
    ks = KEYS
    if t <= ks[0][0]:
        return ks[0][1:]
    for a, b in zip(ks, ks[1:]):
        if t <= b[0]:
            u = smooth((t - a[0]) / (b[0] - a[0]))
            out = [x + (y - x) * u for x, y in zip(a[1:5], b[1:5])]
            aim = b[5] if u > 0.5 else a[5]
            if a[5] != b[5]:
                out.append(("blend", a[5], b[5], u))
            else:
                out.append(aim)
            out.append(a[6] + (b[6] - a[6]) * u)
            return out
    return ks[-1][1:]


def hand_blend(t):
    """How much the camera is flying the palm rather than the orbit."""
    return smooth((t - 21.4) / 1.6)


def aim_point(i, kind):
    T = TRK[i]
    if isinstance(kind, tuple):                 # blending between two aims
        _, A, B, u = kind
        return aim_point(i, A) * (1 - u) + aim_point(i, B) * u
    if kind == "hands":
        return (T[1] + T[2]) / 2
    if kind == "arms":                      # the layer that is about the arms
        return np.array([(T[1] + T[2])[0] / 2, (T[1] + T[2])[1] / 2, 0.0])
    if kind == "feet":                      # the layer that is about the floor
        return np.array([T[3:, 0].mean(), T[3:, 1].mean(), 0.0])
    return np.array([T[3:, 0].mean(), T[3:, 1].mean(), 0.0])


# ── scene ──────────────────────────────────────────────────────────────────
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE_NEXT'
sc.eevee.taa_render_samples = 24
for flag in ("use_shadows", "use_raytracing"):
    if hasattr(sc.eevee, flag):
        setattr(sc.eevee, flag, True)
sc.render.resolution_x = int(W * RES_SCALE)
sc.render.resolution_y = int(H * RES_SCALE)
sc.render.fps = FPS
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.compression = 20
sc.view_settings.view_transform = 'Filmic'
sc.view_settings.look = 'Medium High Contrast'
sc.view_settings.exposure = SCENE_EXPOSURE
sc.world = bpy.data.worlds.new('w'); sc.world.use_nodes = True
next(n for n in sc.world.node_tree.nodes
     if n.type == 'BACKGROUND').inputs[0].default_value = (.013, .015, .020, 1)


def principled(m):
    return next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')


def mat(name, rgba, rough=.6, metal=.0, emit=None, es=1.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = principled(m)
    def s(k, v):
        if k in b.inputs:
            b.inputs[k].default_value = v
    s('Base Color', rgba); s('Roughness', rough); s('Metallic', metal)
    if emit:
        s('Emission Color', emit); s('Emission Strength', es)
    return m


L = SCENE_LEVEL
def room_rgb(v):
    """Room albedo, scaled by the dial but never to pure black."""
    return tuple([c * (0.10 + 0.90 * L) for c in v[:3]] + [1.0])

WALL  = mat('wall',  room_rgb((.150, .157, .172)), rough=.92)
FLOOR = mat('floor', room_rgb((.092, .097, .108)), rough=.55)
CAB   = mat('cab',   room_rgb((.112, .122, .140)), rough=.70)
TOP   = mat('top',   room_rgb((.170, .178, .194)), rough=.38)
METAL = mat('metal', room_rgb((.205, .216, .236)), rough=.28, metal=.75)
PROP  = mat('prop',  room_rgb((.196, .172, .146)), rough=.72)
EDGE  = mat('edge',  (0, 0, 0, 1),
            emit=(.44 * SCENE_EDGES * (.3 + .7 * L),
                  .50 * SCENE_EDGES * (.3 + .7 * L),
                  .62 * SCENE_EDGES * (.3 + .7 * L), 1), es=1.0)


def box(name, x0, x1, y0, y1, z0, z1, m, edges=True):
    bpy.ops.mesh.primitive_cube_add(size=1)
    o = bpy.context.object; o.name = name
    o.scale = ((x1 - x0) / 2, (y1 - y0) / 2, (z1 - z0) / 2)
    o.location = ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
    bpy.ops.object.transform_apply(scale=True)
    o.data.materials.append(m)
    if edges and SCENE_EDGES > 0:
        e = o.copy(); e.data = o.data.copy(); e.name = name + "_e"
        bpy.context.collection.objects.link(e)
        e.data.materials.clear(); e.data.materials.append(EDGE)
        wf = e.modifiers.new('wf', 'WIREFRAME')
        wf.thickness = .006; wf.use_replace = True
    return o


# shell: only the two walls the camera never crosses
box('floor', -9.0, 9.0, -9.0, 3.1, -0.04, 0.0, FLOOR, edges=False)
box('wall_back', -2.6, 2.6, 3.06, 3.12, 0, 2.55, WALL, edges=False)
box('wall_left', -2.66, -2.60, -9.0, 3.12, 0, 2.55, WALL, edges=False)

# Every surface below is placed from the body's own occupancy, so the figure
# can come right up to the furniture but never passes through it. Measured
# over the whole clip: with its front face at y = 2.40 the body never drops
# below z = 0.788 over the counter run, and with its back face at y = -0.70
# it never drops below z = 0.854 over the island. The tops sit just under
# those ceilings.
box('base',        -2.55, 1.35,  2.40, 3.05, 0,     0.745, CAB)
box('worktop',     -2.58, 1.40,  2.40, 3.06, 0.745, 0.780, TOP)
box('upper',       -2.55, 0.35,  2.62, 3.05, 1.55,  2.18,  CAB)
box('tall',         1.42, 1.98,  2.42, 3.05, 0,     1.62,  CAB)
box('island',      -0.05, 1.45, -1.55, -0.70, 0,    0.810, CAB)
box('island_top',  -0.08, 1.48, -1.58, -0.70, 0.810, 0.845, TOP)
# props live where the hands never dwell (counter x -0.59..0.80, island
# x 0.13..0.85), so they can stand proud of the surface without being clipped
box('box_a',       -2.30, -1.94, 2.52, 2.88, 0.780, 1.06, PROP)
box('box_b',       -1.86, -1.62, 2.58, 2.84, 0.780, 0.98, CAB)
box('jar',         -1.44, -1.22, 2.60, 2.82, 0.780, 1.00, PROP)
box('tray',         0.95,  1.33, 2.46, 2.92, 0.780, 0.83, METAL)
box('board2',       0.98,  1.42, -1.45, -0.80, 0.845, 0.875, PROP)
box('stool',        1.62, 2.00, -0.96, -0.58, 0,     0.62,  METAL)
for i, x in enumerate(np.arange(-2.3, 0.3, 0.52)):      # cabinet door reveals
    box(f'door{i}', x, x + 0.46, 2.38, 2.40, 0.08, 0.68, CAB, edges=False)


def light(name, loc, energy, size, col=(1, 1, 1), rot=(0, 0, 0), kind='AREA'):
    bpy.ops.object.light_add(type=kind, location=loc)
    o = bpy.context.object; o.name = name
    o.data.energy = energy * (0.22 + 0.78 * L)
    o.data.color = col
    if kind == 'AREA':
        o.data.size = size
    o.rotation_euler = tuple(math.radians(a) for a in rot)
    return o

light('key',   (2.4, -1.4, 2.9), 300, 3.2, (1.0, .95, .88), (36, 0, 28))
light('fill',  (-1.6, -0.4, 2.4), 110, 3.6, (.78, .85, 1.0), (28, 0, -34))
light('under', (-0.6, 2.35, 1.46), 22, 1.4, (1.0, .86, .68), (90, 0, 0))
light('pend',  (0.6, -0.95, 1.74), 26, 0.5, (1.0, .88, .72), (0, 0, 0))
box('pend_shade', 0.44, 0.76, -1.11, -0.79, 1.74, 1.86, METAL)
# a practical the camera can see, so the room has a light source in shot
bpy.ops.mesh.primitive_cylinder_add(radius=.012, depth=.9,
                                    location=(0.6, -0.95, 2.26))
bpy.context.object.data.materials.append(METAL)


# ── the body ───────────────────────────────────────────────────────────────
BODY = bpy.data.materials.new('body'); BODY.use_nodes = True
nt = BODY.node_tree
bp = principled(BODY)
BODY.blend_method = 'BLEND'
if hasattr(BODY, 'show_transparent_back'):
    BODY.show_transparent_back = False
bp.inputs['Base Color'].default_value = SKIN
bp.inputs['Roughness'].default_value = .52
if 'Subsurface Weight' in bp.inputs:
    bp.inputs['Subsurface Weight'].default_value = .08
# One uniform body. An earlier cut shaded the trunk and thighs as cloth to
# avoid a bare mannequin, but soft-edged patches on a figure whose hands carry
# a heat map read as tactile data on the torso — exactly the wrong reading,
# since only the hands are instrumented.
attr = nt.nodes.new('ShaderNodeAttribute'); attr.attribute_name = 'touch'
attr.location = (-900, -200)
ramp = nt.nodes.new('ShaderNodeValToRGB'); ramp.location = (-700, -200)
ramp.color_ramp.elements[0].position = 0.02
ramp.color_ramp.elements[0].color = (.06, .10, .18, 1)
ramp.color_ramp.elements[1].position = 1.0
ramp.color_ramp.elements[1].color = (1.0, .97, .88, 1)
for p, c in ((0.16, (.24, .34, .62, 1)), (0.40, (.86, .26, .05, 1)),
             (0.72, (1.0, .62, .12, 1))):
    e = ramp.color_ramp.elements.new(p); e.color = c
mixv = nt.nodes.new('ShaderNodeMath'); mixv.operation = 'MULTIPLY'
mixv.location = (-700, -420); mixv.inputs[1].default_value = 0.0   # TOUCH gate
pw = nt.nodes.new('ShaderNodeMath'); pw.operation = 'POWER'
pw.location = (-520, -420); pw.inputs[1].default_value = 1.05
gain = nt.nodes.new('ShaderNodeMath'); gain.operation = 'MULTIPLY'
gain.location = (-340, -420); gain.inputs[1].default_value = 9.0 * TOUCH_GAIN
# the bake normalises each side by its 99th percentile, which leaves most of
# the signal in the bottom of the ramp; lift it so the mid pressures are
# visible and the frame-to-frame change reads
lift = nt.nodes.new('ShaderNodeMath'); lift.operation = 'MULTIPLY'
lift.use_clamp = True; lift.inputs[1].default_value = 1.45
lift.location = (-880, -340)
nt.links.new(attr.outputs['Fac'], lift.inputs[0])
nt.links.new(lift.outputs[0], ramp.inputs['Fac'])
nt.links.new(lift.outputs[0], mixv.inputs[0])
nt.links.new(mixv.outputs[0], pw.inputs[0])
nt.links.new(pw.outputs[0], gain.inputs[0])
nt.links.new(ramp.outputs['Color'], bp.inputs['Emission Color'])
nt.links.new(gain.outputs[0], bp.inputs['Emission Strength'])
TOUCH_GATE = mixv.inputs[1]

me = bpy.data.meshes.new('body')
me.from_pydata([tuple(p) for p in np.asarray(VERT[0], np.float64)], [],
               [tuple(t) for t in FACE])
me.update()
body = bpy.data.objects.new('body', me)
bpy.context.collection.objects.link(body)
body.data.materials.append(BODY)
for p in me.polygons:
    p.use_smooth = True
# the film pushes to within 0.6 m of a hand, where SMPL-X's own tessellation
# is visibly faceted
_sub = body.modifiers.new('subsurf', 'SUBSURF')
_sub.subdivision_type = 'CATMULL_CLARK'
_sub.levels = 0
_sub.render_levels = 2
CA = me.color_attributes.new(name='touch', type='FLOAT_COLOR', domain='POINT')
NV = len(me.vertices)
body.hide_render = True         # faded in during act 1


# ── trackers and their trails ──────────────────────────────────────────────
TRAIL_N = int(TRAIL_SEC * FPS)
gizmos, trails, rig_mats = [], [], []
for k, role in enumerate(ROLES):
    col = ROLE_COL.get(role, WARM)
    m = mat('g_' + role, (0, 0, 0, 1), emit=col, es=9.0)
    rig_mats.append((principled(m), 9.0))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=.019, segments=20, ring_count=11)
    o = bpy.context.object; o.name = 'g_' + role
    o.data.materials.append(m); bpy.ops.object.shade_smooth()
    gizmos.append(o)

    cu = bpy.data.curves.new('t_' + role, 'CURVE')
    cu.dimensions = '3D'; cu.bevel_resolution = 2
    # the head trail is the quietest of the three: it reads as where the camera
    # has been, not as a gesture
    cu.bevel_depth = .0052 if role == 'camera' else .0090
    cu.use_fill_caps = True
    sp = cu.splines.new('POLY'); sp.points.add(TRAIL_N - 1)
    tes = 2.0 if role == 'camera' else 4.0
    tm = mat('tm_' + role, (0, 0, 0, 1), emit=col, es=tes)
    rig_mats.append((principled(tm), tes))
    cu.materials.append(tm)
    to = bpy.data.objects.new('t_' + role, cu)
    bpy.context.collection.objects.link(to)
    trails.append(sp)

RAD = (np.linspace(0, 1, TRAIL_N) ** 2.1).astype(np.float64)


# ── camera ─────────────────────────────────────────────────────────────────
bpy.ops.object.camera_add(location=(0, -4, 1.4))
cam = bpy.context.object; sc.camera = cam
bpy.ops.object.empty_add(location=(0, 0, 1))
tgt = bpy.context.object
c = cam.constraints.new('TRACK_TO')
c.target = tgt; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'


def on_frame(scene, _=None):
    i = min(max(scene.frame_current - 1, 0), NF - 1)
    t = i / FPS

    me.vertices.foreach_set('co', np.asarray(VERT[i], np.float32).reshape(-1))
    me.update()
    # fade in, never scale in: scaling about the world origin made the body
    # look like it flew in from across the room
    g = smooth((t - BODY_IN[0]) / (BODY_IN[1] - BODY_IN[0]))
    bp.inputs['Alpha'].default_value = g
    body.hide_render = g <= 0.002

    tv = np.asarray(TOUCH[i], np.float32)
    col = np.empty((NV, 4), np.float32)
    col[:, 0] = col[:, 1] = col[:, 2] = tv
    col[:, 3] = 1.0
    CA.data.foreach_set('color', col.reshape(-1))
    TOUCH_GATE.default_value = smooth((t - TOUCH_IN[0]) /
                                      (TOUCH_IN[1] - TOUCH_IN[0]))

    lo = max(i - TRAIL_N + 1, 0)
    hist = TRK[lo:i + 1]                                   # (n,5,3)
    n = len(hist)
    for k, (o, sp) in enumerate(zip(gizmos, trails)):
        o.location = tuple(TRK[i, k])
        pts = np.empty((TRAIL_N, 4), np.float64)
        pts[TRAIL_N - n:, :3] = hist[:, k]
        pts[:TRAIL_N - n, :3] = hist[0, k]
        pts[:, 3] = 1.0
        sp.points.foreach_set('co', pts.reshape(-1))
        r = RAD.copy()
        r[:TRAIL_N - n] = 0.0
        sp.points.foreach_set('radius', r)

    # the rig dims out as the hands take over
    rig = 1.0 - smooth((t - RIG_OUT[0]) / (RIG_OUT[1] - RIG_OUT[0])) * 0.86
    for o in gizmos:
        o.scale = (rig,) * 3
    for m in rig_mats:
        m[0].inputs['Emission Strength'].default_value = m[1] * rig

    hb = hand_blend(t)
    cam.location = tuple(CAMPOS[i])
    tgt.location = tuple(LOOKAT[i])
    cam.data.lens = float(LENS[i])
    # the typography lives in the left third, so the subject is composed right
    cam.data.shift_x = -0.155 + 0.055 * hb
    # close to the skin the key light would blow out; ride the stop down
    scene.view_settings.exposure = SCENE_EXPOSURE - 1.34 * hb


def solve_camera():
    pos = np.empty((NF, 3)); look = np.empty((NF, 3)); lens = np.empty(NF)
    for i in range(NF):
        t = i / FPS
        yaw, pitch, dist, ln, aim, hgt = lerp_keys(t)
        a = aim_point(i, aim)
        L = np.array([a[0], a[1], a[2] + hgt])
        P = place(L, float(FACING[i]), yaw, pitch, dist)
        hb = hand_blend(t)
        if hb > 0:
            c, n = PALM[i]
            nh = n[:2] / (np.linalg.norm(n[:2]) + 1e-9)
            el2 = math.radians(29)
            d3 = np.array([nh[0] * math.cos(el2), nh[1] * math.cos(el2),
                           math.sin(el2)])
            hp = c + d3 * dist
            hp[2] = max(hp[2], 0.95)         # never below the worktop
            P = P * (1 - hb) + hp * hb
            L = L * (1 - hb) + np.asarray(c, np.float64) * hb
        pos[i], look[i], lens[i] = P, L, ln
    # the search can snap between candidate angles; glide instead
    w = int(FPS * 0.55) | 1
    k = np.ones(w) / w
    sm = lambda A: np.stack([np.convolve(
        np.pad(A[:, j], w // 2, mode='edge'), k, 'valid')[:NF] for j in range(3)], 1)
    return sm(pos), sm(look), lens


print("solving camera track…", flush=True)
CAMPOS, LOOKAT, LENS = solve_camera()
print("  camera z %.2f..%.2f" % (CAMPOS[:, 2].min(), CAMPOS[:, 2].max()), flush=True)

bpy.app.handlers.frame_change_pre.clear()
bpy.app.handlers.frame_change_pre.append(on_frame)

OUT.mkdir(exist_ok=True)
sc.frame_start, sc.frame_end = FA + 1, FB
sc.render.filepath = str(OUT / "f_")
print(f"rendering {FA+1}..{FB} of {NF} at {W}x{H} {FPS}fps", flush=True)
bpy.ops.render.render(animation=True)
print("DONE")
