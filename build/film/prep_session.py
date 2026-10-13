"""Bake one session window to arrays Blender can read without torch.

Blender's bundled Python has no torch, so SMPL-X is evaluated here and the
result is written as plain .npy:

  verts.npy    (NF, 10475, 3) float32   Z-up, floor at 0, 60 fps
  faces.npy    (20908, 3) int32
  track.npy    (NF, 5, 3)   float32     camera, wrists, ankles
  touch.npy    (NF, 10475)  float32     per-vertex tactile, 0..1
  meta.json    fps, window, roles, ground, the touch normalisation used

The 30 Hz source is upsampled to 60 by interpolating vertices, not parameters —
over a 33 ms step the two are indistinguishable and this keeps the bake simple.
"""
import json, sys
import numpy as np
np.seterr(all="ignore")
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from egodata import Session, YUP2Z
from hand_regions import build as build_regions, REGIONS

HERE = Path(__file__).resolve().parent
OUT = HERE / "bake"

SESSION = "session_J"       # sandwich making: a kitchen, both gloves, dense contact
F0, SECONDS, FPS = 1160, 27.0, 60   # placed so the palm-facing beat lands in the hand act


def main(alias=SESSION, f0=F0, seconds=SECONDS, fps=FPS, out=OUT):
    out.mkdir(exist_ok=True)
    s = Session(alias)
    nf = int(round(seconds * fps))
    src = f0 + np.arange(nf) * (s.rate / fps)            # fractional 30 Hz index
    lo = np.floor(src).astype(int)
    hi = np.minimum(lo + 1, s.n_src - 1)
    w = (src - lo).astype(np.float32)[:, None, None]
    need = np.unique(np.concatenate([lo, hi]))
    print(f"{alias}: {nf} frames at {fps} fps from {len(need)} source poses")

    s.idx = need
    V, J = s.vertices(with_joints=True)                  # (len(need),10475,3)
    pos = {f: i for i, f in enumerate(need)}
    il = np.array([pos[f] for f in lo]); ih = np.array([pos[f] for f in hi])
    # float32, not float16: at these world magnitudes the float16 step is
    # millimetres, which put ~1 mm of noise on every vertex of every frame and
    # made the fingers crawl and kink at close range
    verts = (V[il] * (1 - w) + V[ih] * w).astype(np.float32)
    np.save(out / "verts.npy", verts)
    # the joints too, interpolated exactly as the vertices are so they stay on
    # the same body: make_silhouette.py needs them to place the five anchor
    # pins, and deriving those from the vertex cloud is guesswork
    np.save(out / "joints.npy",
            (J[il] * (1 - w) + J[ih] * w).astype(np.float32))
    np.save(out / "faces.npy", s.faces())

    T = s.trackers()
    track = (T[il] * (1 - w) + T[ih] * w).astype(np.float32)
    np.save(out / "track.npy", track)

    # ── tactile, spread from 17 regions onto the hand vertices ──────────
    _, _, regs = build_regions()
    touch = np.zeros((nf, verts.shape[1]), np.float32)
    names = [str(x) for x in s.z["tactile_region_names"]]
    norm = {}
    for side in ("L", "R"):
        key = f"tactile_{side}_L2_score"
        if key not in s.z.files:
            continue
        sc = s.z[key][lo] * (1 - w[:, :, 0]) + s.z[key][hi] * w[:, :, 0]
        hi95 = float(np.nanpercentile(s.z[key], 99.0)) or 1.0
        norm[side] = hi95
        reg, _ = regs[side]
        for ri, rname in enumerate(names):
            if rname not in REGIONS:
                continue
            vid = np.where(reg == REGIONS.index(rname))[0]
            if not len(vid):
                continue
            v = np.clip(sc[:, ri] / hi95, 0, 1).astype(np.float32)
            touch[:, vid] = v[:, None]
    # The 17 regions are disjoint sets of vertices, so a hard assignment shows
    # as sawtooth stripes once it is lit. A few Laplacian passes over the hand
    # mesh blend the boundaries into the gradient a pressure field should have,
    # without moving where the pressure is.
    F = s.faces()
    hv = np.unique(np.concatenate([np.where(regs[k][0] >= 0)[0] for k in regs]))
    hs = set(hv.tolist())
    e = F[[i for i, f in enumerate(F) if any(v in hs for v in f)]]
    pairs = np.concatenate([e[:, [0, 1]], e[:, [1, 2]], e[:, [2, 0]]])
    pairs = np.concatenate([pairs, pairs[:, ::-1]])
    deg = np.bincount(pairs[:, 0], minlength=touch.shape[1]).astype(np.float32)
    deg[deg == 0] = 1
    for _ in range(3):
        acc = np.zeros_like(touch, dtype=np.float32)
        np.add.at(acc.T, pairs[:, 0], touch.T[pairs[:, 1]].astype(np.float32))
        sm = (acc / deg).astype(np.float32)
        touch[:, hv] = (0.45 * touch[:, hv] + 0.55 * sm[:, hv])
    np.save(out / "touch.npy", touch)

    (out / "meta.json").write_text(json.dumps({
        "alias": alias, "f0": f0, "fps": fps, "frames": nf,
        "seconds": seconds, "roles": s.roles, "touch_norm": norm,
        "task": [r.split(",")[2] for r in
                 (Path("/Volumes/NASStorage/Downloads/session_package/sessions.csv")
                  ).read_text().splitlines()[1:] if r.startswith(alias + ",")][0],
    }, indent=1))
    print("verts", verts.shape, verts.nbytes / 1e6, "MB; touch max",
          float(touch.max()), "; track", track.shape)


