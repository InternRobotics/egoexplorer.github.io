"""Render a MANO hand stream per session, driven by the glove keypoints.

  /Applications/Blender.app/Contents/MacOS/Blender -b -P hand_streams.py [session_X ...]

Replaces the stick skeleton in panel C. The MANO right hand from
fivetrackerlocal/tmp/hand_tactile_figure/mano_pinch.npz (778 v, 1538 f, LBS
weights over 16 joints) is posed from the glove's 21 MediaPipe-style keypoints:

  * the wrist frame comes from a Kabsch fit on the palm (wrist + four MCPs)
  * each finger bone gets the minimal (swing-only) rotation carrying its rest
    direction onto the measured one, composed down the chain
  * the mesh keeps MANO's own bone lengths — only rotation comes from the glove

Twist about a bone is unobservable from three points, so it is left at zero.
The left hand is solved by mirroring in X and mirroring the result back.
"""
import bpy, csv, gzip, math, sys
import numpy as np
from pathlib import Path

np.seterr(all="ignore")   # numpy 2 + macOS Accelerate: spurious matmul warnings

SP = Path("/Volumes/NASStorage/Downloads/session_package")
MANO = Path("/Volumes/NASStorage/Documents/code/fivetrackerlocal/tmp/"
            "hand_tactile_figure/mano_pinch.npz")
OUT = Path(__file__).resolve().parent / "hand_streams"
OUT.mkdir(exist_ok=True)

FPS, W, H = 12.5, 696, 392
HEAD = {"session_F": 14.0}
SPEED, KEEP, GLOVE_HZ = 5.0, 0.98, 10.0

M = np.load(MANO)
REST_V = M["rest_vertices"].astype(np.float64)     # (778,3)
REST_J = M["rest_joints"].astype(np.float64)       # (16,3)
Wgt = M["lbs_weights"].astype(np.float64)          # (778,16)
FACES = M["faces"].astype(np.int32)
NAMES = [str(x) for x in M["joint_names"]]

PARENT = [-1, 0, 1, 2, 0, 4, 5, 0, 7, 8, 0, 10, 11, 0, 13, 14]
# MANO joint -> glove keypoint (MediaPipe: 0 wrist, 1-4 thumb, 5-8 index,
# 9-12 middle, 13-16 ring, 17-20 pinky); CHILD is the next point along the bone
GMAP  = {0: 0, 1: 5, 2: 6, 3: 7, 4: 9, 5: 10, 6: 11,
         7: 17, 8: 18, 9: 19, 10: 13, 11: 14, 12: 15, 13: 1, 14: 2, 15: 3}
GCHILD = {1: 6, 2: 7, 3: 8, 4: 10, 5: 11, 6: 12, 7: 18, 8: 19, 9: 20,
          10: 14, 11: 15, 12: 16, 13: 2, 14: 3, 15: 4}
PALM = [0, 5, 9, 13, 17]                 # wrist + the four MCPs
PALM_MANO = [0, 1, 4, 10, 7]             # wrist, index1, middle1, ring1, pinky1

def kabsch(P, Q):
    """Rotation taking P onto Q (both centred)."""
    Pc, Qc = P - P.mean(0), Q - Q.mean(0)
    U, _, Vt = np.linalg.svd(Pc.T @ Qc)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    return Vt.T @ np.diag([1, 1, d]) @ U.T

def align(a, b):
    """Minimal rotation carrying unit vector a onto unit vector b."""
    v = np.cross(a, b); c = float(np.dot(a, b))
    if c < -0.999999:
        axis = np.cross(a, [1.0, 0, 0])
        if np.linalg.norm(axis) < 1e-6:
            axis = np.cross(a, [0, 1.0, 0])
        axis /= np.linalg.norm(axis)
        K = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
        return np.eye(3) + 2 * K @ K
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K / (1 + c)

