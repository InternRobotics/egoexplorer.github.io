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
@misc{zhou2026egoexplorer,
      title={EgoExplorer: A Vision-Motion-Touch Observatory for Human Loco-Manipulation In Situ},
      author={Yunsong Zhou and Xuekun Jiang and Haiqi Shen and Hangxu Liu and Chaojian Shi and Yujie Liu and Jingyuan Li and Haoran Yang and Jiafei Cao and Dongzhan Zhou and Dong Wang and Yao Mu and Chunhua Shen and Weinan Zhang},
      year={2026},
      eprint={2610.18872},
      archivePrefix={arXiv},
      primaryClass={cs.RO},
      url={https://arxiv.org/abs/2610.18872},
}
```
