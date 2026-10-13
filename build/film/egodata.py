"""Load a unified-30 Hz session export and pose SMPL-X from it.

The session_package meshes are capped at 300 frames per session (1-8 Hz), which
is what made the rendered streams look like slideshows. These exports carry the
same sessions at 30 Hz, plus the five tracker poses, the glove keypoints and the
17-region tactile stream on the same index. Everything downstream reads this.

Source frame is Y-up with the floor at ground_y_m; we hand back Z-up with the
floor at z = 0, which is what Blender and every renderer here expects.
"""
import numpy as np
from pathlib import Path

SMPLX_DIR = Path("/Volumes/NASStorage/Downloads/models/smplx")
UNI = Path("/Volumes/NASStorage/Downloads/smplx")
SP = Path("/Volumes/NASStorage/Downloads/session_package")

ALIAS = {r.split(",")[0]: r.split(",")[4] for r in
         (SP / "sessions.csv").read_text().splitlines()[1:]}


def npz_for(alias):
    base = ALIAS[alias]
    hits = [p for p in UNI.glob("*.npz") if p.name.startswith(base)]
    if not hits:
        raise FileNotFoundError(f"no unified export for {alias} ({base})")
    return hits[0]


# Y-up -> Z-up, right-handed
YUP2Z = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], dtype=np.float64)


