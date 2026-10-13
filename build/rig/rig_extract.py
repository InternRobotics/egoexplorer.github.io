"""Decode the geometry embedded in smplx_rig.html into an npz Blender can read.

The page is a self-contained viewer: `const payload=[...]` holds every part as
gzipped base64, either a triangle soup (n,3,6 — position + normal) or an
indexed mesh, with a colour, a group name, and optional instance transforms.
Nothing is redrawn here; this just lifts the same geometry out so it can be
rendered with a real renderer and a moving camera.
"""
import base64, gzip, json, re, sys
import numpy as np
from pathlib import Path

SRC = Path("/Volumes/NASStorage/Documents/code/camera_tracker_extrinsics/smplx_rig.html")
OUT = Path(__file__).resolve().parent / "rig_geo.npz"


def grab(name, text):
    """Pull `const <name>=<json>,` out of the bundle."""
    i = text.index(f"const {name}=") if f"const {name}=" in text else text.index(f",{name}=")
    i = text.index("=", i) + 1
    depth, j, instr, esc = 0, i, False, False
    while j < len(text):
        c = text[j]
        if instr:
            if esc: esc = False
            elif c == "\\": esc = True
            elif c == '"': instr = False
        elif c == '"': instr = True
        elif c in "[{": depth += 1
        elif c in "]}":
            depth -= 1
            if depth == 0:
                return json.loads(text[i:j + 1])
        j += 1
    raise ValueError(name)


def main():
    t = SRC.read_text(encoding="utf-8", errors="replace")
    payload = grab("payload", t)
    views = grab("views", t)
    print(f"{len(payload)} parts")
    out, meta = {}, []
    for k, it in enumerate(payload):
        d = lambda key: np.frombuffer(gzip.decompress(base64.b64decode(it[key])),
                                      dtype="<f4")
        if it.get("kind") == "mesh":
            v = d("verts").reshape(-1, 3)
            f = np.frombuffer(gzip.decompress(base64.b64decode(it["faces"])),
                              dtype="<u4").reshape(-1, 3)
        else:
            soup = d("data").reshape(-1, 3, 6)
            v = soup[:, :, :3].reshape(-1, 3)
            f = np.arange(len(v), dtype=np.uint32).reshape(-1, 3)
        out[f"v{k}"] = v.astype(np.float32)
        out[f"f{k}"] = f.astype(np.uint32)
        inst = it.get("inst") or []
        if inst:
            out[f"m{k}"] = np.array([i["m"] for i in inst], np.float32)
            out[f"o{k}"] = np.array([i["o"] for i in inst], np.float32)
        meta.append(dict(i=k, name=it.get("name", f"part{k}"),
                         group=it.get("group", ""), color=it.get("color"),
                         nv=len(v), nf=len(f), ninst=len(inst),
                         ig=[i.get("g") for i in inst]))
    out["meta"] = json.dumps(meta)
    out["views"] = json.dumps(views)
    np.savez_compressed(OUT, **out)
    for m in meta:
        print(f"  {m['name'][:30]:32s} {m['group'][:14]:16s} "
              f"v{m['nv']:7d} f{m['nf']:7d} inst {m['ninst']}")
    print("->", OUT, round(OUT.stat().st_size / 1e6, 1), "MB")


if __name__ == "__main__":
    main()
