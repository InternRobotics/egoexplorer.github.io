"""Assign the 17 Wuji tactile regions to SMPL-X hand vertices.

The Wuji glove reports one value per anatomical region, not per vertex, so to
light the measured pressure on the real hand we need the region each vertex
belongs to. SMPL-X carries MANO's hand rig verbatim — the fifteen hand joints
per side are index1..3, middle1..3, pinky1..3, ring1..3, thumb1..3 in that
order — so the recipe from the paper's hand figure transfers directly: a vertex
takes the region of its dominant LBS joint, kept only on the palmar side, and
the wrist-dominant palm is split radial / central / ulnar.
"""
import numpy as np
np.seterr(all="ignore")   # numpy 2 + macOS Accelerate: spurious matmul warnings

REGIONS = ["thumb_distal", "thumb_proximal",
           "index_distal", "index_middle", "index_proximal",
           "middle_distal", "middle_middle", "middle_proximal",
           "ring_distal", "ring_middle", "ring_proximal",
           "pinky_distal", "pinky_middle", "pinky_proximal",
           "palm_radial", "palm_central", "palm_ulnar"]
# offset from the side's first hand joint -> region  (thumb1 carries no taxels)
SEG = {0: "index_proximal", 1: "index_middle", 2: "index_distal",
       3: "middle_proximal", 4: "middle_middle", 5: "middle_distal",
       6: "pinky_proximal", 7: "pinky_middle", 8: "pinky_distal",
       9: "ring_proximal", 10: "ring_middle", 11: "ring_distal",
       13: "thumb_proximal", 14: "thumb_distal"}
BASE = {"L": 25, "R": 40}
WRIST = {"L": 20, "R": 21}


def vertex_normals(V, F):
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    vn = np.zeros_like(V)
    for k in range(3):
        np.add.at(vn, F[:, k], fn)
    return vn / (np.linalg.norm(vn, axis=1, keepdims=True) + 1e-12)


def assign(V, F, W, J, side):
    """V,F: rest mesh.  W: (nv,55) lbs weights.  J: (55,3) rest joints."""
    base, wrist = BASE[side], WRIST[side]
    seg = W.argmax(1)
    n = vertex_normals(V, F)
    hand = np.isin(seg, [wrist] + list(range(base, base + 15)))

    # palm normal: average the normals of the vertices between the MCPs, taking
    # the side the thumb curls toward as palmar
    mcp = J[[base, base + 3, base + 9, base + 6]]          # index/middle/ring/pinky1
    thumb = J[base + 13]
    ctr = mcp.mean(0)
    pn = thumb - ctr
    pn -= np.dot(pn, (mcp[0] - mcp[3]) / np.linalg.norm(mcp[0] - mcp[3])) * \
          (mcp[0] - mcp[3]) / np.linalg.norm(mcp[0] - mcp[3])
    fwd = ctr - J[wrist]; fwd /= np.linalg.norm(fwd)
    pn -= np.dot(pn, fwd) * fwd
    pn /= np.linalg.norm(pn)

    palmar = n @ pn
    reg = np.full(len(V), -1, np.int32)
    for off, name in SEG.items():
        thr = -0.15 if name.endswith("distal") else 0.20
        reg[(seg == base + off) & (palmar > thr)] = REGIONS.index(name)

    along = (V - J[wrist]) @ fwd
    palm = hand & (seg == wrist) & (palmar > 0.35) & (along > 0.030)
    # across the palm: radial is the thumb/index side, ulnar the pinky side
    lat = (mcp[0] - mcp[3]); lat /= np.linalg.norm(lat)      # pinky -> index
    u = (V - J[wrist]) @ lat
    a, b = np.quantile(u[palm], [1 / 3, 2 / 3]) if palm.sum() else (0, 0)
    reg[palm & (u <= a)] = REGIONS.index("palm_ulnar")
    reg[palm & (u > a) & (u <= b)] = REGIONS.index("palm_central")
    reg[palm & (u > b)] = REGIONS.index("palm_radial")
    return reg, hand


def build(model_dir="/Volumes/NASStorage/Downloads/models"):
    import smplx, torch
    m = smplx.create(model_dir, model_type="smplx", gender="neutral",
                     use_pca=False, flat_hand_mean=True, batch_size=1)
    with torch.no_grad():
        o = m(betas=torch.zeros(1, 10))
    V = o.vertices[0].numpy().astype(np.float64)
    J = o.joints[0].numpy().astype(np.float64)[:55]
    F = m.faces.astype(np.int32)
    W = m.lbs_weights.numpy()
    out = {}
    for s in ("L", "R"):
        out[s] = assign(V, F, W, J, s)
    return V, F, out


if __name__ == "__main__":
    V, F, out = build()
    for s in ("L", "R"):
        reg, hand = out[s]
        print(s, "hand verts", int(hand.sum()), "assigned", int((reg >= 0).sum()))
        for i, nm in enumerate(REGIONS):
            print(f"   {nm:16s} {int((reg == i).sum()):4d}")