def presentation():
    """Rotation putting the MANO rest hand palm-to-camera, fingers up.

    Camera sits at -Y looking toward +Y, so 'palm out' means the palm normal
    maps to -Y and the finger axis to +Z.
    """
    wrist = REST_J[0]
    tips = REST_J[[3, 6, 9, 12]]
    f = tips.mean(0) - wrist; f /= np.linalg.norm(f)
    P = np.vstack([wrist, REST_J[[1, 4, 7, 10]]]); P = P - P.mean(0)
    n = np.linalg.svd(P)[2][2]; n /= np.linalg.norm(n)
    if np.dot(n, REST_V.mean(0) - wrist) > 0:
        n = -n
    n = n - np.dot(n, f) * f; n /= np.linalg.norm(n)   # orthonormalise
    E = np.stack([f, n, np.cross(f, n)], 1)            # source basis (columns)
    T = np.stack([[0, 0, 1.0], [0, -1.0, 0], [1.0, 0, 0]], 1)
    return T @ E.T

PRESENT = presentation()

def pose(gl):
    """gl: (21,3) right-handed glove keypoints -> (vertices, wrist rotation)."""
    Rg = [np.eye(3)] * 16
    Rg[0] = kabsch(REST_J[PALM_MANO] - REST_J[0], gl[PALM] - gl[0])
    for j in range(1, 16):
        p = PARENT[j]
        rest_dir = REST_J[j] - REST_J[p] if p > 0 else REST_J[j] - REST_J[0]
        cj = GCHILD.get(j)
        obs = gl[cj] - gl[GMAP[j]] if cj is not None else None
        rest_child = None
        for k in range(16):
            if PARENT[k] == j:
                rest_child = REST_J[k] - REST_J[j]
        if rest_child is None or obs is None or np.linalg.norm(obs) < 1e-6:
            Rg[j] = Rg[p]
            continue
        cur = Rg[p] @ (rest_child / np.linalg.norm(rest_child))
        Rg[j] = align(cur, obs / np.linalg.norm(obs)) @ Rg[p]
    # forward kinematics for joint positions
    Jp = np.zeros((16, 3))
    for j in range(16):
        p = PARENT[j]
        Jp[j] = Jp[p] + Rg[p] @ (REST_J[j] - REST_J[p]) if p >= 0 else REST_J[0]
    R = np.stack(Rg)                                  # (16,3,3)
    t = Jp - np.einsum('kij,kj->ki', R, REST_J)       # (16,3)
    Vp = np.einsum('vk,kij,vj->vi', Wgt, R, REST_V) + Wgt @ t
    return Vp, Rg[0]

MIR = np.diag([-1.0, 1.0, 1.0])

def hand_vertices(gl, left):
    """Articulation only: the measured wrist orientation is divided out so both
    hands sit in the same canonical pose and the panel shows the fingers."""
    g = gl @ MIR if left else gl
    v, R0 = pose(g)
    v = (v - REST_J[0]) @ R0              # undo the global wrist rotation
    v = v @ PRESENT.T                     # palm to camera, fingers up
    return v @ MIR if left else v

# ── scene ──────────────────────────────────────────────────────────────────
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE_NEXT'
sc.eevee.taa_render_samples = 16
sc.render.resolution_x, sc.render.resolution_y = W, H
sc.render.image_settings.file_format = 'PNG'
sc.view_settings.view_transform = 'Filmic'
sc.view_settings.look = 'Medium High Contrast'
sc.view_settings.exposure = -1.15
sc.world = bpy.data.worlds.new('w'); sc.world.use_nodes = True
next(n for n in sc.world.node_tree.nodes if n.type == 'BACKGROUND'
     ).inputs[0].default_value = (.020, .024, .031, 1)

