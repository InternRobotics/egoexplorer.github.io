"""Render the EgoExplorer capture rig as a diagram.

  /Applications/Blender.app/Contents/MacOS/Blender -b -P rig_render.py

The body is the real SMPL-X mesh decoded from a session, not a stand-in. Facing
is derived from the nose so the figure can be turned to the camera, and each
device is seated on its anchor along the outward normal from the trunk, so the
mounting layout is the measured one. Rendered on transparency; the page adds
leader lines and labels in SVG, using the projected anchor pixels printed here.
"""
import bpy, math
from pathlib import Path
from mathutils import Vector, Matrix

HERE = Path(__file__).resolve().parent
OBJ, OUT = HERE / "body.obj", HERE / "rig.png"
W, H, SAMPLES = 1500, 2000, 110

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'CYCLES'
sc.cycles.samples = SAMPLES
sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = W, H
sc.render.film_transparent = True
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.color_mode = 'RGBA'
sc.view_settings.view_transform = 'Filmic'
sc.view_settings.look = 'Medium High Contrast'

def mat(name, rgba, rough=.55, metal=.0, emit=None, es=1.2):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    def s(k, v):
        if k in b.inputs: b.inputs[k].default_value = v
    s('Base Color', rgba); s('Roughness', rough); s('Metallic', metal)
    if emit:
        s('Emission Color', emit); s('Emission', emit); s('Emission Strength', es)
    return m

BODY   = mat('body',   (.300, .323, .368, 1), rough=.60)
CLOTH  = mat('cloth',  (.118, .140, .196, 1), rough=.86)
DEVICE = mat('device', (.070, .076, .090, 1), rough=.34, metal=.25)
ACCENT = mat('accent', (.820, .286, .055, 1), rough=.36, metal=.1)
GLASS  = mat('glass',  (.274, .498, .847, 1), rough=.18, emit=(.274, .498, .847, 1), es=1.6)
CUFF   = mat('cuff',   (.105, .112, .130, 1), rough=.78)

# ── body, turned to face the camera ────────────────────────────────────────
bpy.ops.wm.obj_import(filepath=str(OBJ), forward_axis='NEGATIVE_Y', up_axis='Z')
body = bpy.context.selected_objects[0]; body.name = 'body'
body.data.materials.append(BODY)
# SMPL-X has no clothing; the same baked mask the film uses shades the trunk
# and thighs as cloth, so the two figures on the page are the same person.
# The mask goes in as a vertex colour and the hem is thresholded in the
# shader: assigning it per polygon instead gives a sawtooth edge.
import numpy as np
_g = np.load(HERE / 'garment.npy').astype(np.float32)
if len(body.data.vertices) == len(_g):
    _ca = body.data.color_attributes.new(name='garment', type='FLOAT_COLOR',
                                         domain='POINT')
    _c = np.ones((len(_g), 4), np.float32)
    _c[:, 0] = _c[:, 1] = _c[:, 2] = _g
    _ca.data.foreach_set('color', _c.reshape(-1))
    _nt = BODY.node_tree
    _b = next(n for n in _nt.nodes if n.type == 'BSDF_PRINCIPLED')
    _at = _nt.nodes.new('ShaderNodeAttribute'); _at.attribute_name = 'garment'
    _at.location = (-900, 160)
    _st = _nt.nodes.new('ShaderNodeMath'); _st.operation = 'GREATER_THAN'
    _st.inputs[1].default_value = 0.5; _st.location = (-700, 160)
    _mx = _nt.nodes.new('ShaderNodeMixRGB'); _mx.location = (-520, 160)
    _mx.inputs['Color1'].default_value = (.300, .323, .368, 1)
    _mx.inputs['Color2'].default_value = (.118, .140, .196, 1)
    _rg = _nt.nodes.new('ShaderNodeMapRange'); _rg.location = (-520, -40)
    _rg.inputs['To Min'].default_value = .60
    _rg.inputs['To Max'].default_value = .88
    _nt.links.new(_at.outputs['Fac'], _st.inputs[0])
    _nt.links.new(_st.outputs[0], _mx.inputs['Fac'])
    _nt.links.new(_st.outputs[0], _rg.inputs['Value'])
    _nt.links.new(_mx.outputs['Color'], _b.inputs['Base Color'])
    _nt.links.new(_rg.outputs['Result'], _b.inputs['Roughness'])
else:
    print('WARNING: garment mask does not match the mesh; left unclothed')
bpy.ops.object.shade_smooth()

P = [v.co.copy() for v in body.data.vertices]
zs = [p.z for p in P]; top, bot = max(zs), min(zs); height = top - bot

# the nose is the head-band vertex furthest from the head's own vertical axis
headband = [p for p in P if p.z > top - .13 * height]
hc = Vector((sum(p.x for p in headband) / len(headband),
             sum(p.y for p in headband) / len(headband), 0))
nose = max(headband, key=lambda p: (Vector((p.x, p.y, 0)) - hc).length)
facing = (Vector((nose.x, nose.y, 0)) - hc).normalized()
cur = math.atan2(facing.y, facing.x)
print('FACING %.1f deg' % math.degrees(cur))
body.data.transform(Matrix.Rotation(math.radians(-90) - cur, 4, 'Z'))
body.data.update()

