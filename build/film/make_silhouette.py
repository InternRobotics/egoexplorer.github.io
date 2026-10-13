"""Render the project's own SMPL-X silhouette for film_type's inset figures.

Writes body_silhouette.png, body_sil_mask.png and prints the five anchor
percentages for film_type.ANCH, measured from the same camera that drew the
figure rather than read off the image by hand.

This exists because the two PNGs lived only in a session scratchpad, which is
wiped on restart: the film then rendered with empty boxes where the little
bodies should be, and nothing in the build failed.

  /Applications/Blender.app/Contents/MacOS/Blender -b -P make_silhouette.py
"""
import bpy, sys, json, math
import numpy as np
from pathlib import Path

HERE = Path(__file__).resolve().parent
BAKE = HERE / "bake"
W, H = 751, 1500                      # the aspect film_type's CSS box uses
FRAME = 300                          # upright, front-on once yawed, limbs clear

V = np.load(BAKE / "verts.npy", mmap_mode="r")
F = np.load(BAKE / "faces.npy")

JIDX_SH = (16, 17)                    # left, right shoulder
J_ALL = np.load(BAKE / "joints.npy", mmap_mode="r")

def upright(frame):
    """Vertices and joints of one frame, yawed to face the camera.

    The subject turns around the room, so a world-fixed camera catches
    whatever side happens to point at it: at frame 300 both wrists projected
    onto the same 8% of the image. Rotating about Z by the shoulder bearing
    puts the figure front-on, which is what the inset wants.
    """
    v = np.asarray(V[frame], np.float64)
    j = np.asarray(J_ALL[frame], np.float64)
    lat = j[JIDX_SH[0]] - j[JIDX_SH[1]]
    a = math.pi / 2 - math.atan2(lat[0], -lat[1])
    ca, sa = math.cos(a), math.sin(a)
    R = np.array([[ca, -sa, 0], [sa, ca, 0], [0, 0, 1.0]])
    c = np.array([v[:, 0].mean(), v[:, 1].mean(), 0.0])
    return (v - c) @ R.T, (j - c) @ R.T

verts, JOINTS = upright(FRAME)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE_NEXT'
sc.eevee.taa_render_samples = 64
sc.render.film_transparent = True
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.color_mode = 'RGBA'
sc.view_settings.view_transform = 'Standard'
sc.render.resolution_x, sc.render.resolution_y = W, H

me = bpy.data.meshes.new('b')
me.from_pydata([tuple(p) for p in verts], [], [tuple(t) for t in F])
me.update()
ob = bpy.data.objects.new('b', me)
bpy.context.collection.objects.link(ob)
for p in me.polygons:
    p.use_smooth = True
mt = bpy.data.materials.new('m'); mt.use_nodes = True
nt = mt.node_tree
for n in list(nt.nodes):
    nt.nodes.remove(n)
em = nt.nodes.new('ShaderNodeEmission')
em.inputs[0].default_value = (1, 1, 1, 1); em.inputs[1].default_value = 1.0
out = nt.nodes.new('ShaderNodeOutputMaterial')
nt.links.new(em.outputs[0], out.inputs[0])
ob.data.materials.append(mt)

# orthographic front view, so image position is a linear function of world x,z
lo, hi = verts.min(0), verts.max(0)
cx, cz = (lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2
height = (hi[2] - lo[2]) * 1.06
width = height * W / H
bpy.ops.object.camera_add(location=(cx, lo[1] - 6.0, cz),
                          rotation=(math.radians(90), 0, 0))
cam = bpy.context.object
cam.data.type = 'ORTHO'
cam.data.ortho_scale = max(width, height)
sc.camera = cam

sc.render.filepath = str(HERE / "body_silhouette.png")
bpy.ops.render.render(write_still=True)
import shutil
shutil.copyfile(HERE / "body_silhouette.png", HERE / "body_sil_mask.png")

# the five anchors, in the camera's own coordinates
def pct(p):
    u = (p[0] - cx) / width + 0.5
    v = 0.5 - (p[2] - cz) / height
    return round(100 * u, 1), round(100 * v, 1)

# SMPL-X's body joint order is fixed, and Blender's bundled Python has no
# smplx to look the names up in, so the five indices are written out here.
JIDX = [("head", 15), ("wristR", 21), ("wristL", 20),
        ("ankleR", 8), ("ankleL", 7)]
anch = [(tag, *pct(JOINTS[i])) for tag, i in JIDX]
print("SIL OK", W, H)
print("ANCH =", anch)