if __name__ == "__main__":
    main()


def bake_palm(out=OUT, smooth_s=0.5, fps=FPS):
    """Per-frame palm centre and outward palm normal for the right hand.

    The hand act points the camera down this normal, so the close-up always
    shows the palm — and therefore the tactile regions — instead of landing on
    the back of the hand whenever the wrist happens to roll.
    """
    from hand_regions import build as build_regions, REGIONS, BASE, WRIST
    V = np.load(out / "verts.npy", mmap_mode="r")
    _, _, regs = build_regions()
    reg, _ = regs["R"]
    palm = np.where(np.isin(reg, [REGIONS.index(n) for n in
                                  ("palm_radial", "palm_central", "palm_ulnar")]))[0]
    F = np.load(out / "faces.npy")
    pset = set(palm.tolist())
    pf = F[[k for k, f in enumerate(F) if all(v in pset for v in f)]]
    if len(pf) < 8:                       # fall back to any face touching the palm
        pf = F[[k for k, f in enumerate(F) if any(v in pset for v in f)]]
    nf = len(V)
    ctr = np.empty((nf, 3), np.float32); nrm = np.empty((nf, 3), np.float32)
    for i in range(nf):
        Vi = np.asarray(V[i], np.float64)
        P = Vi[palm]
        c = P.mean(0)
        # the palm's outward direction is the mesh's own surface normal there;
        # a plane fit alone cannot tell palmar from dorsal
        fn = np.cross(Vi[pf[:, 1]] - Vi[pf[:, 0]], Vi[pf[:, 2]] - Vi[pf[:, 0]])
        n = fn.sum(0)
        ctr[i] = c; nrm[i] = n / (np.linalg.norm(n) + 1e-9)
    k = max(int(smooth_s * fps) | 1, 3)
    ker = np.ones(k) / k
    pad = lambda a: np.pad(a, ((k // 2, k // 2), (0, 0)), mode="edge")
    ctr = np.stack([np.convolve(pad(ctr)[:, j], ker, "valid")[:nf] for j in range(3)], 1)
    nrm = np.stack([np.convolve(pad(nrm)[:, j], ker, "valid")[:nf] for j in range(3)], 1)
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-9
    np.save(out / "palm.npy", np.stack([ctr, nrm], 1).astype(np.float32))
    print("palm.npy", ctr.shape)


def bake_facing(alias=SESSION, f0=F0, seconds=SECONDS, fps=FPS, out=OUT,
                smooth_s=0.9):
    """Per-frame bearing of the direction the subject faces.

    The camera is placed relative to this rather than to world axes, so a
    three-quarter shot stays a three-quarter shot when the person turns from
    the counter to the island.
    """
    import torch, smplx
    from smplx.joint_names import JOINT_NAMES
    s = Session(alias)
    nf = int(round(seconds * fps))
    src = np.clip(np.round(f0 + np.arange(nf) * (s.rate / fps)), 0,
                  s.n_src - 1).astype(int)
    need = np.unique(src)
    m = smplx.create("/Volumes/NASStorage/Downloads/models", model_type="smplx",
                     gender="neutral", use_pca=False, flat_hand_mean=True,
                     batch_size=len(need), num_betas=10)
    z = s.z
    t = lambda k: torch.tensor(z[k][need])
    with torch.no_grad():
        o = m(betas=torch.tensor(np.tile(z["betas"][None], (len(need), 1))),
              global_orient=t("global_orient"), body_pose=t("body_pose"),
              transl=t("transl"))
    J = o.joints.numpy()[:, :55]
    name = {n: i for i, n in enumerate(JOINT_NAMES[:55])}
    # pelvis forward = up x (left hip -> right hip), in the Y-up source frame
    hip = J[:, name["right_hip"]] - J[:, name["left_hip"]]
    up = np.array([0, 1.0, 0])
    fwd = np.cross(up, hip)
    fwd = (fwd @ YUP2Z.T)[:, :2]
    fwd /= np.linalg.norm(fwd, axis=1, keepdims=True) + 1e-9
    pos = {f: i for i, f in enumerate(need)}
    fwd = fwd[[pos[f] for f in src]]
    k = max(int(smooth_s * fps) | 1, 3)
    ker = np.ones(k) / k
    pad = np.pad(fwd, ((k // 2, k // 2), (0, 0)), mode="edge")
    fwd = np.stack([np.convolve(pad[:, j], ker, "valid")[:nf] for j in range(2)], 1)
    bearing = np.arctan2(fwd[:, 0], fwd[:, 1])      # 0 = facing +y
    np.save(out / "facing.npy", bearing.astype(np.float32))
    print("facing.npy", bearing.shape, "deg range %.0f..%.0f" %
          (np.degrees(bearing).min(), np.degrees(bearing).max()))
