"""Rebuild only hands.npy for each session, reusing the baked vertices.

The presentation frame was wrong for one hand; the body vertices are fine, and
re-running SMPL-X for all ten sessions to fix a rotation would be wasteful.
"""
import json, sys
import numpy as np
np.seterr(all="ignore")
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import prep_streams as P
from hand_regions import BASE, WRIST
import smplx, torch

ROOT = P.ROOT
m = smplx.create("/Volumes/NASStorage/Downloads/models", model_type="smplx",
                 gender="neutral", use_pca=False, flat_hand_mean=True, batch_size=1)
seg = m.lbs_weights.numpy().argmax(1)

for alias in (sys.argv[1:] or sorted(P.ROWS)):
    d = ROOT / alias
    if not (d / "verts.npy").exists():
        print("skip", alias); continue
    V = np.load(d / "verts.npy", mmap_mode="r")
    hidx = np.load(d / "hidx.npy")
    from egodata import Session
    z = Session(alias).z
    with torch.no_grad():
        Jrest = m(betas=torch.tensor(z["betas"][None])).joints[0].numpy()[:55]
    hv = np.empty((len(V), 2, hidx.shape[1], 3), np.float16)
    for f in range(len(V)):
        Vt = np.asarray(V[f], np.float64)
        for si, side in enumerate(("L", "R")):
            ids = hidx[si]
            Pm = Vt[ids]
            Jf = Jrest.copy()
            for j in (WRIST[side], BASE[side], BASE[side] + 3,
                      BASE[side] + 6, BASE[side] + 9):
                sel = np.where(seg[ids] == j)[0]
                if len(sel):
                    Jf[j] = Pm[sel].mean(0)
            hv[f, si] = P.canonical(Pm, Jf, side).astype(np.float16)
    np.save(d / "hands.npy", hv)
    print(f"{alias}: hands {hv.shape}", flush=True)