skin = bpy.data.materials.new('skin'); skin.use_nodes = True
b = next(n for n in skin.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
for k, v in (('Base Color', (.792, .741, .702, 1)), ('Roughness', .44), ('Subsurface Weight', .18)):
    if k in b.inputs: b.inputs[k].default_value = v

objs = {}
for side, dx in (('L', -0.105), ('R', 0.105)):
    me = bpy.data.meshes.new('hand' + side)
    me.from_pydata([tuple(p) for p in REST_V], [], [tuple(f) for f in FACES])
    me.update()
    o = bpy.data.objects.new('hand' + side, me)
    bpy.context.collection.objects.link(o)
    o.location = (dx, 0, 0)
    o.data.materials.append(skin)
    for poly in me.polygons:
        poly.use_smooth = True
    objs[side] = (o, me)

# the camera always looks along +Y with world +Z up, so set the rotation
# outright: a TRACK_TO constraint here evaluated to a view that missed the hands
bpy.ops.object.camera_add(location=(0, -0.40, 0.03),
                          rotation=(math.radians(90), 0, 0))
cam = bpy.context.object; cam.data.lens = 46; sc.camera = cam

def light(loc, e, col=(1, 1, 1), rot=(62, 0, -28)):
    bpy.ops.object.light_add(type='AREA', location=loc)
    L = bpy.context.object; L.data.energy = e; L.data.size = .9; L.data.color = col
    L.rotation_euler = tuple(math.radians(a) for a in rot)
light((-.38, -.36, .42), 26)
light((.42, -.22, .26), 16, (.78, .86, 1.0), (72, 0, 56))
light((0, .38, .30), 14, (1.0, .80, .62), (64, 0, 182))

rows = {r["alias"]: r for r in csv.DictReader(open(SP / "sessions.csv"))}
targets = [a for a in sys.argv if a.startswith("session_")] or list(rows)

for sid in targets:
    raw = np.frombuffer(gzip.open(SP / sid / "glove.i16.gz").read(), dtype="<i2")
    nfg = raw.size // (21 * 3 * 2)
    G = raw[:nfg * 126].reshape(nfg, 2, 21, 3).astype(np.float64) * 1e-4
    dur_src = float(rows[sid]["duration_s"]); head = HEAD.get(sid, 2.0)
    n = max(int(round((dur_src / SPEED - head) * KEEP * FPS)), 1)

    # frame from the actual posed extent, sampled across the session
    samp = np.linspace(0, nfg - 1, 24).astype(int)
    pts = []
    for k in samp:
        for si, side in ((0, 'L'), (1, 'R')):
            v = hand_vertices(G[k, si], left=(side == 'L'))
            # object transform: +90 deg about Y, then the side offset
            vr = v.copy()
            vr[:, 0] += (-0.105 if side == 'L' else 0.105)
            pts.append(vr)
    P = np.concatenate(pts, 0)
    ctr = (P.max(0) + P.min(0)) / 2
    ext = P.max(0) - P.min(0)
    sensor_w = 36.0
    hfov = 2 * math.atan((sensor_w / 2) / cam.data.lens)
    vfov = 2 * math.atan((sensor_w * H / W / 2) / cam.data.lens)
    dist = max((ext[0] / 0.86 / 2) / math.tan(hfov / 2),
               (ext[2] / 0.80 / 2) / math.tan(vfov / 2)) + ext[1] * 0.6
    cam.location = (ctr[0], ctr[1] - dist, ctr[2])

    d = OUT / sid; d.mkdir(exist_ok=True)
    for f in d.glob("*.png"):
        f.unlink()
    for i in range(n):
        t_src = (i / FPS + head) * SPEED
        k = int(np.clip(round(t_src * GLOVE_HZ), 0, nfg - 1))
        for si, side in ((0, 'L'), (1, 'R')):
            v = hand_vertices(G[k, si], left=(side == 'L'))
            o, me = objs[side]
            me.vertices.foreach_set('co', v.astype(np.float32).reshape(-1))
            me.update()
        sc.render.filepath = str(d / f"f_{i:05d}.png")
        bpy.ops.render.render(write_still=True)
    print(f"DONE {sid} {n} frames", flush=True)

print("ALL DONE")