class Session:
    def __init__(self, alias, frames=None):
        self.alias = alias
        z = np.load(npz_for(alias), allow_pickle=True)
        self.z = z
        self.n_src = len(z["body_pose"])
        self.rate = float(z["rate_hz"])
        self.idx = np.arange(self.n_src) if frames is None else np.asarray(frames)
        self.ground = float(z["ground_y_m"])
        self.roles = [str(r) for r in z["tracker_roles"]]
        self.regions = [str(r) for r in z["tactile_region_names"]]

    # ── body ────────────────────────────────────────────────────────────
    # ── finger joint limits ─────────────────────────────────────────────
    # The glove fit returns a free 3-DOF rotation at every finger joint. Two
    # of those axes do not exist in a finger: the middle and distal joints are
    # hinges, and no finger joint twists about its own bone. Measured on
    # session_A, the fit puts 50-72 deg of twist into the index and middle
    # PIP/DIP joints, which is what makes the fingers look dislocated.
    #
    # Each joint is projected back onto the degrees of freedom it has. The
    # axes are derived from the model's own rest pose, per joint and per side:
    # the bone runs to the child joint, the hinge axis is perpendicular to the
    # bone and lies in the plane of the palm, and abduction is what is left.
    _AXES = {}

    @classmethod
    def finger_axes(cls, side, model_dir=str(SMPLX_DIR.parent)):
        if side in cls._AXES:
            return cls._AXES[side]
        import torch, smplx
        from smplx.joint_names import JOINT_NAMES
        nm = {n: i for i, n in enumerate(JOINT_NAMES[:55])}
        m = smplx.create(model_dir, model_type="smplx", gender="neutral",
                         use_pca=False, flat_hand_mean=True, batch_size=1)
        with torch.no_grad():
            J = m(betas=torch.zeros(1, 10)).joints[0].numpy()[:55].astype(np.float64)
        w = J[nm[f"{side}_wrist"]]
        mcp = np.stack([J[nm[f"{side}_{f}1"]] for f in
                        ("index", "middle", "ring", "pinky")])
        fwd = mcp.mean(0) - w; fwd /= np.linalg.norm(fwd)
        lat = mcp[0] - mcp[3]; lat -= lat @ fwd * fwd
        lat /= np.linalg.norm(lat)
        # Out of the palm. NOT signed from the thumb: in the flat rest pose the
        # thumb tip lies almost in the palm plane (|dot| ~ 0.023), so that test
        # is noise and a different body shape can flip it. Oriented instead
        # from MANO's own relaxed hand mean, which is a curl toward the palm by
        # construction, so +theta about cross(b, pn) must agree with it.
        pn = np.cross(fwd, lat)
        _rel = smplx.create(model_dir, model_type="smplx", gender="neutral",
                            use_pca=False, flat_hand_mean=False, batch_size=1)
        _mean = getattr(_rel, f"{side}_hand_mean").detach().cpu().numpy().reshape(15, 3)
        _bm = J[nm[f"{side}_middle2"]] - J[nm[f"{side}_middle1"]]
        _bm /= np.linalg.norm(_bm)
        if _mean[3] @ np.cross(_bm, pn) < 0:
            pn = -pn
        out = []
        for f in ("index", "middle", "pinky", "ring", "thumb"):   # MANO order
            for k in (1, 2, 3):
                j = nm[f"{side}_{f}{k}"]
                nxt = nm.get(f"{side}_{f}{k+1}")
                d = (J[nxt] - J[j]) if nxt is not None else \
                    (J[j] - J[nm[f"{side}_{f}{k-1}"]])
                b = d / np.linalg.norm(d)
                # cross(b, pn), NOT cross(pn, b). Rotating a bone about k moves
                # it along k x b, and (cross(pn,b) x b) . pn = (b.pn)^2 - 1 <= 0,
                # so cross(pn, b) flexes toward the BACK. With it the wrong way
                # round every finger of every session bent backwards in 100% of
                # frames. Checked on the model: +0.6 rad about this axis moves
                # the fingertips +37 mm toward the palm.
                fl = np.cross(b, pn)                 # +theta flexes toward the palm
                n = np.linalg.norm(fl)
                fl = fl / n if n > 1e-6 else np.array([0, 0, 1.0])
                prev = nm[f"{side}_{f}{k-1}"] if k > 1 else nm[f"{side}_wrist"]
                u = J[j] - J[prev]
                u = u / np.linalg.norm(u)        # the incoming bone
                out.append((b, fl, np.cross(b, fl), u, pn))
        cls._AXES[side] = out
        return out

    @classmethod
    def clean_hand(cls, pose, side, mcp_flex=(0, 95), ip_flex=(2, 112),
                   mcp_abd=18):
        """Project a glove-fitted hand pose onto anatomically real motion."""
        q = np.asarray(pose, np.float64).reshape(len(pose), 15, 3).copy()
        for j, (b, fl, ab, u_in, pn) in enumerate(cls.finger_axes(side)):
            v = q[:, j]
            th = np.linalg.norm(v, axis=1, keepdims=True)
            k = v / np.maximum(th, 1e-12)
            # quaternion, then split off the twist about the bone
            qw = np.cos(th[:, 0] / 2)
            qv = k * np.sin(th[:, 0] / 2)[:, None]
            proj = (qv @ b)[:, None] * b
            tw = np.concatenate([qw[:, None], proj], 1)
            tw /= np.maximum(np.linalg.norm(tw, axis=1, keepdims=True), 1e-12)
            # swing = q * conj(twist)
            sw = np.empty_like(tw)
            sw[:, 0] = qw * tw[:, 0] + (qv * tw[:, 1:]).sum(1)
            sw[:, 1:] = (qw[:, None] * -tw[:, 1:] + tw[:, :1] * qv
                         + np.cross(qv, -tw[:, 1:]))
            sw /= np.maximum(np.linalg.norm(sw, axis=1, keepdims=True), 1e-12)
            ang = 2 * np.arccos(np.clip(np.abs(sw[:, 0]), -1, 1))
            axis = sw[:, 1:] * np.sign(sw[:, :1])
            n = np.linalg.norm(axis, axis=1, keepdims=True)
            axis = axis / np.maximum(n, 1e-12)
            # the swing axis is perpendicular to the bone, so it decomposes
            # exactly onto the hinge and abduction axes
            flex = ang * (axis @ fl)
            abd = ang * (axis @ ab)
            # the thumb is not a hinge at any of its joints, so it keeps both
            # swing axes; only the impossible twist is removed
            # The thumb is not a hinge at any of its joints and its flexion
            # plane is rotated away from the fingers', so the axes derived
            # here do not carve it up cleanly. It keeps both swing axes with
            # only a generous sanity limit: for the thumb this pass is a
            # twist removal and nothing more.
            thumb = j >= 12
            knuckle = (j % 3 == 0)
            if thumb:
                lim = np.radians(95)
                flex = np.clip(flex, -lim, lim)
                abd = np.clip(abd, -lim, lim)
            else:
                lo, hi = (mcp_flex if knuckle else ip_flex)
                flex = np.clip(flex, np.radians(lo), np.radians(hi))
                abd = (np.clip(abd, -np.radians(mcp_abd), np.radians(mcp_abd))
                       if knuckle else np.zeros_like(abd))
            # Clamping the flexion component is not quite enough: the hinge
            # axis is the rest-pose one, so a joint held at zero can still come
            # out a few degrees dorsal once posed. Rotate the outgoing bone by
            # the FULL joint rotation -- abduction swings it out of the flexion
            # plane and can tilt it dorsally on its own -- and add flexion
            # until it no longer moves away from the palm.
            def bend_sign(fx):
                r = fx[:, None] * fl + abd[:, None] * ab
                th = np.linalg.norm(r, axis=1)
                k = np.divide(r, th[:, None], out=np.zeros_like(r),
                              where=th[:, None] > 1e-9)
                c, sn = np.cos(th)[:, None], np.sin(th)[:, None]
                w = (b * c + np.cross(k, b) * sn
                     + k * (k * b).sum(1)[:, None] * (1 - c))
                return (w - u_in) @ pn

            for _ in range(40):
                bad = bend_sign(flex) < 0
                if not bad.any():
                    break
                flex = np.where(bad, flex + np.radians(1.2), flex)
            q[:, j] = flex[:, None] * fl + abd[:, None] * ab
        return q.reshape(len(pose), 45)


    # MANO's pose rows, in the order finger_axes() builds them
    _MANO_ORDER = ("index", "middle", "pinky", "ring", "thumb")
    # +abduction swings a finger toward the thumb on the right hand and away
    # from it on the left -- the same mirror as every other hand sign here.
    # Measured on the rest model: 0.15 rad moves a fingertip ~8 mm radially.
    _RADIAL_ABD = {"left": -1.0, "right": +1.0}
    _ABD_LEVER = 0.008 / 0.15          # metres of tip travel per radian
    _RAD = {}

    @classmethod
    def undorsal(cls, J, pose, side, margin_deg=1.0):
        """Push finger joints out of hyperextension, measured on the posed hand.

        Clamping the pose parameters is not enough. An analytic test on
        rest-pose bones declared every joint clean while 14.5% of them measured
        dorsal on the posed hand, because a joint's bend depends on the whole
        chain above it and on the abduction component, not just its own
        flexion. So this works on the real quantity: pose the hand, measure the
        angle between the incoming and outgoing bones against the per-frame
        palm normal, add exactly that much flexion back, and let the caller
        iterate. It converges on what the audit measures because it is what the
        audit measures.
        """
        from smplx.joint_names import JOINT_NAMES
        nm = {n: i for i, n in enumerate(JOINT_NAMES[:55])}
        FING = ("index", "middle", "ring", "pinky")
        ax = cls.finger_axes(side)
        J = np.asarray(J, np.float64)
        q = np.array(pose, np.float64).reshape(len(pose), 15, 3)

        w = J[:, nm[f"{side}_wrist"]]
        mcp = J[:, [nm[f"{side}_{x}1"] for x in FING]]
        fwd = mcp.mean(1) - w
        fwd /= np.linalg.norm(fwd, axis=1, keepdims=True)
        lat = mcp[:, 0] - mcp[:, 3]
        lat -= (lat * fwd).sum(1, keepdims=True) * fwd
        lat /= np.linalg.norm(lat, axis=1, keepdims=True)
        pn = {"left": +1.0, "right": -1.0}[side] * np.cross(fwd, lat)

        for x in FING:
            chain = [nm[f"{side}_wrist"]] + [nm[f"{side}_{x}{k}"] for k in (1, 2, 3)]
            for lvl, (a, b_, c) in enumerate(zip(chain, chain[1:], chain[2:]), 1):
                u, v = J[:, b_] - J[:, a], J[:, c] - J[:, b_]
                u /= np.linalg.norm(u, axis=1, keepdims=True)
                v /= np.linalg.norm(v, axis=1, keepdims=True)
                ang = np.arccos(np.clip((u * v).sum(1), -1, 1))
                dorsal = ((v - u) * pn).sum(1) < 0
                add = np.where(dorsal, ang + np.radians(margin_deg), 0.0)
                row = cls._MANO_ORDER.index(x) * 3 + (lvl - 1)
                q[:, row] += add[:, None] * ax[row][1]
        return q.reshape(len(pose), 45).astype(np.float32)

    @classmethod
    def finger_radii(cls, side):
        """Skin radius of each phalanx, from the rest mesh.

        Every vertex is assigned to its nearest hand bone first, so palm
        vertices cannot inflate a finger. Comes out at 10.6 mm at the index
        knuckle down to 7.4 mm at the fingertip, which is a real hand.
        """
        if side in cls._RAD:
            return cls._RAD[side]
        import torch, smplx
        from smplx.joint_names import JOINT_NAMES
        nm = {n: i for i, n in enumerate(JOINT_NAMES[:55])}
        m = smplx.create(str(SMPLX_DIR.parent), model_type="smplx",
                         gender="neutral", use_pca=False, flat_hand_mean=True,
                         batch_size=1)
        with torch.no_grad():
            o = m(betas=torch.zeros(1, 10))
        V = o.vertices[0].numpy().astype(np.float64)
        J = o.joints[0].numpy()[:55].astype(np.float64)
        bones = [(f, k) for f in ("thumb", "index", "middle", "ring", "pinky")
                 for k in (1, 2, 3)]

        def seg_pt(a, b, p):
            ab = b - a
            t = np.clip(((p - a) @ ab) / max(float(ab @ ab), 1e-12), 0, 1)
            return np.linalg.norm(p - (a + t[:, None] * ab), axis=1)

        D = []
        for f, k in bones:
            a = J[nm[f"{side}_{f}{k}"]]
            b = (J[nm[f"{side}_{f}{k+1}"]] if k < 3
                 else a + (a - J[nm[f"{side}_{f}{k-1}"]]))
            D.append(seg_pt(a, b, V))
        D = np.stack(D)
        own, best = D.argmin(0), D.min(0)
        out = {}
        for i, (f, k) in enumerate(bones):
            mine = best[(own == i) & (best < 0.025)]
            out[(f, k)] = float(np.median(mine)) if len(mine) > 20 else 0.008
        cls._RAD[side] = out
        return out

    @staticmethod
    def _seg_seg(p1, q1, p2, q2):
        """Distance between two segments, vectorised over the batch."""
        d1, d2 = q1 - p1, q2 - p2
        r = p1 - p2
        a = (d1 * d1).sum(-1); e = (d2 * d2).sum(-1)
        f = (d2 * r).sum(-1); c = (d1 * r).sum(-1); b = (d1 * d2).sum(-1)
        den = a * e - b * b
        s = np.where(den > 1e-12,
                     np.clip((b * f - c * e) / np.where(den > 1e-12, den, 1), 0, 1), 0.0)
        t = np.clip((b * s + f) / np.where(e > 1e-12, e, 1), 0, 1)
        s = np.clip((b * t - c) / np.where(a > 1e-12, a, 1), 0, 1)
        return np.linalg.norm((p1 + s[..., None] * d1) - (p2 + t[..., None] * d2), axis=-1)

    @classmethod
    def separate(cls, J, pose, side, clearance=0.0045, cap_deg=9.0):
        """Pull adjacent fingers apart until their skin stops intersecting.

        The glove is fitted finger by finger, so nothing stops two neighbours
        occupying the same space, and clean_hand's abduction clamp is per
        finger too -- two of them can lean 18 deg into each other. This is not
        our artefact: the raw glove pose has adjacent fingers crossing on 93.6%
        of frames, up to 19.2 mm deep. Each phalanx is a capsule of its
        measured skin radius; where two overlap, both knuckles rotate apart
        about the abduction axis, half the correction each. The clearance is
        positive because a finger is flatter than a capsule -- at the frame the
        user caught, the axes were still 2 mm apart while the surfaces already
        crossed.
        """
        from smplx.joint_names import JOINT_NAMES
        nm = {n: i for i, n in enumerate(JOINT_NAMES[:55])}
        FING = ("index", "middle", "ring", "pinky")
        rad = cls.finger_radii(side)
        ax = cls.finger_axes(side)
        sgn = cls._RADIAL_ABD[side]
        cap = np.radians(cap_deg)
        J = np.asarray(J, np.float64)
        q = np.array(pose, np.float64).reshape(len(pose), 15, 3)

        def ends(f, k):
            a = J[:, nm[f"{side}_{f}{k}"]]
            b = (J[:, nm[f"{side}_{f}{k+1}"]] if k < 3
                 else a + (a - J[:, nm[f"{side}_{f}{k-1}"]]))
            return a, b

        for fa, fb in zip(FING, FING[1:]):          # radial -> ulnar
            worst = np.zeros(len(J))
            for ka in (1, 2, 3):
                for kb in (1, 2, 3):
                    if ka == 1 and kb == 1:
                        continue                    # the knuckles always touch
                    d = cls._seg_seg(*ends(fa, ka), *ends(fb, kb))
                    worst = np.maximum(worst,
                                       rad[(fa, ka)] + rad[(fb, kb)] + clearance - d)
            if not (worst > 0).any():
                continue
            dth = np.clip(np.maximum(worst, 0) / 2 / cls._ABD_LEVER, 0, cap)
            ra = cls._MANO_ORDER.index(fa) * 3
            rb = cls._MANO_ORDER.index(fb) * 3
            q[:, ra] += (+sgn * dth)[:, None] * ax[ra][2]
            q[:, rb] += (-sgn * dth)[:, None] * ax[rb][2]
        return q.reshape(len(pose), 45).astype(np.float32)

    def vertices(self, batch=96, device="cpu", with_joints=False):
        """(len(idx), 10475, 3) float32, Z-up, floor at 0.

        Returned as float32 and stored that way. float16 is not safe for world
        coordinates here: session_A reaches -5.5 m, where the float16 step is
        3.9 mm, which put 1 mm of noise on every vertex of every frame — 7% of
        a finger's width, re-randomised each frame, so fingers crawled and
        kinked and stopped matching the body.
        """
        import torch, smplx
        m = smplx.create(str(SMPLX_DIR.parent), model_type="smplx", gender="neutral",
                         use_pca=False, flat_hand_mean=True, batch_size=batch,
                         num_betas=10).to(device)
        z, I = self.z, self.idx
        betas = torch.tensor(np.tile(z["betas"][None], (batch, 1)), device=device)
        s = float(z["scale"])
        out = np.empty((len(I), 10475, 3), np.float32)
        jts = np.empty((len(I), 55, 3), np.float32) if with_joints else None
        for a in range(0, len(I), batch):
            k = I[a:a + batch]
            pad = batch - len(k)
            if pad:
                k = np.concatenate([k, np.repeat(k[-1:], pad)])
            t = lambda key: torch.tensor(z[key][k], device=device)
            lh = self.clean_hand(z["left_hand_pose"][k], "left")
            rh = self.clean_hand(z["right_hand_pose"][k], "right")
            with torch.no_grad():
                def fwd(lhp, rhp):
                    return m(betas=betas, global_orient=t("global_orient"),
                             body_pose=t("body_pose"), transl=t("transl"),
                             left_hand_pose=torch.tensor(
                                 lhp, dtype=torch.float32, device=device),
                             right_hand_pose=torch.tensor(
                                 rhp, dtype=torch.float32, device=device))
                # Both corrections run off the same posed hand and act on
                # different axes -- flexion for the hyperextension, abduction
                # for the crossings -- so they do not fight each other.
                for _ in range(4):
                    Jt = fwd(lh, rh).joints.cpu().numpy()[:, :55]
                    lh = self.undorsal(Jt, self.separate(Jt, lh, "left"), "left")
                    rh = self.undorsal(Jt, self.separate(Jt, rh, "right"), "right")
                r = fwd(lh, rh)
            keep = batch - pad if pad else batch
            v = r.vertices.cpu().numpy() * s
            out[a:a + len(I[a:a + batch])] = v[:keep]
            if with_joints:
                jts[a:a + len(I[a:a + batch])] = \
                    r.joints.cpu().numpy()[:, :55][:keep] * s
        out[:, :, 1] -= self.ground * s           # floor to 0 in the Y-up frame
        v = (out @ YUP2Z.T).astype(np.float32)
        if not with_joints:
            return v
        jts[:, :, 1] -= self.ground * s
        return v, (jts @ YUP2Z.T).astype(np.float32)

    def faces(self):
        import smplx
        m = smplx.create(str(SMPLX_DIR.parent), model_type="smplx", gender="neutral",
                         use_pca=False, num_betas=10, batch_size=1)
        return m.faces.astype(np.int32)

    # ── trackers, gloves, touch ─────────────────────────────────────────
    def trackers(self):
        p = self.z["tracker_position"][self.idx].astype(np.float64) * float(self.z["scale"])
        p[:, :, 1] -= self.ground * float(self.z["scale"])
        return p @ YUP2Z.T

    def tactile(self, side="R", level="L2_score"):
        return self.z[f"tactile_{side}_{level}"][self.idx]