P = [v.co.copy() for v in body.data.vertices]
xs = [p.x for p in P]; zs = [p.z for p in P]
top, bot = max(zs), min(zs); height = top - bot
cx = (max(xs) + min(xs)) / 2
trunk = Vector((sum(p.x for p in P) / len(P), sum(p.y for p in P) / len(P), 0))

def centroid(pts):
    n = len(pts)
    return Vector((sum(p.x for p in pts) / n, sum(p.y for p in pts) / n,
                   sum(p.z for p in pts) / n))

head = centroid([p for p in P if p.z > top - .05 * height])
lowz = bot + .07 * height
footL = centroid([p for p in P if p.z < lowz and p.x < cx])
footR = centroid([p for p in P if p.z < lowz and p.x > cx])
band = [p for p in P if bot + .32 * height < p.z < bot + .84 * height]
def hand(side):
    pts = [p for p in band if (p.x < cx if side < 0 else p.x > cx)]
    tip = max(pts, key=lambda p: (Vector((p.x, p.y, 0)) - trunk).length)
    # the wrist sits ~9 cm back along the arm from the fingertip
    near = [p for p in pts if (p - tip).length < .17]
    far = max(near, key=lambda p: (p - tip).length) if len(near) > 20 else tip
    d = (far - tip)
    return tip + d.normalized() * min(d.length, .095) if d.length > 1e-6 else tip
handL, handR = hand(-1), hand(1)

def outward(p):
    d = Vector((p.x, p.y, 0)) - trunk
    return d.normalized() if d.length > 1e-6 else Vector((1, 0, 0))

def puck(name, loc, mtl, size, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object; o.name = name
    o.scale = size; o.rotation_euler = rot
    b = o.modifiers.new('b', 'BEVEL'); b.width = .010; b.segments = 5
    o.data.materials.append(mtl); bpy.ops.object.shade_smooth()
    return o

ANCH = {}
ANCH['head'] = Vector((head.x, head.y, head.z + .055))



for tag, h in (('wristL', handL), ('wristR', handR)):
    n = outward(h)
    ANCH[tag] = Vector((h.x + n.x * .012, h.y + n.y * .012, h.z + .034))

for tag, f in (('ankleL', footL), ('ankleR', footR)):
    n = outward(f)
    ANCH[tag] = Vector((f.x + n.x * .018, f.y + n.y * .018, f.z + .075))

print('HEIGHT %.4f  BOT %.4f  CX %.4f' % (height, bot, cx))

# ── stage ──────────────────────────────────────────────────────────────────
bpy.ops.mesh.primitive_plane_add(size=16, location=(cx, trunk.y, bot - .002))
g = bpy.context.object; g.name = 'ground'
g.data.materials.append(mat('ground', (.05, .053, .060, 1), rough=.95))
g.is_shadow_catcher = True

def area(loc, e, size, rot):
    bpy.ops.object.light_add(type='AREA', location=loc, rotation=rot)
    L = bpy.context.object; L.data.energy = e; L.data.size = size
    return L
area((cx - 1.9, trunk.y - 2.4, bot + 2.7), 260, 3.0, (math.radians(52), 0, math.radians(-38)))
area((cx + 2.4, trunk.y - 1.2, bot + 1.9), 120, 2.4, (math.radians(72), 0, math.radians(60)))
area((cx + .3, trunk.y + 2.8, bot + 2.3), 150, 3.0, (math.radians(64), 0, math.radians(184)))

bpy.ops.object.camera_add(location=(cx - 1.35, trunk.y - 5.6, bot + height * .56))
cam = bpy.context.object; cam.data.lens = 108; sc.camera = cam
bpy.ops.object.empty_add(location=(cx, trunk.y, bot + height * .54))
c = cam.constraints.new('TRACK_TO'); c.target = bpy.context.object
c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'

# project the anchors to pixels so the page can place its leader lines
from bpy_extras.object_utils import world_to_camera_view
bpy.context.view_layer.update()
for k, v in ANCH.items():
    p = world_to_camera_view(sc, cam, v)
    print('PIX %s %.4f %.4f' % (k, p.x, 1 - p.y))
# the markers the page draws should sit ON the body, so project the landmarks
# themselves rather than the device anchors, which are offset outboard
for k, v in (('head', head), ('wristL', handL), ('wristR', handR),
             ('ankleL', footL), ('ankleR', footR)):
    q = world_to_camera_view(sc, cam, body.matrix_world @ v)
    print('MARK %s %.4f %.4f' % (k, q.x, 1 - q.y))
# and the figure's own extent, so the page crop can be derived rather than guessed
_u = [world_to_camera_view(sc, cam, body.matrix_world @ vv.co)
      for vv in body.data.vertices]
print('BBOX %.4f %.4f %.4f %.4f' % (min(q.x for q in _u), max(q.x for q in _u),
                                    min(1 - q.y for q in _u), max(1 - q.y for q in _u)))

sc.render.filepath = str(OUT)
bpy.ops.render.render(write_still=True)
print('WROTE', OUT)
