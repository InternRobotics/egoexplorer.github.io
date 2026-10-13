"""Bake the body and hand panels of one session at the page's playback rate.

The panels on the page were built from session_package/*/mesh.i8c.gz, which is
capped at 300 frames per session. At 5x playback that left session_A with about
seven distinct poses per second of video — the stutter was the data, not the
encode. The unified export carries the same session at 30 Hz, which at 5x is
150 source poses per second of video: more than a 60 fps panel can show.

  verts.npy  (N,10475,3) f32  world, Z-up, floor at 0
  joints.npy (N,55,3)    f32  the same frames' joints, for the hand frame
  hands.npy  (N,2,V,3)   f32  left/right hand, canonical: palm out, fingers up
  hidx.npy   (V,)        i32  which SMPL-X vertices those are
  touch.npy  (N,2,17)    f16  per-region pressure, 0..1, for the tactile panel
"""
import json, sys
import numpy as np
np.seterr(all="ignore")
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from egodata import Session, SP
from hand_regions import build as build_regions, BASE, WRIST

FPS, SPEED, KEEP = 60, 5.0, 0.98
HEAD = {"session_F": 14.0}
ROOT = Path("/Volumes/NASStorage/Documents/code/.egoexplorer_build/streams")

ROWS = {r.split(",")[0]: r.split(",") for r in
        (SP / "sessions.csv").read_text().splitlines()[1:]}


# cross(fwd, lat) with lat running pinky -> index comes out palmar on the left
# hand and dorsal on the right, because the two hands are mirror images.
# Measured against the thumb in the model's rest pose; see the check in the
# commit message.
PALM_SIGN = {"L": +1.0, "R": -1.0}


def canonical(Vh, J, side):
    """Put a hand in a fixed presentation frame: palm toward the viewer (-Y),
    fingers up (+Z).

    The rotation is built from the hand's own palmar normal, so each hand gets
    a proper rotation and neither is mirrored: both palms face the viewer and
    the thumbs therefore sit on opposite sides, the way two real hands held up
    would. Only the wrist's measured orientation is divided out, so what is
    left on screen is the articulation itself.
    """
    base, wrist = BASE[side], WRIST[side]
    w = J[wrist]
    mcp = J[[base, base + 3, base + 9, base + 6]]
    fwd = mcp.mean(0) - w                       # along the fingers
    fwd /= np.linalg.norm(fwd)
    lat = mcp[0] - mcp[3]                       # pinky -> index
    lat -= lat @ fwd * fwd
    lat /= np.linalg.norm(lat)
    pn = PALM_SIGN[side] * np.cross(fwd, lat)   # out of the palm, both hands
    E = np.stack([fwd, pn, np.cross(fwd, pn)], 1)
    T = np.stack([[0, 0, 1.0], [0, -1.0, 0], [1.0, 0, 0]], 1)
    return (Vh - w) @ (T @ E.T).T


def main(alias, fps=FPS, out_root=ROOT):
    out = out_root / alias
    out.mkdir(parents=True, exist_ok=True)
    s = Session(alias)
    dur = float(ROWS[alias][5])
    head = HEAD.get(alias, 2.0)
    n = max(int(round((dur / SPEED - head) * KEEP * fps)), 1)
    src = np.clip(np.round((np.arange(n) / fps + head) * SPEED * s.rate),
                  0, s.n_src - 1).astype(int)
    need = np.unique(src)
    s.idx = need
    print(f"{alias}: {n} panel frames at {fps} fps from {len(need)} poses", flush=True)
    V, J = s.vertices(with_joints=True)
    pos = {f: i for i, f in enumerate(need)}
    take = np.array([pos[f] for f in src])
    np.save(out / "verts.npy", V[take])
    np.save(out / "joints.npy", J[take])

    # hands, in their own canonical frame
    import smplx, torch
    m = smplx.create("/Volumes/NASStorage/Downloads/models", model_type="smplx",
                     gender="neutral", use_pca=False, flat_hand_mean=True, batch_size=1)
    with torch.no_grad():
        o = m(betas=torch.tensor(s.z["betas"][None]))
    Jrest = o.joints[0].numpy()[:55]
    _, _, regs = build_regions()
    W = m.lbs_weights.numpy()
    seg = W.argmax(1)
    # take every vertex of every face that touches the hand, so the sub-mesh
    # has no holes where a face straddles the wrist
    F0 = s.faces()
    H, HF = {}, {}
    for side in ("L", "R"):
        base, wrist = BASE[side], WRIST[side]
        core = set(np.where(np.isin(seg, [wrist] + list(range(base, base + 15))))[0].tolist())
        keep = np.array([any(v in core for v in f) for f in F0])
        idx = np.unique(F0[keep].reshape(-1))
        pos = {v: k for k, v in enumerate(idx)}
        H[side] = idx
        HF[side] = np.array([[pos[v] for v in f] for f in F0[keep]], np.int32)
    k = max(len(H["L"]), len(H["R"]))
    hidx = np.stack([np.pad(H[si], (0, k - len(H[si])), mode="edge")
                     for si in ("L", "R")])
    hv = np.empty((len(take), 2, k, 3), np.float32)
    Vt, Jt = V[take], J[take]
    for f in range(len(take)):
        for si, side in enumerate(("L", "R")):
            hv[f, si] = canonical(np.asarray(Vt[f][hidx[si]], np.float64),
                                  np.asarray(Jt[f], np.float64), side)
    np.save(out / "hands.npy", hv)
    np.save(out / "hidx.npy", hidx.astype(np.int32))
    np.save(out / "faces.npy", F0)
    k2 = max(len(HF["L"]), len(HF["R"]))
    # pad with a degenerate triangle, never by repeating the last face: a
    # duplicated coincident face z-fights and shows as a dark patch
    np.save(out / "hfaces.npy", np.stack(
        [np.concatenate([HF[si], np.zeros((k2 - len(HF[si]), 3), np.int32)])
         for si in ("L", "R")]))

    tt = np.zeros((len(take), 2, 17), np.float32)
    for si, side in enumerate(("L", "R")):
        key = f"tactile_{side}_L2_score"
        if key in s.z.files:
            hi = float(np.nanpercentile(s.z[key], 99.0)) or 1.0
            tt[:, si] = np.clip(s.z[key][src] / hi, 0, 1)
    np.save(out / "touch.npy", tt)
    (out / "meta.json").write_text(json.dumps(
        {"alias": alias, "frames": n, "fps": fps, "head": head,
         "speed": SPEED, "hand_verts": int(k)}, indent=1))
    print(f"  verts {V[take].shape} hands {hv.shape}", flush=True)


if __name__ == "__main__":
    for a in (sys.argv[1:] or sorted(ROWS)):
        main(a)
