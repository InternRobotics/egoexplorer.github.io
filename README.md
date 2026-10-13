# EgoExplorer — project page

The official website for **EgoExplorer: A Vision–Motion–Touch Observatory for
Human Loco-Manipulation In Situ**.

**Live:** https://internrobotics.github.io/egoexplorer.github.io/

| | |
| --- | --- |
| Dataset | https://huggingface.co/datasets/InternRobotics/EgoExplorer |
| Capture toolkit | https://github.com/InternRobotics/EgoExplorer |
| Paper | to appear |

## Running it locally

The page is static — no build step, no dependencies.

```sh
python3 -m http.server 8799
open http://127.0.0.1:8799/
```

## Layout

```
index.html            the page
styles.css  *.js      styles and behaviour
assets/               the videos and stills it plays
fonts/                self-hosted webfonts
build/                the scripts that render assets/ from the recordings
docs/build-notes.md   working notes from building it
```

`assets/` is committed because GitHub Pages serves the site straight from the
repository. `build/` is kept for provenance: every video on the page can be
regenerated from the recordings with the scripts in it.

## Citation

```bibtex
@misc{egoexplorer2026,
  title  = {EgoExplorer: A Vision-Motion-Touch Observatory for
            Human Loco-Manipulation In Situ},
  author = {Anonymous authors},
  year   = {2026},
  note   = {Paper under double-blind review}
}
```
